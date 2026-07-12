/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 *
 * FaceEventModifier — 本地人脸检测反应 (M3 第二步: 看向人脸 + 主动问好)。
 * 监听 HAL 的 onFaceEvent:
 *   Appear — 有人凑到镜头前: 播一句本地问候音(OGG_WELCOME) + Happy + 爱心,
 *            带冷却(默认 20s), 免得人一晃就反复喊。
 *   Track  — 持续看到人脸: 让果冻眼瞳孔看向人脸方向 (归一化 x/y → setPosition)。
 *            仅在待机(未被更强反应 modifyLock、且不在问好表情期)时生效, 平滑逼近。
 *   Gone   — 人离开: 眼神回正中, 允许待机 saccade 接管。
 *
 * 注册顺序在 IdleLifeModifier 之后 → 跟随时每帧覆盖待机 saccade 的眼位。
 */
#pragma once
#include "../modifiable.h"
#include "../avatar/decorators/decorators.h"
#include "../utils/random.h"
#include <hal/hal.h>
#include <hal/board/hal_bridge.h>
#include <assets/assets.h>
#include <lvgl.h>
#include <cstdint>

namespace stackchan {

class FaceEventModifier : public Modifier {
public:
    explicit FaceEventModifier(uint32_t greetDurationMs = 2500, uint32_t greetCooldownMs = 60000)
        : _greet_duration_ms(greetDurationMs), _greet_cooldown_ms(greetCooldownMs)
    {
        _signal_connection = GetHAL().onFaceEvent.connect([this](FaceEvent event) {
            switch (event.type) {
                case FaceEventType::Appear:
                    _event_appear = true;
                    _face_x = event.x; _face_y = event.y; _face_present = true;
                    break;
                case FaceEventType::Track:
                    _face_x = event.x; _face_y = event.y; _face_present = true;
                    break;
                case FaceEventType::Gone:
                    _face_present = false;
                    break;
                default:
                    break;
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

        // ---- 问好 (Appear, 带冷却) ----
        if (_event_appear) {
            _event_appear = false;
            if (now - _last_greet_at >= _greet_cooldown_ms || _last_greet_at == 0) {
                start_greet(stackchan, now);
                _last_greet_at = now;
            }
        }

        if (_is_greeting) {
            // 问好表情期间眼睛跟着 Happy 走, 不做跟随; 到点恢复
            if (now >= _restore_at) {
                restore_state(stackchan);
            }
            return;
        }

        // ---- 看向人脸 (Track) ----
        auto& avatar = stackchan.avatar();
        if (avatar.isModifyLocked()) {
            return;  // 晃动/倒扣等更强反应进行中, 让路
        }
        if (_face_present) {
            // 平滑逼近目标眼位 (每帧走 1/3), 避免瞳孔跳动
            _eye_x += (_face_x - _eye_x) / 3;
            _eye_y += (_face_y - _eye_y) / 3;
            avatar.leftEye().setPosition({_eye_x, _eye_y});
            avatar.rightEye().setPosition({_eye_x, _eye_y});
        }
        // 无人脸: 不动眼睛, 交回 IdleLifeModifier 的待机 saccade (它在本 modifier 之前跑)
    }

private:
    void start_greet(Modifiable& stackchan, uint32_t now)
    {
        auto& avatar = stackchan.avatar();
        if (avatar.isModifyLocked()) {
            return;
        }
        _is_greeting = true;
        avatar.setEmotion(avatar::Emotion::Happy);
        avatar.removeDecorator(_heart_decorator_id);
        _heart_decorator_id = avatar.addDecorator(
            std::make_unique<avatar::HeartDecorator>(lv_screen_active(), _greet_duration_ms, 500));
        // 本地问候音兜底: 云希声随机一句中文问候, 秒响、不依赖大脑, 保证一定有反应
        int idx = Random::getInstance().getInt(0, OGG_GREETS_COUNT - 1);
        hal_bridge::app_play_sound(OGG_GREETS[idx]);
        // 大脑加料: 同时让设备主动发起一轮对话, 大脑生成一句更应景的问候跟上
        // (待机时才触发; 大脑抽风也无妨, 上面本地音已兜底不会冷场)
        hal_bridge::trigger_face_greeting(
            "(有人靠近了，用一句话热情自然地跟大哥打个招呼，别太长)");
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
    volatile bool _face_present = false;
    volatile int  _face_x = 0;
    volatile int  _face_y = 0;

    int _eye_x = 0;
    int _eye_y = 0;
    bool _is_greeting          = false;
    uint32_t _restore_at       = 0;
    uint32_t _last_greet_at    = 0;
    uint32_t _greet_duration_ms;
    uint32_t _greet_cooldown_ms;
    int _heart_decorator_id    = -1;
};

}  // namespace stackchan
