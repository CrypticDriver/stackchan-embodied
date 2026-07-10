# deploy/ — EC2 部署产物

## 已上线 (2026-07-10)

| 组件 | 位置 | 说明 |
|---|---|---|
| LiteLLM proxy | systemd `stackchan-litellm`, 127.0.0.1:4000 | OpenAI 兼容端点 → Bedrock Claude (Haiku 4.5 默认 / Sonnet 4.6 备用)。临时顶替 OpenClaw gateway，永不公网暴露 |
| xiaozhi-esp32-server | systemd `stackchan-xiaozhi`, :8000 WS / :8003 OTA | 源码部署(非 Docker, 磁盘原因) venv=~/worklog/stackchan/xiaozhi-venv, python3.11 + torch-cpu。VAD=Silero, ASR=FunASR/SenseVoiceSmall(本地), TTS=EdgeTTS(YunxiaNeural), LLM=StackChanBrain |
| ALB | stackchan-alb (us-east-2) | 默认 403；仅 X-Origin-Verify 头匹配才转发 /xiaozhi/ota/* → :8003, /xiaozhi/v1/* → :8000 |
| CloudFront | E3IEVE3OVA8AW5 → da8daz4hvc7q8.cloudfront.net | 设备入口 (wss/https)，注入 X-Origin-Verify 自定义头 |
| EC2 SG | claude-code-sg | 8000-8003 仅放行 stackchan-alb-sg，无公网入站 |

## 设备侧只需要一个地址

配网门户「高级选项」OTA 地址填：

    https://da8daz4hvc7q8.cloudfront.net/xiaozhi/ota/

OTA 响应会自动下发 websocket `wss://da8daz4hvc7q8.cloudfront.net/xiaozhi/v1/`。

## 密钥 (全部 gitignored, 在 EC2 本机)

- `~/worklog/stackchan/.env-litellm` — LITELLM_MASTER_KEY
- `~/worklog/stackchan/.secrets-origin-verify` — CloudFront↔ALB 校验头
- 运行时配置(含密钥): `xiaozhi-esp32-server/main/xiaozhi-server/data/.config.yaml`
  (由本仓库 `deploy/xiaozhi-server/data/.config.yaml` 模板 + sed 注入生成)

## 验证记录

- OTA via CloudFront: 200, 返回正确 wss 地址 ✅
- WSS via CloudFront: 101 Switching Protocols ✅
- 无 X-Origin-Verify 头直连 ALB: 403 ✅
- 公网直连 EC2:8003: 超时(SG 阻断) ✅
- E2E (hello→文本→LLM→TTS): 本机与 CloudFront 路径均 PASS, opus 音频 400+ 帧 ✅
- FunASR 本地推理: rtf≈0.19 ✅
