# 固定字幕分条与音频同步

[文档导航](README.md) · [使用指南](usage.md) · [AI 操作指南](ai-guide.md)

本文描述 `--caption-mode speech` 的生成旁白流程。IndexTTS 默认启用；Edge 和 macOS 需要显式选择。普通 `file` 模式与已有录音的 ASR 字幕不自动进入该强制对齐验收。

## 当前规则

先确定每屏字幕文本，再选择显示时机。默认整句显示，切换规则为“一句话口播结束，立刻显示下一句话”，供观众预读，不再等待下一句音频文件起点。

```text
口播稿、分条、切换规则 → caption-plan.json（固定）
  previous_speech_end → Qwen 找每句末字结束 → 上句结束立即换下一条
  audio_clip         → 直接按 WAV 采样区间显示（兼容旧规则）
  显式句内拆条       → Qwen 找每条起点，保留阅读提前量
                                    ↓
                       SRT → 回读渲染 → 全部成片帧验收
```

- 默认 `caption_layout="utterance"`、`caption_switch="previous_speech_end"`。首屏从 0 秒显示；后续整句字幕从上一句末字结束时显示。声学边界使用已有 Qwen 对齐，缓存可复用，不改声音。
- 相邻字幕的结束和开始为同一个时间点，最后一条保持到视频结束。字幕贯穿句间留白，不能出现空白帧。
- `caption_switch="audio_clip"` 恢复一条字幕绑定自己 WAV 的完整区间，包含首尾留白；这个模式不运行对齐模型，但下一条要等到下一个文件起点才显示。
- 显式 `caption_layout="phrases"` 或 `subtitle_phrases` 才进行句内拆条；其默认切换规则仍为 `audio_clip`，按首字起点减 200ms 阅读提前量，不能越过上一条末字结束。拆条不能同时要求跨句的 `previous_speech_end`。
- 固定分条不能由算法临时合并。`captions.srt` 是渲染的唯一时间输入。

“上一句结束立刻预读下一句”允许字幕出现在自身音频开始之前。审计明确记录 `switch_at`（上一句末字结束）和本句真正音频起点，不能把二者混称为音轨偏移。模型时间仍有估计误差；当前 Qwen 模型刻度为 80ms，SRT 的毫秒精度不代表毫秒级声学准确度。

## 明确指定字幕分条

配置保留原口播稿，另可添加：

```json
{
  "caption_layout": "phrases",
  "caption_switch": "audio_clip",
  "subtitle_phrases": {
    "喜欢清爽，就喝一口黑咖啡。": ["喜欢清爽", "就喝一口黑咖啡"]
  },
  "caption_lead_seconds": 0.2
}
```

每条字幕连接后的文字必须与口播稿一致，允许标点差异。不能漏字、增字、调换顺序；字幕边界不得切进一个模型返回的完整词。需要整句显示时必须在这里明确指定单条，不能由对齐算法自行决定。提前量允许 0～250ms；它是阅读参数，原始字词时间另存，不能修改原始对齐记录来伪装准确。

## 口播结束检测与拆条对齐的安装

默认“上一句结束即切换”以及句内拆条需要以下环境；显式 `caption_switch="audio_clip"` 不需要模型。

