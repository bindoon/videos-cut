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

## 换成自己的内容

复制修改 `examples/coffee.json` 的标题、各镜 `lines`、素材查询标签 `query`、转场和贴纸。基础时间轴取逐句音频的真实采样数；IndexTTS 默认再按实际语音和短语边界安排字幕，不根据字数估算整句时长。

`examples/materials.json` 是素材目录。每条包括 `id`、`kind`、`filename`、`tags`，以及下载 `url` 或本地 `path`。`kind` 支持 `video`、`image`、`sticker`、`music`。本地文件同样填写 `filename`。可以用 `material_id` 在镜头中固定某条素材。

```bash
uv run videocut render --config examples/coffee.json --materials examples/materials.json --tts edge --output outputs/my-video
```

选片目前使用素材标签与查询词匹配，并对重复使用扣分。示例标签来自素材页描述；**还没有把任意上传视频自动做视觉理解**。配置中的剧本由人提供，也不会假装调用过大模型写稿。

转场可选 `fade`、`slideleft`、`slideright`、`wipeleft`、`wiperight`、`circleopen`、`dissolve`。贴纸支持透明 PNG，带淡入、缩放和浮动；不是通用 AE/Lottie 特效引擎。

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
