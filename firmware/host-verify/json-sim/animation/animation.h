// Host-test stub: keyframe structs copied to match firmware animation.h fields.
#pragma once
#include <string>
#include <vector>

namespace uitk {
struct V2i {
    int x = 0, y = 0;
};
}

namespace stackchan::animation {

struct FeatureKeyframe {
    struct {
        int x = 0, y = 0;
    } position;
    int rotation = 0;
    int weight = 0;
    int size = 0;
};

struct ServoKeyframe {
    int angle = 0;
    int speed = 0;
};

struct Keyframe {
    FeatureKeyframe leftEye, rightEye, mouth;
    ServoKeyframe yawServo, pitchServo;
    std::string leftRgbColor, rightRgbColor;
    int durationMs = 0;
};

using KeyframeSequence = std::vector<Keyframe>;

}  // namespace stackchan::animation
