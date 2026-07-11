# Quickstart：从零到桌上的狗蛋

三步：①云端部署大脑与语音栈 ②刷固件 ③配网。全程约 1 小时，其中刷固件有完整的备份/回滚保障。

## 前置

- 一台 **M5Stack StackChan**（CoreS3，ESP32-S3）
- 一台云主机（本项目用 AWS EC2；语音栈 CPU 版 torch 即可，建议 ≥8G 内存）
- 一个 **OpenClaw** 部署，里面建好一个给机器人用的 agent（本项目叫 `xiaogoudan`）
- 一个 Mac/PC 用来刷固件

---

## 第一步：云端（大脑 + 语音栈）

```bash
git clone https://github.com/CrypticDriver/stackchan-embodied
cd stackchan-embodied
cp deploy/env.example .env-stack        # 填入你的密钥/端点 (见文件内注释)
./scripts/deploy.sh                     # 幂等: 建 venv、装依赖、下模型、装 systemd、起服务
./scripts/health-check.sh               # 应全绿
```

`deploy.sh` 会部署：
- **xiaozhi-server**（语音栈）
- **brain-router**（异步总线，指向你的 OpenClaw agent）
- **LiteLLM 辅脑**（视觉/记忆/兜底）

然后配公网入口（CloudFront → ALB，注入 `X-Origin-Verify`）——脚本会打印需要在 AWS 控制台/CLI
建的资源清单（ALB 目标组、CloudFront origin），或参考 [deploy/uswest/README.md](../deploy/uswest/README.md)
的实际配置照抄。

拿到 CloudFront 域名后，语音栈的 OTA 接口会把它作为 wss 地址下发给设备。

## 第二步：刷固件（先备份！）

固件产物已编译好在 [`firmware/build-artifacts/`](../firmware/build-artifacts/)（含 goudan 皮肤、
待机动画、唤醒词）。**唯一需要注意的是把固件里的服务器地址改成你自己的 CloudFront 域名**——
见 [firmware/README.md](../firmware/README.md) 用 `sdkconfig.defaults.local` 重编译，或直接改 assets。

Mac 完整刷机步骤（含 esptool 安装、全片备份、三层回滚）：
**[docs/flash-guide.html](flash-guide.html)** — 照着一步步敲即可。

⚠️ **务必先全片备份**：`esptool read_flash 0x0 0x1000000 backup.bin`。有它，任何时候能 100% 回出厂。
ESP32-S3 的流程不碰 eFuse，物理上刷不成砖。

## 第三步：配网

设备进配网模式 → 手机连它的热点 → 选家里 **2.4G** WiFi。若配网页有「高级选项/OTA 地址」，
填你的 `https://<你的域名>/xiaozhi/ota/`。

## 验证

1. 开机有**果冻大眼脸**、待机会眨眼 → 皮肤+动画 OK
2. 说唤醒词（默认「嘿狗蛋」），问一句 → 它用 agent 大脑回答 → 全链路通
3. 云端 `./scripts/health-check.sh` 或看 [控制台](https://da8daz4hvc7q8.cloudfront.net/console/)

## 给狗蛋加能力

大脑侧插一个"关注点"就能让它主动找你（监工/提醒/打招呼都是这么做的）。
模式和示例见 [capabilities/README.md](../capabilities/)。核心：**加能力只动大脑侧，身体侧零改动。**

## 出问题？

- 刷机/回滚：[docs/operator-guide.md](operator-guide.md)
- 固件行为/踩坑：[docs/firmware-verification.md](firmware-verification.md)、[docs/firmware-repoint.md](firmware-repoint.md)
- 架构/数据流：[docs/ARCHITECTURE.md](ARCHITECTURE.md)
