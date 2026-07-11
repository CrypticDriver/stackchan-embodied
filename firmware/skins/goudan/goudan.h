/*
 * Goudan skin — "果冻高光眼" (jelly-highlight eyes)
 * 大圆眼 + 高光缺口 + 弧线嘴。参数语义与 default 皮肤一致
 * (x/y ±100, weight 0-100 眼睑开合, rotation 0.1°, size ±100)，
 * 因此 0x03 协议、body-client 与表情预设库无需任何改动。
 *
 * SPDX-License-Identifier: MIT
 */
#pragma once
#include "../../avatar/avatar.h"
#include "../../avatar/elements/feature.h"
#include "../default/default.h"  // reuse DefaultSpeechBubble
#include <lvgl.h>
#include <smooth_lvgl.hpp>
#include <memory>

namespace stackchan::avatar {

class GoudanAvatar : public Avatar {
public:
    lv_color_t primaryColor   = lv_color_white();
    lv_color_t secondaryColor = lv_color_black();

    void init(lv_obj_t* parent, const lv_font_t* font = &lv_font_montserrat_16);
    uitk::lvgl_cpp::Container* getPanel() const;

private:
    std::unique_ptr<uitk::lvgl_cpp::Container> _pannel;
};

class GoudanEyes : public Feature {
public:
    GoudanEyes(lv_obj_t* parent, lv_color_t primaryColor, lv_color_t secondaryColor, bool isLeftEye);
    ~GoudanEyes();

    void setPosition(const uitk::Vector2i& position) override;
    void setWeight(int weight) override;
    void setRotation(int rotation) override;
    void setEmotion(const Emotion& emotion) override;
    void setVisible(bool visible) override;
    void setSize(int size) override;

private:
    void relayout();

    bool _is_left_eye = false;
    int _eye_diameter = 0;

    std::unique_ptr<uitk::lvgl_cpp::Container> _container;
    std::unique_ptr<uitk::lvgl_cpp::Container> _eye;
    std::unique_ptr<uitk::lvgl_cpp::Container> _highlight;
    std::unique_ptr<uitk::lvgl_cpp::Container> _eyelid;
};

class GoudanMouth : public Feature {
public:
    GoudanMouth(lv_obj_t* parent, lv_color_t primaryColor, lv_color_t secondaryColor);
    ~GoudanMouth();

    void setPosition(const uitk::Vector2i& position) override;
    void setWeight(int weight) override;
    void setRotation(int rotation) override;
    void setEmotion(const Emotion& emotion) override;
    void setVisible(bool visible) override;

private:
    void relayout();

    bool _is_frown = false;  // 难过时倒扣的弧线
    lv_obj_t* _arc = nullptr;
    std::unique_ptr<uitk::lvgl_cpp::Container> _open_mouth;
};

}  // namespace stackchan::avatar
