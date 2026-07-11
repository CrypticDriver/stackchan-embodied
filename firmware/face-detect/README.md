# M3 · 本地人脸检测 (on-device face detection)

狗蛋在**本机**用摄像头认出"有人凑到跟前"，凑近就眨眼打招呼 (Happy + 爱心)。
全程跑在 ESP32-S3 上，**不联网、不上传任何图像** —— 隐私零外泄。

## 这是什么

- 检测器: Espressif `human_face_detect` (MSRMNP_S8_V1, 两阶段 MSR→MNP)，底层 `esp-dl` v3.x
- 模型内嵌在 app 的 rodata (无独立分区)，s3 量化模型约 190KB
- 输入: 摄像头原生 **RGB565**，esp-dl 原生支持，**零格式转换**
- 输出: `FaceEvent::Appear` / `Gone` 信号，交给 avatar 侧变表情

这是 M3 第一步 —— **最小闭环**，只验证"摄像头→推理→表情"整条链路能在这套固件上跑、
性能可接受。后续再做"看向人脸/主动问好"。

## 文件

| 文件 | 作用 |
|---|---|
| `hal_face_detect.cpp` | 后台任务: 每 0.5s 静默取一帧 → esp-dl 推理 → 去抖后发 FaceEvent |
| `face_event.h` | `FaceEventModifier`: 收到 Appear → 短暂 Happy+爱心，自动恢复 (不长锁 avatar) |
| `partitions.csv` | **新分区表** (见下方"分区变更") |
| `stackchan_camera.h.ref` | 摄像头头文件 (参考，含新增的 `GrabForDetect`) |

### 接入点 (改动清单)

1. `main/idf_component.yml` — 加 `espressif/human_face_detect: ^0.5.0` (仅 esp32s3/p4)
2. `main/CMakeLists.txt` — `PRIV_REQUIRES` 加 `human_face_detect`
3. `main/hal/hal.h` — 加 `enum class FaceEvent`、`onFaceEvent` 信号、`face_detect_init()`
4. `main/hal/board/stackchan_camera.{h,cc}` — 加 `GrabForDetect()` 静默取帧 + `frame_mutex_`
   与拍照路径 (`Capture`) 串行 (共用同一块 V4L2 buffer)；取帧 `try_lock` 失败即跳过，**绝不阻塞拍照**
5. `main/stackchan/modifiers/modifiers.h` — `#include "face_event.h"`
6. `main/hal/board/stackchan_display.cc` — 注册 `FaceEventModifier` + 调 `GetHAL().face_detect_init()`

## ⚠️ 分区变更 (刷机必看)

esp-dl 推理运行时 + 内嵌模型让 app 从 **3.79MB → 5.65MB**，超出原来 5.06MB 的 OTA 槽 465KB。
16MB flash 有余量，于是重排 (保留**双 OTA 可回滚**，符合防砖要求):

| 分区 | 旧 | 新 |
|---|---|---|
| ota_0 | 0x20000, 5.06MB | 0x20000, **6.02MB** |
| ota_1 | 0x510000, 5.06MB | 0x5E0000, **6.02MB** |
| assets | **0xA00000**, 5MB | **0xBA0000**, 4.39MB (实占 4.02MB) |
| coredump | 尾部, 64KB | 0xFD0000, 64KB |

`nvs`/`otadata` 偏移**未动** → 家里 WiFi/配置不丢。
但**分区表本身变了**，刷机必须整套刷 (含新 partition-table.bin，assets 用新地址 `0xBA0000`)，
否则分区不匹配起不来。全片备份是后悔药。

## 验证状态

- ✅ 依赖解析 + reconfigure 通过 (组件能拉下来、无冲突)
- ✅ **完整编译 + 链接通过** (esp-dl 真正编进这套固件，这是 M3 最大关卡)
- ✅ Flash 容量: app 5.65MB 落在 6.02MB 槽 (余 6%)，assets 4.21MB 落在 4.39MB 分区
- ⚠️ **无法 QEMU 验证**: QEMU esp32s3 无摄像头模型，推理精度/帧率/内存占用只能真机实测
  —— 这是本项目第一个不能完全预验证的改动，务必先全片备份再刷

## 真机上线后要看什么

1. 串口 `HAL-FACE` 日志: `model loaded` → 凑脸出现 `face APPEAR` → 离开 `face GONE`
2. 凑近镜头，狗蛋是否眨眼变 Happy + 冒爱心，离开后恢复
3. 性能: 推理是否卡住音频/动画 (任务在 core 1，节奏 0.5s/帧，理论上不挤 core 0)
4. 内存: `heap_caps` 是否够 (帧缓冲在 PSRAM，模型在 flash rodata)
   若推理太慢/占内存，可换更轻的 `espdet_pico_224_224` 或降检测频率
