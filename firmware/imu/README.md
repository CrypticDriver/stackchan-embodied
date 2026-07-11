# firmware/imu/ — 体感反应 (IMU 手势 → 表情动作)

CoreS3 板载 BMI270 (九轴 IMU)。在官方只有 Shake 的基础上补了 Flip(倒扣)/PickUp(拿起)。

## 手势检测 (motion_detector.h, 纯加速度计, 零延迟设备侧)
- **Shake** 晃动: 三轴差分高通 (原有)
- **Flip** 倒扣: acc_z 稳定翻负 (<-5) 持续 400ms; 翻回正放解锁 (可重复触发)
- **PickUp** 拿起: 连续静止(≥3帧纯重力) 后竖直向上突增 (z_jerk>4 且 acc_z>11); 2s 去抖

阈值全部用 host-verify/imu-sim 验证过 6 场景(静置/倒扣/二次倒扣/拿起/拿起放回/晃动不误报)。

## 反应 (imu_event_modifier.h, 配 goudan 果冻皮肤)
- 晃动 → 头晕 (Dizzy+Shy, 嘴左右摆) [原有]
- **倒扣 → 生气抗议** (Angry 表情 + Sweat 冒汗)
- **拿起 → 好奇惊喜** (Happy 表情 + 瞳孔放大 size=60 + Heart 爱心)
反应 4s 后自动恢复 Neutral。装在 AI 模式 (stackchan_display.cc 已注册 ImuEventModifier)。

刷 stack-chan.bin (712e29d8) 生效。
