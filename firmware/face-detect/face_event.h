/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 *
 * FaceEventModifier — 本地人脸检测反应 (M3 最小闭环)。
 * 监听 HAL 的 onFaceEvent: 有人凑到镜头前 (Appear) 就"打个招呼" —
 * 短暂 Happy 表情 + 爱心, 到点自动恢复 (不长按 modifyLock, 免得冻住待机动画)。
 *
 * 这一版只验证"摄像头→esp-dl 推理→表情"整条链路; 后续再做"看向人脸/主动问好"。
 */
#pragma once
#include "../modifiable.h"
#include "../avatar/decorators/decorators.h"
#include <hal/hal.h>
#include <lvgl.h>
#include <cstdint>

namespace stackchan {

class FaceEventModifier : public Modifier {
public:
    explicit FaceEventModifier(uint32_t greetDurationMs = 2500) : _greet_duration_ms(greetDurationMs)
    {
        _signal_connection = GetHAL().onFaceEvent.connect([this](FaceEvent event) {
            if (event == FaceEvent::Appear) {
                _event_appear = true;
            } else if (event == FaceEvent::Gone) {
                _event_gone = true;
            }
        });
    }

    ~FaceEventModifier()
    {
        GetHAL().onFaceEvent.disconnect(_signal_connection);
    }

    void _update(Modifiable& stackchan) override
    {
        if (!stackchan.hasAvatar()) {
            return;
        }
        uint32_t now = GetHAL().millis();

        if (_event_appear) {
            _event_appear = false;
            _event_gone   = false;
            start_greet(stackchan, now);
        }
        _event_gone = false;  // Gone 暂不特殊反应, 清标志即可

        if (_is_greeting && now >= _restore_at) {
            restore_state(stackchan);
        }
    }

private:
    void start_greet(Modifiable& stackchan, uint32_t now)
    {
        auto& avatar = stackchan.avatar();
        if (avatar.isModifyLocked()) {
            return;  // 有更强的反应(晃动/倒扣)正在进行, 让路
        }
        if (!_is_greeting) {
            _is_greeting = true;
        }
        avatar.setEmotion(avatar::Emotion::Happy);
        avatar.removeDecorator(_heart_decorator_id);
        _heart_decorator_id = avatar.addDecorator(
            std::make_unique<avatar::HeartDecorator>(lv_screen_active(), _greet_duration_ms, 500));
        _restore_at = now + _greet_duration_ms;
    }

    void restore_state(Modifiable& stackchan)
    {
        if (!_is_greeting) {
            return;
        }
        auto& avatar = stackchan.avatar();
        avatar.removeDecorator(_heart_decorator_id);
        _heart_decorator_id = -1;
        avatar.setEmotion(avatar::Emotion::Neutral);
        _is_greeting = false;
    }

    int _signal_connection;
    volatile bool _event_appear = false;
    volatile bool _event_gone   = false;

    bool _is_greeting          = false;
    uint32_t _restore_at       = 0;
    uint32_t _greet_duration_ms;
    int _heart_decorator_id    = -1;
};

}  // namespace stackchan
