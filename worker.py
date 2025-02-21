# worker.py
from redis import asyncio as redis
from datetime import timedelta
import asyncio
from loguru import logger
from sys import stdout

from database import get_session, Books, Chapters
from utils import (config, RawChapter, TooManyChaptersError,
                   s3_check_file, s3_upload_file, s3_get_link)
import utils

logger.remove()
logger.add("logs/worker.log", rotation="20 MB", encoding="utf-8", enqueue=True, level=config.logs.level)
logger.add(stdout, colorize=True, enqueue=True)

redis_conn = redis.Redis(host=config.redis.host,
                         port=config.redis.port,
                         db=config.redis.db)
db = get_session()


async def main():
    while True:
        # 异步阻塞获取任务
        task_id_ = await redis_conn.brpop(["task_queue"])

        task_id = task_id_[1].decode()
        logger.info(f"Processing task {task_id}")

        try:
            # 异步标记为处理中
            await redis_conn.hset(f"task:{task_id}", "status", "processing")

            # 异步执行任务处理
            await process_task(task_id)

            logger.success(f"Task {task_id} completed")

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            logger.exception(e)
            await redis_conn.hset(f"task:{task_id}", "status", "failed")
            if isinstance(e, TooManyChaptersError):
                await redis_conn.hset(f"task:{task_id}", "message", "你提交的小说章节数量过多，超过3000章限制")
            await redis_conn.expire(f"task:{task_id}", timedelta(hours=config.ttls.tasks))

        finally:
            await utils.notify_user(task_id, redis_conn)


async def process_task(task_id):
    # 异步获取任务数据
    book_id = await redis_conn.hget(f"task:{task_id}", "book_id")
    book_id = book_id.decode()  # noqa: 返回的是bytes类型，需要解码
    result = await utils.get_existed_book(book_id, redis_conn, db)
    if not result:
        logger.debug(f"Task {task_id}: Book {book_id} not found in cache and database")
        info = await utils.get_info(book_id, redis_conn)
        title = info["data"]["book_info"]["book_name"]
        original_title = info["data"]["book_info"]["original_book_name"]
        author = info["data"]["book_info"]["author"]
        status = int(info["data"]["book_info"]["creation_status"])
        items = [chapter["item_id"] for chapter in info["data"]["item_data_list"]]
        if len(items) > 3000:
            logger.warning(f"Task {task_id} failed: Too many chapters, {len(items)} chapters")
            raise TooManyChaptersError(f"小说{book_id}章节数量过多，共{len(items)}章，超过3000章限制")

        # 获取已有章节
        rows = db.query(Chapters).filter(Chapters.book_id == book_id).all()
        if rows:
            logger.debug(f"Task {task_id}: Found {len(rows)} existed chapters")
            existed_chapters_list = [row.item_id for row in rows if row.item_id in items]
            chapters: dict[str, str] = {
                row.item_id: row.content
                for row in rows
                if row.item_id in items
            }
            # 比较已有章节中是否有缺失
            diff = list(set(items) - set(existed_chapters_list))
        else:
            # 无已有章节
            logger.debug(f"Task {task_id}: No existed chapters")
            diff = items
            chapters: dict[str, str] = {}

        # 获取缺失章节内容
        raw_chapters: list[RawChapter] = await utils.get_chapters(diff)
        # 格式化章节内容
        new_chapters: dict[str, str] = {chapter["item_id"]: await utils.format_chapter_content(chapter)
                                        for chapter in raw_chapters}
        # 将新章节加入数据库
        if status != 0:
            for item_id, content in new_chapters.items():
                db.add(Chapters(book_id=book_id, item_id=item_id, content=content))
            db.commit()
            logger.debug(f"Added {len(new_chapters)} new chapters to database")

        # 合并已有章节和新章节
        chapters.update(new_chapters)
        # 合并为完整小说文本
        content = await utils.format_content(items, title, original_title, author, chapters)

        # 保存到缓存
        await redis_conn.setex(f"book:{book_id}", timedelta(hours=config.ttls.contents), content)
        # 如果完结保存到数据库
        if status == 0:
            logger.debug(f"Task {task_id}: Saving book to database")
            db.add(Books(book_id=book_id, content=content))
            db.commit()
    else:
        logger.debug(f"Task {task_id}: Found book {book_id} in cache or database")
        content = result
    content = content.encode("utf-8") if not isinstance(content, bytes) else content
    # 过去12小时内下载过的相同小说，或曾经下载过的已完结的小说，检查文件是否存在，如果不存在则上传
    if result:
        try:
            s3_check_file(f"{book_id}.txt")
        except Exception:  # noqa: 无法获取文件ID，说明文件不存在
            s3_upload_file(content, f"{book_id}.txt")
        finally:
            url = s3_get_link(f"{book_id}.txt")
    else:
        s3_upload_file(content, f"{book_id}.txt")
        url = s3_get_link(f"{book_id}.txt")

    # for i in range(1, 11):
    #     # 异步更新进度
    #     await redis_conn.hset(f"task:{task_id}", "progress", f"{i*10}%")

    # 异步标记任务完成
    await redis_conn.hset(f"task:{task_id}", mapping={
        "status": "completed",
        "content": content,
        "url": url
    })
    await redis_conn.expire(f"task:{task_id}", timedelta(hours=config.ttls.tasks))


if __name__ == "__main__":
    # 启动异步事件循环
    asyncio.run(main())
