# 混剪运行方式

本地 CLI 项目，不依赖数据库或云端任务服务。

```text
脚本 + 素材目录 → 配音/字幕时间轴 → 选素材 → 画面和转场 → 叠字幕/贴纸/配乐 → 成片
原始口播视频 → 真实 ASR → 删停顿/配置词 → 精剪视频 + 重排词时间轴 → 同一条混剪管线
参考录音 + 对应文字 + 新稿 → F5-TTS/Vocos → 48kHz 逐句 WAV → 同一条混剪管线
参考录音 + 新稿 + 原生控制参数 → IndexTTS-2.5 → 22.05kHz WAV → 48kHz 逐句 WAV → 同一条混剪管线
参考录音 + 控制样例 → IndexTTS-2.5 / SSML 实验适配层 → 独立音频对照与验收
```

## 数据与边界

- **素材**：`examples/materials*.json` 描述来源、类型、标签。下载在 `assets/cache`，生成 SHA-256。也支持用户本地文件。
- **脚本**：`examples/coffee.json` 包含标题、逐镜台词、素材查询、画幅与效果配置。
- **字幕**：基础时间轴按真实 PCM 采样数累计；IndexTTS 默认整句显示，上一句末字结束时立即切换到下一句，跨过句间留白供预读；显式 audio_clip 才绑定 WAV 区间。字词和句末由 Qwen 定位，不能在异常时改分条。已有录音按实际 ASR 时间戳定时，报告不把它标为通过强制对齐验收。
- **时间轴**：`outputs/<name>/timeline.json` 是该成片实际使用的镜头、素材、时间、转场、贴纸。不是只保留一段不可检查的自然语言提示词。
- **精剪计划**：`edit-plan.json` 保存识别后的删除理由、删除区间、保留区间和重排后的词时间。

## 模块

| 文件 | 职责 |
| --- | --- |
| `videocut/cli.py` | 串起 `demo / render / mix / cut / rough-cut` 命令 |
| `videocut/assets.py` | 下载、来源记录和标签选片；不做未接入的视觉模型理解 |
| `videocut/speech.py` | 明确选择 Edge/macOS 配音或读取克隆语音，按 WAV 采样数输出逐句字幕 |
| `videocut/captions.py` | 固定展示计划；整句使用 PCM 片段边界，显式拆条使用 Qwen 字词时间；校验音频摘要 |
| `scripts/align_qwen.py` | 独立 `.venv-align` 环境调用 Qwen3ForcedAligner；缓存给定原稿的字词起止时间和完整模型摘要 |
| `videocut/sync.py` | 检查所有成片帧里的字幕字形、出现/消失时间，并对比编码前后的语音波形；失败阻止交付 |
| `scripts/clone_narration.py` | 独立 MLX 环境加载 F5-TTS 和 Vocos，参考录音生成新稿；保留逐句模型、输入和音频校验和 |
| `scripts/index_narration.py` | 独立 PyTorch 环境生成 IndexTTS-2.5 逐句旁白，转换到 48kHz；记录参考音频、模型、代码修订、逐句参数及缓存校验和 |
| `scripts/test_indextts_controls.py` | 独立 PyTorch 环境生成 7 组控制样例，转换部分 SSML，记录片段/停顿时间及校验和；SSML 适配器尚未接入视频 CLI |
| `scripts/fetch_clone_model.py` | 固定模型元数据修订、分片续传、核对摘要；可从镜像下载相同内容 |
| `videocut/cleaning.py` | faster-whisper、静音定位、完整词匹配、帧对齐音画裁切和字幕重排 |
| `videocut/render.py` | FFmpeg 运镜/转场，MoviePy 图层合成，音量标准化与完整解码验收 |
| `videocut/media.py` | 有超时、检查退出码的进程调用与 ffprobe |

`mix` 使用同一份剪后音频时间轴：原视频镜头从对应时间截取，插入素材时只替换画面。不会把原片声音和旁白重复播放。字幕图层在背景转场之后叠加，避免两条字幕跟着转场重影。

