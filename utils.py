import httpx
import asyncio
import functools
from bs4 import BeautifulSoup
import boto3

from datetime import timedelta
from redis import asyncio as redis
from typing import TypedDict
import json

from config import config
from database import Books


class RawChapter(TypedDict):
    item_id: str
    title: str
    content: str


s3 = boto3.client("s3",
                  endpoint_url=config.s3.endpoint,
                  region_name=config.s3.region,
                  aws_access_key_id=config.s3.id,
                  aws_secret_access_key=config.s3.secret)


def retry(times: int = 1, delay: int = 0):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            for i in range(times + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if i == times:
                        raise e
                    await asyncio.sleep(delay)
        return wrapper
    return decorator


@retry(1)
async def get_info(book_id: str, redis_conn: redis.Redis) -> dict:
    info = await redis_conn.get(f"info:{book_id}")
    if info:
        return json.loads(info)
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{config.main.fqweb.endpoint}/catalog",
                                    params={"book_id": book_id},
                                    timeout=10)
        response.raise_for_status()
        res = response.json()
    if res["code"] != 0:
        raise Exception(f"请求失败，响应信息：{str(res)}")
    await redis_conn.setex(f"info:{book_id}", timedelta(hours=config.ttls.infos), json.dumps(res))
    return res


# noinspection PyUnusedLocal
@retry(1)
async def get_chapters(items):
    async with httpx.AsyncClient() as client:
        # 创建并发量限制信号量（5个并发槽）
        semaphore = asyncio.Semaphore(5)

        async def fetch_data(item_id):
            async with semaphore:  # 进入信号量区域（自动释放）
                response = await client.get(
                    f"{config.main.fqweb.endpoint}/content",
                    params={"item_id": item_id},
                    timeout=10
                )
                response.raise_for_status()
                response = response.json()
                if response["code"] != 0 and response["message"]:
                    raise Exception(f"请求失败，错误信息：{response['message']}")
                elif response["code"] != 0 and not response["message"]:
                    raise Exception("请求失败，未知错误")
                res: RawChapter = {
                    "item_id": item_id,
                    "title": response["data"]["title"],
                    "content": response["data"]["content"]
                }
                return res

        # 创建所有异步任务
        tasks = [
            fetch_data(item)
            for item in items
        ]

        # 并发执行（自动限制同时只有5个请求）
        results = await asyncio.gather(*tasks)
        return results


async def format_chapter_content(chapter: RawChapter) -> str:
    soup = BeautifulSoup(chapter["content"], "html.parser")
    # noinspection PyArgumentList
    text = soup.get_text(separator="\n", strip=True)
    res = f"\n\n\n{chapter['title']}\n\n{text}"
    return res


async def format_content(items, title, otitle, author, chapters):
    if title == otitle:
        content = f"\n{title}\n作者：{author}"
    else:
        content = f"\n{title}\n原名：{otitle}\n作者：{author}"
    for item in items:
        content += chapters[item]
    return content


async def get_existed_book(book_id: str, redis_conn: redis.Redis, db) -> str | None:
    data = await redis_conn.get(f"book:{book_id}")
    if data:
        return data
    data = db.query(Books).filter(Books.book_id == book_id).first()
    if data:
        await redis_conn.setex(f"book:{book_id}", timedelta(hours=config.ttls.contents), data.content)
        return data.content
    return None


async def notify_user(task_id: str, redis_conn: redis.Redis):
    task = await redis_conn.hgetall(f"task:{task_id}")
    notify_addr = task.get(b"notify", b"").decode()
    if notify_addr:
        with httpx.Client() as client:
            client.post(notify_addr, json={"status": task[b"status"].decode(),
                                           "task_id": task_id,
                                           "url": task.get(b"url", b"").decode()})


def s3_check_file(path: str):
    try:
        s3.head_object(Bucket=config.s3.bucket, Key=path)
        return True
    except s3.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        raise e


def s3_upload_file(data: bytes, path: str):
    s3.put_object(Bucket=config.s3.bucket, Key=path, Body=data,
                  ContentType="text/plain", ContentDisposition="attachment")


def s3_get_link(path: str):
    url = s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": config.s3.bucket, "Key": path},
        ExpiresIn=3600*8
    )
    return url


class TooManyChaptersError(Exception):
    def __init__(self, message="章节数量过多"):
        self.message = message
        super().__init__(self.message)
