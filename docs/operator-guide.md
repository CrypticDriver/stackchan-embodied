# 大哥操作手册 — StackChan 切换到自建大脑

**原则：防变砖第一。** 手册分两个阶段，阶段一零风险（不碰固件），阶段二才刷机，且每一步都有回滚。
所有云端服务已在 EC2 上运行并验证，你只需要操作设备。

---

## 阶段一：语音大脑切换（免刷固件，随时可撤销）

出厂固件的语音链路从 OTA 接口读服务器地址，改一个 URL 就能把"小智云"换成"咱自建的狗蛋大脑"。

### 步骤

1. 让 StackChan 进入配网模式（设置里重置 WiFi，或按住配网键 —— 见机身说明）
2. 手机连上它发出的热点（名字形如 `Xiaozhi-XXXX`），浏览器打开配网页面（通常自动弹出，或访问 `192.168.4.1`）
3. 点开 **「高级选项」(Advanced Options)**
4. **OTA 地址**填：

       https://da8daz4hvc7q8.cloudfront.net/xiaozhi/ota/

5. 选家里 2.4G WiFi，保存，设备重启

### 验证

- 对它说唤醒词，随便问一句。若回答自称**狗蛋**、叫你**大哥**（声音是云希男声）→ 切换成功
- 云端看实时日志：`journalctl -u stackchan-xiaozhi -f`（EC2 上）

### 回滚（一分钟）

再进配网模式，把 OTA 地址改回官方：

    https://api.tenclass.net/xiaozhi/ota/

### 若配网页面没有「高级选项」

说明出厂固件版本较老没暴露该字段 → 语音切换也只能走阶段二刷机（刷机后两条链路一起切）。**不要尝试其他野路子。**

---

## 阶段二：身体链路切换（需刷固件一次 —— 谨慎，先备份）

身体控制（表情/转头/摄像头 relay）的服务器地址是编译进固件的，必须刷一次自编译固件。
自编译固件已在 EC2 上构建好：`~/worklog/stackchan/m5stack-StackChan/firmware/build/`（含 SHA256 清单）。

### 2.0 准备

- 一台电脑装 esptool：`pip install esptool`
- USB-C 线连接 StackChan 底座（数据线，不是纯充电线）
- 设备管理器/`ls /dev/tty*` 确认串口（Windows: COMx；Mac: /dev/cu.usbmodem*；Linux: /dev/ttyACM0）

### 2.1 全片备份（必做！这是唯一完整回滚保障）

CoreS3 是 16MB flash：

```bash
esptool --chip esp32s3 --port <串口> --baud 921600 read_flash 0x0 0x1000000 stackchan-factory-backup-$(date +%Y%m%d).bin
```

约 3-5 分钟。**备份文件立刻拷两份**（本地 + 传到 EC2/网盘）。验证大小恰好 16777216 字节。

> 为什么必须备份：出厂固件里 M5 官方的闭源鉴权实现和密钥刷掉就没了。有这份备份，任何时候
> `esptool write_flash 0x0 backup.bin` 就能 100% 回到出厂状态（含官方云、小智绑定能力）。

### 2.2 刷自编译固件

产物已存档在本仓库 `firmware/build-artifacts/`（5 个 bin + flash_args + SHA256SUMS）。
拷到电脑后先 `sha256sum -c SHA256SUMS` 校验，再刷：

```bash
# 偏移来自 build/flash_args（已验证）:
esptool --chip esp32s3 --port <串口> --baud 460800 write_flash \
  --flash_mode dio --flash_size 16MB --flash_freq 80m \
  0x0 bootloader.bin \
  0x8000 partition-table.bin \
  0xd000 ota_data_initial.bin \
  0x20000 stack-chan.bin \
  0xa00000 generated_assets.bin
```

刷完重启，重新配网（WiFi 信息不会保留时需重配）。

### 2.3 验证

1. 设备开机有脸、能配网 → 固件基本 OK
2. EC2 上看 Go server 日志：`journalctl -u stackchan-goserver -f`，应出现设备 WS 连入（MAC 可见）
3. EC2 上跑冒烟脚本驱动真机：
   ```bash
   cd ~/worklog/stackchan/stackchan-embodied/body-client
   STACKCHAN_DEVICE_MAC=<设备MAC> ~/worklog/stackchan/xiaozhi-venv/bin/python examples/wave_hello.py
   ```
   预期：转头 + 屏幕表情变化 + 收到文本消息
4. 语音链路照常（OTA 已编译指向自建，狗蛋应答）

### 2.4 回滚（三层，按顺序尝试）

| 层级 | 场景 | 操作 |
|---|---|---|
| L1 | 固件能启动但行为不对 | `esptool write_flash 0x0 备份.bin` 整片恢复出厂 |
| L2 | 没做备份/备份损坏 | M5Burner 下载官方 StackChan-UserDemo 固件重刷（回官方云，绑定信息可能需重来） |
| L3 | 完全不启动（几乎不可能，写入错误才会） | 按住 BOOT 键上电进下载模式，再走 L1/L2；ESP32-S3 的 ROM bootloader 在掩膜 ROM 里，物理上刷不坏 |

> 定心丸：esptool 刷 ESP32 唯一真正的"变砖"方式是烧错 eFuse——咱们的流程完全不碰 eFuse，
> 最坏情况就是反复重刷 flash，设备本体不会坏。

---

## 云端服务速查（EC2 上）

| 服务 | systemd | 端口 | 日志 |
|---|---|---|---|
| 语音大脑 | `stackchan-xiaozhi` | :8000 WS / :8003 OTA | `journalctl -u stackchan-xiaozhi -f` |
| LLM 网关 | `stackchan-litellm` | 127.0.0.1:4000 | `journalctl -u stackchan-litellm -f` |
| 身体 relay | `stackchan-goserver` | :12800 | `journalctl -u stackchan-goserver -f` |

公网入口（唯一）：`da8daz4hvc7q8.cloudfront.net` → ALB（X-Origin-Verify）→ EC2。
EC2 安全组无公网服务端口；直连 IP 全部超时，属预期。

## 密钥位置（都在 EC2，gitignored）

- `~/worklog/stackchan/.env-litellm` — LiteLLM master key
- `~/worklog/stackchan/.secrets-origin-verify` — CloudFront↔ALB 校验头
- `~/worklog/stackchan/stackchan-go-server/*.pem` — 自建 RSA 密钥对（固件里只嵌了公钥）
