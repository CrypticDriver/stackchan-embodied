/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 *
 * 本地人脸检测 (on-device, esp-dl / human_face_detect MSRMNP_S8_V1)。
 * 后台低频跑推理: 静默取一帧 RGB565 → 检测 → 发 FaceEvent::Appear / Gone。
 * 全程本机, 不联网、不上传图像。摄像头拍照(Capture) 优先, 取帧用 try_lock 让路。
 *
 * M3 第一步 (最小闭环): 只判断"有没有脸"并发事件, 交给 avatar 侧变表情,
 * 用来验证 esp-dl 在这套固件上能跑、性能可接受。
 */
#include "hal.h"
#include "board/hal_bridge.h"
#include "board/stackchan_camera.h"
#include <mooncake_log.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <esp_heap_caps.h>
#include <memory>

#include "human_face_detect.hpp"
#include "dl_image_define.hpp"
#include "linux/videodev2.h"   // V4L2_PIX_FMT_RGB565 / YUYV / YUV422P

static const std::string_view _tag = "HAL-FACE";

// 检测节奏与去抖 (帧率不必高, "有人在看" 是慢事件)
static constexpr int   DETECT_PERIOD_MS   = 500;   // 每 0.5s 检测一帧
static constexpr int   APPEAR_HITS        = 1;     // 连续 1 帧有脸即判定"出现" (灵敏)
static constexpr int   GONE_MISSES        = 4;     // 连续 4 帧 (~2s) 无脸才判"离开" (防抖)

static void _face_task(void*)
{
    auto* camera = hal_bridge::board_get_camera();
    if (!camera) {
        mclog::tagError(_tag, "no camera, face detect task exits");
        vTaskDelete(nullptr);
        return;
    }

    // 等摄像头 streaming 就绪 (init 阶段 ISP 会先丢几秒帧)
    vTaskDelay(pdMS_TO_TICKS(6000));

    // 帧缓冲: 分辨率启动后才知道, 首次成功取帧时按需分配
    uint8_t* buf     = nullptr;
    size_t   buf_cap = 0;

    // 模型 lazy_load=false: 构造时即载入, 避免首次检测卡顿; 失败则退出任务
    std::unique_ptr<HumanFaceDetect> detector;
    detector = std::make_unique<HumanFaceDetect>();
    mclog::tagInfo(_tag, "HumanFaceDetect model loaded");

    bool face_present = false;
    int  hit_streak   = 0;
    int  miss_streak  = 0;
    int  grab_fail    = 0;   // 连续取帧失败计数 (诊断静默空转)
    int  loop_count   = 0;   // 检测循环心跳计数

    while (1) {
        vTaskDelay(pdMS_TO_TICKS(DETECT_PERIOD_MS));

        // 先探一次分辨率 (拿宽高), 需要时分配缓冲
        int w = camera->GetFrameWidth();
        int h = camera->GetFrameHeight();
        if (w <= 0 || h <= 0) {
            continue;
        }
        size_t need = (size_t)w * (size_t)h * 2;
        if (need > buf_cap) {
            if (buf) {
                heap_caps_free(buf);
            }
            buf = (uint8_t*)heap_caps_malloc(need, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
            buf_cap = buf ? need : 0;
            if (!buf) {
                mclog::tagError(_tag, "alloc detect buffer failed (%u bytes)", (unsigned)need);
                continue;
            }
        }

        int gw = 0, gh = 0;
        uint32_t fmt = 0;
        if (!camera->GrabForDetect(buf, buf_cap, gw, gh, fmt)) {
            // 拍照占用中 / 格式不符 / 取帧失败, 下一轮再来。
            // 每 ~10s 报一次连续取帧失败, 便于真机排查 (静默空转最难查)。
            if (++grab_fail % 20 == 0) {
                mclog::tagWarn(_tag, "GrabForDetect failing (x%d), sensor fmt=0x%08x",
                               grab_fail, (unsigned)camera->GetFrameFormat());
            }
            continue;
        }
        grab_fail = 0;

        dl::image::img_t img;
        img.data   = buf;
        img.width  = (uint16_t)gw;
        img.height = (uint16_t)gh;
        // 按相机实际输出选 esp-dl 像素类型 (RGB565 小端 / YUYV)
        if (fmt == V4L2_PIX_FMT_YUYV || fmt == V4L2_PIX_FMT_YUV422P) {
            img.pix_type = dl::image::DL_IMAGE_PIX_TYPE_YUYV;
        } else {
            img.pix_type = dl::image::DL_IMAGE_PIX_TYPE_RGB565LE;
        }

        auto& results = detector->run(img);
        bool  seen    = !results.empty();

        // 每 ~10s 报一次心跳, 确认检测循环在跑 (真机可见)
        if (++loop_count % 20 == 0) {
            mclog::tagInfo(_tag, "detecting... (loop %d, fmt=0x%08x, %dx%d, boxes=%d)",
                           loop_count, (unsigned)fmt, gw, gh, (int)results.size());
        }

        if (seen) {
            hit_streak++;
            miss_streak = 0;
        } else {
            miss_streak++;
            hit_streak = 0;
        }

        if (!face_present && hit_streak >= APPEAR_HITS) {
            face_present = true;
            mclog::tagInfo(_tag, "face APPEAR (%d boxes)", (int)results.size());
            GetHAL().onFaceEvent.emit(FaceEvent::Appear);
        } else if (face_present && miss_streak >= GONE_MISSES) {
            face_present = false;
            mclog::tagInfo(_tag, "face GONE");
            GetHAL().onFaceEvent.emit(FaceEvent::Gone);
        }
    }
}

void Hal::face_detect_init()
{
    mclog::tagInfo(_tag, "init");
    // esp-dl 推理吃内存, 用大栈, 跑在 core 1 (与 IMU 同核, 让 core 0 专注音频/网络)
    xTaskCreatePinnedToCore(_face_task, "face_detect", 8192, nullptr, 2, nullptr, 1);
}
