# firmware/ — 自编译固件 (M1-A)

## 产物 (build-artifacts/)

从 `m5stack/StackChan` `firmware/` (v1.4.3, ESP-IDF v5.5.4, target esp32s3) 构建，含两处自托管修改：

1. **`sdkconfig.defaults.local`** — CONFIG_STACKCHAN_SERVER_URL / CONFIG_OTA_URL 指向
   `https://da8daz4hvc7q8.cloudfront.net`（CloudFront→ALB→EC2，设备零直连）
2. **`selfhost_patch/secret_logic_selfhost.cpp`** — 非弱符号实现，替代开源 stub：
   mbedtls RSA-OAEP-SHA256 用自建 server 公钥加密 `mac|nonce|ts` 生成 Authorization token
   （与 Go server GetMac() 校验逻辑精确配对，回环测试已验证同构 Python 实现可通过鉴权）

## 复现构建

```bash
cd m5stack-StackChan/firmware
python3 fetch_repos.py                       # 拉 xiaozhi-esp32 v2.2.4 + patch 等依赖
cp <本目录>/sdkconfig.defaults.local .
cp <本目录>/selfhost_patch/secret_logic_selfhost.cpp main/hal/utils/secret_logic/
source ~/esp/esp-idf/export.sh
idf.py set-target esp32s3 && idf.py build
```

⚠️ 尚未烧录到任何设备。烧录步骤与回滚方案见 docs/operator-guide.md（先全片备份！）。

## 已知待实机验证项

- 出厂固件的 NVS 里若存有 xiaozhi ota_url，可能覆盖编译期 CONFIG_OTA_URL（优先级 NVS > Kconfig）
  → 刷机后若语音链路还连旧服务器，进配网门户高级选项改一次即可
- WS 心跳/断线重连行为在广域网(250ms RTT)下未实测
