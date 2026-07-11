# deploy/uswest/ — 语音栈搬迁 us-west-2 (2026-07-11)

## 为什么
原语音栈在 us-east-2, 大脑在 us-west-2, 北京设备每轮对话横穿美国往返。
搬到 dogegg (us-west-2, 与 OpenClaw 大脑同机) 后, OpenClaw 变 loopback, 省一台机器。

## 拓扑 (搬迁后)
- **us-west-2 dogegg (i-0d66513435366291e, c7g.xlarge ARM)**:
  - openclaw-gateway (大脑, 原有) :18789 loopback / :18790 peering
  - stackchan-xiaozhi (语音: FunASR/EdgeTTS/VAD) :8000/:8003
  - stackchan-brainrouter (异步总线) :4001 → loopback 18789
  - stackchan-litellm (辅脑, bedrock us-west-2 sonnet-5) :4000
  - 服务用户 = ubuntu, venv=/home/ubuntu/xiaozhi-venv (py3.12, torch 2.13 aarch64 SVE256)
  - 配置/密钥: /home/ubuntu/stackchan-deploy/env-all (S3 中转部署, 非 repo)
- **us-west-2 stackchan-uswest-alb**: CloudFront origin, X-Origin-Verify 同 us-east 密钥
- **us-east-2 (本机)**: 只留 stackchan-watcher (守 ~/.happy 解密凭据) + stackchan-console + stackchan-goserver(桌宠身体relay备用)
  - watcher PUSH_URL/AGENT_URL 经 peering 指 dogegg

## 数据流 (搬迁后)
设备 → CloudFront → stackchan-uswest-alb → dogegg 语音栈 → loopback 大脑 (全 us-west)
监工: us-east watcher → peering → dogegg :9101 播报

## 回滚
CloudFront E3IEVE3OVA8AW5 origin 改回 stackchan-alb-786340720.us-east-2 + 重启 us-east 四服务。
OpenClaw 模型: openclaw.json.bak-sonnet46 (Sonnet 5 在此 gateway 不稳, 现用 4.6)
