/*
 * Goudan skin eyes — 果冻高光眼 (v2: 黑瞳孔在眼白里转)。
 * 结构: _container(旋转层,固定基准位) > _eye(白眼眶,固定) + _pupil(黑瞳孔,随视线滑动)
 *        + _highlight(瞳孔上的白高光) + _eyelid(眼睑遮挡)
 * 参数映射:
 *   position ±100 → 瞳孔在眼白内滑动 (视线方向, 一眼可辨);
 *   weight 0-100 → 眼睑全遮→全开; size ±100 → 眼球直径 44→76px; rotation 0.1°。
 *
 * SPDX-License-Identifier: MIT
 */
#include "goudan.h"

using namespace uitk;
using namespace uitk::lvgl_cpp;
using namespace stackchan::avatar;

static const Vector2i _eye_pos     = Vector2i(-70, -20);
static const Vector2i _eye_size_limit = Vector2i(44, 76);  // size -100 → +100
static const int _container_size   = 84;
static const int _pupil_pct        = 55;   // 瞳孔直径 = 眼球的 55%
static const int _pupil_range_pct  = 90;   // 瞳孔可移动范围 (占眼白余量的比例)

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

    // 白眼眶 (固定居中)
    _eye = std::make_unique<Container>(_container->get());
    _eye->setRadius(LV_RADIUS_CIRCLE);
    _eye->align(LV_ALIGN_CENTER, 0, 0);
    _eye->setBorderWidth(0);
    _eye->setBgColor(primaryColor);
    _eye->removeFlag(LV_OBJ_FLAG_SCROLLABLE);

    // 黑瞳孔 (在眼白里滑动 = 视线方向)
    _pupil = std::make_unique<Container>(_container->get());
    _pupil->setRadius(LV_RADIUS_CIRCLE);
    _pupil->align(LV_ALIGN_CENTER, 0, 0);
    _pupil->setBorderWidth(0);
    _pupil->setBgColor(secondaryColor);
    _pupil->removeFlag(LV_OBJ_FLAG_SCROLLABLE);

    // 高光: 瞳孔上的一小块白点 (跟瞳孔走, "湿润反光")
    _highlight = std::make_unique<Container>(_pupil->get());
    _highlight->setRadius(LV_RADIUS_CIRCLE);
    _highlight->setBorderWidth(0);
    _highlight->setBgColor(primaryColor);
    _highlight->removeFlag(LV_OBJ_FLAG_SCROLLABLE);

    // 眼睑: 从上向下遮挡
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
    _pupil.reset();
    _eye.reset();
    _container.reset();
}

void GoudanEyes::relayout()
{
    const int d = _eye_diameter;
    _eye->setSize(d, d);

    // 瞳孔
    const int pd = d * _pupil_pct / 100;
    _pupil->setSize(pd, pd);

    // 高光: 瞳孔直径 30% 的小白点, 瞳孔右上
    const int hd = pd * 30 / 100;
    _highlight->setSize(hd, hd);
    _highlight->align(LV_ALIGN_CENTER, pd * 15 / 100, -pd * 20 / 100);

    // 眼睑: weight 0-100 → 遮挡 100%→0%
    const int lid_h = map_range(100 - _weight, 0, 100, 0, d);
    _eyelid->setSize(d + 4, lid_h);
    _eyelid->align(LV_ALIGN_TOP_MID, 0, (_container_size - d) / 2 - 2);

    // 视线: 瞳孔在眼白内滑动 (随 d 变化, 每次 relayout 重定位)
    reposition_pupil();
}

void GoudanEyes::reposition_pupil()
{
    const int d  = _eye_diameter;
    const int pd = d * _pupil_pct / 100;
    const int range = (d - pd) / 2 * _pupil_range_pct / 100;   // 瞳孔中心可偏移的最大半径
    const int ppx = map_range(_position.x, -100, 100, -range, range);
    const int ppy = map_range(_position.y, -100, 100, -range, range);
    _pupil->align(LV_ALIGN_CENTER, ppx, ppy);
}

void GoudanEyes::setPosition(const Vector2i& position)
{
    Element::setPosition(position);
    // 眼睛整体固定在基准位; 视线 = 瞳孔在眼白内滑动
    _container->setPos(_is_left_eye ? _eye_pos.x : -_eye_pos.x, _eye_pos.y);
    reposition_pupil();
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
