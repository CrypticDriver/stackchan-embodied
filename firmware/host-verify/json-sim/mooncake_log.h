// Host-test stub for mooncake_log.
#pragma once
#include <cstdio>
#include <string>

namespace mclog {
template <typename... Args>
inline void tagError(const char* tag, const char* fmt, Args&&... args) {
    fprintf(stderr, "E %s: %s\n", tag, fmt);
}
}  // namespace mclog
