"""check_work — 狗蛋的监工查询工具 (stackchan-embodied)。

function call 插件: 大哥问工作/任务/审批状态时, 狗蛋调它拿真实数据再回答, 不凭空编。

架构: Happy 解密凭据只在 us-east 的 watcher 上, 所以本工具 (跑在 us-west 语音栈里)
经 VPC peering 调 watcher 的只读查询 API (WORK_QUERY_URL), 而不是自己解密。
"""

import json
import os
import time
import urllib.request

from plugins_func.register import register_function, ToolType, ActionResponse, Action

WORK_QUERY_URL = os.environ.get("WORK_QUERY_URL", "http://172.31.0.86:9102/")

check_work_function_desc = {
    "type": "function",
    "function": {
        "name": "check_work",
        "description": (
            "查询大哥的 CC (Claude Code) 编程任务的实时状态。"
            "当大哥问：现在有什么活、有没有任务等审批、CC 在干嘛、监工情况、"
            "有几个在跑之类的问题时，必须调用此工具获取真实数据后再回答。"
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

_cache = {"ts": 0.0, "text": ""}


def _fetch_summary():
    with urllib.request.urlopen(WORK_QUERY_URL, timeout=8) as r:
        data = json.load(r)
    pending = data.get("pending", [])
    running = data.get("running", [])
    parts = []
    if pending:
        lines = []
        for p in pending[:4]:
            cmd = (p.get("command") or p.get("tool", ""))[:50]
            lines.append(f"{p['title']}要用 {p.get('tool','')} 跑「{cmd}」")
        parts.append(f"有 {len(pending)} 个审批在等大哥: " + "；".join(lines)
                     + ("，还有更多" if len(pending) > 4 else "")
                     + "。大哥去手机上点一下就行")
    else:
        parts.append("现在没有任务等审批")
    if running:
        parts.append(f"另外 {len(running)} 个在干活: " + "、".join(running[:5]))
    return "。".join(parts)


@register_function("check_work", check_work_function_desc, ToolType.SYSTEM_CTL)
def check_work(conn=None):
    """查询 CC 工作状态, 15s 缓存。"""
    now = time.time()
    if now - _cache["ts"] > 15:
        try:
            _cache["text"] = _fetch_summary()
            _cache["ts"] = now
        except Exception as e:
            return ActionResponse(Action.REQLLM, f"监工数据拉取失败了: {e}", None)
    return ActionResponse(Action.REQLLM, _cache["text"], None)
