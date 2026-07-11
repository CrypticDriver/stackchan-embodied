/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 */
#pragma once
#include "../modifiable.h"
#include <hal/hal.h>
#include <cstdint>

namespace stackchan {

/**
 * @brief
 *
 */
class ImuEventModifier : public Modifier {
public:
    ImuEventModifier(uint32_t reactionDurationMs = 4000) : _reaction_duration_ms(reactionDurationMs)
    {
        _signal_connection = GetHAL().onImuMotionEvent.connect([this](ImuMotionEvent event) {
            if (event == ImuMotionEvent::Shake) {
                _event_shake = true;
            } else if (event == ImuMotionEvent::Flip) {
                _event_flip = true;
            } else if (event == ImuMotionEvent::PickUp) {
                _event_pickup = true;
            }
        });
    }

    ~ImuEventModifier()
    {
        GetHAL().onImuMotionEvent.disconnect(_signal_connection);
    }

    void _update(Modifiable& stackchan) override
    {
        uint32_t now = GetHAL().millis();

        // 收到晃动事件
        if (_event_shake) {
            _event_shake = false;
            handle_shake_start(stackchan, now);
        }
        // 倒扣: 委屈抗议 (Angry+Sweat 表情, 短促反应)
        if (_event_flip) {
            _event_flip = false;
            handle_flip(stackchan, now);
        }
        // 拿起: 好奇惊喜 (Happy+Heart, 眼睛张大)
        if (_event_pickup) {
            _event_pickup = false;
            handle_pickup(stackchan, now);
        }

        // 如果处于晃动反应状态
        if (_is_reacting) {
            if (now >= _next_toggle_tick) {
                _next_toggle_tick = now + 600;

                _toggle_phase      = !_toggle_phase;
                int mouth_rotation = _toggle_phase ? -25 : 25;

                auto& avatar = stackchan.avatar();
                avatar.mouth().setRotation(mouth_rotation);
                avatar.mouth().setWeight(65);
            }

            //  Lock motion modify and move home
            auto& motion = stackchan.motion();
            if (!motion.isModifyLocked()) {
                motion.setModifyLock(true);
                motion.goHome(300);
            }

            // 检查是否结束反应
            if (now >= _restore_at) {
                restore_state(stackchan);
            }
        }
    }

private:
    void handle_shake_start(Modifiable& stackchan, uint32_t now)
    {
        if (!_is_reacting) {
            // 首次触发时，记录状态以便恢复
            _is_reacting = true;

            auto& avatar = stackchan.avatar();

            avatar.setModifyLock(true);
            avatar.leftEye().setVisible(false);
            avatar.rightEye().setVisible(false);

            stackchan.avatar().removeDecorator(_dizzy_decorator_id);
            stackchan.avatar().removeDecorator(_shy_decorator_id);
            _dizzy_decorator_id =
                stackchan.avatar().addDecorator(std::make_unique<avatar::DizzyDecorator>(lv_screen_active(), 0, 300));
            _shy_decorator_id =
                stackchan.avatar().addDecorator(std::make_unique<avatar::ShyDecorator>(lv_screen_active(), 0));
        }

        // 刷新恢复时间和切换时间
        _restore_at = now + _reaction_duration_ms;
        if (_next_toggle_tick <= now) {
            _next_toggle_tick = now;  // 立即触发第一次嘴巴动作
        }
    }

    // 倒扣反应: 生气+冒汗, 委屈地"抗议"
    void handle_flip(Modifiable& stackchan, uint32_t now)
    {
        auto& avatar = stackchan.avatar();
        if (!_is_reacting) {
            _is_reacting = true;
            avatar.setModifyLock(true);
        }
        avatar.setEmotion(avatar::Emotion::Angry);
        avatar.removeDecorator(_dizzy_decorator_id);
        avatar.removeDecorator(_shy_decorator_id);
        _dizzy_decorator_id = avatar.addDecorator(
            std::make_unique<avatar::SweatDecorator>(lv_screen_active(), 0));
        _restore_at       = now + _reaction_duration_ms;
        _next_toggle_tick = now + 999999;  // 倒扣不做嘴巴摆动(那是晃动的)
    }

    // 拿起反应: 惊喜好奇, 眼睛张大 + 爱心
    void handle_pickup(Modifiable& stackchan, uint32_t now)
    {
        auto& avatar = stackchan.avatar();
        if (!_is_reacting) {
            _is_reacting = true;
            avatar.setModifyLock(true);
        }
        avatar.setEmotion(avatar::Emotion::Happy);
        avatar.leftEye().setSize(60);    // 瞳孔放大 = 好奇
        avatar.rightEye().setSize(60);
        avatar.removeDecorator(_shy_decorator_id);
        _shy_decorator_id = avatar.addDecorator(
            std::make_unique<avatar::HeartDecorator>(lv_screen_active(), _reaction_duration_ms, 500));
        _restore_at       = now + _reaction_duration_ms;
        _next_toggle_tick = now + 999999;
    }

    void restore_state(Modifiable& stackchan)
    {
        if (!_is_reacting) {
            return;
        }

        auto& avatar = stackchan.avatar();
        avatar.setModifyLock(false);
        avatar.leftEye().setVisible(true);
        avatar.rightEye().setVisible(true);
        avatar.leftEye().setSize(0);
        avatar.rightEye().setSize(0);
        avatar.mouth().setWeight(0);
        avatar.mouth().setRotation(0);
        avatar.setEmotion(avatar::Emotion::Neutral);

        stackchan.avatar().removeDecorator(_dizzy_decorator_id);
        stackchan.avatar().removeDecorator(_shy_decorator_id);
        _dizzy_decorator_id = -1;
        _shy_decorator_id   = -1;

        auto& motion = stackchan.motion();
        motion.setModifyLock(false);

        _is_reacting = false;
    }

    // 信号相关
    int _signal_connection;
    volatile bool _event_shake = false;
    volatile bool _event_flip = false;
    volatile bool _event_pickup = false;

    // 状态控制
    bool _is_reacting          = false;
    bool _toggle_phase         = false;
    uint32_t _restore_at       = 0;
    uint32_t _next_toggle_tick = 0;
    uint32_t _reaction_duration_ms;

    int _dizzy_decorator_id = -1;
    int _shy_decorator_id   = -1;
};

}  // namespace stackchan
