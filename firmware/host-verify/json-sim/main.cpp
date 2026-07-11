// Semantic-layer test: the REAL firmware json_helper.cpp (sha256-identical copy)
// parses payloads produced by the REAL body-client encoders.
// Input : JSON payload on argv[1] (avatar) / argv[2]=mode
// Output: the exact avatar/servo calls the firmware would make.
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "json/json_helper.h"

std::vector<std::string> g_calls;

int main(int argc, char** argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: %s <avatar|motion|neon> <json>\n", argv[0]);
        return 2;
    }
    std::string mode = argv[1];
    const char* json = argv[2];

    stackchan::avatar::Avatar avatar;
    stackchan::motion::Motion motion;
    stackchan::addon::NeonLight left("leftRgb"), right("rightRgb");

    if (mode == "avatar") {
        stackchan::avatar::update_from_json(&avatar, json);
    } else if (mode == "motion") {
        stackchan::motion::update_from_json(&motion, json);
    } else if (mode == "neon") {
        stackchan::addon::update_neon_light_from_json(&left, &right, json);
    } else {
        return 2;
    }

    for (auto& c : g_calls) printf("%s\n", c.c_str());
    return 0;
}
