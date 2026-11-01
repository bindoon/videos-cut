# 架构与运行方式

本地 CLI 项目，不依赖数据库或云端任务服务。CLI 参数与 JSON 文件定义一次任务，`outputs/` 保存结果，`assets/cache/` 保存可复用素材与转录。

架构分为通用工具、场景技能与作品工程。[能力地图](capabilities.md)维护完整清单。`.agents/skills/xiaohongshu-quotes/` 负责小红书图文的内容/版式决策，调用通用 `images`；`films/` 持有具体影片的数据和美术，复用 `codefilm`。工具不读取平台技能或隐式应用其默认值。

`codefilm` 是独立的代码画面入口：本地 HTML / Canvas / Three.js 按确定性的 `render(t)` 绘制，经无损 PNG 与现有 `videocut ffmpeg sequence` 编码成可续跑的片段。`films/hangzhou/` 拥有城市 GIS 转换、历史内容、相机和配音/配乐，通过配置复用该渲染器。完整制作流程见[代码视频指南](code-films.md)，具体数据与片子复现见[杭州短片说明](../films/hangzhou/README.md)。

[文档导航](README.md) · [使用指南](usage.md) · [AI 操作指南](ai-guide.md) · [开源来源](open-source.md)

## 入口与数据流

```text
网页链接 / 文件直链 → 下载与校验 → materials.json → 渲染素材入口
宿主 Agent 写计划/生图 → 本地文件 → prepare 缺项与媒体检查 → project.json + materials.json → 渲染
本地音视频 → 独立 ASR → TXT / SRT / transcript.json → 可选的编辑消费
视频 + SRT/VTT/同源 ASR → images index/sample/band → Agent 选题与核帧 → 图卡 manifest
图卡 manifest → images plan/render → JPG + 内容摘要报告 → images verify + Agent 逐图检查
剧本 + 素材目录 → 配音/字幕时间轴 → 选素材 → 画面和转场 → 叠字幕/贴纸/配乐 → 成片
原始口播视频 → 真实 ASR → 删停顿/配置词 → 精剪视频 + 重排词时间轴 → 同一条混剪管线
参考录音 + 新稿 + 原生控制参数 → IndexTTS-2.5 → 22.05kHz WAV → 48kHz 逐句 WAV → 同一条混剪管线
参考录音 + 控制样例 → IndexTTS-2.5 / SSML 实验适配层 → 独立音频对照与验收
已有媒体 → videocut ffmpeg TOOL → 新媒体 / 工具报告 / 可选剪辑软件时间线
本地代码 + 数据 + 时间轴 → codefilm → 静帧 / 已校验分段 + manifest → FFmpeg 后期与独立交付检查
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
| `videocut/cli.py` | 提供 `prepare / download / transcribe / demo / render / mix / cut / rough-cut / raw-sample`，以及 `ffmpeg / codefilm` 转发入口 |
| `videocut/creation.py` | `prepare` 检查宿主创作计划，输出待补素材任务或现有渲染器配置；不调用模型或网络 |
| `videocut/assets.py` | 下载、来源记录和标签选片；不做未接入的视觉模型理解 |
| `videocut/downloads.py` | HTTP Range 与 yt-dlp 导入、规格隔离缓存、大小预算、逐项失败结果和媒体校验；网页下载依赖可选 `download` extra |
| `videocut/wechat_downloads.py` | 微信视频号本地 API 适配、捕获记录匹配、格式选择与解密流接入；复用下载校验与素材协议 |
| `videocut/speech.py` | 合并默认 IndexTTS 生成的逐句语音，或显式使用 Edge/macOS；按 WAV 采样数建立时间轴 |
| `videocut/captions.py` | 固定展示计划；默认整句预读用 Qwen 句末定位，显式 audio_clip 用 PCM 区间，拆条用 Qwen 字词时间；校验音频摘要 |
| `scripts/align_qwen.py` | 独立 `.venv-align` 环境调用 Qwen3ForcedAligner；缓存给定原稿的字词起止时间和完整模型摘要 |
| `videocut/sync.py` | 检查所有成片帧里的字幕字形、出现/消失时间，并对比编码前后的语音波形；失败阻止交付 |
| `scripts/index_narration.py` | 独立 PyTorch 环境生成 IndexTTS-2.5 逐句旁白，转换到 48kHz；记录参考音频、模型、代码修订、逐句参数及缓存校验和 |
| `scripts/test_indextts_controls.py` | 独立 PyTorch 环境生成 7 组控制样例，转换部分 SSML，记录片段/停顿时间及校验和；SSML 适配器尚未接入视频 CLI |
| `scripts/fetch_clone_model.py` | 固定模型元数据修订、分片续传、核对摘要；可从镜像下载相同内容 |
| `videocut/cleaning.py` | 复用独立 ASR，并执行剪辑准入检查、静音定位、完整词匹配、帧对齐音画裁切和字幕重排 |
| `videocut/transcription.py` | 独立 ASR 实现、分段读取、逐词时间归属、校验缓存和 TXT/SRT/JSON 导出；不调用下载、剪辑或大模型 |
| `videocut/render.py` | FFmpeg 运镜/转场，MoviePy 图层合成，音量标准化与完整解码验收 |
| `videocut/media.py` | 有超时、检查退出码的进程调用与 ffprobe |
| `videocut/image_cli.py`、`image_ops.py` | 通用图像 CLI、双阶段 seek、区域预览、等比总览与像素指标 |
| `videocut/text_index.py` | SRT/VTT/同源 ASR 检索索引、有限滚动字幕去重与来源记录；不改变 ASR 算法和缓存 |
| `videocut/image_cards.py` | 原生像素拼接/脚本文字排版、输入合同、输出锁、按内容续跑和实际图片摘要/尺寸/边界检查 |
| `videocut/ffmpeg_tools.py` | `ffmpeg` 子命令，将工具参数、标准输出和退出码原样交给项目内固定的 ffmpeg-skill；不接管配音、ASR 或字幕同步门禁 |
| `videocut/codefilm.py`、`codefilm_runner.mjs` | 配置与输入摘要、私有浏览器逐帧捕获、输出锁、分段缓存、实际媒体校验；不负责 GIS、叙事、配音或 Qwen 验收 |

`mix` 使用同一份剪后音频时间轴：原视频镜头从对应时间截取，插入素材时只替换画面。不会把原片声音和旁白重复播放。字幕图层在背景转场之后叠加，避免两条字幕跟着转场重影。

`images` 不调用下载或 ASR。原生模式完整拼图统一缩放；脚本模式要求逐行校对声明和 `text_source`，字体参与缓存键。每卡输出文件名包含源视频/配置摘要；续跑按当前报告核对真实文件，变化项重算，旧版本保留。失败报告不引用旧总览。图片机械检查与 Agent 视觉/语义检查分别记录，不能继承视频的 Qwen 门禁。详见[图像工具](image-tools.md)。

生成配音启用 `speech` 字幕模式时先冻结 `caption-plan.json`。IndexTTS 默认启用；Edge、macOS 默认是文件区间字幕，需显式 `--caption-mode speech` 才进入该流程。默认 `previous_speech_end` 使用 Qwen 的末字结束时间切换到下一句，保持相邻字幕无缝连接，末条到视频结束；这是预读策略，审计同时记录切换时刻与本句实际音频起点。显式 `audio_clip` 直接使用 WAV 采样区间，无需模型；显式拆条使用首字时间和阅读提前量。所有模式写出 SRT 后重新读取它作为渲染时间轴，并检查编码帧。见 [字幕同步工作流](subtitle-sync.md)。

成片先写 `candidate.mp4` 并做基本媒体检查。启用上述字幕对齐流程后，`videocut/sync.py` 从所有真实编码帧识别当前固定样式的字幕字形，比较声学参考、计划时间和真实显示时间，并用高能量语音窗口测量最终音轨偏移。相应检查通过后才改名 `final.mp4`；失败保留候选和失败报告。文件区间字幕和已有录音的 ASR 字幕没有该强制对齐门禁，`verification.json` 的 `subtitle_sync.passed` 为 `null`。该验收没有将模型时间当作人工标注的真值，也不评判音色、情绪和发音自然度。阈值、安装、缓存及复用边界见 [字幕同步工作流](subtitle-sync.md)。

ASR 和 Auto-Editor 是 `asr` 可选依赖，普通脚本混剪不需要安装它们或下载识别模型。主剪辑环境的包版本固定在 `uv.lock`；语音模型使用各自独立的环境和版本清单。

`videocut ffmpeg TOOL ...` 是独立的文件处理入口：当前 Python 启动 `.agents/skills/ffmpeg-skill/scripts/` 中的固定工具，保留调用者工作目录，不经过 shell，也不自动下载或更新代码。`doctor` / `contract` 交给上游 `_contract.py`；42 个公开工具的参数由各自解析器定义。上游在 macOS 检测到 Homebrew 精简版 FFmpeg 时，优先使用相同 Homebrew 前缀的 `opt/ffmpeg-full/bin`；项目原有命令仍使用其原来的 FFmpeg 入口。wheel 内也包含同一份工具，安装后从 `videocut/_vendor/ffmpeg_skill` 读取。版本与文件摘要见技能目录的 `UPSTREAM.json`。

扩展工具可以显式接收当前流程输出的 MP4、WAV、SRT，再写出新文件。上游的 `verified` 与平台 `check` 只代表其自己的文件检查，不代表通过本项目 `sync.py` 的字幕逐帧和音轨同步验收；上游自带 `--transcribe` 也不共享项目 ASR 缓存与审计格式。用法与边界见 [ffmpeg-tools.md](ffmpeg-tools.md)。

## 宿主创作边界

`videocut-creation-v1` 包含现有 `project` 配置、显式绑定的 `assets` 与独立 `publication` 文案。宿主拥有创意、提示词和图像生成能力；本地准备器只检查结构、解析原计划目录下的文件路径，并复用 `downloads.inspect_material` 做图片验证、音视频完整解码与 SHA-256。生成需求通过文件交接，不运行模型服务、数据库或后台任务。

缺失素材按 `local / host_image / external_video` 输出不同动作；已有文件即使带生成提示词，也只校验并复用，不重新生成。可选 `sha256` 不符或文件损坏会产生 `invalid`，不会自动覆盖；缺文件产生 `pending`；全部就绪才输出渲染配置和素材清单。每次占用新目录，保留计划原始快照与摘要。素材清单中的 `creation` 保留提示词、参考路径与调用者提供的生成元数据，通过现有素材导入继续进入 `sources.json`。参考路径不等于参考文件的不可变快照，宿主需另行保存生成服务实际采用的参考信息。

`prepare` 不做内容质量评审，也不接管旁白、字幕或同步验收。宿主生图可能联网并使用账户额度；准备命令自身的零模型/零网络统计不代表全流程成本。`external_video` 是显式缺项，当前没有自动提交 AI 视频服务的适配器。批量调度、浏览器发布和增量合成未新增。

## 代码画面与影片工程

代码画面使用 `codefilm-v1` 配置、JSON 时间轴和 `window.READY / render(t)` 页面接口；配置与结果不等于主混剪配置或 ffmpeg-skill 后期配置。输入文件、工具包装代码、画幅设置和浏览器/GPU 身份参与缓存；完成段保存摘要，复用仍重新探测实际文件。源码改变采用新的整片缓存键；局部预览不会自动与其他源码版本合并。完整性检查拒绝片段缺口与局部预览冒充整片，字幕声学验收另行进行。具体协议与限制见[代码视频指南](code-films.md)。

## 素材导入边界

```text
URL / 素材清单 → 解析来源 → 按规格检查缓存 → 下载/续传 → 合并/提取 → 校验 → 本地素材清单 → 原有渲染流程
```

`download` 可接多个 URL、`--materials` 或 `--retry-failed`，三种入口互斥。播放列表需要显式 `--playlist`，默认上限 20 项；单项失败不会丢弃已成功项。每项完成后更新任务清单，最终 CLI 在存在失败时返回非零；渲染调用 `download_materials` 时采用严格模式，缺少素材就停止。

缓存材料记录在 `assets/cache/imports/<provider>/<identity-and-variant>/material.json`。身份考虑平台和视频 ID，通用网页还考虑来源 URL；规格考虑视频／音频、清晰度、字幕开关与语言。文件路径不是唯一来源真相，命中缓存仍检查摘要与大小。旧素材目录的直链文件名尽量兼容，同名不同 URL 隔离。每个文件夹使用进程锁，避免两个下载进程同时写入；缓存文件和任务 JSON 原子替换。续传只在服务端提供校验标识并正确响应 Range 时追加，返回完整响应则重新写入。

只有媒体流类型检查、完整解码和摘要生成成功的素材才进入清单。导入结果沿用 `id/kind/path/tags` 等字段，额外记录原页面、平台、作者、实际音视频流和字幕轨道；字幕的人工／自动属性不明确时不推断。下载字幕不等于 ASR，也不会替代现有配音字幕计划。网络上限用于远程获取，已提供的本地素材不受传输预算约束。

`download` extra 固定 yt-dlp 发布版本并使用官方 Python API，默认忽略用户全局 yt-dlp 配置，代理沿用环境或显式 CLI 配置，Cookie 仅显式文件输入。项目不依赖 `upstream/yt-dlp` 工作区运行。下载不自动触发 ASR 或剪辑；独立转录见下节。大模型 API、数据库和定时任务仍未接入。

视频号分享/详情链接在进入 yt-dlp 前路由到 `wechat_downloads.py`，连接独立运行的 `wx_channels_download` v260907 本地 API。`--wechat-list` 查询捕获历史；明确 ID 或精确 URL 匹配后，经 `/api/channels/feed/profile` 读取详情，选择显式格式，再通过本地 `/play` 解密流复用有界 HTTP 下载、完整解码与摘要校验。缓存位于 `imports/wechat/`；来源 URL 与可选视频选择 ID 参与请求索引，视频 ID 与规格参与素材身份。实际尺寸必须符合选定格式，音频独立提取，画面字幕不视为可下载字幕轨。

短链接不以“最新记录”隐式匹配；本地 API 限制在 loopback HTTP origin，JSON 控制请求拒绝重定向并绕开外部代理。报告不保留 CDN 签名或解密密钥，流传输的临时请求状态在退出时清理，因此视频号重试会重新获取详情；完整缓存可离线复用。外部服务拥有独立运行时、数据库、证书和代理，本项目不管理其进程或修改系统安全设置，不分发其代码/二进制。完整使用边界见[视频号导入](usage.md#微信视频号)。

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
| `.venv-align` / Python 3.11 | Qwen3 强制对齐，CPU float32 | `requirements-align.lock.txt` |
| `.venv-index` / Python 3.11 | IndexTTS-2.5 官方 PyTorch / MPS 旁白与控制 | `requirements-index.lock.txt` |

IndexTTS-2.5 使用 `.venv-index`（Python 3.11 / PyTorch MPS）。语音合成默认选择 `--tts indextts`（包括 `raw-sample`），需要 `--reference-audio`。由 CLI 写入 `index-request.json`，启动 `scripts/index_narration.py`，再读取 `speech/index-manifest.json` 将逐句 WAV 交给 `build_narration`；原生语音参数来自配置 `index_tts`。缓存同时考虑参考声音、模型文件摘要、代码修订和各句控制参数；调整某句的 `line_overrides` 只需重生成对应句子，字幕仍使用原稿。Edge 和 macOS 系统声音需显式选择。F5 的 `clone` 及专用 CLI 参数已移除；旧生成脚本和锁文件仅保留供历史实验查阅。

`scripts/test_indextts_controls.py` 保留为短句实验：SSML 仅由实验适配层转换为拼音标记及音频停顿，不宣称模型原生兼容完整 SSML。该适配层尚未用于视频提供方。详细运行方式、SSML 支持表与实测结果见 [voice-controls.md](voice-controls.md)。原生 IndexTTS 输出为单声道 22.05kHz PCM16；视频提供方通过 FFmpeg 重采样和响度处理转换为 48kHz，按实际采样数重建字幕和镜头时间。原生拼音标记只进入模型输入，不进入字幕显示文本。

语音输入先由系统 FFmpeg 解码为单声道 16kHz float32，再交给 faster-whisper 支持的 NumPy 波形入口。这样不会走 faster-whisper 1.2.1 与 PyAV 19 不兼容的文件解码接口，参见 [上游问题 #1589](https://github.com/SYSTRAN/faster-whisper/issues/1589)。这条 ASR 解码路径没有修改 site-packages 或打运行时补丁。

识别使用 Silero VAD 避免长停顿造成整句漏识别；剪辑消费时对完全没有词时间戳覆盖的有声片段报错。该检查只发现漏段，不承诺语义逐字正确；独立转录不执行这项剪辑准入检查。允许用户校对原始词文本后通过 `--transcript` 重渲染，保留时间戳与源文件校验和；报告明确区分生成的识别结果和外部提供的结果。


## 开发者修改入口

| 变更 | 优先查看 |
| --- | --- |
| 素材下载、缓存与来源 | `downloads.py`、`assets.py`、`tests/test_downloads.py` |
| 独立转录与时间归属 | `transcription.py`、`tests/test_transcription.py`；缓存语义改变时同步 `SCHEMA` |
| 静音和口头词精剪 | `cleaning.py`、`tests/test_editing.py` |
| 配音提供方、逐句缓存 | `speech.py`、`scripts/*narration.py`、`tests/test_prepared_voice.py` |
| 字幕计划与显示验收 | `captions.py`、`sync.py`、`tests/test_caption_alignment.py`、`tests/test_subtitle_delivery.py` |
| 画面图层与合成 | `render.py`；保持转场与字幕分层关系，结合实际截图检查 |
| FFmpeg 扩展接入 | `ffmpeg_tools.py`、`tests/test_ffmpeg_tools.py`、`scripts/verify_ffmpeg_tools.py` |
| 代码动画、浏览器逐帧与分段完整性 | `codefilm.py`、`codefilm_runner.mjs`、`tests/test_codefilm.py`、`scripts/verify_codefilm.py` |

各模式通过显式文件衔接，没有隐藏任务队列。主项目配置与 ffmpeg-skill 项目配置不是同一协议，不能直接互换；后期输出也不自动继承旧的同步验收。完整测试需安装 `download` 与 `asr` 两个 extra，执行方式见[使用指南](usage.md)。
