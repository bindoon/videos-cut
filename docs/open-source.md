# 开源选型与边界

首次调研于 2026-10-24，后续接入按实际代码更新。Star 是调研时 GitHub 显示的约数，主要作为社区规模参考；依赖版本以锁文件为准。

| 项目 | 约 Star | 本项目如何使用 |
| --- | --- | --- |
| [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) | 135k | 参考主题/脚本→配音→素材→字幕→合成的工作流，以及 MoviePy/Pillow 的分层合成方式；不宣称整个上游应用已经作为本项目后端运行 |
| [WhisperX](https://github.com/m-bain/whisperX) | 24k | 早期参考其中文 CTC 选型；没有安装完整 WhisperX 或复制其对齐实现，旧实验保留 |
| [Qwen3-ASR / ForcedAligner](https://github.com/QwenLM/Qwen3-ASR) | 以仓库为准 | 默认整句字幕使用官方 Qwen3ForcedAligner 定位上一句末字结束以立即切换；显式 audio_clip 按 PCM 区间显示无需模型 |
| [MoviePy](https://github.com/Zulko/moviepy) | 15k | 实际用于字幕、渐变遮罩、浮动贴纸、进度条、配音/配乐的合成 |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | 以仓库为准 | 独立 `transcribe` 与原有精剪共用的识别实现，分段解码、逐词时间和可校验缓存；CPU int8，不需要 CUDA |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | 以仓库为准 | 可选 `download` extra 固定 2026.10.21；官方 Python API 解析网页视频、音轨、字幕与播放列表，结果校验后进入本地素材清单 |
| [Auto-Editor](https://github.com/WyattBlue/auto-editor) | 5.5k | `rough-cut` 命令真实调用上游 CLI，做静音粗剪 |
| [Edge TTS](https://github.com/rany2/edge-tts) | 以仓库为准 | 提供可选在线中文配音；演示还支持明确选择 macOS 本地声音 |
| [F5-TTS MLX](https://github.com/lucasnewman/f5-tts-mlx) | 以仓库为准 | 实际生成参考音色的 12 句旁白，并接入完整视频；v1 4-bit 权重、Vocos、独立 MLX 环境 |
| [IndexTTS](https://github.com/index-tts/index-tts) | 24.7k | 2.5 官方实现已跑通 7 组音频控制实验，并接入 `--tts indextts` 完整视频配音；支持原生语速、情绪向量与逐句拼音输入 |
| [FFmpeg](https://ffmpeg.org/) | 不以 GitHub 镜像 Star 比较 | 实际用于图片运镜、音画裁切、xfade 转场、编码、探测和完整解码验收 |
| [ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill) | 以仓库为准 | MIT；2.16.1 / `f2d90ea603a663711c3d6aa9775d2a2380d83182` 的运行脚本、技能与模板纳入 `.agents/skills/ffmpeg-skill/`，省略演示 GIF；通过 `videocut ffmpeg` 调用，来源与摘要见 `UPSTREAM.json` |
| [Twemoji](https://github.com/jdecked/twemoji) | 以仓库为准 | 下载透明贴纸图，图形为 CC-BY-4.0；来源与归属保存在成片目录 |

MoneyPrinterTurbo 的参考基线是 v1.3.9 / `6992380c5e82f07f3e1fc46b90927b6f1c655407`。本地稀疏检出在忽略的 `upstream/MoneyPrinterTurbo-reference/`，重点阅读 `app/services/video.py`、`app/services/voice.py` 和素材/任务处理代码。本项目采用较小的独立编排层，没有复制上游业务代码后声称是自主实现。

剪辑依赖的确切解析版本由 `uv.lock` 固定；F5 与 IndexTTS 分别记录在 `requirements-voice.lock.txt`、`requirements-index.lock.txt`。上游 Auto-Editor 的 GitHub 最新实现与 PyPI 发布可能不同，实际执行版本以安装包和运行报告为准。

示例视频来自 Mixkit，照片来自 Unsplash，配乐来自 Mixkit，贴纸来自 Twemoji。每个下载结果都保留 URL、许可引用和 SHA-256，不把外部素材冒充自制素材。

参考声音克隆使用 [F5-TTS 的 MLX 实现](https://github.com/lucasnewman/f5-tts-mlx)，在独立 Apple Silicon 环境加载本地 v1 4-bit 权重；安装与模型来源见 [voice-cloning.md](voice-cloning.md)。

IndexTTS-2.5 的实测代码修订为 `d9e41aac89fd00b3d71497fddb287b7f24613712`，主模型修订为 `c39ce5ba981572cb187443877ff559dfb246ce63`。其数值情绪和拼音控制属于模型接口，完整视频提供方已接入这些原生参数；SSML 停顿及标签转换属于单独的实验适配层，尚未用于视频输入。完整下载命令、支持边界与本机试听见 [voice-controls.md](voice-controls.md)。

当前默认一条完整字幕对应一句口播，上一句末字结束即显示下一句。句末定位及显式拆条使用 [Qwen3-ForcedAligner-0.6B](https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B)，官方 `qwen-asr==0.0.6`，独立依赖见 `requirements-align.lock.txt`。早期中文 Wav2Vec2 CTC 与 Whisper 交叉对齐保留为历史实验，不能再用“分歧就合并字幕”的规则。安装、固定分条和成片验收见 [subtitle-sync.md](subtitle-sync.md)。

对话中也调研了 Kokoro-FastAPI、CosyVoice 的相关控制接口，但本机本轮没有运行这些模型，不能把文档中的能力记作本项目验证通过。

当前没有实现：任意素材的视觉模型自动打标、专门的呼吸声检测、交互式时间线编辑器、`w` 强制连读约束、词级重读/情绪及完整 SSML 兼容。这些与实际能跑的混剪/精剪管线和短句实验分开记录。
