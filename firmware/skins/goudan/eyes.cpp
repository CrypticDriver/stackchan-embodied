/*
 * Goudan skin eyes — 果冻高光眼。
 * 结构: _container(旋转层) > _eye(白色圆) + _highlight(黑色高光缺口) + _eyelid(眼睑遮挡)
 * 参数映射与 default 皮肤同构:
 *   position ±100 → 物理 ±16px; weight 0-100 → 眼睑全遮→全开;
 *   size ±100 → 眼球直径 44→76px (比 default 大一圈, 果冻感); rotation 0.1°。
 *
 * SPDX-License-Identifier: MIT
 */
#include "goudan.h"

using namespace uitk;
using namespace uitk::lvgl_cpp;
using namespace stackchan::avatar;

static const Vector2i _eye_pos        = Vector2i(-70, -20);
static const Vector2i _eye_min_offset = Vector2i(-16, -16);
static const Vector2i _eye_max_offset = Vector2i(16, 16);
static const Vector2i _eye_size_limit = Vector2i(44, 76);  // size -100 → +100
static const int _container_size      = 84;

static int map_range(int v, int inMin, int inMax, int outMin, int outMax)
{
    return outMin + (v - inMin) * (outMax - outMin) / (inMax - inMin);
}

GoudanEyes::GoudanEyes(lv_obj_t* parent, lv_color_t primaryColor, lv_color_t secondaryColor, bool isLeftEye)
{
    _is_left_eye = isLeftEye;

    _container = std::make_unique<Container>(parent);
    _container->setRadius(0);
    _container->setAlign(LV_ALIGN_CENTER);
    _container->setBorderWidth(0);
    _container->setBgOpa(0);
    _container->removeFlag(LV_OBJ_FLAG_SCROLLABLE);
    _container->setPadding(0, 0, 0, 0);
    _container->setSize(_container_size, _container_size);
    _container->setTransformPivot(_container_size / 2, _container_size / 2);

    _eye = std::make_unique<Container>(_container->get());
    _eye->setRadius(LV_RADIUS_CIRCLE);
    _eye->align(LV_ALIGN_CENTER, 0, 0);
    _eye->setBorderWidth(0);
    _eye->setBgColor(primaryColor);
    _eye->removeFlag(LV_OBJ_FLAG_SCROLLABLE);

    // 高光缺口: 眼球右上角的一小块背景色圆 —— "湿润反光"
    _highlight = std::make_unique<Container>(_container->get());
    _highlight->setRadius(LV_RADIUS_CIRCLE);
    _highlight->align(LV_ALIGN_CENTER, 0, 0);
    _highlight->setBorderWidth(0);
    _highlight->setBgColor(secondaryColor);
    _highlight->removeFlag(LV_OBJ_FLAG_SCROLLABLE);

    // 眼睑: 从上向下遮挡的背景色方块
    _eyelid = std::make_unique<Container>(_container->get());
    _eyelid->setRadius(0);
    _eyelid->align(LV_ALIGN_TOP_MID, 0, 0);
    _eyelid->setBorderWidth(0);
    _eyelid->setBgColor(secondaryColor);
    _eyelid->removeFlag(LV_OBJ_FLAG_SCROLLABLE);

    setSize(0);
    setWeight(100);
    setPosition(_position);
    setRotation(0);
}

GoudanEyes::~GoudanEyes()
{
    _eyelid.reset();
    _highlight.reset();
    _eye.reset();
    _container.reset();
}

void GoudanEyes::relayout()
{
    const int d = _eye_diameter;
    _eye->setSize(d, d);

    // 高光: 直径 22% 的小圆, 位于眼球右上 (左右眼对称内翻)
    const int hd = d * 22 / 100;
    const int hx = (_is_left_eye ? 1 : 1) * (d * 22 / 100);  // 统一右上, 更像同一光源
    const int hy = -(d * 24 / 100);
    _highlight->setSize(hd, hd);
    _highlight->align(LV_ALIGN_CENTER, hx, hy);

    // 眼睑: weight 0-100 → 遮挡 100%→0%
    const int lid_h = map_range(100 - _weight, 0, 100, 0, d);
    _eyelid->setSize(d + 4, lid_h);
    _eyelid->align(LV_ALIGN_TOP_MID, 0, (_container_size - d) / 2 - 2);
}

void GoudanEyes::setPosition(const Vector2i& position)
{
    Element::setPosition(position);

    auto pos_x = _is_left_eye ? _eye_pos.x : -_eye_pos.x;
    pos_x += map_range(_position.x, -100, 100, _eye_min_offset.x, _eye_max_offset.x);
    auto pos_y = _eye_pos.y + map_range(_position.y, -100, 100, _eye_min_offset.y, _eye_max_offset.y);

    _container->setPos(pos_x, pos_y);
}

void GoudanEyes::setWeight(int weight)
{
    Feature::setWeight(weight);
    relayout();
}

void GoudanEyes::setRotation(int rotation)
{
    Element::setRotation(rotation);
    _container->setRotation(rotation);
}

void GoudanEyes::setSize(int size)
{
    Feature::setSize(size);
    _eye_diameter = map_range(_size, -100, 100, _eye_size_limit.x, _eye_size_limit.y);
    relayout();
}

void GoudanEyes::setEmotion(const Emotion& emotion)
{
    if (getIgnoreEmotion()) {
        return;
    }

    auto apply = [this](int weight, int rotation, int size) {
        setWeight(weight);
        setSize(size);
        if (_is_left_eye) {
            setRotation(rotation);
        } else {
            setRotation(-rotation);
        }
    };

    switch (emotion) {
        case Emotion::Neutral:
            apply(100, 0, 0);
            break;
        case Emotion::Happy:
            // 月牙眼: 眼睑压半 + 大角度旋转让弧线朝下
            apply(55, 1550, 10);
            break;
        case Emotion::Angry:
            apply(62, 450, -10);
            break;
        case Emotion::Sad:
            apply(60, -400, 0);
            break;
        case Emotion::Doubt:
            apply(70, 0, -15);
            break;
        case Emotion::Sleepy:
            apply(30, -50, -5);
            break;
        default:
            break;
    }
}

void GoudanEyes::setVisible(bool visible)
{
    Element::setVisible(visible);
    _container->setHidden(!visible);
}
