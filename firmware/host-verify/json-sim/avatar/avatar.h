// Host-test stub: records every mutation the REAL json_helper.cpp makes.
// Interfaces mirror firmware avatar (Feature: setPosition/setRotation/setWeight/setSize).
#pragma once
#include <string>
#include <vector>

namespace uitk {
struct Vector2i {
    int x = 0, y = 0;
};
}  // namespace uitk

extern std::vector<std::string> g_calls;

namespace stackchan::avatar {

class Feature {
public:
    explicit Feature(std::string name) : _name(std::move(name)) {}
    void setPosition(uitk::Vector2i p) { g_calls.push_back(_name + ".pos(" + std::to_string(p.x) + "," + std::to_string(p.y) + ")"); }
    void setRotation(int r) { g_calls.push_back(_name + ".rot(" + std::to_string(r) + ")"); }
    void setWeight(int w) { g_calls.push_back(_name + ".weight(" + std::to_string(w) + ")"); }
    void setSize(int s) { g_calls.push_back(_name + ".size(" + std::to_string(s) + ")"); }

private:
    std::string _name;
};

class Avatar {
public:
    Feature& leftEye() { return _l; }
    Feature& rightEye() { return _r; }
    Feature& mouth() { return _m; }

private:
    Feature _l{"leftEye"}, _r{"rightEye"}, _m{"mouth"};
};

}  // namespace stackchan::avatar
