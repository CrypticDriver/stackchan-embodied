# 架构

## 核心理念：脑体分离

StackChan 机器人本身**不含智能**——它是一套外设：麦克风、扬声器、屏幕、摄像头、两个舵机、RGB 灯。
智能（对话、记忆、决策、工具）全在云端的 OpenClaw agent「狗蛋」里。机器人是这个 agent 伸进物理世界的
**耳朵、嘴、眼睛和脖子**。

这带来一个关键的能力反转：传统语音设备只能被动响应用户输入；有了身体，agent 可以**主动**——
发现值得说的事，就通过身体开口、转头、变表情。「监工」「提醒」「打招呼」都只是这个能力的具象化，
是插在大脑上的**能力槽位**（见 `capabilities/`），不是硬编码进设备的功能。

## 组件全景

| 组件 | 位置 | 作用 |
|---|---|---|
| **StackChan 固件** | 设备 (CoreS3) | 纯身体：唤醒词识别、录音、播放、屏幕渲染、舵机。自编译版含 goudan 皮肤 + 待机动画 |
| **CloudFront** | 边缘 | 设备的唯一公网入口，TLS/wss 终结，注入 `X-Origin-Verify` 头 |
| **ALB** | us-west-2 | 无校验头一律 403；按路径分发到语音栈/OTA/控制台 |
| **xiaozhi-server** | us-west-2 | 语音栈：VAD(Silero) → ASR(FunASR/SenseVoice 本地) → LLM → TTS(EdgeTTS 云希) |
| **brain-router** | us-west-2 | 异步总线：快答直出；慢活先应一声、后台干完经身体主动播报；agent 出错回落辅脑 |
| **OpenClaw「狗蛋」** | us-west-2 | 真 agent 大脑：跨对话记忆、工具、人格。loopback 被 brain-router 调用 |
| **LiteLLM 辅脑** | us-west-2 | 视觉识图 + 记忆总结 + agent 故障时的兜底，直连 Bedrock Claude |
| **body 端点 (goudan_push)** | us-west-2 | 让大脑/能力槽位主动"借嘴说话"的 HTTP 端点 (X-Body-Token 鉴权) |
| **能力 watcher** | us-east-2 | 能力槽位的执行器示例：轮询关注源 → 交 agent 措辞 → 推 body 端点 |
| **控制台** | us-east-2 | 只读运维面板：各组件状态灯、架构图、数据流 |

> **为什么分两区**：大脑（OpenClaw）在 us-west-2。语音栈最初在 us-east-2，导致每轮对话的
> 内部往返横穿美国（~51ms×N）。2026-07 把语音栈搬到 us-west-2 与大脑同机，跨区往返归零，
> 只留必须依赖本机凭据的能力 watcher + 控制台在 us-east-2。见 [deploy/uswest](../deploy/uswest/)。

## 数据流

**一次对话**：
```
"嘿狗蛋"(设备本地 MultiNet 识别) → 录音 Opus 帧 ⇡wss→ CloudFront → ALB → xiaozhi-server
  → SileroVAD 断句 → FunASR 转文字 → brain-router → OpenClaw agent(带人格/记忆/工具)
  → 回复切句 → EdgeTTS 合成 → Opus 帧 ⇣wss→ 设备播放 + 表情/口型同步
```

**慢任务（异步应答）**：agent 超过 ~8s 没答完 → brain-router 先回一句"我去办" → 后台等 agent 干完
→ 经 body 端点让设备主动开口播结果。语音对话永不卡死。

**看**：设备 JPEG ⇡https→ 视觉接口 → LiteLLM/Claude 看图 → 文字回到对话流。

**能力主动播报**（槽位模式）：watcher 轮询某个关注源 → 检测到值得说的事 → 把事件交给 agent
用自己的话组织 → 经 body 端点开口。加新能力 = 在大脑侧加工具/关注点，**身体侧一行不用改**。

## 安全模型

- **设备零入站**：家里不开任何端口转发，设备所有连接都是 outbound wss/https
- **公网唯一入口**：CloudFront → ALB。ALB 默认 403，只有携带 `X-Origin-Verify`（CloudFront 注入的密钥头）
  的请求才转发 → 阻断绕过 CloudFront 直连 ALB
- **EC2 安全组**：语音栈端口只放行 ALB 的 SG；跨区/身体端点只放行指定实例 /32
- **大脑永不公网**：OpenClaw gateway、LiteLLM 只绑 loopback
- **token 分层**：控制台 token / body token / gateway token 各自独立，泄露一个不波及其他
- **密钥不入库**：所有密钥走 `.env*`（gitignored），仓库里只有占位符，部署时注入

## 固件要点（踩过的坑，见 docs/firmware-*.md）

- 设备开机默认进 xiaozhi AI 模式；身体控制在该模式走 agent 的 MCP 工具（转头/拍照/LED），
  0x03 二进制 relay 通道仅桌宠模式生效
- 皮肤/唤醒词配置从 assets 包的 `index.json` 读，**不走** Kconfig 固件代码路径（两处都要改）
- WS 客户端 URL 必须带显式端口（`:443`）；LVGL 旋转顺时针为正
- 设备只在收到 `tts start` 进入 Speaking 态后才播放音频（主动播报必须先发 start）
