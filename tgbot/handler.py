from common import config, bookid_parser, get_remaining_time, redis_conn
# noinspection PyPackageRequirements
from telebot.async_telebot import AsyncTeleBot
import httpx


endpoint = config.api.endpoint


async def commands_handler(chat_id: str, command: str, bot: AsyncTeleBot) -> str:
    command = command[1:] if command.startswith("/") else command
    action = command[:2]
    args = command[2:].lstrip() if command[2:].startswith(" ") else command[2:]

    quota = await redis_conn.get(f"tgbot:quota:{chat_id}")
    if quota is None:
        await redis_conn.set(f"tgbot:quota:{chat_id}", config.quota, ex=get_remaining_time())
        quota = config.quota
    else:
        quota = int(quota.decode())

    match action:
        case "下载" | "xz" | "dl":
            if quota <= 0:
                return f"今日下载次数已用完"
            await redis_conn.decr(f"tgbot:quota:{chat_id}")
            book_id = bookid_parser(args)
            if not book_id:
                return f"无效的书籍ID/链接"
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{endpoint}/tasks",
                                             json={"book_id": book_id, "notify": f"{config.no.endpoint}/notify"},
                                             headers={"User-Agent": config.api.ua})
                task_id = response.json()["task_id"]
                await redis_conn.set(f"tgbot:task:{task_id}", chat_id, ex=7200)
                await redis_conn.lpush(f"tgbot:hists:{chat_id}", task_id)
                await redis_conn.expire(f"tgbot:hists:{chat_id}", get_remaining_time())
                return f"任务已提交\n任务ID: `{task_id}`"
            pass
        case "获取" | "hq" | "gt":
            if not len(args) == 36:
                return f"无效的任务ID"
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{endpoint}/data/{args}",
                                            headers={"User-Agent": config.api.ua})
            if response.status_code == 404:
                return f"任务不存在"
            status = response.json()["status"]
            if status == "pending":
                status = "排队中"
                return f"任务状态: {status}"
            elif status == "processing":
                status = "正在下载"
                return f"任务状态: {status}"
            elif status == "failed":
                status = "下载失败"
                return f"任务状态: {status}"
            elif status == "completed":
                await bot.send_message(chat_id, f"正在发送文件，请稍候...")
                data = response.json()["content"].encode("utf-8")
                await bot.send_document(chat_id, data, caption="小说文件",
                                        visible_file_name=f"{response.json()['book_id']}.txt")
                return ""
        case "历史" | "ls" | "ht":
            hists = await redis_conn.lrange(f"tgbot:hists:{chat_id}", 0, -1)
            if not hists:
                return f"今日无历史记录"
            content = f"今日历史记录："
            for hist in hists:
                content += f"\n{hist.decode()}"
            return content
        case "我的" | "wd" | "me" | "my":
            return (f"剩余下载次数: {quota}\n"
                    f"你的ChatID: \n{chat_id}")
        case "帮助" | "bz" | "hp":
            content = (f"使用说明：\n"
                       f"下载小说：/dl 书籍ID/链接\n"
                       f"获取小说文件：/gt 任务ID\n"
                       f"查看历史记录：/ht\n"
                       f"查看我的信息：/my\n"
                       f"查看所有命令别名：/别名")
            return content
        case "别名":
            content = (f"所有命令别名：\n"
                       f"下载：下载 xz dl\n"
                       f"获取：获取 hq gt\n"
                       f"历史：历史 ls ht\n"
                       f"我的：我的 wd me my\n"
                       f"帮助：帮助 bz hp\n"
                       f"命令的“/”前缀可省略")
            return content
