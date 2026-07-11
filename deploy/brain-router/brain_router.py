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
PUSH_URL = os.environ.get("PUSH_URL", "http://127.0.0.1:9101/goudan/say")
INLINE_WAIT = float(os.environ.get("INLINE_WAIT", "8"))
HOLD_LINE = "稍等，这个我得去查查，弄好了叫你。"

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


async def _call_upstream(payload: dict) -> str:
    """非流式调上游, 返回完整回答文本。"""
    payload = dict(payload)
    payload["stream"] = False
    async with ClientSession() as s:
        async with s.post(
            UPSTREAM,
            json=payload,
            headers={"Authorization": f"Bearer {UPSTREAM_TOKEN}"},
            timeout=ClientTimeout(total=600),
        ) as r:
            data = await r.json()
    return data["choices"][0]["message"]["content"]


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
        content = HOLD_LINE

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
