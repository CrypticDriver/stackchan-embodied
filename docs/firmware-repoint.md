# 固件指向调研：到底要不要重刷？(2026-07-10)

**结论：两条链路命运不同。语音链路（xiaozhi）免刷可改；身体链路（StackChan WS）URL 是编译期常量，必须重编译刷机一次。**

依据：源码级核查 `m5stack/StackChan`（固件 v1.4.3 + Go server）与 `78/xiaozhi-esp32` v2.2.4。

## 1. 语音链路（M1-B）：免刷 ✅

OTA URL 的运行时解析顺序（`xiaozhi-esp32/main/ota.cc:46-53`）：

```cpp
std::string Ota::GetCheckVersionUrl() {
    Settings settings("wifi", false);
    std::string url = settings.GetString("ota_url");   // ① NVS 优先
    if (url.empty()) url = CONFIG_OTA_URL;             // ② 编译期默认兜底
    return url;
}
```

- NVS `wifi/ota_url` 的写入口在配网门户组件 `78/esp-wifi-connect`（M5 固件与 xiaozhi 同用 `~3.1.1`，见 `main/idf_component.yml`）：门户网页高级选项提交 JSON `{"ota_url": ...}` → `nvs_set_str(nvs, "ota_url", ...)`（`wifi_configuration_ap.cc:605-608`）。
- OTA 响应里的 `websocket` JSON 段会被整体写入 NVS `websocket` 命名空间（`ota.cc:167-185`），设备随后连这个 WS 地址做语音对话。**即：谁控制 OTA endpoint，谁就控制语音大脑指向。**

**操作路径（不刷机）**：设备进配网模式 → 门户「高级选项」填自建 OTA 地址（xiaozhi-esp32-server 的 `:8003/xiaozhi/ota/`）→ 重启后语音链路整体切到自建服务器。

## 2. 身体链路（M1-A）：必须重刷 ❌

StackChan server 地址在固件里是**纯编译期常量，无任何 NVS/OTA 覆盖机制**（`firmware/main/hal/utils/secret_logic/secret_logic.cpp`）：

```cpp
__attribute__((weak)) std::string get_server_url() {
#ifdef CONFIG_STACKCHAN_SERVER_URL
    return CONFIG_STACKCHAN_SERVER_URL;   // 编译期烧死
#else
    return "http://localhost:3000";
#endif
}
```

调用方（`hal_ws_avatar.cpp:66` 等）全部直接拼 `get_server_url() + "/stackChan/ws?..."`，全程没有查 NVS。OTA 响应解析（xiaozhi 侧）也只写 `websocket`/`mqtt` 段，**不含 stackchan server 字段**。

固件已为自托管留了官方入口：`firmware/CMakeLists.txt:16-21` 自动加载 git-ignored 的 **`sdkconfig.defaults.local`** 覆盖 `CONFIG_STACKCHAN_SERVER_URL` / `CONFIG_OTA_URL`，不动仓库默认值。

## 3. 重刷时的额外发现（比 URL 更重要）

### 3a. 开源固件的鉴权是残缺的 stub —— 必须自己补齐
`secret_logic` 的三个函数都是 `__attribute__((weak))` 弱符号，开源版 `generate_auth_token()` 只返回字面量 `"hi-stack-chan"`。而 Go server 侧（`server/internal/web_socket/web_socket.go:79-104`）要求 Authorization 头是：

```
base64( RSA加密( "mac|<?>|unix_ts" ) )，时间窗 ±10 秒
```

密钥来自 server 配置 `rsa.server.*` / `rsa.client.*`（`server/utility/rsa.go`，config 里默认为空，启动时必须填）。**出厂固件显然带了一份闭源的非弱符号实现 + M5 官方密钥；开源自编译版发 "hi-stack-chan" 会直接 401。**

→ 自托管方案：自己生成 RSA 密钥对，填进自建 Go server 配置；固件侧写一个非弱符号的 `secret_logic` 实现（用自己的 client 公钥加密 `mac|x|ts`）。我们同时控制两端，完全可行，但这是 M1-A 必做项，路线图没写。

### 3b. body-client 伪装 App 的鉴权同理
`GetMac()` 对所有连接（含 `deviceType=App`）统一校验 RSA token，App 还需 `deviceId` query 参数。body-client 用同一套自有密钥签 token 即可。注意 ±10s 时间窗要求 EC2 时钟准（NTP）。

### 3c. 重刷不可逆风险照旧
出厂固件的闭源 secret_logic/密钥刷掉就没了（回官方云需 M5Burner 重刷官方固件）。刷前 `esptool read_flash` 全片备份仍然必要。

## 4. 对 ROADMAP 的修订建议

| 原计划 | 修订 |
|---|---|
| "固件重编译一次: CONFIG_OTA_URL + CONFIG_STACKCHAN_SERVER_URL" | OTA_URL 不必编译进去（配网门户可改），但既然为身体链路必须重刷，两个一起用 `sdkconfig.defaults.local` 烧上更稳（免得门户设置被重置） |
| M1-B 依赖刷机 | **M1-B 可先行**：不刷机、只改配网门户 OTA 地址就能把语音大脑切到自建 xiaozhi-server —— 可作为第一个零风险里程碑先跑通 |
| 鉴权"沿用协议 token 机制" | 明确为：自生成 RSA 密钥对 + 固件补 `secret_logic` 非弱实现 + body-client 签同款 token |
| ASR: faster-whisper | xiaozhi-esp32-server 无此 provider，本地 ASR 用 **FunASR/SenseVoice**（另见核查报告） |

## 5. 建议的新交付顺序

1. **M1-B 先行（零刷机风险）**：EC2 起 xiaozhi-esp32-server → 设备配网门户改 OTA 地址 → 语音大脑即归自建（LLM=OpenClaw、TTS=edge-tts YunxiaNeural、ASR=FunASR）
2. 验证门户「高级选项」确实存在于当前出厂固件（唯一待实机确认点：进配网模式看一眼）
3. **M1-A 再上（一次性刷机）**：生成 RSA 密钥 → 部署 Go server → 编译固件（`sdkconfig.defaults.local` + secret_logic 实现）→ esptool 全片备份 → 刷机
