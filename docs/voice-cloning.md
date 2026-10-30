# 使用参考录音重配旁白

语音合成默认使用 **IndexTTS-2.5**（`--tts indextts`）。先按 [安装与模型下载说明](voice-controls.md#安装与下载) 准备独立环境，再安装默认字幕需要的 [Qwen 对齐环境](subtitle-sync.md)。

```bash
uv run videocut demo \
  --reference-audio /absolute/path/reference.m4a \
  --output outputs/new-voice-run
```

不需要参考录音逐字稿。逐句生成后转换为单声道 48kHz PCM16，以实际采样数重算镜头；默认字幕由 Qwen 定位句末，并在上一句口播结束时立即显示下一句。语速、情绪和逐句拼音控制见 [完整视频配音](voice-controls.md#完整视频配音)。每次使用新的输出目录。

## 输入与生成记录

- `--reference-audio` 提供音色参考，`scenes[].lines` 提供新稿。模型实际朗读的拼音标记可通过 `index_tts.line_overrides` 指定，字幕继续使用原稿。
- `index-request.json` 保存请求；`speech/index-manifest.json` 保存参考录音、模型摘要、官方代码修订、逐句参数和音频 SHA-256。模型、参考录音或某句控制参数变化会使相应缓存失效。
- 已有逐句语音可用 `--speech-manifest /absolute/path/index-manifest.json` 复用，无需再次提供参考录音；CLI 核对提供方与音频摘要。默认字幕仍需要 Qwen 环境，或提供同一音频已核验的 `--caption-alignment`。

## 字幕与质量检查

默认整句字幕采用 `previous_speech_end`：上一句末字结束就显示下一句，供观众预读。Qwen 负责定位句末，成片由字幕逐帧与音轨同步检查验收；这不代表发音、音色或情绪已经过人工听审。

显式 `--caption-mode file` 按每句 WAV 的实际区间显示，不进入 Qwen 强制对齐验收。`caption_switch="audio_clip"` 则在 `speech` 流程中使用 PCM 区间，无需模型，仍检查实际成片。详细边界见 [字幕同步](subtitle-sync.md)。

如果输入本身就是需要保留的旁白，使用 `render --audio`；如果需要保留口播视频原声并精剪混剪，使用 `mix`。这些入口不重新合成声音，见 [使用指南](usage.md)。

## 历史 F5 实验

F5 的 `--tts clone` 和专用 CLI 参数已移除。早期安装命令、实现说明和测试媒体来源保存在 [F5 历史实验](voice-cloning-f5-history.md)，用于查阅既有结果。
