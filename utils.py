import httpx
import asyncio
import functools
from bs4 import BeautifulSoup

from datetime import timedelta
from redis import asyncio as redis
from typing import TypedDict
import json
from ofb_python_sdk import Client

from config import config
from database import Books


class RawChapter(TypedDict):
    item_id: str
    title: str
    content: str


oclient = Client(config.onedrive.client_id,
                 config.onedrive.client_secret,
                 config.onedrive.refresh_token,
                 config.onedrive.redirect_uri,
                 disable_progress=True)


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


async def format_content(items, title, author, chapters):
    content = f"\n{title}\n作者：{author}"
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


class TooManyChaptersError(Exception):
    def __init__(self, message="章节数量过多"):
        self.message = message
        super().__init__(self.message)
