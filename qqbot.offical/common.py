from botpy import logging
import tomli as toml
from munch import DefaultMunch
from datetime import datetime, timedelta, time
from redis import asyncio as redis
import re

with open("config.toml", "rb") as f:
    config = toml.load(f)
    config = DefaultMunch.fromDict(config)

botid = config.botid
secret = config.secret
endpoint = config.api.endpoint

redis_conn = redis.Redis(host=config.redis.host, port=config.redis.port, db=config.redis.db)

logger = logging.get_logger()


def bookid_parser(book_id: str) -> str:
    try:
        if 'fanqienovel.com/page' in book_id:
            book_id = re.search(r"page/(\d+)", book_id).group(1)
        elif 'changdunovel.com' in book_id:
            book_id = re.search(r"book_id=(\d+)&", book_id).group(1)
        if book_id.isdigit() and len(book_id) == 19:
            return book_id
        elif book_id == "727241257177946":  # TODO: 提审限制
            return "7272412571779468340"
        else:
            return ""
    except AttributeError:
        return ""


def get_remaining_time() -> int:
    now = datetime.now()
    end_of_day = datetime.combine(now.date() + timedelta(days=1), time.min)
    delta = end_of_day - now
    remaining = int(delta.total_seconds())
    return remaining
