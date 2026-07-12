# 狗蛋本地问候音 (云希声, 人脸检测到人时随机播一句)

用 EdgeTTS `zh-CN-YunxiaNeural` (与狗蛋对话同音色) 生成, 转 Opus/Ogg 单声道:
`ffmpeg -i x.mp3 -c:a libopus -ac 1 -b:a 24k x.ogg`

| 文件 | 文案 |
|---|---|
| greet_0.ogg | 哟，大哥来啦 |
| greet_1.ogg | 大哥，我在呢 |
| greet_2.ogg | 嘿，你回来啦 |
| greet_3.ogg | 大哥好呀 |
| greet_4.ogg | 大哥，想我没 |

嵌入: 放 firmware/main/assets/sfx/, CMake glob `assets/sfx/*.ogg` 自动 EMBED_FILES。
新增 .ogg 后必须 `idf.py reconfigure` (glob 在 configure 期求值), 否则符号找不到。
符号: `_binary_greet_N_ogg_start/end` → assets.h 的 OGG_GREETS[]。