生成配音先冻结 `caption-plan.json`。默认 `previous_speech_end` 使用 Qwen 的末字结束时间切换到下一句，保持相邻字幕无缝连接，末条到视频结束；这是预读策略，审计同时记录切换时刻与本句实际音频起点。显式 `audio_clip` 直接使用 WAV 采样区间，无需模型；显式拆条使用首字时间和阅读提前量。所有模式写出 SRT 后重新读取它作为渲染时间轴，并检查编码帧。见 [字幕同步工作流](subtitle-sync.md)。

成片先写 `candidate.mp4`。`videocut/sync.py` 从所有真实编码帧识别当前固定样式的字幕字形，比较声学参考、计划时间和真实显示时间，并用高能量语音窗口测量最终音轨偏移。通过后才改名 `final.mp4`；失败保留候选和失败报告。该验收没有将模型时间当作人工标注的真值，也不评判音色、情绪和发音自然度。阈值、安装、缓存及复用边界见 [字幕同步工作流](subtitle-sync.md)。

ASR 和 Auto-Editor 是 `asr` 可选依赖，普通脚本混剪不需要安装它们或下载识别模型。主剪辑环境的包版本固定在 `uv.lock`；语音模型使用各自独立的环境和版本清单。

| 环境 | 职责 | 版本记录 |
| --- | --- | --- |
| `.venv` / Python 3.12 | 素材、ASR、剪辑、渲染与验收 | `uv.lock` |
| `.venv-voice` / Python 3.12 | F5-TTS MLX 克隆旁白 | `requirements-voice.lock.txt` |
| `.venv-align` / Python 3.11 | Qwen3 强制对齐，CPU float32 | `requirements-align.lock.txt` |
| `.venv-index` / Python 3.11 | IndexTTS-2.5 官方 PyTorch / MPS 控制实验 | `requirements-index.lock.txt` |

声音克隆依赖单独固定在 `requirements-voice.lock.txt`。F5 0.2.6 会把张量作为随机噪声的维度；独立生成进程把这些维度转换成 Python 整数以适配 MLX 0.32，未修改上游安装文件。模型和参考音频变化会使语音缓存失效。

IndexTTS-2.5 使用 `.venv-index`（Python 3.11 / PyTorch MPS）。`--tts indextts` 由 CLI 写入 `index-request.json`，启动 `scripts/index_narration.py`，再读取 `speech/index-manifest.json` 将逐句 WAV 交给 `build_narration`；原生语音参数来自配置 `index_tts`。缓存同时考虑参考声音、模型文件摘要、代码修订和各句控制参数；调整某句的 `line_overrides` 只需重生成对应句子，字幕仍使用原稿。F5 继续作为 `--tts clone` 的显式选项，两条环境相互隔离。

`scripts/test_indextts_controls.py` 保留为短句实验：SSML 仅由实验适配层转换为拼音标记及音频停顿，不宣称模型原生兼容完整 SSML。该适配层尚未用于视频提供方。详细运行方式、SSML 支持表与实测结果见 [voice-controls.md](voice-controls.md)。原生 IndexTTS 输出为单声道 22.05kHz PCM16；视频提供方通过 FFmpeg 重采样和响度处理转换为 48kHz，按实际采样数重建字幕和镜头时间。原生拼音标记只进入模型输入，不进入字幕显示文本。

语音输入先由系统 FFmpeg 解码为单声道 16kHz float32，再交给 faster-whisper 支持的 NumPy 波形入口。这样不会走 faster-whisper 1.2.1 与 PyAV 19 不兼容的文件解码接口，参见 [上游问题 #1589](https://github.com/SYSTRAN/faster-whisper/issues/1589)。这条 ASR 解码路径没有修改 site-packages 或打运行时补丁。

识别使用 Silero VAD 避免长停顿造成整句漏识别；对完全没有词时间戳覆盖的有声片段报错。该检查只发现漏段，不承诺语义逐字正确。允许用户校对原始词文本后通过 `--transcript` 重渲染，保留时间戳与源文件校验和；报告明确区分生成的识别结果和外部提供的结果。
