/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 */
#pragma once
#include <lvgl.h>
#include <string_view>

LV_FONT_DECLARE(MontserratSemiBold26);

extern const char ogg_camera_shutter_start[] asm("_binary_camera_shutter_ogg_start");
extern const char ogg_camera_shutter_end[] asm("_binary_camera_shutter_ogg_end");
static const std::string_view OGG_CAMERA_SHUTTER{
    static_cast<const char*>(ogg_camera_shutter_start),
    static_cast<size_t>(ogg_camera_shutter_end - ogg_camera_shutter_start)};

extern const char ogg_new_notification_start[] asm("_binary_new_notification_ogg_start");
extern const char ogg_new_notification_end[] asm("_binary_new_notification_ogg_end");
static const std::string_view OGG_NEW_NOTIFICATION{
    static_cast<const char*>(ogg_new_notification_start),
    static_cast<size_t>(ogg_new_notification_end - ogg_new_notification_start)};

// 狗蛋本地问候音 (云希声 zh-CN-YunxiaNeural 生成, 人脸检测到人时随机播一句)
#define GOUDAN_GREET_OGG(n)                                                                      \
    extern const char ogg_greet_##n##_start[] asm("_binary_greet_" #n "_ogg_start");             \
    extern const char ogg_greet_##n##_end[] asm("_binary_greet_" #n "_ogg_end");                 \
    static const std::string_view OGG_GREET_##n{                                                 \
        static_cast<const char*>(ogg_greet_##n##_start),                                         \
        static_cast<size_t>(ogg_greet_##n##_end - ogg_greet_##n##_start)};
GOUDAN_GREET_OGG(0)
GOUDAN_GREET_OGG(1)
GOUDAN_GREET_OGG(2)
GOUDAN_GREET_OGG(3)
GOUDAN_GREET_OGG(4)
#undef GOUDAN_GREET_OGG

static const std::string_view OGG_GREETS[] = {
    OGG_GREET_0, OGG_GREET_1, OGG_GREET_2, OGG_GREET_3, OGG_GREET_4};
static constexpr int OGG_GREETS_COUNT = 5;

namespace assets {

lv_image_dsc_t get_image(std::string_view name);

}  // namespace assets
