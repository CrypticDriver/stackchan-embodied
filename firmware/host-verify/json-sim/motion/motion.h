// Host-test stub: records servo commands issued by the REAL json_helper.cpp.
#pragma once
#include <string>
#include <vector>

extern std::vector<std::string> g_calls;

namespace stackchan::motion {

class Servo {
public:
    explicit Servo(std::string name) : _name(std::move(name)) {}
    void move(int angle) { g_calls.push_back(_name + ".move(" + std::to_string(angle) + ")"); }
    void moveWithSpeed(int angle, int speed) {
        g_calls.push_back(_name + ".moveWithSpeed(" + std::to_string(angle) + "," + std::to_string(speed) + ")");
    }
    void moveWithSpringParams(int angle, float stiffness = 170.0f, float damping = 26.0f) {
        g_calls.push_back(_name + ".spring(" + std::to_string(angle) + "," + std::to_string((int)stiffness) + "," +
                          std::to_string((int)damping) + ")");
    }
    void rotate(int velocity) { g_calls.push_back(_name + ".rotate(" + std::to_string(velocity) + ")"); }

private:
    std::string _name;
};

class Motion {
public:
    Servo& yawServo() { return _yaw; }
    Servo& pitchServo() { return _pitch; }

private:
    Servo _yaw{"yaw"}, _pitch{"pitch"};
};

}  // namespace stackchan::motion
