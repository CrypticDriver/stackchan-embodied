/*
 * Active skin selector — 通过 Kconfig 选择编译期皮肤。
 * 所有创建 avatar 的调用点统一用 avatar::ActiveAvatar,
 * 皮肤切换只改 menuconfig (或 sdkconfig.defaults.local), 不动业务代码。
 *
 * SPDX-License-Identifier: MIT
 */
#pragma once
#include <sdkconfig.h>

#ifdef CONFIG_STACKCHAN_SKIN_GOUDAN
#include "goudan/goudan.h"
#else
#include "default/default.h"
#endif

namespace stackchan::avatar {

#ifdef CONFIG_STACKCHAN_SKIN_GOUDAN
using ActiveAvatar = GoudanAvatar;
#else
using ActiveAvatar = DefaultAvatar;
#endif

}  // namespace stackchan::avatar
