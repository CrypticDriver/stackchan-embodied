// Host-side harness: compiles the REAL firmware secret_logic_selfhost.cpp
// (unmodified, via #include below) against host mbedtls, prints a token.
// esp_* functions and headers are shimmed; the crypto path is byte-identical.

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <random>

// ---- shims for esp headers pulled in by the firmware source ----
#define ESP_LOGE(tag, fmt, ...) fprintf(stderr, "E %s: " fmt "\n", tag, ##__VA_ARGS__)
enum { ESP_MAC_WIFI_STA = 0 };
static const char* g_mac_env = nullptr;
static int esp_read_mac(uint8_t* mac, int) {
    unsigned b[6] = {0xca, 0xfe, 0x00, 0x11, 0x22, 0x33};
    if (g_mac_env) sscanf(g_mac_env, "%02x%02x%02x%02x%02x%02x", &b[0], &b[1], &b[2], &b[3], &b[4], &b[5]);
    for (int i = 0; i < 6; i++) mac[i] = (uint8_t)b[i];
    return 0;
}
static uint32_t esp_random() {
    static std::random_device rd;
    return rd();
}
// Kconfig shim (matches sdkconfig.defaults.local)
#define CONFIG_STACKCHAN_SERVER_URL "https://da8daz4hvc7q8.cloudfront.net"

// Firmware headers replaced by the shims above:
#define SECRET_LOGIC_HOST_TEST 1
#include "secret_logic_selfhost_body.inc"   // the firmware file, minus its #includes

int main(int argc, char** argv) {
    if (argc > 1) g_mac_env = argv[1];
    printf("server_url=%s\n", secret_logic::get_server_url().c_str());
    std::string token = secret_logic::generate_auth_token();
    if (token.empty()) {
        fprintf(stderr, "TOKEN GENERATION FAILED\n");
        return 1;
    }
    printf("token=%s\n", token.c_str());
    return 0;
}
