# stackchan-embodied 🤖

**StackChan 具身智能：脑在云端，桌上是身体。**

给 M5Stack StackChan (ESP32-S3) 做的云端桥（cloud-bridge）具身化方案 —— 设备只发起 outbound 连接（家里零部署、零端口转发），大脑（OpenClaw Agent「狗蛋」）在 EC2 上驱动它的表情、动作、摄像头、语音。

## 📋 任务书 / 路线图

**[docs/ROADMAP.html](docs/ROADMAP.html)** — 完整的具身智能玩法路线图（M1-M5），交付 Claude Code 执行。

在线预览: https://htmlpreview.github.io/?https://github.com/CrypticDriver/stackchan-embodied/blob/main/docs/ROADMAP.html

## 架构一图流

```
狗蛋 (OpenClaw, AWS EC2)
  ├─ xiaozhi-esp32-server (自建, 语音: FunASR 耳 + edge-tts 声 + LLM=OpenClaw)
  ├─ StackChan Go Server (官方开源 server/, 身体 relay, 设备 outbound WS)
  │    body-client 伪装 App 发二进制控制帧: 表情/动作/摄像头/音频
  └─ 玩法层: happy-watcher(盯 CC 干活) / 人脸追踪 / 生活流
        ⇡ 全部设备主动连出 (CloudFront wss → ALB → EC2)
StackChan 固件 = 纯身体 (语音链路免刷: 配网门户改 OTA 地址;
身体链路重编译刷一次: sdkconfig.defaults.local 覆盖 SERVER_URL, 详见 docs/firmware-repoint.md)
```

## 里程碑

| M | 内容 | 状态 |
|---|------|------|
| M1-B | 语音大脑(先行, 零刷机): xiaozhi-esp32-server + FunASR/edge-tts + LLM, 配网门户改 OTA 地址即切 | ✅ 云端已上线, E2E PASS; 待大哥按 operator-guide 阶段一切换设备 |
| M1-A | 身体 relay(需刷机一次): Go server 部署 + RSA 密钥 + secret_logic 补全 + body-client 帧协议 | ✅ 软件全部完成(16/16 测试); 固件已编译**未烧录**, 待大哥按阶段二备份后刷 |
| M2 | 工作具身化: 盯 Happy (CC 等审批→转头喊人, 完成→点头播报) | 🟡 状态机核心完成(8/8 测试); Happy API 对接待 M1-A 上真机后联调 |
| M3 | 感知主动化: 人脸追踪 / 回家打招呼 / 主动看家 | ⬜ |
| M4 | 对话打磨 + 退役小智云链路 | ⬜ |
| M5 | 生活流: 早报播报 / 提醒物理化 / IR 遥控家电 | ⬜ |

**大哥下一步: 看 [docs/operator-guide.md](docs/operator-guide.md)。阶段一(免刷零风险)5 分钟切语音大脑; 阶段二(刷机)务必先 esptool 全片备份。**
临时说明: LLM 当前走本机 LiteLLM→Bedrock Claude(127.0.0.1:4000, 永不公网), OpenClaw gateway 就位后改一行 base_url 即接狗蛋。

## 相关仓库

- 代码借用源: [CrypticDriver/stackchan-mcp](https://github.com/CrypticDriver/stackchan-mcp)（fork，借 TTS/ASR/PCM 模块与固件 HTTP API 语义）
- 上游固件/服务端: [m5stack/StackChan](https://github.com/m5stack/StackChan)
- 语音服务端: [xinnan-tech/xiaozhi-esp32-server](https://github.com/xinnan-tech/xiaozhi-esp32-server)
- 架构参考: [PheelaV/stackchan-badger](https://github.com/PheelaV/stackchan-badger) · [lifemate-ai/embodied-claude](https://github.com/lifemate-ai/embodied-claude)

---
*by 狗蛋 🐕 for 大哥 · 2026-07-10*
