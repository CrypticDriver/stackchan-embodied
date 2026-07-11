/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 *
 * stackchan-embodied: 在原有 Shake 基础上补 Flip(倒扣) / PickUp(拿起) 检测。
 * 全部只用加速度计三轴 (m/s^2)，正放时 acc_z ≈ +9.8。
 */
#pragma once

#include <cstdint>
#include <cmath>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

class MotionDetector {
public:
    MotionDetector() = default;

    void setShakeThreshold(float threshold) { _shake_threshold = threshold; }

    void update(const float& acc_x, const float& acc_y, const float& acc_z)
    {
        uint32_t now = pdTICKS_TO_MS(xTaskGetTickCount());

        float diff = std::abs(acc_x - _prev_acc_x) + std::abs(acc_y - _prev_acc_y) + std::abs(acc_z - _prev_acc_z);
        _prev_acc_x = acc_x;
        _prev_acc_y = acc_y;
        _prev_acc_z = acc_z;

        // --- Shake: 差分高通, 与重力朝向无关 ---
        if (diff > _shake_threshold) {
            if (now - _last_shake_peak_time > 100) {
                if (now - _last_shake_peak_time < 1000) _shake_count++;
                else _shake_count = 1;
                _last_shake_peak_time = now;
                if (_shake_count >= 3) { _shake_detected = true; _shake_count = 0; }
            }
        }

        // --- Flip: acc_z 稳定翻负 = 倒扣 (持续 400ms 确认, 防翻转过程瞬时误判) ---
        bool z_inverted = acc_z < -5.0f;
        if (z_inverted) {
            if (_flip_since == 0) _flip_since = now;
            else if (!_flip_latched && now - _flip_since > 400) {
                _flip_detected = true;
                _flip_latched  = true;   // 保持倒扣不重复触发
            }
        } else {
            _flip_since   = 0;
            _flip_latched = false;       // 翻回正放解锁
        }

        // --- PickUp: 之前连续静止(纯重力) + 竖直向上突增 ---
        float mag = std::sqrt(acc_x * acc_x + acc_y * acc_y + acc_z * acc_z);
        bool rest_now = std::abs(mag - 9.8f) < 1.2f && diff < 2.0f;
        _rest_frames = rest_now ? _rest_frames + 1 : 0;
        float z_jerk = std::abs(acc_z - _pickup_prev_z);
        _pickup_prev_z = acc_z;
        if (_was_resting && z_jerk > _pickup_jerk_threshold && acc_z > 11.0f) {
            if (!_pickup_ever || now - _last_pickup_time > 2000) {
                _pickup_detected  = true;
                _last_pickup_time = now;
                _pickup_ever      = true;
            }
        }
        _was_resting = _rest_frames >= 3;
    }

    bool isShakeDetected()  { return _consume(_shake_detected); }
    bool isFlipDetected()   { return _consume(_flip_detected); }
    bool isPickUpDetected() { return _consume(_pickup_detected); }

private:
    static bool _consume(bool& flag) { if (flag) { flag = false; return true; } return false; }

    int _shake_count = 0;
    uint32_t _last_shake_peak_time = 0;
    bool _shake_detected = false;
    float _shake_threshold = 4.0f;
    float _prev_acc_x = 0, _prev_acc_y = 0, _prev_acc_z = 0;

    uint32_t _flip_since = 0;
    bool _flip_detected = false;
    bool _flip_latched = false;

    float _pickup_prev_z = 9.8f;
    int _rest_frames = 0;
    bool _was_resting = false;
    uint32_t _last_pickup_time = 0;
    bool _pickup_ever = false;
    bool _pickup_detected = false;
    float _pickup_jerk_threshold = 4.0f;
};
