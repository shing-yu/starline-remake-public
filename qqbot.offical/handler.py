from botpy.message import C2CMessage, GroupMessage
from common import config
import httpx


endpoint = config.api.endpoint


async def commands_handler(openid: str, command: str, _message: C2CMessage | GroupMessage, prefix: str = "\n") -> str:
    command = command[1:] if command.startswith("/") else command
    action = command[:2]
    args = command[2:].lstrip() if command[2:].startswith(" ") else command[2:]

    match action:
        case "下载" | "xz" | "dl":
            if len(args) != 19:
                return "无效的 book_id 长度，请检查后重试"
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{endpoint}/tasks", json={"book_id": args})
                task_id = response.json()["task_id"]
                return f"{prefix}任务已提交\n任务ID: {task_id}"
            pass
        case "查询" | "状态" | "cx" | "qu" | "st":
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{endpoint}/tasks/{args}")
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
            pass
        case "我的" | "wd" | "me" | "my":
            pass
        case "帮助" | "bz" | "hp":
            content = (f"{prefix}使用说明："
                       f"{prefix}1. 下载小说：/下载 书籍ID"
                       f"{prefix}2. 查询任务状态：/查询 任务ID"
                       f"获取小说文件请到群精华链接")
            return content
