# stackchan-embodied 🐕

**给 M5Stack StackChan 一个云端的灵魂——脑在外面，桌上的机器人只是身体。**

一台 M5Stack StackChan（CoreS3，ESP32-S3）机器人，接上一个真正的 AI agent 大脑：
能自然语音对话、看东西、转头做表情、还能被赋予各种"关注点"主动开口找你。
传统语音音箱是"你问它才答"；这个项目让机器人**有 agency**——大脑可以主动通过身体表达、提醒、汇报。

> 名字梗：这台机器人的大脑是一个叫「狗蛋」的 OpenClaw agent，所以机器人也叫狗蛋。

---

## 它能做什么

- 🗣 **自然对话**：说「嘿狗蛋」唤醒，本地识别→云端 agent 思考→语音回答，带表情和口型同步
- 👁 **看**：摄像头拍照 + 视觉模型，"看看我手里是什么"
- 🦾 **动**：转头、12 套表情（含专属「果冻高光眼」皮肤）、机身 RGB 灯、待机眨眼
- 🧠 **真 agent 大脑**：不是无状态问答机——有跨对话记忆、能调工具、慢任务"先应一声、干完主动播报"
- 🔌 **能力槽位**：大脑侧插入任意"关注点"（示例见 [capabilities/](capabilities/)），发现值得说的事就通过身体主动告诉你

## 一眼架构

```
   🏠 家里                    ☁️ 边缘                🌎 us-west-2 (脑体同区)
┌──────────┐   outbound   ┌────────────┐   ┌──────────────────────────────┐
│ StackChan │═══ wss ════▶│ CloudFront  │──▶│ ALB → 语音栈(ASR/TTS/VAD)     │
│ 自编译固件 │  (设备只连出) │ +X-Origin- │    │     → brain-router(异步总线)  │
│ 果冻眼皮肤 │◀═════════════│  Verify→ALB │   │     → OpenClaw「狗蛋」agent    │
└──────────┘              └────────────┘   │       (loopback, 有记忆+工具)  │
   零入站端口                   TLS/wss 终结  └──────────────────────────────┘
                                                   ▲ 能力槽位在大脑侧插入
```

设备**只发起 outbound 连接**（家里零端口转发）；一切公网入口经 CloudFront→ALB（`X-Origin-Verify` 头校验），EC2 安全组只放行 ALB。详见 **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**。

## 从零到桌上的狗蛋

看 **[docs/QUICKSTART.md](docs/QUICKSTART.md)** —— 三步：①云端一键部署 ②刷固件（先备份，防砖流程齐全）③配网。

```bash
git clone https://github.com/CrypticDriver/stackchan-embodied && cd stackchan-embodied
./scripts/deploy.sh            # 云端: 装语音栈+brain-router+服务 (幂等)
# 固件: 见 docs/flash-guide.html (Mac) / docs/operator-guide.md
```

## 目录

| 路径 | 内容 |
|---|---|
| [`firmware/`](firmware/) | 自编译固件产物 + goudan skin 源码 + secret_logic + 唤醒词补丁 + 复现说明 |
| [`body-client/`](body-client/) | Python 库：WS 帧协议、RSA 鉴权、表情预设、驱动身体 API（含测试） |
| [`deploy/`](deploy/) | 云端组件：xiaozhi 语音栈配置、brain-router、LiteLLM 辅脑、控制台、systemd |
| [`capabilities/`](capabilities/) | 大脑能力槽位示例（如何给狗蛋加新"关注点"） |
| [`scripts/`](scripts/) | `deploy.sh` 一键部署 · `health-check.sh` 健康检查 |
| [`docs/`](docs/) | 架构、快速上手、刷机指南、表情模拟器、固件核查报告 |

## 在线页面

- [控制台](https://da8daz4hvc7q8.cloudfront.net/console/)（需 token）· [表情模拟器](https://crypticdriver.github.io/stackchan-embodied/face-simulator.html) · [画风画廊](https://crypticdriver.github.io/stackchan-embodied/skin-gallery.html) · [刷机指南](https://crypticdriver.github.io/stackchan-embodied/flash-guide.html)

## 上游 / 致谢

固件基于 [m5stack/StackChan](https://github.com/m5stack/StackChan)（含 [78/xiaozhi-esp32](https://github.com/78/xiaozhi-esp32)），语音服务端 [xinnan-tech/xiaozhi-esp32-server](https://github.com/xinnan-tech/xiaozhi-esp32-server)。

---
*脑在云端，桌上是身体。*
