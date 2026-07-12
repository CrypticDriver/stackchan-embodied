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
static constexpr int   APPEAR_HITS        = 2;     // 连续 2 帧有脸才判"出现" (防单帧误检)
// 强滞后: 一旦判定有人, 要连续 ~40s 真没脸才算"人离开"。
// 目的: 大哥坐着不动时检测偶尔漏帧(轻微晃动/光线)不算走, 免得反复 Gone→Appear
// 触发"又来人了"而反复打招呼。只有真的离开够久, 回来才当"新的一次到访"。
static constexpr int   GONE_MISSES        = 80;    // 连续 80 帧 (~40s) 无脸才判"离开"

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
                mclog::tagError(_tag, "alloc detect buffer failed ({} bytes)", (unsigned)need);
                continue;
            }
        }

        int gw = 0, gh = 0;
        uint32_t fmt = 0;
        if (!camera->GrabForDetect(buf, buf_cap, gw, gh, fmt)) {
            // 拍照占用中 / 格式不符 / 取帧失败, 下一轮再来。
            // 每 ~10s 报一次连续取帧失败, 便于真机排查 (静默空转最难查)。
            if (++grab_fail % 20 == 0) {
                mclog::tagWarn(_tag, "GrabForDetect failing (x{}), sensor fmt=0x{:08x}",
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

        // 选面积最大的人脸 (最靠近的那张), 算中心的归一化坐标 [-100,100]。
        // 摄像头未镜像, 屏幕对着大哥: 画面里大哥偏右 → 设备该往右看, 故 x 直接用;
        // 若真机方向反了, 把 face_x 取负即可 (见下方注释)。
        int face_x = 0, face_y = 0;
        if (seen) {
            const dl::detect::result_t* best = nullptr;
            for (auto& r : results) {
                if (!best || r.box_area() > best->box_area()) best = &r;
            }
            if (best && best->box.size() >= 4) {
                int cx = (best->box[0] + best->box[2]) / 2;
                int cy = (best->box[1] + best->box[3]) / 2;
                // 图像坐标 → [-100,100]; x 取负 = 镜像 (大哥在画面右, 果冻眼往右瞟去"看他")
                face_x = -(cx * 200 / (gw > 0 ? gw : 1) - 100);
                face_y = (cy * 200 / (gh > 0 ? gh : 1) - 100);
                if (face_x < -100) face_x = -100; else if (face_x > 100) face_x = 100;
                if (face_y < -100) face_y = -100; else if (face_y > 100) face_y = 100;
            }
        }

        // 每 ~10s 报一次心跳, 确认检测循环在跑 (真机可见)
        if (++loop_count % 20 == 0) {
            mclog::tagInfo(_tag, "detecting... (loop {}, fmt=0x{:08x}, {}x{}, boxes={}, x={}, y={})",
                           loop_count, (unsigned)fmt, gw, gh, (int)results.size(), face_x, face_y);
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
            mclog::tagInfo(_tag, "face APPEAR ({} boxes)", (int)results.size());
            GetHAL().onFaceEvent.emit(FaceEvent{FaceEventType::Appear, face_x, face_y});
        } else if (face_present && seen) {
            // 持续看到: 发 Track 让眼睛看向人脸
            GetHAL().onFaceEvent.emit(FaceEvent{FaceEventType::Track, face_x, face_y});
        } else if (face_present && miss_streak >= GONE_MISSES) {
            face_present = false;
            mclog::tagInfo(_tag, "face GONE");
            GetHAL().onFaceEvent.emit(FaceEvent{FaceEventType::Gone, 0, 0});
        }
    }
}

void Hal::face_detect_init()
{
    mclog::tagInfo(_tag, "init");
    // esp-dl 推理吃内存, 用大栈, 跑在 core 1 (与 IMU 同核, 让 core 0 专注音频/网络)
    xTaskCreatePinnedToCore(_face_task, "face_detect", 8192, nullptr, 2, nullptr, 1);
}
