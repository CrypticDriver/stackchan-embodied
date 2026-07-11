/*
 * IdleLifeModifier — 待机"生命感"动画（为 goudan skin 设计，语义参数对任意皮肤生效）。
 *
 * 三个通道:
 *   1. 眨眼: 4.2-5.8s 随机间隔, 闭眼 140ms（快速自然）, 偶尔连眨两下
 *   2. 瞳孔漂移: 2.5-6s 随机小幅看向别处, 12% 概率回正中("看镜头")
 *   3. 嘴部微动: 低频改变微笑弧度, 像在轻轻呼吸/哼歌
 *
 * WS 避让: 外部(狗蛋 body-client / 小智情绪)控制表情时调 suppress(ms),
 * 待机动画立刻停手并在窗口结束后柔和接管——避免与远程控制打架。
 *
 * SPDX-License-Identifier: MIT
 */
#pragma once
#include "../modifiable.h"
#include "../utils/random.h"
#include <hal/hal.h>
#include <cstdint>

namespace stackchan {

class IdleLifeModifier : public Modifier {
public:
    explicit IdleLifeModifier(bool enableBlink = true) : _enable_blink(enableBlink)
    {
        uint32_t now    = GetHAL().millis();
        _next_blink     = now + 1800;
        _next_drift     = now + 3000;
        _next_mouth     = now + 5000;
        _suppress_until = 0;
    }

    /// 外部控制到来时调用: 未来 ms 毫秒内待机动画完全静默
    void suppress(uint32_t ms)
    {
        uint32_t until = GetHAL().millis() + ms;
        if (until > _suppress_until) {
            _suppress_until = until;
        }
        // 若正闭着眼, 立即恢复, 别让远程表情叠在闭眼帧上
        _blink_state = BlinkState::OPEN;
        _was_suppressed = true;
    }

    void _update(Modifiable& stackchan) override
    {
        if (!stackchan.hasAvatar() || stackchan.avatar().isModifyLocked()) {
            return;
        }

        uint32_t now = GetHAL().millis();
        if (now < _suppress_until) {
            return;
        }

        auto& avatar = stackchan.avatar();

        // 避让窗口刚结束: 重新以当前(远程设过的)状态为基线, 柔和接管
        if (_was_suppressed) {
            _was_suppressed  = false;
            _base_weight_l   = avatar.leftEye().getWeight();
            _base_weight_r   = avatar.rightEye().getWeight();
            _next_blink      = now + 1200;
            _next_drift      = now + 2500;
            _next_mouth      = now + 4000;
        }

        // ---- 1. 眨眼 ----
        if (_enable_blink && now >= _next_blink) {
            if (_blink_state == BlinkState::OPEN) {
                _base_weight_l = avatar.leftEye().getWeight();
                _base_weight_r = avatar.rightEye().getWeight();
                avatar.leftEye().setWeight(6);
                avatar.rightEye().setWeight(6);
                _blink_state = BlinkState::CLOSED;
                _next_blink  = now + 140;
            } else {
                avatar.leftEye().setWeight(_base_weight_l);
                avatar.rightEye().setWeight(_base_weight_r);
                _blink_state = BlinkState::OPEN;
                // 18% 概率 400ms 后连眨第二下
                if (Random::getInstance().getInt(0, 100) < 18) {
                    _next_blink = now + 400;
                } else {
                    _next_blink = now + Random::getInstance().getInt(4200, 5800);
                }
            }
        }

        // 闭眼期间不做其他动作
        if (_blink_state == BlinkState::CLOSED) {
            return;
        }

        // ---- 2. 瞳孔漂移 ----
        if (now >= _next_drift) {
            if (Random::getInstance().getInt(0, 100) < 12) {
                // 回正中, "看镜头"
                avatar.leftEye().setPosition({0, 0});
                avatar.rightEye().setPosition({0, 0});
            } else {
                int dx = Random::getInstance().getInt(-26, 26);
                int dy = Random::getInstance().getInt(-16, 12);
                avatar.leftEye().setPosition({dx, dy});
                avatar.rightEye().setPosition({dx, dy});
            }
            _next_drift = now + Random::getInstance().getInt(2500, 6000);
        }

        // ---- 3. 嘴部微动 (微笑弧度轻微起伏) ----
        if (now >= _next_mouth) {
            int w = Random::getInstance().getInt(12, 26);
            avatar.mouth().setWeight(w);
            _next_mouth = now + Random::getInstance().getInt(6000, 14000);
        }
    }

private:
    enum class BlinkState { OPEN, CLOSED };

    BlinkState _blink_state = BlinkState::OPEN;
    uint32_t _next_blink    = 0;
    uint32_t _next_drift    = 0;
    uint32_t _next_mouth    = 0;
    uint32_t _suppress_until = 0;
    bool _was_suppressed    = false;
    bool _enable_blink      = true;
    int _base_weight_l      = 100;
    int _base_weight_r      = 100;
};

}  // namespace stackchan
