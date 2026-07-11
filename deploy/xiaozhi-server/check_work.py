"""check_work — 狗蛋的监工查询工具 (stackchan-embodied M2)。

function call 插件: 让狗蛋在对话中真的去查大哥的 CC (Claude Code) 工作状态,
而不是凭空编。数据源与 happy-watcher 同一套 (Happy API + 本机密钥解密)。

部署: 拷到 plugins_func/functions/, 在 Intent.function_call.functions 加 check_work。
"""

import subprocess
import sys
import time

from plugins_func.register import register_function, ToolType, ActionResponse, Action

WATCHER_PATH = "/home/ec2-user/worklog/stackchan/stackchan-embodied/happy-watcher"

check_work_function_desc = {
    "type": "function",
    "function": {
        "name": "check_work",
        "description": (
            "查询大哥的 CC (Claude Code) 编程任务/会话的实时状态。"
            "当大哥问：现在有什么活、有没有任务等审批、CC 在干嘛、监工情况、"
            "工作进展、有几个任务在跑之类的问题时，必须调用此工具获取真实数据后再回答。"
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

_cache: dict = {"ts": 0.0, "text": ""}


def _fetch_summary() -> str:
    if WATCHER_PATH not in sys.path:
        sys.path.insert(0, WATCHER_PATH)
    from happy_watcher.poller import HappyPoller  # noqa: PLC0415

    snaps = HappyPoller("https://d2nkikyt4i91kk.cloudfront.net").fetch()
    waiting = [s for s in snaps if s.state.value == "waiting_input"]
    running = [s for s in snaps if s.state.value == "running"]

    parts = []
    if waiting:
        names = "、".join(s.title for s in waiting[:5])
        parts.append(f"有 {len(waiting)} 个任务在等大哥处理: {names}"
                     + ("等" if len(waiting) > 5 else ""))
    else:
        parts.append("现在没有任务等大哥审批")
    if running:
        names = "、".join(s.title for s in running[:5])
        parts.append(f"{len(running)} 个 CC 正在干活: {names}"
                     + ("等" if len(running) > 5 else ""))
    else:
        parts.append("没有 CC 在干活")

    # 最近播报 (journald, 最多3条)
    try:
        logs = subprocess.run(
            ["journalctl", "-u", "stackchan-watcher", "--since", "-2hour", "-o", "cat", "--no-pager"],
            capture_output=True, text=True, timeout=5).stdout
        spoken = [l.split("] ", 1)[1].split(" <- ")[0]
                  for l in logs.split("\n") if "] " in l and "(表情)" not in l]
        if spoken:
            parts.append("我最近播报过: " + "；".join(spoken[-3:]))
    except Exception:  # noqa: BLE001
        pass

    return "。".join(parts)


@register_function("check_work", check_work_function_desc, ToolType.SYSTEM_CTL)
def check_work(conn=None):
    """查询 CC 工作状态, 30s 缓存防止连续追问重复拉取。"""
    now = time.time()
    if now - _cache["ts"] > 30:
        try:
            _cache["text"] = _fetch_summary()
            _cache["ts"] = now
        except Exception as e:  # noqa: BLE001
            return ActionResponse(Action.REQLLM, f"监工数据拉取失败了: {e}", None)
    return ActionResponse(Action.REQLLM, _cache["text"], None)
