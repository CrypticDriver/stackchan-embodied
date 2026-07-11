// Host-test stub for RGB LED strip control.
#pragma once
#include <string>
#include <vector>

extern std::vector<std::string> g_calls;

namespace stackchan::addon {

class NeonLight {
public:
    explicit NeonLight(std::string name) : _name(std::move(name)) {}
    void setDuration(float d) { g_calls.push_back(_name + ".duration(" + std::to_string((int)(d * 1000)) + "ms)"); }
    void setColor(const std::string& c) { g_calls.push_back(_name + ".color(" + c + ")"); }

private:
    std::string _name;
};

}  // namespace stackchan::addon
