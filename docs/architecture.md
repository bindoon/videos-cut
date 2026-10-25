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

- **素材**：`examples/materials*.json` 描述来源、类型、标签。统一导入文件直链、网页视频和本地文件；下载在 `assets/cache`，校验后生成来源、实际流信息和 SHA-256。`download` 也可输出可直接用于渲染的 `materials.json`。
- **脚本**：`examples/coffee.json` 包含标题、逐镜台词、素材查询、画幅与效果配置。
- **字幕**：基础时间轴按真实 PCM 采样数累计；IndexTTS 默认整句显示，上一句末字结束时立即切换到下一句，跨过句间留白供预读；显式 audio_clip 才绑定 WAV 区间。字词和句末由 Qwen 定位，不能在异常时改分条。已有录音按实际 ASR 时间戳定时，报告不把它标为通过强制对齐验收。
- **时间轴**：`outputs/<name>/timeline.json` 是该成片实际使用的镜头、素材、时间、转场、贴纸。不是只保留一段不可检查的自然语言提示词。
- **精剪计划**：`edit-plan.json` 保存识别后的删除理由、删除区间、保留区间和重排后的词时间。

## 模块

| 文件 | 职责 |
| --- | --- |
| `videocut/cli.py` | 提供 `download / transcribe / demo / render / mix / cut / rough-cut` 各独立命令入口 |
| `videocut/assets.py` | 下载、来源记录和标签选片；不做未接入的视觉模型理解 |
| `videocut/downloads.py` | HTTP Range 与 yt-dlp 导入、规格隔离缓存、大小预算、逐项失败结果和媒体校验；网页下载依赖可选 `download` extra |
| `videocut/speech.py` | 明确选择 Edge/macOS 配音或读取克隆语音，按 WAV 采样数输出逐句字幕 |
| `videocut/captions.py` | 固定展示计划；整句使用 PCM 片段边界，显式拆条使用 Qwen 字词时间；校验音频摘要 |
| `scripts/align_qwen.py` | 独立 `.venv-align` 环境调用 Qwen3ForcedAligner；缓存给定原稿的字词起止时间和完整模型摘要 |
| `videocut/sync.py` | 检查所有成片帧里的字幕字形、出现/消失时间，并对比编码前后的语音波形；失败阻止交付 |
| `scripts/clone_narration.py` | 独立 MLX 环境加载 F5-TTS 和 Vocos，参考录音生成新稿；保留逐句模型、输入和音频校验和 |
| `scripts/index_narration.py` | 独立 PyTorch 环境生成 IndexTTS-2.5 逐句旁白，转换到 48kHz；记录参考音频、模型、代码修订、逐句参数及缓存校验和 |
| `scripts/test_indextts_controls.py` | 独立 PyTorch 环境生成 7 组控制样例，转换部分 SSML，记录片段/停顿时间及校验和；SSML 适配器尚未接入视频 CLI |
| `scripts/fetch_clone_model.py` | 固定模型元数据修订、分片续传、核对摘要；可从镜像下载相同内容 |
| `videocut/cleaning.py` | 复用独立 ASR，并执行剪辑准入检查、静音定位、完整词匹配、帧对齐音画裁切和字幕重排 |
| `videocut/transcription.py` | 独立 ASR 实现、分段读取、逐词时间归属、校验缓存和 TXT/SRT/JSON 导出；不调用下载、剪辑或大模型 |
| `videocut/render.py` | FFmpeg 运镜/转场，MoviePy 图层合成，音量标准化与完整解码验收 |
| `videocut/media.py` | 有超时、检查退出码的进程调用与 ffprobe |

`mix` 使用同一份剪后音频时间轴：原视频镜头从对应时间截取，插入素材时只替换画面。不会把原片声音和旁白重复播放。字幕图层在背景转场之后叠加，避免两条字幕跟着转场重影。

生成配音先冻结 `caption-plan.json`。默认 `previous_speech_end` 使用 Qwen 的末字结束时间切换到下一句，保持相邻字幕无缝连接，末条到视频结束；这是预读策略，审计同时记录切换时刻与本句实际音频起点。显式 `audio_clip` 直接使用 WAV 采样区间，无需模型；显式拆条使用首字时间和阅读提前量。所有模式写出 SRT 后重新读取它作为渲染时间轴，并检查编码帧。见 [字幕同步工作流](subtitle-sync.md)。

成片先写 `candidate.mp4`。`videocut/sync.py` 从所有真实编码帧识别当前固定样式的字幕字形，比较声学参考、计划时间和真实显示时间，并用高能量语音窗口测量最终音轨偏移。通过后才改名 `final.mp4`；失败保留候选和失败报告。该验收没有将模型时间当作人工标注的真值，也不评判音色、情绪和发音自然度。阈值、安装、缓存及复用边界见 [字幕同步工作流](subtitle-sync.md)。

