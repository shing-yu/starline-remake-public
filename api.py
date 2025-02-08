from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse
import uvicorn
# noinspection PyPackageRequirements
from redis import asyncio as redis
import uuid
from loguru import logger
from sys import stdout

from utils import config

logger.remove()
logger.add("logs/api.log", rotation="20 MB", encoding="utf-8", enqueue=True, level=config.logs.level)
logger.add(stdout, colorize=True, enqueue=True)

app = FastAPI()
templates = Jinja2Templates(directory="templates")
redis_conn = redis.Redis(host=config.redis.host,
                         port=config.redis.port,
                         db=config.redis.db)


@app.post("/tasks")
async def submit_task(request: Request):
    data = await request.json()
    book_id = data.get("book_id", "")
    notify = data.get("notify", "")
    if not book_id:
        raise HTTPException(status_code=400, detail="Missing book_id")
    task_id = str(uuid.uuid4())
    platform = request.headers.get("User-Agent", "unknown")
    logger.info(f"Received task {task_id} from {platform}, book_id: {book_id}")
    if len(book_id) != 19 or not book_id.isdigit():
        raise HTTPException(status_code=400, detail="Invalid book_id format")
    # 存储任务元数据
    await redis_conn.hset(f"task:{task_id}", mapping={
        "book_id": book_id,
        "status": "pending",
        "notify": notify
    })
    await redis_conn.expire(f"task:{task_id}", 86400)  # 后端任务超时时间为24小时
    # 任务入队
    await redis_conn.lpush("task_queue", task_id)
    return {"task_id": task_id}


@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    task_data = await redis_conn.hgetall(f"task:{task_id}")
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "book_id": task_data.get(b"book_id").decode(),
        "status": task_data.get(b"status").decode(),
    }


@app.get("/get/{task_id}")
async def get_task_status(task_id: str):
    task_data = await redis_conn.hgetall(f"task:{task_id}")
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "status": task_data.get(b"status").decode(),
        "url": task_data.get(b"url", b"").decode(),
    }


@app.get("/data/{task_id}")
async def get_task_status(task_id: str, request: Request):
    platform = request.headers.get("User-Agent", "unknown")
    if not platform.startswith("Bot"):
        raise HTTPException(status_code=403, detail="Forbidden，Only bots are allowed to access this API")
    task_data = await redis_conn.hgetall(f"task:{task_id}")
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "status": task_data.get(b"status").decode(),
        "book_id": task_data.get(b"book_id").decode(),
        "content": task_data.get(b"content", b"").decode(),
    }


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/status")
async def download_file(task_id: str, request: Request):
    if not task_id:
        return templates.TemplateResponse(
            "status.html",
            {
                "request": request,
                "status": "not_found",
                "status_code": 422  # 无效的任务ID
            }
        )
    task_data = await redis_conn.hgetall(f"task:{task_id}")
    if not task_data:
        return templates.TemplateResponse(
            "status.html",
            {
                "request": request,
                "status": "not_found",
                "status_code": 404
            }
        )
    status = task_data.get(b"status").decode()
    context = {
        "request": request,
        "status": status,
    }
    if status == "pending" or status == "processing":
        context["status_code"] = 202
    elif status == "completed":
        context["status_code"] = 200
        context["download_url"] = task_data.get(b"url").decode()
    elif status == "failed":
        message = task_data.get(b"message", b"").decode()
        if message:
            context["status_code"] = 422  # 有信息表示是由于超过章节数量限制而失败
            context["message"] = message
        else:
            context["status_code"] = 500
            context["message"] = "请检查你提交的书籍ID是否正确和是否被下架，或稍后再试"
    return templates.TemplateResponse("status.html", context)


@app.get("/favicon.ico")
async def favicon():
    return FileResponse("templates/favicon.ico")


if __name__ == "__main__":
    uvicorn.run(app, host=config.main.api.host, port=config.main.api.port)
