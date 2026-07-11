# 自编译固件预验证报告 (2026-07-10, 未接触真机)

三层验证，逐层加深。**结论：刷机前能在云端验证的部分全部通过；剩余风险仅剩真机外设路径，且有全片备份兜底。**

## 第 1 层：镜像结构 ✅

`esptool --chip esp32s3 image_info build/stack-chan.bin`:
- 合法 ESP32-S3 应用镜像，6 段，入口 0x40379710
- Checksum 07 valid + Validation Hash valid
- 分区表解析正常：ota_0/ota_1 各 5056K，app 3.6MB < 5056K（放得下，OTA 双分区都够）
- assets 分区 4M @ 0xa00000，generated_assets.bin 2.2MB 放得下

## 第 2 层：鉴权逻辑回环（最关键）✅

把固件里的 `secret_logic_selfhost.cpp` **原封不动**（仅剥离 esp 头文件，esp_read_mac/esp_random 用 shim）
在宿主机上以 mbedtls v3.6.2 编译成 `token_harness`，然后：

| 测试 | 结果 |
|---|---|
| 固件 C++ 代码生成 token → 连真实 Go server `deviceType=StackChan` | **101 接受** ✅ |
| 复刻固件 hello 消息 + body-client 从 App 侧发动作帧 | **帧路由到位**，收到 `{"yawServo":{"angle":30},...}` ✅ |
| 11 秒旧 token 重放 | **401 拒绝**（±10s 窗口生效）✅ |
| 连续两次生成 token | 不同（nonce/随机数正常）✅ |
| CONFIG_STACKCHAN_SERVER_URL 注入 | 输出 `https://da8daz4hvc7q8.cloudfront.net` ✅ |

> 意义：这条链路 = 刷机后设备连 relay 的完整鉴权路径（同一份 C++ 源码、同一 mbedtls API、
> 同一 Go server、同一 RSA 公钥）。**设备侧唯一差异是 SNTP 校时质量**——±10s 窗口要求
> 设备时钟基本准，固件本身自带 SNTP（xiaozhi 底座），风险低。

字节级核对：`strings stack-chan.bin` 确认镜像内嵌 `da8daz4hvc7q8.cloudfront.net` ×2
（STACKCHAN_SERVER_URL + OTA_URL）与自建 server RSA 公钥体。

## 第 3 层：QEMU esp32s3 整机仿真 ✅（到硬件边界）

按 flash_args 布局拼 16MB 完整 flash 镜像（与真机一致），esp-develop QEMU 9.2.2 启动：

- ✅ ROM bootloader → 二级 bootloader (v5.5.4) 加载
- ✅ 分区表识别、`No factory image, trying OTA 0`、五段全部加载无 hash 错
- ✅ 8MB PSRAM 识别挂堆、双核启动、cpu 240MHz
- ✅ `Project name: stack-chan / App version: 1.4.3` 进入用户代码
- ⏹ 停在 I2C 外设初始化（AXP2101 电源管理芯片）——QEMU 无 CoreS3 板级外设模型，**预期边界**，
  不代表固件缺陷（任何 CoreS3 固件在裸 QEMU 都停在这）

## 残余风险清单（只能真机验证）

1. 板级外设初始化（屏/触摸/摄像头/舵机）——但这部分代码与官方出厂固件**完全同源**（我们只改了
   secret_logic + 两个 URL 常量），出厂固件能跑 → 这部分就能跑
2. 设备 SNTP 校时到位前首个 WS 连接可能 401 → 固件有重连逻辑，校时后自愈
3. NVS 里遗留的官方 ota_url 可能覆盖编译期 OTA_URL → 配网门户改一次即可（手册已写）

结论：**与出厂固件的 diff 面（鉴权+URL）已 100% 云端验证；未验证面与出厂固件同源。**
配合全片备份，刷机风险已压到最低。

## 复现

- 宿主鉴权回环: `/tmp/secret-logic-host/`（harness.cpp + ws_connect_test.py，本文档同目录归档见 `firmware/host-verify/`）
- QEMU: `idf_tools.py install qemu-xtensa` + 手动补 libslirp/SDL2（AL2023 无包，源码编）

---

## 第 4 层（追加 2026-07-11）：表情/动作语义闭环 ✅ — 并抓到一个真 bug

**方法**：固件的 `json_helper.cpp`（sha256 与固件源完全一致，一字未改）在宿主编译，
Avatar/Servo/NeonLight 换成记录调用的 spy 桩。然后跑**全真链路**:

```
BodyClient(真) → Go relay :12800(真, RSA 鉴权) → 设备侧帧接收(固件 token) → 固件 json 解析器(真) → spy
```

链路上唯一非真实的环节是"物理执行"（舵机 PWM/屏幕像素）。

**11 项语义测试全过**，覆盖:
- 表情: mouth.size / 眼睛位移+旋转+粗细 复合指令 → 逐一调用对应 setter
- 动作: speed 模式(moveWithSpeed)、默认弹簧(move)、自定义弹簧参数(spring)、
  360° rotate 模式、以及固件规则"rotate 优先于 angle"
- 防御: 坏 JSON / 错误类型(字符串角度) / 无关键名 → **零动作**（不会乱动）
- RGB 灯: 颜色+呼吸时长解析正确

**抓到的真 bug**: 固件 `update_feature()` 要求 `x` 和 `y` **同时**为 int 才调 setPosition —
body-client 只发 `{"leftEye":{"y":-3}}` 时会被固件静默忽略。已修：编码器自动补全缺失轴为 0，
加了 2 个回归测试（body-client 现 18/18）。**这正是模拟验证的价值——真机上这会表现为
"表情指令偶尔没反应"的玄学问题。**

**关于屏幕表情的说明**: WS 0x03 通道控制的是官方固件的"五官参数体系"
（位置/旋转/粗细/大小——眨眼、看向某处、张嘴闭嘴都由此组合），不是切换 happy/sad 表情包。
出厂固件的成套情绪表情走小智语音链路的 emotion 事件（M1-B 的 LLM 回复里已带 emotion 字段）。
两条路都已在咱手里: 语音说话自带表情, 0x03 做精细五官控制（M2 的"thinking 表情"将用组合参数实现）。

**身体的"反应"(传感器回传)**: 设备→云的上行通道 (JPEG 0x02 / Opus 0x01 / 文本 0x07 /
上下线 0x16,0x17) 已在 16 项集成测试覆盖（摄像头开→JPEG 回传→关 全周期）。
IMU/触摸事件在官方 WS 协议里无上行帧型——M3 若需要, 走固件侧 MCP 或自定义帧扩展（咱自己编译固件, 可加）。