ASR 和 Auto-Editor 是 `asr` 可选依赖，普通脚本混剪不需要安装它们或下载识别模型。主剪辑环境的包版本固定在 `uv.lock`；语音模型使用各自独立的环境和版本清单。

## 素材导入边界

```text
URL / 素材清单 → 解析来源 → 按规格检查缓存 → 下载/续传 → 合并/提取 → 校验 → 本地素材清单 → 原有渲染流程
```

`download` 可接多个 URL、`--materials` 或 `--retry-failed`，三种入口互斥。播放列表需要显式 `--playlist`，默认上限 20 项；单项失败不会丢弃已成功项。每项完成后更新任务清单，最终 CLI 在存在失败时返回非零；渲染调用 `download_materials` 时采用严格模式，缺少素材就停止。

缓存材料记录在 `assets/cache/imports/<provider>/<identity-and-variant>/material.json`。身份考虑平台和视频 ID，通用网页还考虑来源 URL；规格考虑视频／音频、清晰度、字幕开关与语言。文件路径不是唯一来源真相，命中缓存仍检查摘要与大小。旧素材目录的直链文件名尽量兼容，同名不同 URL 隔离。每个文件夹使用进程锁，避免两个下载进程同时写入；缓存文件和任务 JSON 原子替换。续传只在服务端提供校验标识并正确响应 Range 时追加，返回完整响应则重新写入。

只有媒体流类型检查、完整解码和摘要生成成功的素材才进入清单。导入结果沿用 `id/kind/path/tags` 等字段，额外记录原页面、平台、作者、实际音视频流和字幕轨道；字幕的人工／自动属性不明确时不推断。下载字幕不等于 ASR，也不会替代现有配音字幕计划。网络上限用于远程获取，已提供的本地素材不受传输预算约束。

`download` extra 固定 yt-dlp 发布版本并使用官方 Python API，默认忽略用户全局 yt-dlp 配置，代理沿用环境或显式 CLI 配置，Cookie 仅显式文件输入。项目不依赖 `upstream/yt-dlp` 工作区运行。下载不自动触发 ASR 或剪辑；独立转录见下节。大模型 API、数据库和定时任务仍未接入。

## 独立转录与剪辑消费

```text
本地音视频 → transcription.py → transcript.json / transcript.txt / transcript.srt
                            ↘ cleaning.py 的消费检查 → cut / mix / render --audio
```

模型加载和识别只实现一次。`cleaning.transcribe` 保留原调用接口和默认中文，但委托 `transcription.transcribe`，再检查词时间和未覆盖的有声片段。独立 CLI 默认为自动语言检测，可正常输出 `no_speech`；编辑器继续拒绝不足以安全剪辑的结果。`mix`、`render --audio` 增加显式语言参数，默认行为仍为中文。已有 `--transcript` 路径继续可用，`render --audio` 也会检查提供的词时间和源文件摘要。

每个窗口包含核心区间及两侧上下文，输出时间回到原文件坐标；一个词按估计中点归属核心区间，真正重复的相同文字不会被内容去重。源文件不被裁剪或改写；解码通过系统 FFmpeg 的有界 float32 PCM 窗口完成，后端仍是 CPU int8 / 4 线程 faster-whisper。

缓存身份考虑输入文件 SHA-256、实际模型权重与配置、后端和 FFmpeg 版本、语言、VAD、提示词及分段参数。单段 JSON 带独立摘要并原子写入，失败或中断后可从完整段继续。`--force` 跳过有效缓存重新推理。`runtime.max_decoded_samples` 记录本次新解码的最大数组长度，全缓存时为 0；`max_chunk_samples` 记录这套分段的最大长度，不是进程 RSS 内存。

输出目录与缓存目录分别加进程锁。已有输出必须同时匹配请求身份和已记录的文件摘要，才允许正常重导出；校对内容或不同输入需要新的目录或显式 `--overwrite`。即使显式覆盖也不能覆盖输入媒体本身。缓存不包含用户对导出文件的人工修订，校对后的 JSON 通过 `--transcript` 明确交给消费方。

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

识别使用 Silero VAD 避免长停顿造成整句漏识别；剪辑消费时对完全没有词时间戳覆盖的有声片段报错。该检查只发现漏段，不承诺语义逐字正确；独立转录不执行这项剪辑准入检查。允许用户校对原始词文本后通过 `--transcript` 重渲染，保留时间戳与源文件校验和；报告明确区分生成的识别结果和外部提供的结果。
