# Bug: 对话结束后气泡挂整夜 + 再唤醒无法聊天只能重启

**现象** (2026-07-12 大哥反馈, 附图: 屏幕停在最后一句气泡"晚安~", 眼睛不眨)
1. 说完话/告别后，最后一个聊天气泡一直挂着不消失，能挂一整晚
2. 之后再唤醒，就没法聊天了，只能重启设备

## ✅ 真机串口坐实 (2026-07-12, stackchan-diag-20260712-121519.log)

抓到 634 行日志, **修正了初始假设**:

- 设备全程在 `speaking ↔ listening` 之间跳, **从未进过 idle**。
- 静置 **47 分钟** 期间: 只有 `free sram` 心跳, **无 `Websocket disconnected`、
  无 `Channel timeout`、无任何断连**。连接一直是活的。
- 47 分钟后一句"哎，狗蛋，我回来了" → 立刻 `listening -> speaking` 正常应答。
  **现象2 (唤醒卡死) 本次未复现** —— 说明它不是必现, 更像偶发 (某次连接真断/
  服务端 session 超时清理), 暂缓, 下次真卡死时接线抓串口再定位。

**现象1 (气泡挂整夜+不眨眼) 根因确定, 与"跨区断连收不到回调"无关**:
狗蛋 `GetDefaultListeningMode()` = AutoStop(AEC 关) / Realtime(AEC 开), **都不是
ManualStop**。而 `OnIncomingJson` 里 TTS `stop` 后, 只有 ManualStop 才
`SetDeviceState(Idle)`, AutoStop/Realtime **都回 `Listening`**。
→ 说完话永远回 listening, 永远不进 idle
→ `HandleStateChangedEvent` 里进 idle 才做的 `ClearChatMessages()` 永不触发
→ **气泡永久挂着**; 待机眨眼动画也只在 idle 跑 → **不眨眼**。

## 修复 (已实现, 已编译+宿主验证, 待刷机)

**方案: listening 态空闲超时自动回待机** (application.cc)
- 新增 `listening_idle_ticks_`; clock tick (每秒) 里若 `Listening` 且
  `!IsVoiceDetected()` 则累加, 达 `kListeningIdleTimeoutSeconds=30` 秒 →
  收链 + 清气泡 + `SetDeviceState(Idle)` (显式做全套清理, 不裸依赖
  `~WebSocket` 的析构回调时序)。
- VAD 检测到语音 / 任何状态切换 → 计数清零。Speaking 态不计。
- 效果: 说完话没人接话 30 秒 → 自动回待机 (气泡消失、恢复眨眼、需重新唤醒)。

宿主验证: `firmware/host-verify/idle_timeout_test.cpp` 复刻状态机, 5 场景全过
(静默30s回idle / 中途说话清零 / Speaking不超时 / 持续说话不超时 / 回idle后不重触发)。

---
## (存档) 初始源码级推断 (部分被日志推翻)

> 曾推断两现象同源于"设备守着被中间层掐断的 WS"。日志证明静置期间连接未断,
> 现象1 实为监听模式设计所致 (见上)。保留以备现象2 复现时参考跨区断连方向。

两个现象是**同一根因**: 设备端守着一条已经名存实亡的 WebSocket 不放，
状态机停在非 Idle 态。

### 证据链 (固件源码)

1. **气泡只在回 Idle 时清**
   `application.cc: HandleStateChangedEvent()` → 进入 `kDeviceStateIdle` 时
   `display->ClearChatMessages()`。待机眨眼动画也只在 Idle 跑。
   → 气泡整夜挂着 + 眼睛不眨 = **设备根本没回到 Idle**。

2. **回 Idle 依赖断开回调**
   正常结束: 服务端断开 → `websocket_protocol.cc: OnDisconnected()` →
   `on_audio_channel_closed_()` → `application.cc:512` `Schedule` 里
   `SetChatMessage("system","") + SetDeviceState(kDeviceStateIdle)`。
   → 气泡没清 = **这个回调没触发** = 设备没收到 TCP 断开。

3. **为什么没收到断开**
   语音栈在 us-west-2，设备在北京，走 CloudFront→ALB 长连接。
   对话结束后通道空闲，中间层 (CloudFront/ALB 空闲超时) 静默丢弃连接，
   **TCP FIN 未能传回设备**。xiaozhi 客户端**无 keepalive/ping**，也**不主动收链**:
   `Protocol::IsTimeout()` 判 120s 无数据只是把 `IsAudioChannelOpened()` 标 false，
   **不触发任何回调、不改状态机**。设备就一直以为通道开着。

4. **再唤醒卡死**
   `HandleWakeWordDetectedEvent()` 只在 `state == kDeviceStateIdle` 才响应唤醒。
   设备卡在非 Idle (Speaking/Listening 残留态) → 喊唤醒词落到别的分支或无匹配 →
   **啥也不发生，只能重启**。
   即便侥幸在 Idle: `ContinueWakeWordInvoke()` 复用半死的 `websocket_` 重连，
   `error_occurred_` 未必置位，握手时序易错乱 → 连上也 session 对不上。

### 真机串口证据 (复现时抓, 用 tools/diag-serial.sh)

设备状态数字: **3=Idle 4=Connecting 5=Listening 6=Speaking**
- 卡死时喊唤醒词，看 `Wake word detected: xxx (state: N)`:
  - N≠3 → 坐实卡在非 Idle (最可能 6 Speaking 残留 或 4 Connecting)
  - 无此行 → 唤醒词识别本身也挂了 (另查)
- 有没有 `Websocket disconnected` → 无 = 断开回调确实没到 (证据2)
- 有没有 `Channel timeout 120 seconds` → 有 = 通道判超时但没自愈

## 候选修法 (待大哥定, 复现确认后实施)

| 方案 | 做法 | 代价 |
|---|---|---|
| **A 设备主动收链** (根治) | 固件: Idle 且通道空闲 >N 秒主动 `CloseAudioChannel()` 回干净 Idle; 唤醒时若旧通道可疑先强制重建 | 改固件重刷 (已备份+双OTA可回滚) |
| B WS keepalive | 固件: Idle 定期 ping 撑住连接 | 改固件; 长期占资源; 治标(中间层策略仍可能变) |
| C 服务端/网关兜底 | ALB/服务端调空闲超时 + 断开时多做清理 | 见效快无需重刷; 改不了设备守死连接的核心, 唤醒卡死可能仍在 |

推荐 A (根治现象1+2)，可叠加 C 兜底。B 单独用治标不治本。

## 状态
- [x] 源码级根因分析完成
- [ ] 真机串口复现坐实 (大哥用 tools/diag-serial.sh 抓日志回传)
- [ ] 按选定方案修复 + 宿主/QEMU 验证 + 重刷
