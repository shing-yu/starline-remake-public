# noinspection PyPackageRequirements
from telebot.async_telebot import AsyncTeleBot
# noinspection PyPackageRequirements
from telebot import asyncio_helper
# noinspection PyPackageRequirements
from telebot.types import Message
from fastapi import FastAPI, Request
import uvicorn
import asyncio

from common import config, logger, redis_conn
from handler import commands_handler

asyncio_helper.proxy = config.proxy
bot = AsyncTeleBot(config.token)


@bot.message_handler(commands=["start"])
async def send_welcome(message):
    await bot.send_message(message.chat.id, "欢迎使用本机器人！\n"
                                            "本机器人是由 @星隅 制作的番茄小说下载机器人\n"
                                            "使用 /hp 命令获取帮助")


@bot.message_handler(func=lambda msg: msg.chat.type == "private")
async def message_handler(message: Message):
    content = message.text.lstrip(" ")
    logger.info(f"PRIVATE||{message.chat.id}||{content}")
    result = await commands_handler(str(message.chat.id), content, bot)
    await bot.send_message(message.chat.id, result, parse_mode="Markdown") if result else None


@bot.message_handler(func=lambda msg: msg.chat.type in ["group", "supergroup"])
async def group_message_handler(message: Message):
    await bot.reply_to(message, "请私聊使用机器人功能哦~")


fastapi_app = FastAPI()


@fastapi_app.post("/notify")
async def handle_backend_notify(request: Request):
    data = await request.json()
    status = data["status"]
    task_id = data["task_id"]
    chat_id = await redis_conn.get(f"tgbot:task:{task_id}")
    res = await redis_conn.hgetall(f"task:{task_id}")
    book_id = res[b"book_id"].decode()
    data = res[b"content"]
    chat_id = chat_id.decode() if chat_id else None

    if status != "completed":
        await redis_conn.incr(f"tgbot:quota:{chat_id}")
        await bot.send_message(
            chat_id=chat_id,
            text=f"任务{task_id}下载失败\n下载次数已返还"
        )
    else:
        await bot.send_document(
            chat_id=chat_id,
            document=data,
            caption="小说下载完成",
            visible_file_name=f"{book_id}.txt"
        )
    return {"code": 200}


async def start():
    config_ = uvicorn.Config(fastapi_app, port=config.no.port, host=config.no.host, log_level="info")
    server = uvicorn.Server(config_)
    # await server.serve()
    # await bot.polling(skip_pending=True)
    await asyncio.gather(
        bot.polling(skip_pending=True),
        server.serve(),
    )


if __name__ == "__main__":
    asyncio.run(start())