口播结束检测和拆条模式使用 [Qwen3-ForcedAligner](https://github.com/QwenLM/Qwen3-ASR) 官方 `Qwen3ForcedAligner.align(audio, text, language)` 接口，直接输入原稿和已有 WAV，不再做自由转写，也不再用能量阈值猜句内分界。代码在 `scripts/align_qwen.py`，独立环境避免改动 IndexTTS 的依赖。

```bash
uv venv --python 3.11 .venv-align
uv pip install --python .venv-align/bin/python -r requirements-align.lock.txt
uv run python scripts/fetch_clone_model.py \
  --repo Qwen/Qwen3-ForcedAligner-0.6B \
  --output assets/models/Qwen3-ForcedAligner-0.6B \
  --include '*.json' '*.safetensors' '*.txt' \
  --mirror-repo-url https://modelscope.cn/models/Qwen/Qwen3-ForcedAligner-0.6B
```

模型修订 `c7cbfc2048c462b0d63a45797104fc9db3ad62b7`，权重 SHA-256 `47831d0e82f96b20e9034dba01a075ee06436654719f6a68289e49f1b65ce0e7`。实际安装 `qwen-asr==0.0.6`、`transformers==4.57.6`、`torch==2.8.0`，CPU float32。缓存键包含模型配置、权重、分词文件的摘要及音频摘要、原稿；命中缓存不加载模型。

## 一条命令执行

新配音：

```bash
uv run videocut demo --tts indextts \
  --reference-audio /absolute/path/reference.m4a \
  --output outputs/new-fixed-lines
```

复用原来的配音与背景、只重新制作字幕：

```bash
uv run videocut demo --tts indextts \
  --config outputs/coffee-indextts25-20261024-213812/input-config.json \
  --speech-manifest outputs/coffee-indextts25-20261024-213812/speech/index-manifest.json \
  --background outputs/coffee-indextts25-20261024-213812/background.mp4 \
  --output outputs/my-next-fixed-lines
```

可用 `--alignment-python`、`--alignment-model` 指定环境与模型；`--caption-alignment` 只接收同一音频的新 `qwen-alignment.json`。旧 `ctc-alignment.json`、自由转写报告必须重新对齐。已有 `final.mp4` 的目录不可覆盖。

## 验收与排查

`caption-plan.json` 定义条数和内容。显式整句 `audio_clip` 的 `caption-alignment.json` 为 `pcm-caption-v1`，只保存真实音频片段边界，不把它伪装为模型发声边界。默认整句 `previous_speech_end` 与显式拆条都使用 Qwen：`qwen-alignment.json` 保存原始字词时间，`caption-alignment.json` 以 `qwen-forced-v1` 保存片段偏移、显示时间及策略。`subtitle-sync-verification.json` 保存实际视频帧与音轨检查。

1. SRT 条数与文字必须完全符合固定计划；渲染输入必须与落盘 SRT 一致。
2. `previous_speech_end` 模式：真实显示应在上一句末字结束的一帧范围内切换，全部成片帧均须有字幕；相邻字幕无空白、无重叠，最后一条到视频结束。
3. `audio_clip` 模式：每条字幕的真实起止应在对应音频文件起止的一帧范围内。
4. 显式拆条模式：首条绑定当前音频片段起点，后续按字词起点及阅读提前量检查。
5. 核对最终混音与旁白的时间偏移。任一失败保留候选和失败报告，不交付 `final.mp4`。

普通 `file` 字幕模式与已有音频自由识别模式不宣称通过上述强制对齐验收。检测器针对当前固定字体、位置和颜色；修改样式需同步调整检测器。

此前双模型分歧时合并整句的实现已移除。它违背“一行一行切换”的展示合同；“按模型时间渲染正确”也不能单独证明字幕跟随感正确。旧视频和审计保留为历史记录。

## 首版与 IndexTTS 的控制对比

首版 Edge 使用 12 条整句字幕，并按每个 WAV 的真实采样数计时；后来同时更换声音和拆成 23 条，混入了两个变量。对同一份 IndexTTS 配音对比整句和拆条，前者从 0 秒已经显示“不必一开始就匆忙”，后者到 0.960 秒才显示；“留一杯咖啡的时间”相差 2.040 秒。这个差异属于文字提前可读的时间，不应直接认定为音轨错位。

上一轮恢复了整句显示，但仍绑定本句音频起点；用户进一步明确需要“上一句口播结束即换下一条”，当前默认已改为 `previous_speech_end`。保留 IndexTTS 音色，显式拆条继续使用 Qwen。两种模式都按 SRT 渲染并检查编码帧。整句模式没有逐字跟随的声明；默认仍需 Qwen 定位上一句结束，不计算整句内部逐字显示。
