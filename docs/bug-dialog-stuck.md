# Bug: 对话结束后气泡挂整夜 + 再唤醒无法聊天只能重启

**现象** (2026-07-12 大哥反馈, 附图: 屏幕停在最后一句气泡"晚安~", 眼睛不眨)
1. 说完话/告别后，最后一个聊天气泡一直挂着不消失，能挂一整晚
2. 之后再唤醒，就没法聊天了，只能重启设备

## 源码级根因分析 (待真机串口坐实)

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
