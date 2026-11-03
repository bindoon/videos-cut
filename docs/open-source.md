# 开源来源与集成说明

本项目把成熟的语音、下载和视频处理组件组织成一条可复现的本地工作流。这里说明**用了谁的哪部分、怎样接入，以及本项目补了什么**。确切依赖版本以锁文件和固定来源记录为准，不使用会过期的 Star 数量衡量能力。

[文档导航](README.md) · [架构](architecture.md) · [验证记录](verification.md)

## 本项目许可证

原创代码、`skills/` 中自有工作流及文档采用根目录 [MIT License](../LICENSE)，包元数据声明 `MIT` 并携带 LICENSE。MIT 授权范围不改变第三方代码、模型权重、原始素材及衍生展示媒体的许可证；杭州和太极媒体继续使用其 CC BY-SA 4.0 归属说明，ffmpeg-skill 和 Lemo 保留各自 MIT 版权声明。

## 吸收的思路与实际接入

| 来源 | 吸收或使用的部分 | 接入方式 | 本项目负责的部分 |
| --- | --- | --- | --- |
| [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) | 脚本→配音→素材→字幕→合成的工作流，MoviePy/Pillow 分层合成思路 | **设计参考**；本地阅读过素材、语音和视频服务代码 | 独立 CLI 与 JSON 配置、逐句实际音频时间轴、素材选择与处理报告 |
| [AiToEarn](https://github.com/yikart/AiToEarn) | 结构化创作计划、媒体生成工具拆分、画面要求与发布文案分离 | **设计参考**；未复制业务代码或引入服务端运行时 | 宿主 Agent 写稿/生图，`prepare` 用本地文件交接、检查缺项并衔接原渲染器 |
| [MoviePy](https://github.com/Zulko/moviepy) / [Pillow](https://github.com/python-pillow/Pillow) | 视频/音频图层、文字栅格化、渐变遮罩、动态贴纸与进度条 | **实际依赖调用**，主要在 `videocut/render.py` | 统一图层顺序、转场后再叠字幕、配置化画面包装 |
| [FFmpeg](https://ffmpeg.org/) | 运镜、裁切、xfade 转场、重采样、响度、编码、媒体探测和完整解码 | **系统程序调用**，经 `media.py` 等模块执行 | 音画按帧共同裁切、错误/超时处理与实际成片检查 |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Whisper 识别、VAD 与逐词时间 | **可选 ASR 依赖**；当前后端 CPU int8 | 分段有界解码、原文件时间归属、校验缓存与恢复、TXT/SRT/JSON 导出，以及编辑消费者的准入检查 |
| [Auto-Editor](https://github.com/WyattBlue/auto-editor) | 按静音进行粗剪 | **可选 CLI 调用**，由 `rough-cut` 启动 | 单独保留粗剪入口；中文口头词精剪由本项目 `cleaning.py` 处理 |
| [Qwen3-ASR / ForcedAligner](https://github.com/QwenLM/Qwen3-ASR) | 给定音频与原稿的字词起止定位 | **官方接口调用**，`scripts/align_qwen.py` 使用独立环境 | 固定字幕分条、句末预读策略、SRT 回读，以及成片全部帧和音轨偏移验收 |
| [Edge TTS](https://github.com/rany2/edge-tts) | 在线文字转语音 | **实际依赖调用**，`--tts edge` | 逐句合成、声音显式选择、PCM 时长和缓存；另提供 macOS 系统音色入口 |
| [F5-TTS MLX](https://github.com/lucasnewman/f5-tts-mlx) / [Vocos](https://github.com/gemelo-ai/vocos) | 参考音频与对应文字条件下生成新旁白、还原波形 | **历史实验**，已移除 CLI 选项；保留旧脚本与锁文件 | 逐句生成清单、参考/模型摘要、48kHz 转换和视频接入 |
| [IndexTTS](https://github.com/index-tts/index-tts) | 2.5 参考音色、原生语速、数值情绪向量、中文拼音标记 | **默认语音引擎，固定官方代码与独立模型环境**，`--tts indextts` | 逐句参数覆盖、缓存与归属记录、音频格式统一、字幕和镜头重算 |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | 网页媒体、音轨、字幕和播放列表解析 | **可选 Python API 依赖**，`download` extra | 素材协议、规格隔离缓存、大小预算、媒体校验、失败项和续传恢复 |
| [wx_channels_download](https://github.com/ltaoo/wx_channels_download) | 微信视频号捕获、本地 API 与视频解密流 | **可选的独立本地服务调用**，核对 v260907 API；不分发上游代码或二进制 | 明确目标匹配、格式选择、流大小预算、实测尺寸/完整解码、缓存与素材来源记录；证书和系统代理由外部服务单独管理 |
| [ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill) | 42 个本地处理工具、技能说明、交付模板与工具合同 | **Git submodule 固定引用上游源码，构建时收录运行文件**，`videocut ffmpeg` 转发调用 | 工具发现、入口和 wheel 打包；与主项目 ASR/字幕验收保持明确边界 |
| [huashu-motion](https://github.com/alchaincyf/huashu-motion) | 导演节奏、播放器/镜头时间轴/右侧批注布局、改片交接 | **设计参考**，基线 `52467f99c602b76ba86d511d37acdfe93fa1e16e` / v0.3.1；本地独立实现，未分发其代码或素材 | 双渲染路线的不可变视频版本、声明输入校验、原版本区域意见、Agent CLI 领取与实际新版回复 |
| [native-subtitle-quote-image](https://github.com/chengyi-ai/native-subtitle-quote-image) | 原生/脚本字幕来源区分、候选帧复核、主图与连续字幕条工作流 | **设计参考**；本地独立编写图像工具与小红书场景技能，未分发上游脚本或安装其 Skill | `image-cards-v1`、复用本项目下载/ASR、内容摘要缓存、逐卡失败恢复、输入变化失效与报告 |
| [Twemoji](https://github.com/jdecked/twemoji) | 透明表情图形，作为动态贴纸素材 | **下载图形资产**，图形许可 CC-BY-4.0 | 贴纸位置、缩放/浮动动画与素材归属记录 |
| [Three.js](https://github.com/mrdoob/three.js) / [Playwright](https://github.com/microsoft/playwright) | 城市白模 WebGL 绘制与私有 Chromium 的逐帧捕获 | **影片内 npm 依赖**；各工程 `package-lock.json` 固定版本 | `codefilm` 配置、确定性检查、分段续跑、实际媒体与摘要校验 |
| [Lemo Opuscar](https://github.com/lemomo-ai/lemo-opuscar) | 杭州影片后处理和 headless GPU 启动方式参考 | **杭州工程内固定 MIT 源码**，修订 `f17136060781a0068a7951245a3aa7835a7230de`；保留许可 | 真实杭州模型、相机、光层与共享渲染器；通用命令不依赖其 studio 服务 |

上表中的本项目部分主要是可审计的编排和验收：`timeline.json`、`edit-plan.json`、ASR 分段缓存、来源校验、固定字幕计划与成片检查。模型推理、编码器和上游工具的能力归属于对应项目。

## 设计参考：MoneyPrinterTurbo

参考基线为 **v1.3.9 / `6992380c5e82f07f3e1fc46b90927b6f1c655407`**。本地稀疏检出保存在忽略的 `upstream/MoneyPrinterTurbo-reference/`，重点阅读 `app/services/video.py`、`app/services/voice.py` 和素材/任务处理代码。

吸收的是分阶段完成作品的工作流与分层合成方式。当前仓库使用较小的独立编排层，未复制其业务代码，也没有运行其完整 WebUI、任务服务或供应商集合；复现本项目不需要安装整个 MoneyPrinterTurbo。

## 设计参考：AiToEarn

参考提交 **`cc13deb6ab6d17b55e733d9353ad3300e31f40f7`**（2026-10-29 核对），阅读了 [draft-generation-planner.service.ts](https://github.com/yikart/AiToEarn/blob/cc13deb6ab6d17b55e733d9353ad3300e31f40f7/project/aitoearn-backend/apps/aitoearn-ai/src/core/draft-generation/draft-generation-planner.service.ts)、[media.mcp.ts](https://github.com/yikart/AiToEarn/blob/cc13deb6ab6d17b55e733d9353ad3300e31f40f7/project/aitoearn-backend/apps/aitoearn-ai/src/core/agent/mcp/media.mcp.ts) 及视频编辑工具的结构化参数。

本项目借鉴其规划与工具边界，具体执行采用本地 `creation.py`，宿主生成素材后通过文件交接。未接入 AiToEarn API、Relay、数据库、队列或平台授权；未移植其云端视频处理和字幕实现。宿主无生图能力时不会静默改调付费服务。生成式 AI 视频仅标记外部需求，调用适配器尚未实现。

## 设计参考：huashu-motion

在本地测试其基本示例和太极 V3 适配后，吸收导演计划、节奏复核与画面批注交接。videos-cut 保留原素材渲染器和 codefilm，新增 `review` 交接层；网页与技能独立编写，没有复制上游服务、前端源码、GSAP、字体或作者角色形象。上游代码/文档 MIT 与第三方素材许可须分别看待，其 [THIRD_PARTY.md](https://github.com/alchaincyf/huashu-motion/blob/52467f99c602b76ba86d511d37acdfe93fa1e16e/THIRD_PARTY.md) 不因设计参考而被重新授权。太极实测副本继续保留本项目原有模型与字体来源。

## 直接引用：ffmpeg-skill

固定版本 **2.16.1**，提交 **`f2d90ea603a663711c3d6aa9775d2a2380d83182`**，MIT。通过 [`.gitmodules`](../.gitmodules) 和父仓库的 gitlink 直接引用上游仓库，工作区路径为 [.agents/skills/ffmpeg-skill](../.agents/skills/ffmpeg-skill/SKILL.md)，保留上游 [LICENSE](../.agents/skills/ffmpeg-skill/LICENSE)。迁移前工具文件与同一提交逐个摘要一致，记录保留在 [ffmpeg-upstream.json](ffmpeg-upstream.json)。

`videocut/ffmpeg_tools.py` 从子模块调用工具，不经 shell，也不在运行时下载或更新。wheel/sdist 构建时仅收录所需固定文件与许可证；没有维护第二份上游源码。主流程与上游的 `render` 使用不同 JSON 格式；主流程 `cut` 与 `ffmpeg cut` 分别对应口头词精剪和指定区间裁切。

初始化、更新和打包说明见 [FFmpeg 工具说明](ffmpeg-tools.md#来源与更新)。上游 `verified` 和平台 `check` 只覆盖其自身合同；可选 `--transcribe` 不使用本项目转录缓存与来源协议。

## 版本与复现入口

城市建筑、水系、字体、参考片与解说来源见杭州 [CREDITS](../films/hangzhou/CREDITS.md)。代码视频的浏览器和 GIS 依赖隔离在影片工程，不混入 Python 主环境；[代码影片技能](../skills/codefilm-workflow/SKILL.md)说明复现及验收边界。

| 组件 | 固定或记录的位置 | 安装与使用 |
| --- | --- | --- |
| MoviePy、Pillow、faster-whisper、Auto-Editor、Edge TTS、yt-dlp 等主环境包 | `pyproject.toml` 声明范围，`uv.lock` 固定解析版本；yt-dlp 当前固定 `2026.10.21` | [使用指南](usage.md) |
| FFmpeg / ffprobe | 系统安装；实际版本记录于对应运行证据，不由 `uv.lock` 锁定 | [FFmpeg 工具说明](ffmpeg-tools.md) |
| F5-TTS MLX / Vocos | `requirements-voice.lock.txt`，模型下载目录的 `source.json` | [F5 历史实验](voice-cloning-f5-history.md) |
| IndexTTS-2.5 | `requirements-index.lock.txt`；实测代码 `d9e41aac89fd00b3d71497fddb287b7f24613712`，主模型修订 `c39ce5ba981572cb187443877ff559dfb246ce63` | [IndexTTS 安装与控制](voice-controls.md) |
| Qwen3-ForcedAligner-0.6B | `requirements-align.lock.txt`，`qwen-asr==0.0.6`；模型修订 `c7cbfc2048c462b0d63a45797104fc9db3ad62b7` | [字幕同步](subtitle-sync.md) |
| ffmpeg-skill | `.gitmodules`、gitlink 固定提交、子模块 LICENSE；迁移摘要在 `docs/ffmpeg-upstream.json` | [工具来源与更新](ffmpeg-tools.md#来源与更新) |

模型与实验用上游工作区保持忽略；第三方技能仅在父仓库记录 submodule 来源和提交指针。下载脚本会保存修订和摘要；新机器首次下载时需核对专项文档中的已验证修订，不能把未来仓库的最新权重当作同一份模型。

## 素材与展示归属

示例视频及音乐来自 Mixkit，照片来自 Unsplash，贴纸来自 Twemoji。原始清单在 [examples/materials.json](../examples/materials.json)，每次实际下载保留 URL、许可引用、大小和 SHA-256；未知许可记作 `unknown`，不推断为可任意使用。

README 的图片和动图是本项目真实渲染结果的截图与节选，来源和归属保存在 [展示媒体说明](media/README.md)。代码、模型权重、素材分别适用各自的许可；本项目的集成不会改变上游许可。

## 历史参考与实验边界

- **WhisperX**：早期参考中文 CTC 模型选型，没有安装完整 WhisperX 或复制其对齐实现。旧 Wav2Vec2 CTC 与 Whisper 交叉对齐作为历史实验保留；当前生成旁白的句末定位及显式拆条使用 Qwen，不能沿用旧“模型分歧就合并字幕”规则。
- **SSML**：`scripts/test_indextts_controls.py` 有局部标签转换与静音拼接适配层。7 组短句实验覆盖语速、情绪、拼音及停顿对照；它尚未接入完整视频提供方，不能称为 IndexTTS 原生完整 SSML。
- **Kokoro-FastAPI、CosyVoice**：早期调研过控制接口，本项目未完成运行接入，不能列作已验证提供方。

当前没有任意视频的视觉自动打标、专门呼吸识别、拖动剪辑时间线、`w` 强制连读约束、词级重读/情绪及完整 SSML。ffmpeg-skill 可以导出时间线、测量场景并给出高光候选，但不等于新增了这些语义理解或交互能力。具体已跑过的输入和结果见[验证记录](verification.md)。
