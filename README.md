# 视频混剪工作流

先把实际成片链路跑通：下载素材 → 逐句配音或已有录音 → 按标签选片 → 图片运镜 → 转场 → 字幕、动态贴纸、配乐 → MP4。

## 运行

需要 Python 3.12、[uv](https://docs.astral.sh/uv/) 和系统 FFmpeg。

```bash
brew install ffmpeg
uv sync
uv run videocut demo --tts macos --output outputs/coffee-local
```

默认输出 720×1280、24fps。`macos` 使用系统 Tingting 中文音色，完全本地运行。跨平台或需要在线音色时：

```bash
uv run videocut demo --tts edge --output outputs/coffee-edge
```

两种音色明确选择，不会在在线服务失败时静默替换声音。在线 Edge TTS 由第三方服务提供，演示之外的长期生产部署建议接入有服务保障的 TTS。

网络较慢时，可以先下载较小的预览素材验证流程：

```bash
uv run videocut demo --tts macos --materials examples/materials-preview.json --width 480 --output outputs/preview
```

每次运行会留下：

- `final.mp4`：H.264 / AAC 成片，字幕、转场和贴纸已经烧录。
- `captions.srt` / `captions.json`：字幕及时间轴。
- `timeline.json`：每镜素材、来源、时间、转场和贴纸。
- `sources.json`：素材下载地址、许可、大小与 SHA-256。
- `verification.json`：实际分辨率、时长、音轨、完整解码和本次处理耗时。
- `contact-sheet.jpg`：六个时间点的画面，供检查字幕、裁切与贴纸。
- `project.json`：本次配置快照。

## FFmpeg 扩展工具

项目内已固定 [ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill) 2.16.1，提供 42 个本地工具：中文字幕、画幅调整、HDR 转 SDR、音乐自动压低、多机位同步、平台导出与交付检查。无需另装全局技能或 Node 包。

```bash
# macOS：扩展工具需要包含字幕、文字和调色滤镜的构建。
brew install ffmpeg-full
uv run videocut ffmpeg doctor --json
uv run videocut ffmpeg --list
uv run videocut ffmpeg caption --help

# 将现有文件调整画幅；原文件保留。
uv run videocut ffmpeg fit input.mp4 --aspect 9:16 --fit blur -o vertical.mp4 --json-brief
```

扩展工具自动识别 Homebrew 的 `ffmpeg-full`，不需要替换全局 FFmpeg。字幕烧录、配乐、平台导出、时间线导出及使用边界见 [FFmpeg 工具说明](docs/ffmpeg-tools.md)。

若原有精简版 FFmpeg 因共享编码库升级而无法启动，执行 `brew upgrade ffmpeg` 修复兼容性，再检查 `ffmpeg -version`。

## 换成自己的内容

复制修改 `examples/coffee.json` 的标题、各镜 `lines`、素材查询标签 `query`、转场和贴纸。基础时间轴取逐句音频的真实采样数；IndexTTS 默认再按实际语音和短语边界安排字幕，不根据字数估算整句时长。

`examples/materials.json` 是素材目录。每条包括 `id`、`kind`、`filename`、`tags`，以及下载 `url` 或本地 `path`。`kind` 支持 `video`、`image`、`sticker`、`music`。本地文件同样填写 `filename`。可以用 `material_id` 在镜头中固定某条素材。

## 从视频链接导入素材

下载网页视频需要可选依赖；同时使用语音识别时保留 `asr`：

```bash
uv sync --extra download --extra asr
uv run videocut download "https://www.bilibili.com/video/BV1nx411u79K" \
  --quality edit --subtitles auto --output outputs/imported
uv run videocut render --config examples/download-demo.json \
  --materials outputs/imported/materials.json --tts macos --output outputs/from-import
```

下载目录的 `materials.json` 可直接用于现有 `render` / `mix` 素材入口；镜头可通过其中的素材 `id` 指定 `material_id`。`download-demo.json` 仅使用视频镜头，可以替换台词、增加图片或贴纸；其他配置仍需与导入素材的类型、标签匹配。下载原视频成为素材后，现有渲染器使用其画面，配音由 `--tts` 或 `--audio` 决定。

`--quality preview / edit / source` 分别选择短边不超过 360 / 720 像素或来源原始分辨率；竖屏 720×1280 也属于 720p。预览和剪辑预设优先选择 H.264，`source` 选择来源的最佳分辨率；实际编码、分辨率、时长和 SHA-256 写入结果。来源没有符合规格的格式时明确失败，可提高规格重试。文件直链按原文件导入，不执行清晰度转换。

```bash
# 多个链接可以一起下载；一个失败会保留其他成功素材，并以非零状态退出。
uv run videocut download "视频链接1" "视频链接2" --output outputs/batch
# 网页音频优先下载独立音轨，必要时由 FFmpeg 提取为 M4A。
uv run videocut download "视频链接" --mode audio --output outputs/audio-import
# 播放列表必须显式开启；默认最多 20 项，可设置本次范围。
uv run videocut download "播放列表链接" --playlist --limit 30 --output outputs/playlist
# 默认远程素材上限 1024 MiB / 整批 4096 MiB；可按需要调整。
uv run videocut download "长视频链接" --max-size-mb 2048 --max-total-mb 4096
# 只重试失败项；代理和 Cookie 如有需要需重新显式提供。
uv run videocut download --retry-failed outputs/batch/download-report.json --output outputs/retry
```

每个任务输出 `download-report.json` 与可用素材清单。网页素材按平台、视频 ID 和音频／视频／清晰度／字幕规格分别缓存；通用 HTML5 页面再按来源 URL 隔离。重跑先检查文件大小与 SHA-256；缓存损坏时重新下载。直链支持带 ETag 或 Last-Modified 的 HTTP Range 续传，网页流使用 yt-dlp 的续传和重试；Ctrl-C 后重新执行相同命令即可继续，已完成素材有独立记录。缓存锁依赖 macOS/Linux 的 `flock`。

字幕是平台提供的轨道，保留语言、来源和摘要；平台没有明确提供人工／自动属性时记录为 `unspecified`。这不会运行 Whisper，也不能替代精剪所需的逐词时间。B 站、TikTok 已实测；YouTube 可能要求登录，微信视频号目前仍不支持。可显式传 `--proxy` 或 `--cookies cookies.txt`；程序不会自动读取浏览器 Cookie。

原有 `videocut download --materials examples/materials.json` 继续可用。清单可混合本地文件、文件直链和网页视频；B 站、YouTube、TikTok 等已知域名自动识别，其他网页填写 `"source": "web"`。自定义 `id`、标签和归属信息会保留；未知许可记录为 `unknown`。远程文件完成流类型检查和完整解码后才登记，图片使用 Pillow 校验；剪辑遇到失败素材会停止，并给出失败报告。

```bash
uv run videocut render --config examples/coffee.json --materials examples/materials.json --tts edge --output outputs/my-video
```

选片目前使用素材标签与查询词匹配，并对重复使用扣分。示例标签来自素材页描述；**还没有把任意上传视频自动做视觉理解**。配置中的剧本由人提供，也不会假装调用过大模型写稿。

转场可选 `fade`、`slideleft`、`slideright`、`wipeleft`、`wiperight`、`circleopen`、`dissolve`。贴纸支持透明 PNG，带淡入、缩放和浮动；不是通用 AE/Lottie 特效引擎。

## 独立转录

`transcribe` 是独立工具：输入已有的本地音频或视频，输出文字、字幕和时间戳。完成后就结束，不自动下载、剪辑或调用大模型。

```bash
uv sync --extra asr --extra download
uv run --extra asr videocut transcribe /absolute/path/input.mp4 \
  --language auto --model base --output outputs/transcribed
```

输出 `transcript.txt`（阅读文字）、`transcript.srt`（模型估计的句段时间）、`transcript.json`（逐词时间、来源 SHA-256、模型摘要和参数）及 `transcription-report.json`（识别状态、缓存命中和文件摘要）。`--output` 不传时创建新的时间戳目录。默认自动检测语言；可显式指定 `--language zh`、`en` 等 Whisper 语言代码。模型可选 `base`、`tiny`、`small` 等名称，或本地 CTranslate2 模型目录；本地没有权重时 SDK 会准备模型，已有权重时可离线运行。

长音频默认按 600 秒分段，每侧增加 1 秒上下文。FFmpeg 只解码当前窗口，不一次把整段音频读入内存；逐词时间加上窗口偏移，再按词中点归属合并，保留原文件时间，不按相同文字删除重复说话。时间仍是 ASR 估计，分段边界和术语需要校对。可配置 `--chunk-seconds 300 --overlap-seconds 1`，重叠必须小于半段时长。

每段完成后保存校验缓存。相同输入重跑会复用已完成段，Ctrl-C 后重新执行相同命令即可继续；损坏段单独重算。来源文件内容、模型权重/配置、语言、分段参数、后端/FFmpeg 版本变化会使旧缓存失效。缓存默认 `assets/cache/transcripts`，可用 `--cache` 更改；`--force` 强制重识别。输出目录存在另一份结果或经过人工修改时会拒绝覆盖，明确需要替换才传 `--overwrite`，也可选择新目录。

静音或没有识别出文字时，独立工具返回 `status=no_speech` 并输出空文本/字幕，不会冒充成功识别到了内容。原有精剪与旁白字幕消费仍要求有效逐词时间和语音覆盖检查；两种策略复用同一份 Whisper 实现。

需要剪辑时再明确调用其他工具，例如：

```bash
uv run --extra asr videocut cut /absolute/path/input.mp4 \
  --transcript outputs/transcribed/transcript.json --output outputs/cut-from-transcript
```

剪辑复用 `transcript.json`，不重新识别。校对时复制 JSON，只改 `words[].text`，保留时间和来源校验和；TXT/SRT 不替代逐词数据。来源摘要针对输入文件本身，换容器或重编码后的文件不能直接冒用旧摘要。`--transcript` 与 Qwen 的 `--caption-alignment` 是不同协议，不能互换。

## 已有录音和口播精剪

额外安装本地语音识别和 Auto-Editor：

```bash
uv sync --extra asr
# 第一次下载 base 模型；也可显式运行下条命令预先下载并记录校验和。
uv run python scripts/fetch_asr_model.py base
uv run --extra asr videocut render --audio /absolute/path/voice.wav --model base --output outputs/from-audio
uv run --extra asr videocut cut /absolute/path/talking.mp4 --fillers 嗯 呃 那个 就是说 --breath-gate --output outputs/cleaned
```

`render --audio` 保留现有声音，以实际识别结果做字幕，并按实际语句边界分配镜头；字幕不是把给定剧本硬贴到不一致的音频上。它不等于声音复刻。

要用参考录音的音色朗读新稿，在 Apple Silicon 上使用本地 F5-TTS：按 [声音克隆说明](docs/voice-cloning.md) 安装独立模型环境，然后运行 `videocut demo --tts clone --reference-audio /absolute/path/reference.m4a --output outputs/new-voice-run`。请使用新的输出目录保留之前的测试结果。

也可以选择 IndexTTS-2.5 生成完整视频。按 [安装与模型下载说明](docs/voice-controls.md#安装与下载) 准备独立环境和本地权重后运行：

```bash
uv run --extra asr videocut demo --tts indextts \
  --reference-audio /absolute/path/reference.m4a \
  --output outputs/new-index-video
```

IndexTTS 不需要参考录音逐字稿；逐句语音会先转换为剪辑器要求的单声道 48kHz PCM16，再重算字幕和镜头时间。默认自然语气；语速、情绪向量、逐句随机种子及原生拼音标注可在配置的 `index_tts` 中指定，见 [完整视频配音](docs/voice-controls.md#完整视频配音)。

IndexTTS 默认使用 `--caption-mode speech`，整句显示，并在上一句口播结束时立即显示下一句供预读：`caption_layout="utterance"`、`caption_switch="previous_speech_end"`。Qwen 定位每句末字结束，字幕跨过句间留白连续显示；不改声音。显式 `caption_switch="audio_clip"` 可按本句 WAV 起止显示而不加载模型；`caption_layout="phrases"` 或 `subtitle_phrases` 可主动拆条。所有模式都直接读取 SRT 渲染并检查成片。配置和安装见 [字幕同步工作流](docs/subtitle-sync.md)。

已另行实测 IndexTTS-2.5 的参考音色、语速、情绪向量和中文拼音控制。完整下载、XML 示例、支持范围和 7 组实测试听见 [语音控制与 SSML 实验](docs/voice-controls.md)。它使用 Python 3.11 的独立 `.venv-index`，依赖记录在 `requirements-index.lock.txt`；实验脚本为 `scripts/test_indextts_controls.py`。备好 `upstream/index-tts-reference` 官方代码及 `assets/models/IndexTTS-2.5` 本地模型后，可生成新的短句对照：

```bash
uv venv --python 3.11 .venv-index
uv pip install --python .venv-index/bin/python -r requirements-index.lock.txt
PYTORCH_ENABLE_MPS_FALLBACK=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  .venv-index/bin/python scripts/test_indextts_controls.py \
  --reference /absolute/path/reference.m4a --output outputs/new-control-test
```

短句脚本中的 SSML 实验适配层支持 `speak`、`break time`、中文 `phoneme alphabet="py"` 及 `sub alias`；后者只验证了转换，未纳入本次语音样例。停顿通过音频拼接插入，拼音转为官方发音标记。`w`、`emphasis`、情绪标签及未知属性会报错，不会静默当作支持。适配层插入的静音时长与人感知的总停顿可能有差别。完整视频提供方已支持 IndexTTS 原生语音参数，尚未接入这层 SSML 适配器。

如果输入本身就是口播视频，一条命令串起“精剪 → 原视频和素材穿插 → 字幕、转场、贴纸和音乐”：

```bash
uv run --extra asr videocut mix /absolute/path/talking.mp4 --fillers 嗯 呃 那个 就是说 --breath-gate --output outputs/mixed
```

`mix` 保留精剪后的原声，字幕复用真实 ASR 结果并重排时间，不重复识别。镜头交替使用原始视频和素材；原始视频按相同的音频时间定位，避免每个镜头都从原片开头重放。原片中的人声不再重复混入。

字幕有同音字错误时，复制 `cleaning/transcript.json`，只修改 `words[].text`，保留时间和文件校验和，再复用识别结果重剪；不用每次重跑模型：

```bash
uv run --extra asr videocut mix input.mp4 --transcript corrected-transcript.json --fillers 嗯 呃 那个 就是说 --output outputs/reviewed
```

给定文件会在报告中标记为 `transcript_source=provided`。本地识别默认使用 base；`--model tiny` 更轻但容易同音字误识别，`--model small` 更重。有声片段完全没有识别结果时会报错，不能把导出成功当作识别正确。字幕仍应校对。

`cut` 真正执行：faster-whisper 逐词识别 → FFmpeg 静音检测 → 配置词匹配 → 统一按视频帧切音画 → 降噪 → 重排字幕时间。输出 `cleaned.mp4`、`cleaned.srt`、原始 `transcript.json` 和可审计的 `edit-plan.json`。字幕为旁挂 SRT；如果要混入图片、转场和贴纸，再把精剪后的音频交给 `render --audio`。

默认只删 `嗯 / 呃 / um / uh`，不会默认删除有语义的“然后”“那个”。只有 ASR 识别到且有完整时间戳的配置词才会切掉；识别模型可能漏掉口头禅。`--breath-gate` 是轻度噪声门，不是已验证的专门呼吸识别模型，也不能保证去掉所有气口。

直接调用上游 Auto-Editor 做静音粗剪：

```bash
uv run --extra asr videocut rough-cut input.mp4 --output outputs/auto-editor.mp4
```

可控的精剪实跑素材（下载的咖啡画面 + 合成中文旁白，刻意加入停顿和口头禅）：

```bash
uv run videocut raw-sample --tts macos
uv run --extra asr videocut mix outputs/raw-sample/raw.mp4 --fillers 嗯 呃 那个 就是说 --output outputs/mixed
```

`ground-truth.json` 仅用于事后比较，绝不交给识别或剪辑程序冒充识别结果。

## 开源基础和验证

工作流参考 MoneyPrinterTurbo；实际执行使用 MoviePy、FFmpeg、Edge TTS、faster-whisper 和 Auto-Editor。版本、职责和来源见 [docs/open-source.md](docs/open-source.md)，素材来源见 [examples/materials.json](examples/materials.json)。不需要把整个 MoneyPrinterTurbo WebUI 及所有供应商依赖装进来。

```bash
uv run pytest -q
```

测试覆盖删除区间合并、剪后时间映射、口头禅不误匹配单词子串，以及真正调用 FFmpeg 的音画同步与字幕重排。模型识别与成片质量另看实际运行报告，不能用单测代替。

未使用付费 API 的实跑，报告会写 `paid_api_calls=0`；本机算力、下载流量和存储仍有成本，不能把它们说成完整生产成本为零。

Git 保存代码、测试、示例配置、文档、下载脚本和依赖锁文件。可重新下载的模型权重、素材缓存、上游源码、虚拟环境及生成视频由 `.gitignore` 排除；忽略规则不会删除本机文件。模型版本与下载方式保留在文档和脚本中，换机按对应安装说明恢复。
