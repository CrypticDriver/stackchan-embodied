"""brain-router — 狗蛋的脑体总线 (127.0.0.1:4001, OpenAI 兼容)。

xiaozhi-server → 这里 → OpenClaw xiaogoudan。

异步应答: 上游在 INLINE_WAIT 秒内回完 → 原样流式转发;
超时 → 立刻回一句"稍等我去办" (对话不卡死), 后台继续等 agent 干完,
完成后通过 goudan_push (/goudan/say) 让设备主动开口播结果。

这样快问题 (寒暄/常识) 无感, 慢问题 (查股价/翻网页/调工具) 不再撞
语音超时, 体验 = "支使一声, 干完喊你"。
"""

import asyncio
import json
import os
import re

from aiohttp import ClientSession, ClientTimeout, web

UPSTREAM = os.environ.get("OPENCLAW_URL", "http://10.0.1.80:18790/v1/chat/completions")
UPSTREAM_TOKEN = os.environ["OPENCLAW_TOKEN"]
FALLBACK_URL = os.environ.get("FALLBACK_URL", "http://127.0.0.1:4000/v1/chat/completions")
FALLBACK_TOKEN = os.environ.get("FALLBACK_TOKEN", "")
FALLBACK_MODEL = os.environ.get("FALLBACK_MODEL", "stackchan-brain")
UPSTREAM_ERR_MARKS = ("LLM request failed", "No response from OpenClaw")
PUSH_URL = os.environ.get("PUSH_URL", "http://127.0.0.1:9101/goudan/say")
INLINE_WAIT = float(os.environ.get("INLINE_WAIT", "8"))
HOLD_LINES = [
    "稍等，这个我得去查查，弄好了叫你。",
    "这事儿得花点功夫，我去办，好了喊你。",
    "收到，我这就去弄，你先忙。",
    "让我查查啊，一会儿给你信儿。",
]
_hold_idx = 0


def next_hold_line() -> str:
    global _hold_idx
    line = HOLD_LINES[_hold_idx % len(HOLD_LINES)]
    _hold_idx += 1
    return line

_background: set[asyncio.Task] = set()


def _strip_md(text: str) -> str:
    """语音场景: 去掉 markdown 痕迹。"""
    text = re.sub(r"[*_`#>\[\]()]|https?://\S+", "", text)
    return re.sub(r"\s{2,}", " ", text).strip()


async def _push_say(text: str) -> None:
    text = _strip_md(text)
    if len(text) > 300:
        text = text[:297] + "……"
    async with ClientSession() as s:
        try:
            await s.post(PUSH_URL, json={"text": text},
                         headers={"X-Body-Token": os.environ.get("BODY_TOKEN", "")},
                         timeout=ClientTimeout(total=20))
        except Exception as e:  # noqa: BLE001
            print("push failed:", e, flush=True)


async def _post_chat(url: str, token: str, payload: dict, total: float) -> str:
    async with ClientSession() as s:
        async with s.post(url, json=payload,
                          headers={"Authorization": f"Bearer {token}"},
                          timeout=ClientTimeout(total=total)) as r:
            data = await r.json()
    return data["choices"][0]["message"]["content"]


AGENT_TIMEOUT = float(os.environ.get("AGENT_TIMEOUT", "25"))   # agent 快速失败阈值 (原 600 → 太久)
# 连续失败熔断: agent 连错 N 次后暂时直接走辅脑, 避免每轮都白等
_agent_fail_streak = 0
_agent_circuit_open_until = 0.0


async def _fallback(payload: dict) -> str:
    fb = dict(payload)
    fb["model"] = FALLBACK_MODEL
    fb["stream"] = False
    fb.setdefault("messages", [])
    return await _post_chat(FALLBACK_URL, FALLBACK_TOKEN, fb, 60)


async def _call_upstream(payload: dict) -> str:
    """agent 优先, 但快速失败/熔断回落辅脑 (LiteLLM), 绝不把错误英文念出来。"""
    global _agent_fail_streak, _agent_circuit_open_until
    import time as _t
    payload = dict(payload)
    payload["stream"] = False

    # 熔断打开期: agent 最近连错, 直接走辅脑 (辅脑快而稳)
    if _t.time() < _agent_circuit_open_until:
        return await _fallback(payload)

    try:
        content = await _post_chat(UPSTREAM, UPSTREAM_TOKEN, payload, AGENT_TIMEOUT)
        if content and not any(m in content for m in UPSTREAM_ERR_MARKS):
            _agent_fail_streak = 0            # agent 成功, 重置
            return content
        print("upstream returned error text, falling back:", (content or "")[:80], flush=True)
    except Exception as e:  # noqa: BLE001
        print("upstream exception, falling back:", e, flush=True)

    # agent 失败: 累计, 连错 3 次熔断 90s
    _agent_fail_streak += 1
    if _agent_fail_streak >= 3:
        _agent_circuit_open_until = _t.time() + 90
        _agent_fail_streak = 0
        print("agent circuit OPEN 90s (too many failures) → aux brain", flush=True)
    return await _fallback(payload)


def _sse(data: dict) -> bytes:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode()


async def chat(request: web.Request) -> web.StreamResponse:
    payload = await request.json()
    stream = payload.get("stream", True)

    task = asyncio.create_task(_call_upstream(payload))

    try:
        content = await asyncio.wait_for(asyncio.shield(task), timeout=INLINE_WAIT)
        answered_inline = True
    except asyncio.TimeoutError:
        answered_inline = False
        content = next_hold_line()

        async def _finish():
            try:
                result = await task
                await _push_say(result)
            except Exception as e:  # noqa: BLE001
                await _push_say("大哥，刚才那事儿我没办成，回头再试。")
                print("background task failed:", e, flush=True)

        bg = asyncio.create_task(_finish())
        _background.add(bg)
        bg.add_done_callback(_background.discard)

    if not stream:
        return web.json_response({
            "id": "brain-router", "object": "chat.completion", "model": "goudan",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                          "finish_reason": "stop"}],
        })

    resp = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
    await resp.prepare(request)
    base = {"id": "brain-router", "object": "chat.completion.chunk", "model": "goudan"}
    await resp.write(_sse({**base, "choices": [{"index": 0, "delta": {"role": "assistant"}}]}))
    # 按句切块, 让 TTS 尽早开工
    for seg in re.split(r"(?<=[。！？!?；;\n])", content):
        if seg:
            await resp.write(_sse({**base, "choices": [{"index": 0, "delta": {"content": seg}}]}))
    await resp.write(_sse({**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}))
    await resp.write(b"data: [DONE]\n\n")
    await resp.write_eof()
    return resp


async def health(_: web.Request) -> web.Response:
    return web.json_response({"ok": True, "background_jobs": len(_background)})


app = web.Application()
app.router.add_post("/v1/chat/completions", chat)
app.router.add_get("/health", health)

if __name__ == "__main__":
    web.run_app(app, host="127.0.0.1", port=4001, print=None)
