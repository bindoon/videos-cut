---
name: video-workflow
description: 使用本项目 CLI 完成本地剧本出片、原声口播精剪与混剪、下载和转录衔接，以及旁白和字幕复用。用于需要组织多个视频工具并检查成片的任务；只需单步后期时使用 ffmpeg-skill，代码动画和小红书图文使用对应专门技能。
---

# 本地视频制作工作流

从仓库根目录运行命令。先读 `AGENTS.md`；参数和配置合同见 [使用指南](../../docs/usage.md)。本技能随本仓库使用，不是独立安装后即可运行的视频工具。

## 1. 阅读与路由

先读根目录 `AGENTS.md`，然后选择最短的已有处理路径：

| 请求 | 入口 | 需要补读 |
| --- | --- | --- |
| 网页或直链素材 | `videocut download` | [使用指南：导入素材](../../docs/usage.md#从视频链接导入素材) |
| 通用候选帧、字幕区域、文字索引或图卡 | `videocut images sample / band / index / plan / render / verify` | [通用图像工具](../../docs/image-tools.md) |
| 小红书访谈截图/字幕图文 | 阅读项目内 `xiaohongshu-quotes` 技能，再组合通用工具 | [场景技能](../xiaohongshu-quotes/SKILL.md) |
| 微信视频号 | `download --wechat-list` → 核对标题/作者 → `download URL --wechat-feed-id ID` | [视频号本地服务](../../docs/usage.md#微信视频号) |
| 只有本地转录 | `videocut transcribe` | [独立转录](../../docs/usage.md#独立转录) |
| 删除长停顿、口头词 | `videocut cut` | [已有录音和精剪](../../docs/usage.md#已有录音和口播精剪) |
| 精剪后加素材与包装 | `videocut mix` | 同上 |
| 自己的剧本和素材 | `videocut render --config ...` | [配置和素材](../../docs/usage.md#换成自己的内容) |
| 从需求规划并生成素材 | 宿主写计划/生图 → `videocut prepare` → `render` | [宿主创作与素材交接](../../docs/usage.md#宿主-agent-创作与本地素材交接) |
| 保留已有旁白 | `videocut render --audio ...` | [已有录音和精剪](../../docs/usage.md#已有录音和口播精剪) |
| 默认 IndexTTS-2.5 参考音色与控制 | `render --reference-audio ...`（等同 `--tts indextts`） | [IndexTTS 控制](../../docs/voice-controls.md)、[字幕同步](../../docs/subtitle-sync.md) |
| 调整画幅、调音、字幕烧录、导出 | `videocut ffmpeg TOOL` | 项目内 [ffmpeg-skill](../../.agents/skills/ffmpeg-skill/SKILL.md)、[工具接入说明](../../docs/ffmpeg-tools.md) |
| 城市白模、数据图解等代码视频 | `videocut codefilm plan / stills / render / verify` | [代码视频技能](../codefilm-workflow/SKILL.md)、[杭州范例](../../films/hangzhou/README.md) |
| 修改项目实现 | 先追踪对应模块和测试 | [架构](../../docs/architecture.md)、[验证记录](../../docs/verification.md) |

本项目提供执行工具，AI 负责理解意图、编写剧本、挑选画面和组织命令。项目没有内置自由调用大模型写稿的服务，也没有任意视频的视觉自动打标。

能力按[工具、技能、作品](../../docs/capabilities.md)分层。新平台的选题、文案和排版习惯放在场景技能/模板；通用抽帧、图卡、缓存和校验放在 `images`。原生字幕的文字只来自真实帧像素，脚本字幕必须记录校对声明和来源；下载轨/ASR 只作定位时，不能声称它们是画面原字幕。图片 `mechanical_passed` 不是语义或声学字幕验收，完成后仍需查看每张实际成品。

### 本地优先的创作流程

1. 使用当前宿主 Agent 写稿、分镜和生图提示词，按 `examples/creation-plan.json` 写本地计划。区分旁白、画面提示词与发布文案，不把生成指令混入朗读内容；参考图、风格描述可以复用，但不承诺跨镜人物自动一致。
2. 优先复用用户已有素材和本地工具；需要新图片时使用宿主已有生图能力。调用前遵循宿主的图像工具与技能要求，本项目不另外调用写稿/生图 API。宿主无此能力时明确说明缺项，不自动切到收费服务。
3. 执行 `prepare`，读取 JSON 状态和 `asset-requests.json`。退出码 2 的 `pending` 是等待素材的正常交接。生成前先补齐 `missing_references`，透明贴纸传透明背景参数；把实际文件放到请求路径，或更新原计划的 `path`。在 `generation` 中只记录已知工具和模型信息。
4. AI 视频不是每个镜头的必需品；照片运镜或已有视频能满足时直接使用。确实需要生成式 AI 视频时保留 `external_video` 请求，明确外部工具与费用选择后再执行，不能用静态图冒充已生成的视频，也不能自动调用付费服务。
5. 用新的输出目录重新 `prepare`。只有 `ready` 才读取生成的 `project.json/materials.json` 进入现有渲染；默认使用 IndexTTS-2.5 并提供参考录音；先确认模型及 Qwen 对齐环境可用。不要按字数估计最终镜头时间，仍由实际音频建立时间轴。
6. 检查真实成片与原有验收报告。浏览器发布作为用户另行指令下的后续工具操作；当前 CLI 没有自动发布入口。

`creation-report.json.execution` 仅统计准备命令自身的模型/网络调用，不能据此声称宿主生图或后续配音也离线、免费。宿主的可用能力依当前会话判断，不假定所有 Codex、WorkBuddy 环境都提供生图工具。

## 2. 检查输入和环境

代码视频先读 [code-films.md](../../docs/code-films.md)，用 `codefilm plan` 检查真实输入，再做 `stills` 和局部预览；检查实际截图后才全片渲染。每次明确 `--output`，把字体、模型、时间轴和依赖锁列入配置 `sources`。完整交付前运行 `codefilm verify`；局部预览只能显式 `--allow-partial` 检查。它的帧数、格式、摘要检查不代表字幕声学同步通过，最终声音和字幕另验。不要将不同源码版本的镜头缓存手工拼成全片。

```bash
uv run videocut --help
uv run videocut render --help
uv run videocut ffmpeg probe /absolute/path/input.mp4 --json
```

只探测本次规划需要的输入，记录真实时长、宽高、帧率、HDR 信号和音轨。输出目录使用本次新路径；不要把输入、旧成片或人工校对文件作为新输出。

- 基础混剪：`uv sync`。下载网页加 `--extra download`，转录和精剪加 `--extra asr`；两个都需要时用 `uv sync --extra download --extra asr`。
- macOS 系统声音为 `--tts macos`；在线声音为 `--tts edge`，不会在服务失败时静默切换声音。
- 语音合成默认使用 IndexTTS-2.5，需要 `--reference-audio`；已移除 F5 的 `--tts clone` 及专用参数。IndexTTS 和 Qwen 分别有 `.venv-index`、`.venv-align`；先按专项文档确认已安装，不把模型包装进主环境。
- 检查配置的图片/视频镜头能在素材目录中匹配。素材 `path` 优先使用绝对路径，标签由调用者提供；要固定画面可使用 `material_id`。
- 独立 FFmpeg 操作按技能使用 `videocut ffmpeg`。先读实际工具的 `--help`；失败提示缺少媒体能力时，再用 `doctor --json` 定位。预演使用 `--dry-run --json`，其具体行为见工具说明。
- 视频号需要外部 `wx_channels_download` 服务和微信播放。先只读查询捕获记录并核对目标，再明确指定 ID；不能以最近一条代替匹配。服务未准备好时返回具体失败原因。证书/代理设置需按用户授权单独处理，并记录和恢复；下载命令自身不会操作这些设置。实测文件尺寸才是画质证据。

## 3. 用文件连接工具

### 下载 → 混剪

```bash
uv sync --extra download --extra asr
uv run videocut download 'https://www.bilibili.com/video/BV1nx411u79K' \
  --quality edit --subtitles auto --output outputs/my-import
uv run videocut render --config examples/download-demo.json \
  --materials outputs/my-import/materials.json --tts macos --output outputs/my-import-film
```

下载后先读 `download-report.json` 和 `materials.json`。批次非零退出可能已有成功素材；核对失败项与成功项，再决定是否能继续目标任务。平台字幕保留来源，未明确说明生成方式时为 `unspecified`。

### 转录 → 校对 → 精剪

```bash
uv run --extra asr videocut transcribe /absolute/path/talking.mp4 \
  --language zh --model base --output outputs/my-transcript
cp outputs/my-transcript/transcript.json outputs/my-corrected-transcript.json
# 校对副本中的 words[].text；不改时间、顺序和来源摘要。
uv run --extra asr videocut cut /absolute/path/talking.mp4 \
  --transcript outputs/my-corrected-transcript.json \
  --fillers 嗯 呃 --output outputs/my-cleaned
```

校对必须依据实际录音；识别结果不是用户预先给出的剧本。`transcript.json` 只能复用于同一输入文件，换容器或重编码后不能沿用其来源摘要。`mix` 同样支持 `--transcript`，复用后会按剪辑区间重排字幕，不重复识别。

### 复用旁白与背景 → 只改字幕

先复制上次的 `project.json` 并修改字幕配置。假设上次使用 IndexTTS、整句字幕：

```bash
uv run videocut render --tts indextts \
  --config projects/revised-captions.json --materials examples/materials.json \
  --speech-manifest outputs/previous/speech/index-manifest.json \
  --background outputs/previous/background.mp4 \
  --output outputs/revised-captions
```

这里的 `previous` 是已有结果目录占位符。原稿与配音清单必须匹配，背景宽高和总时长必须兼容；更换稿子、配音或镜头安排时不要直接复用旧背景。默认句末切换仍需要 Qwen 环境，或显式提供同音频的 `--caption-alignment .../qwen-alignment.json`。

## 4. 三种时间数据不要混用

| 数据 | 代表什么 | 正确用途 |
| --- | --- | --- |
| 下载的字幕轨 / SRT | 来源平台提供的字幕与时间 | 保留语言和来源，按需展示或后期烧录 |
| `transcript.json` | faster-whisper 的识别文字与估计词时间 | `cut / mix / render --audio` 的 `--transcript` |
| `qwen-alignment.json` | 给定原稿与同一音频的强制对齐记录 | 生成配音的 `--caption-alignment` |

`transcribe` 的 `no_speech` 是有效独立结果；编辑器需要足以剪辑的词时间，不能为让剪辑成功而伪造词记录。ASR 文字仍需校对。

字幕模式也要区分：IndexTTS 默认启用 `speech`；Edge、macOS 默认按 WAV 区间显示，需显式 `--caption-mode speech` 才进入对齐流程。默认整句 `previous_speech_end` 提前展示下一句是预读策略；显式 `audio_clip` 按当前 WAV 区间显示，显式拆条按固定文本对齐。不要以“模型分歧”为由自行合并用户确定的分条。

## 5. 交付前检查

依据本次命令读取相应产物：

| 任务 | 要检查的文件或结果 |
| --- | --- |
| 下载 | `download-report.json`、素材清单、失败项与实际流信息 |
| 转录 | `transcription-report.json`、TXT/SRT/JSON、语言、状态、来源摘要和缓存统计 |
| 精剪 | `cleaned.mp4`、`cleaned.srt`、`transcript.json`、`edit-plan.json` 的删除理由与时间区间 |
| 混剪 | `final.mp4`、`verification.json`、`timeline.json`、`sources.json`、`contact-sheet.jpg` |
| 语音对齐字幕 | 另看 `caption-plan.json`、实际 SRT、`caption-alignment.json` 和 `subtitle-sync-verification.json` |
| FFmpeg 后期 | 工具 JSON、实际输出探测与画面；平台交付时再运行对应 `check` |

打开真实截图，核对文字可读性、裁切、贴纸、转场附近画面；涉及声音时播放检查。机器验收不等于听感、语义和素材选择已经通过人工评审。无播放条件时要说明听感尚未检查。

`final.mp4` 存在不代表所有字幕模式都通过强制对齐验收。看 `verification.json` 的 `subtitle_sync`；未做验收时 `passed=null`。独立 FFmpeg 的 `verified`、`check` 和录音 `sync` 均不等于本项目 `videocut/sync.py` 的字幕与音轨门禁；后期产生的新文件也不自动继承旧报告。

最终简要交付：成片或文本路径、真实参数、检查过的截图、报告路径、保留的未决问题。耗时说明是否命中缓存，不把下载、首次模型加载等未计入项目说成已包含。
