/*
 * secret_logic 自托管实现（非弱符号，覆盖 secret_logic.cpp 里的 weak stub）。
 *
 * 与自建 Go server 的鉴权约定 (server/internal/web_socket/web_socket.go GetMac):
 *   Authorization = base64( RSA-OAEP-SHA256( server_pub, "mac|nonce|unix_ts" ) )
 *   - mac: 12 位小写 hex（无冒号）
 *   - 时间窗 ±10s → 设备必须先完成 SNTP 校时再连 WS
 *
 * 构建方式: 把本文件放进 firmware/main/hal/utils/secret_logic/ 一同编译即可，
 * 链接器会用这里的强符号取代同名 weak 符号。公钥是自建 server 的
 * rsa.server.public（不是密钥，泄露无害）。
 */
#include "secret_logic.h"
#include <sdkconfig.h>

#include <cstdio>
#include <cstring>
#include <ctime>
#include <string>

#include <esp_log.h>
#include <esp_mac.h>
#include <esp_random.h>
#include <mbedtls/base64.h>
#include <mbedtls/ctr_drbg.h>
#include <mbedtls/entropy.h>
#include <mbedtls/pk.h>
#include <mbedtls/rsa.h>

static const char* TAG = "secret_logic_selfhost";

// 自建 StackChan Go server 的 RSA server 公钥 (PEM)
static const char SERVER_PUBLIC_KEY_PEM[] =
    "-----BEGIN PUBLIC KEY-----\n"
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA5pgIjw3eCHFuwZMaOZD9\n"
    "YWfAyyOBCaJ78l5BtEszqMBpy8NhrBJBT6R70YXBZb3Gnihc0//n8BFuZyHbNqrJ\n"
    "TFeqHYIOxDPeNSlOMHm/icCkeBVzKqZauhSqE9SYzsXt0d0Yx65OFpoVX+ziap/k\n"
    "gX0gbSJR9eCDA5uSGZKcFHv43+klPJHJeEaHWMqqi0USc21alPGMv0Pftj7e/X6E\n"
    "70nQ7OoogyA6p2x4UXzypiFaPZwDGERo9cwwPDHo2BsKiHStqJdGk4J5RutFNNIv\n"
    "wEnaDeOjxqIsIeZpztQGVlB3CieAxUKwNuwhqMxSlMWZ2ZWS5gQBDoN4xiCgVr9I\n"
    "2wIDAQAB\n"
    "-----END PUBLIC KEY-----\n";

namespace secret_logic {

std::string get_server_url()
{
#ifdef CONFIG_STACKCHAN_SERVER_URL
    return CONFIG_STACKCHAN_SERVER_URL;
#else
    return "http://localhost:3000";
#endif
}

static std::string mac_12hex()
{
    uint8_t mac[6] = {0};
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    char buf[13];
    snprintf(buf, sizeof(buf), "%02x%02x%02x%02x%02x%02x", mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    return buf;
}

static std::string rsa_oaep_b64(const std::string& plain)
{
    mbedtls_pk_context pk;
    mbedtls_entropy_context entropy;
    mbedtls_ctr_drbg_context ctr_drbg;
    mbedtls_pk_init(&pk);
    mbedtls_entropy_init(&entropy);
    mbedtls_ctr_drbg_init(&ctr_drbg);

    std::string out;
    unsigned char cipher[256];  // RSA-2048
    size_t cipher_len = 0;

    do {
        const char* pers = "stackchan_selfhost";
        if (mbedtls_ctr_drbg_seed(&ctr_drbg, mbedtls_entropy_func, &entropy, (const unsigned char*)pers,
                                  strlen(pers)) != 0) {
            ESP_LOGE(TAG, "drbg seed failed");
            break;
        }
        if (mbedtls_pk_parse_public_key(&pk, (const unsigned char*)SERVER_PUBLIC_KEY_PEM,
                                        sizeof(SERVER_PUBLIC_KEY_PEM)) != 0) {
            ESP_LOGE(TAG, "public key parse failed");
            break;
        }
        mbedtls_rsa_context* rsa = mbedtls_pk_rsa(pk);
        if (mbedtls_rsa_set_padding(rsa, MBEDTLS_RSA_PKCS_V21, MBEDTLS_MD_SHA256) != 0) {
            ESP_LOGE(TAG, "set OAEP padding failed");
            break;
        }
        if (mbedtls_rsa_rsaes_oaep_encrypt(rsa, mbedtls_ctr_drbg_random, &ctr_drbg, nullptr, 0,
                                           plain.size(), (const unsigned char*)plain.data(), cipher) != 0) {
            ESP_LOGE(TAG, "oaep encrypt failed");
            break;
        }
        cipher_len = mbedtls_rsa_get_len(rsa);

        size_t b64_len = 0;
        unsigned char b64[512];
        if (mbedtls_base64_encode(b64, sizeof(b64), &b64_len, cipher, cipher_len) != 0) {
            ESP_LOGE(TAG, "base64 failed");
            break;
        }
        out.assign((char*)b64, b64_len);
    } while (false);

    mbedtls_ctr_drbg_free(&ctr_drbg);
    mbedtls_entropy_free(&entropy);
    mbedtls_pk_free(&pk);
    return out;
}

std::string generate_auth_token()
{
    // "mac|nonce|ts"；server 取 parts[0]=mac, parts[2]=ts（±10s 窗口，需 SNTP 已同步）
    char plain[64];
    snprintf(plain, sizeof(plain), "%s|%08lx|%lld", mac_12hex().c_str(), (unsigned long)esp_random(),
             (long long)time(nullptr));
    std::string token = rsa_oaep_b64(plain);
    if (token.empty()) {
        ESP_LOGE(TAG, "token generation failed, WS auth will 401");
    }
    return token;
}

std::string generate_handshake_token(std::string_view data)
{
    // BLE 配网握手回执：自托管场景没有校验方，返回与 auth 同构的 token 即可
    (void)data;
    return generate_auth_token();
}

}  // namespace secret_logic
