# videos-cut · 可复现的视频混剪工具链

**把剧本、素材和声音变成短片，也把剪辑过程变成可检查、可复用的文件。**

面向开发者和 AI Agent 的本地 Python CLI：从网页导入素材，生成或保留旁白，精剪口播，合成字幕、图片运镜、转场、动态贴纸和配乐，输出 H.264 / AAC 视频及完整处理记录。用 JSON 描述作品，用命令组合工作流。

[快速开始](#快速开始) · [使用指南](docs/usage.md) · [让 AI 来操作](docs/ai-guide.md) · [开源来源](docs/open-source.md) · [全部文档](docs/README.md)

## 先看成片

下面是项目实际生成的咖啡短片，展示图片运镜、素材切换、中文字幕与透明贴纸。

![咖啡短片的六个镜头：图片、视频、字幕、贴纸和进度条](docs/media/coffee-contact-sheet.jpg)

<details>
<summary>查看 5 秒动态预览：素材切换、字幕与贴纸</summary>

<img src="docs/media/coffee-demo.gif" alt="真实成片第 5 至 10 秒：咖啡照片转入咖啡豆镜头，字幕和贴纸独立叠加" width="240">

</details>

这版样片为 **41.108 秒、720×1280、24fps**，含 6 个镜头、12 句字幕、5 次转场和 6 个贴纸，使用 Edge TTS 配音。GIF 是其中 5 秒的无声预览；[来源、归属和生成说明](docs/media/README.md)随仓库保存。它展示基础合成效果；Qwen 字幕验收另有[实跑记录](docs/verification.md)。完整视频可按下方命令在本地生成。

## 能做什么

| 能力 | 实际产出 |
| --- | --- |
| **剧本 → 完整短片** | 按句配音、按标签选片、照片缓慢推近、7 种可选转场、字幕、浮动/缩放贴纸、配乐与响度处理 |
| **已有录音 → 保留原声混剪** | 使用实际识别的字幕和句段安排镜头；不需要重新生成声音 |
| **口播精剪与素材穿插** | 按真实词时间删除指定口头词和长停顿，按视频帧同时切音画，重排字幕；`mix` 再交替使用原片和素材 |
| **本地语音转录** | 输出 TXT、SRT、逐词 JSON；长音频分段解码，完成段可缓存、恢复，损坏段单独重算 |
| **网页视频 / 音频导入** | yt-dlp 网页解析，以及微信视频号本地捕获/解密服务接入；清晰度选择、字幕轨、缓存和失败重试；输出可直接用于渲染的素材清单 |
| **参考音色与语音控制** | F5-TTS MLX 与 IndexTTS-2.5 生成新旁白；IndexTTS 支持原生语速、情绪向量与逐句拼音纠音 |
| **字幕显示与成片验收** | IndexTTS 默认用 Qwen 定位句末，上一句结束即显示下一句；固定分条、SRT 回读、全部编码帧及音轨偏移检查 |
| **42 个 FFmpeg 工具** | 改画幅、字幕烧录、音乐自动压低、HDR 转 SDR、多机位同步、平台导出、批处理与剪辑软件时间线导出 |

### 值得开发者关注的设计

- **时间轴来自声音。** 生成旁白按真实 PCM 采样数计算时长；已有录音用 ASR 词时间。换声音后重新计算镜头和字幕，避免按字数猜时长。
- **检查编码后的成片。** 语音对齐模式读取实际视频帧里的字幕并检查音轨偏移，通过后才将候选文件交付为 `final.mp4`；失败保留证据。普通文件字幕和 ASR 字幕会明确标记同步未验证。
- **每一步可追溯。** 素材来源、SHA-256、转录、删除区间、镜头时间轴、字幕计划和验收报告都能落盘；可校对转录后复用，也可复用已有配音与背景。
- **工具可以拆开用。** 下载、转录、精剪、混剪和 FFmpeg 后期各有入口，通过文件组合。主流程不需要接入付费大模型 API；语音模型依赖隔离在独立环境。

## 快速开始

需要 [uv](https://docs.astral.sh/uv/)、Python 3.12（主项目支持 `>=3.12,<3.14`）、系统 FFmpeg 和中文字体。以下是已验证的 macOS 路线，从仓库根目录执行：

```bash
brew install ffmpeg
uv sync
uv run videocut demo --tts macos --output outputs/coffee-local
```

默认输出 `720×1280 / 24fps`；macOS 系统 Tingting 配音在本地运行，首次仍需下载示例素材。使用在线 Edge 配音可显式选择 `--tts edge`。网络较慢时，先生成小尺寸预览：

```bash
uv run videocut demo --tts macos \
  --materials examples/materials-preview.json --width 480 --output outputs/preview
```

结果目录包含 `final.mp4`、`captions.srt`、`timeline.json`、`sources.json`、`verification.json`、`contact-sheet.jpg` 和配置快照。更换剧本、素材、声音以及各模式的附加产物见[使用指南](docs/usage.md)。

主链路实跑平台是 macOS Apple Silicon。F5 的 MLX 路径依赖 Apple Silicon；下载/ASR 文件锁依赖 macOS/Linux 的 `flock`。Linux 需准备中文字体并选择相应配音方案，原生 Windows 全流程尚未验证。

## 按任务使用

下载与 ASR 需要额外依赖；安装后按需选一个入口：

```bash
uv sync --extra download --extra asr

# 只转录：文字、SRT、逐词 JSON。
uv run videocut transcribe /absolute/path/input.mp4 --output outputs/transcribed

# 精剪：删长停顿与默认口头词，保留原声。
uv run videocut cut /absolute/path/talking.mp4 --output outputs/cleaned

# 精剪后混剪：原片与素材交替，叠字幕、贴纸和配乐。
uv run videocut mix /absolute/path/talking.mp4 --output outputs/mixed

# 自己的剧本和素材目录。
uv run videocut render --config examples/coffee.json \
  --materials examples/materials.json --tts edge --output outputs/my-video
```

下载视频链接、已有旁白、F5 / IndexTTS 安装及配置，参见[完整使用方法](docs/usage.md)。每次成片使用新的 `--output` 目录。

独立后期操作走项目内固定的 ffmpeg-skill，无需另装全局技能：

```bash
# macOS 扩展工具推荐完整滤镜构建。
brew install ffmpeg-full
uv run videocut ffmpeg --list
uv run videocut ffmpeg fit input.mp4 --aspect 9:16 --fit blur \
  -o outputs/vertical.mp4 --json-brief
```

具体参数、预演和平台导出见 [FFmpeg 工具说明](docs/ffmpeg-tools.md)。

## 如何让 AI 使用

把项目路径、输入文件和目标告诉 AI，并让它先读 [AI 操作指南](docs/ai-guide.md)。例如：

> 请先阅读 AGENTS.md、docs/ai-guide.md 和 docs/usage.md。把 `/absolute/path/talking.mp4` 精剪后做成竖屏混剪，保留原声，去除长停顿和“嗯、呃”，搭配咖啡素材。先检查输入与素材配置，输出到新的目录；完成后检查实际画面和报告，给我成片、截图和删除记录。

指南包含任务路由、可复制提示词、缓存复用和交付检查，也说明下载字幕、ASR 时间与 Qwen 对齐记录的区别。

## 站在这些开源项目之上

| 项目 | 吸收或使用的部分 |
| --- | --- |
| MoneyPrinterTurbo | 参考“脚本 → 配音 → 素材 → 字幕 → 合成”的编排与分层合成思路 |
| MoviePy / Pillow / FFmpeg | 实际执行画面图层、文字、贴纸、转场、音画裁切与编码 |
| faster-whisper / Auto-Editor | 逐词转录与独立静音粗剪；本项目负责缓存、精剪计划与字幕重排 |
| Qwen3-ForcedAligner | 给定原稿与音频，定位字词及句末；本项目补充固定展示计划与成片验收 |
| F5-TTS MLX / IndexTTS / Edge TTS | 参考音色、本地语音控制及在线配音 |
| yt-dlp | 网页视频、音轨、字幕和播放列表解析；本项目负责素材接入、校验与失败恢复 |
| ffmpeg-skill | 随项目固定分发 2.16.1 的 42 个工具、技能说明与模板，通过 CLI 直接调用 |

[开源来源与集成说明](docs/open-source.md)进一步区分了设计参考、依赖调用、随仓库分发的代码和历史实验，并记录固定版本与素材归属。

## 开发与验证

```bash
uv sync --extra download --extra asr
uv run pytest -q
```

确定性测试含真实本地 HTTP 服务与 FFmpeg；平台联网下载、实际语音模型与听感检查单独记录。[验证记录](docs/verification.md)保留各阶段结果，测试通过数和耗时属于对应运行环境。

继续阅读：[架构与数据流](docs/architecture.md) · [字幕同步](docs/subtitle-sync.md) · [声音克隆](docs/voice-cloning.md) · [IndexTTS 控制](docs/voice-controls.md)。

当前素材选择使用标签匹配；任意视频的视觉理解、交互式时间线、专门呼吸识别、完整 SSML 与自动发布尚未实现。扩展工具的高光候选按声能等指标排序，不等于理解内容；其平台检查也不替代本项目字幕同步验收。

仓库保存代码、示例、文档、锁文件和小型展示媒体；模型、缓存、上游工作区、虚拟环境和生成视频由 `.gitignore` 排除。未调用付费 API 的运行会记录 `paid_api_calls=0`，本机算力、流量和存储另有成本。
