# 使用参考录音重配旁白

当前有两条参考音色路径：`--tts clone` 使用 F5-TTS；`--tts indextts` 使用 IndexTTS-2.5 并复用同一条完整视频渲染流程。IndexTTS 的短句控制实验、安装、XML 示例与完整视频用法见 [voice-controls.md](voice-controls.md)。SSML 适配器目前只在短句实验中使用。

原来的咖啡稿、素材、字幕、转场与贴纸继续复用，按参考录音的音色生成新的语音。不会把参考录音的原话直接循环铺到旧视频上。

本地使用 [F5-TTS](https://github.com/SWivid/F5-TTS) 的 [MLX 实现](https://github.com/lucasnewman/f5-tts-mlx)，加载 v1 4-bit 权重和 Vocos 解码器，在 Apple Silicon 上运行。参考音频与生成都留在本机；网络只用于下载开源依赖和模型。该运行时与剪辑运行时隔离，避免语音模型依赖影响已经验证的剪辑依赖。

```bash
uv venv --python 3.12 .venv-voice
uv pip install --python .venv-voice/bin/python -r requirements-voice.lock.txt
uv run python scripts/fetch_clone_model.py --repo lucasnewman/f5-tts-mlx \
  --output assets/models/F5-TTS-MLX --include model_v1_4b.safetensors vocab.txt
uv run python scripts/fetch_clone_model.py --repo lucasnewman/vocos-mel-24khz \
  --output assets/models/vocos-mel-24khz --include model.safetensors config.yaml
uv run --extra asr videocut demo --tts clone \
  --reference-audio /absolute/path/reference.m4a \
  --output outputs/new-voice-run
```

必须为每个要保留的结果使用不同的 `--output`。参考文本默认用本地 base 模型识别，也可以通过 `--reference-text '录音逐字稿'` 指定。参考文本必须对应录音本身，不能填视频要说的新稿子。

`clone-request.json` 记录本次请求；`speech/clone-manifest.json` 记录模型和参考音频 SHA-256、参考文本、逐句生成时长及输出校验和。缓存同时考虑模型、参考声音和参考文本，不能把另一种声音的缓存当作当前结果。

逐句生成后，合并真实 PCM 音频并重算字幕和镜头时间；随后沿用同一条素材合成与验证流程。参考声音决定的新语速可能让视频总时长发生变化。

首次需下载约 287 MB 的模型权重和解码器。模型固定到 Hugging Face 修订，按官方 LFS SHA-256 验证；支持中断续传和 HTTP Range 下载。逐句语音以真实采样数重排字幕；F5 的生成时长使用上游文本与参考录音比例估算，不额外下载时长预测模型。

本次用户录音的成片单独放到 `outputs/coffee-qianchen-<时间戳>/`。开始前保存旧结果 SHA-256 清单，结束后重新核对；不会覆盖旧测试视频或报告。

## 从参考录音到新旁白

这条路径使用预训练模型进行参考条件生成，没有针对用户录音重新训练专属模型，也没有单独提取并保存一个可替代参考录音的“声纹文件”。

1. 用本地 faster-whisper 识别参考录音的逐字稿；也可以显式提供准确的 `--reference-text`。
2. FFmpeg 将参考音频转为单声道 24kHz WAV，做 60Hz 高通过滤，并在模型输入侧调整过低的 RMS 音量。原始录音不修改。
3. 每句咖啡稿分别与参考音频、参考逐字稿一起输入 F5；使用文本/参考录音比例估算时长、32 步 Euler 采样和记录在清单中的随机种子。
4. Vocos 还原音频波形，裁去对应参考录音的前段，仅保留新稿。每句统一到单声道 48kHz PCM16，并进行响度处理。
5. 本次生成后，另用不带初始提示词的 ASR 核对实际内容，保存原始识别结果。这个内容核对步骤是本次验收脚本执行的，不是 `videocut --tts clone` 内置的强制质量门禁；它也不能代替音色和自然度试听。

## 音频如何决定字幕和画面

F5 默认模式的字幕文字来自已知口播稿，显示起止时间按各句 WAV 的真实采样数累计。每句合并后加入 0.12 秒间隔，末尾另加 0.5 秒。它是逐句文件时间轴，没有精确到逐字发音边界；文件首尾静音也会被计入显示时长。可显式选择 `--caption-mode speech` 进行语音短语对齐，IndexTTS 目前默认采用该模式，详见 [字幕同步修复](voice-controls.md#字幕同步修复)。

镜头分组与素材关键词来自脚本配置；两句旁白组成的镜头，展示时长等于这两句音频加句间隔。图片生成缓慢推近效果，视频过长截取、过短循环；选片仍是素材标签匹配。转场另预留重叠画面，字幕在背景转场完成后叠加。

本次成片的前几句实际为：

| 时间 | 台词 | 画面 |
| --- | --- | --- |
| 0.000～4.565s | 早晨，不必一开始就匆忙。 | 咖啡图片 |
| 4.685～9.997s | 先给自己，留一杯咖啡的时间。 | 同一张图片继续运镜 |
| 10.117～14.683s | 从一把新鲜的咖啡豆开始。 | 咖啡豆视频；此镜头从 10.117s 开始 |

换声音会改变实际语速，因此应重算字幕和镜头时长，不能直接复用上一版的时间点。

## 停顿控制与质量边界

0.12 秒是程序插入的**句间**间隔；一句内部的停顿由 F5 生成，调小这个间隔不能修复“黑……咖啡”。参考录音节奏、时长估算、标点和随机采样都可能影响句内表达；本实现没有 SSML、词级重读或词级情绪控制接口。

本次 F5 在“黑咖啡”中出现过不自然停顿，ASR 仍能识别出正确文字，说明“文字读对”不足以证明语音质量。处理这类问题应结合目标词附近的停顿检查与试听，再考虑重生成该句、调整目标时长或谨慎编辑确认没有发音的间隔。后续 IndexTTS 对照的实测结果见 [语音控制实验](voice-controls.md#实测结果与试听)。

## 本次成片记录

- [成片](../outputs/coffee-qianchen-20261024-194215/final.mp4)、[单独旁白](../outputs/coffee-qianchen-20261024-194215/narration.wav)。
- 60.830 秒、720×1280、H.264/AAC，6 镜头、12 句字幕、6 个贴纸、5 次转场，完整解码通过。
- [机器报告](../outputs/coffee-qianchen-20261024-194215/verification.json)记录合成流程 74.32 秒；这次运行命中了已生成的克隆旁白缓存，不包含首次模型下载及逐句声音生成耗时。
- [旧结果核对](../outputs/coffee-qianchen-20261024-194215/previous-results-verification.json)：此前 268 个输出文件保持不变。

这些媒体和机器报告位于本地忽略的 `outputs/`，换机或只复制代码时不会自动带上。
