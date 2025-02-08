from botpy.message import C2CMessage, GroupMessage
from common import config, bookid_parser, get_remaining_time, redis_conn
import httpx


endpoint = config.api.endpoint


async def commands_handler(openid: str, command: str, _message: C2CMessage | GroupMessage, prefix: str = "\n") -> str:
    command = command[1:] if command.startswith("/") else command
    action = command[:2]
    args = command[2:].lstrip() if command[2:].startswith(" ") else command[2:]

    quota = await redis_conn.get(f"qqbot:quota:{openid}")
    if quota is None:
        await redis_conn.set(f"qqbot:quota:{openid}", config.quota, ex=get_remaining_time())
        quota = config.quota
    else:
        quota = int(quota.decode())

    match action:
        case "下载" | "xz" | "dl":
            if quota <= 0:
                return f"今日下载次数已用完"
            await redis_conn.decr(f"qqbot:quota:{openid}")
            book_id = bookid_parser(args)
            if not book_id:
                return f"无效的书籍ID/链接"
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{endpoint}/tasks", json={"book_id": book_id},
                                             headers={"User-Agent": config.api.ua})
                task_id = response.json()["task_id"]
                await redis_conn.set(f"qqbot:task:{task_id}", openid, ex=7200)
                await redis_conn.lpush(f"qqbot:hists:{openid}", task_id)
                await redis_conn.expire(f"qqbot:hists:{openid}", get_remaining_time())
                return f"任务已提交\n任务ID: {task_id}"
            pass
        case "查询" | "状态" | "cx" | "qu" | "st":
            # if not len(args) == 36:  # TODO: 提审限制
            #     return f"无效的任务ID"
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{endpoint}/tasks/{args}",
                                            headers={"User-Agent": config.api.ua})
            if response.status_code == 404:
                return f"任务不存在"
            status = response.json()["status"]
            if status == "pending":
                status = "排队中"
            elif status == "completed":
                status = "已完成"
            elif status == "processing":
                status = "正在下载"
            elif status == "failed":
                status = "下载失败"
            return f"{prefix}任务状态: {status}"
        case "恢复" | "hf" | "re":
            # 下载失败后恢复配额
            # if not len(args) == 36:  # TODO: 提审限制
            #     return f"无效的任务ID"
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{endpoint}/tasks/{args}",
                                            headers={"User-Agent": config.api.ua})
            if response.status_code == 404:
                return f"任务不存在"
            status = response.json()["status"]
            if status != "failed":
                return f"非下载失败任务"
            # creator_openid = await redis_conn.get(f"qqbot:task:{args}")  # TODO: 提审限制
            # if creator_openid is None:
            #     return f"无法重复恢复下载次数"
            # creator_openid = creator_openid.decode()
            # if creator_openid != openid:
            #     return f"你不是该任务的创建者"
            await redis_conn.incr(f"qqbot:quota:{openid}")
            # await redis_conn.delete(f"qqbot:task:{args}")  # 删除任务  # TODO: 提审限制
            return f"已恢复下载次数"
        case "历史" | "ls" | "ht":
            hists = await redis_conn.lrange(f"qqbot:hists:{openid}", 0, -1)
            if not hists:
                return f"今日无历史记录"
            content = f"{prefix}今日历史记录："
            for hist in hists:
                content += f"\n{hist.decode()}"
            return content
        case "我的" | "wd" | "me" | "my":
            return (f"{prefix}剩余下载次数: {quota}\n"
                    f"你的OpenID: \n{openid}")
        case "帮助" | "bz" | "hp":
            content = (f"{prefix}使用说明：\n"
                       f"下载小说：/下载 书籍ID/链接\n"
                       f"查询任务状态：/查询 任务ID\n"
                       f"恢复下载次数：/恢复 任务ID\n（下载失败后使用该命令恢复次数）\n"
                       f"查看历史记录：/历史\n"
                       f"查看我的信息：/我的\n")
                       # f"查看所有命令别名：/别名")  # TODO: 提审限制
            return content
        case "别名":
            content = (f"{prefix}所有命令别名：\n"
                       f"下载：下载 xz dl\n"
                       f"查询：查询 状态 cx qu st\n"
                       f"恢复：恢复 hf re\n"
                       f"历史：历史 ls ht\n"
                       f"我的：我的 wd me my\n"
                       f"帮助：帮助 bz hp\n"
                       f"命令的“/”前缀可省略")
            return content
