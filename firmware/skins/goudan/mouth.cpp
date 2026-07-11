/*
 * Goudan skin mouth — 弧线嘴 (lv_arc) + 张嘴时的圆角"O 形"。
 * weight 0-100: 0-49 → 弧线微笑(弧越弯), 50-100 → 圆角张嘴(越大)。
 * rotation 沿用 0.1° 语义; Sad 时弧线倒扣。
 *
 * SPDX-License-Identifier: MIT
 */
#include "goudan.h"

using namespace uitk;
using namespace uitk::lvgl_cpp;
using namespace stackchan::avatar;

static const Vector2i _mouth_pos        = Vector2i(0, 42);
static const Vector2i _mouth_min_offset = Vector2i(-16, -16);
static const Vector2i _mouth_max_offset = Vector2i(16, 16);
static const int _arc_w_min = 56, _arc_w_max = 96;    // 弧线嘴宽度随 weight 增大
static const int _arc_thickness = 9;
static const int _open_min = 26, _open_max = 56;      // 张嘴尺寸

static int map_range(int v, int inMin, int inMax, int outMin, int outMax)
{
    return outMin + (v - inMin) * (outMax - outMin) / (inMax - inMin);
}

GoudanMouth::GoudanMouth(lv_obj_t* parent, lv_color_t primaryColor, lv_color_t secondaryColor)
{
    // 弧线嘴 (lv_arc 下半弧)
    _arc = lv_arc_create(parent);
    lv_obj_remove_style(_arc, NULL, LV_PART_KNOB);
    lv_obj_remove_flag(_arc, (lv_obj_flag_t)(LV_OBJ_FLAG_CLICKABLE | LV_OBJ_FLAG_SCROLLABLE));
    lv_obj_set_style_arc_opa(_arc, LV_OPA_TRANSP, LV_PART_MAIN);  // 背景弧透明
    lv_obj_set_style_arc_color(_arc, primaryColor, LV_PART_INDICATOR);
    lv_obj_set_style_arc_width(_arc, _arc_thickness, LV_PART_INDICATOR);
    lv_obj_set_style_arc_rounded(_arc, true, LV_PART_INDICATOR);
    lv_arc_set_bg_angles(_arc, 0, 360);

    // 张嘴 (圆角矩形, weight>=50 时替代弧线)
    _open_mouth = std::make_unique<Container>(parent);
    _open_mouth->setRadius(14);
    _open_mouth->setAlign(LV_ALIGN_CENTER);
    _open_mouth->setBorderWidth(0);
    _open_mouth->setBgColor(primaryColor);
    _open_mouth->removeFlag(LV_OBJ_FLAG_SCROLLABLE);
    _open_mouth->setHidden(true);

    setPosition(_position);
    setWeight(18);  // 默认带一点微笑弧
    setRotation(0);
}

GoudanMouth::~GoudanMouth()
{
    if (_arc) {
        lv_obj_delete(_arc);
        _arc = nullptr;
    }
    _open_mouth.reset();
}

void GoudanMouth::relayout()
{
    const bool open = _weight >= 50;

    if (open) {
        lv_obj_add_flag(_arc, LV_OBJ_FLAG_HIDDEN);
        _open_mouth->setHidden(!_visible ? true : false);
        const int s  = map_range(_weight, 50, 100, _open_min, _open_max);
        const int sx = s * 5 / 4;
        _open_mouth->setSize(sx, s);
    } else {
        _open_mouth->setHidden(true);
        if (_visible) {
            lv_obj_remove_flag(_arc, LV_OBJ_FLAG_HIDDEN);
        }
        // weight 0-49: 弧宽与弧夹角随之增大 (笑得更开)
        const int w = map_range(_weight, 0, 49, _arc_w_min, _arc_w_max);
        lv_obj_set_size(_arc, w, w);
        // 下半弧: 20°→160°; 倒扣(难过)时 200°→340°
        if (_is_frown) {
            lv_arc_set_angles(_arc, 200, 340);
        } else {
            lv_arc_set_angles(_arc, 20, 160);
        }
    }

    // 统一定位 (弧的可视中心在圆心下方, 用偏移补)
    const int px = _mouth_pos.x + map_range(_position.x, -100, 100, _mouth_min_offset.x, _mouth_max_offset.x);
    const int py = _mouth_pos.y + map_range(_position.y, -100, 100, _mouth_min_offset.y, _mouth_max_offset.y);
    if (open) {
        _open_mouth->align(LV_ALIGN_CENTER, px, py);
    } else {
        const int w = lv_obj_get_style_width(_arc, LV_PART_MAIN);
        lv_obj_align(_arc, LV_ALIGN_CENTER, px, py - (_is_frown ? -w / 3 : w / 3));
    }
}

void GoudanMouth::setPosition(const Vector2i& position)
{
    Element::setPosition(position);
    relayout();
}

void GoudanMouth::setWeight(int weight)
{
    Feature::setWeight(weight);
    relayout();
}

void GoudanMouth::setRotation(int rotation)
{
    Element::setRotation(rotation);

    // 语义扩展: rotation 落在 135°-225° 区间 = 倒扣撇嘴(frown), 偏差为撇嘴斜度。
    // 让 0x03 JSON 通道也能做撇嘴 (rotation:1800=纯撇嘴, 1710=左斜 9° 撇嘴)。
    int r = ((rotation % 3600) + 3600) % 3600;
    int tilt;
    if (r >= 1350 && r <= 2250) {
        _is_frown = true;
        tilt      = r - 1800;
    } else {
        _is_frown = false;
        tilt      = (r > 1800) ? r - 3600 : r;
    }

    lv_obj_set_style_transform_rotation(_arc, tilt, LV_PART_MAIN);
    _open_mouth->setRotation(tilt);
    relayout();
}

void GoudanMouth::setEmotion(const Emotion& emotion)
{
    if (getIgnoreEmotion()) {
        return;
    }

    _is_frown = false;
    switch (emotion) {
        case Emotion::Neutral:
            setWeight(18);
            break;
        case Emotion::Happy:
            setWeight(40);
            break;
        case Emotion::Angry:
            _is_frown = true;
            setWeight(12);
            break;
        case Emotion::Sad:
            _is_frown = true;
            setWeight(20);
            break;
        case Emotion::Doubt:
            setWeight(6);
            break;
        case Emotion::Sleepy:
            setWeight(10);
            break;
        default:
            break;
    }
}

void GoudanMouth::setVisible(bool visible)
{
    Element::setVisible(visible);
    if (visible) {
        relayout();
    } else {
        lv_obj_add_flag(_arc, LV_OBJ_FLAG_HIDDEN);
        _open_mouth->setHidden(true);
    }
}
