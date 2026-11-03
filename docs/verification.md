# 验证记录

## 2026-11-03：共用导演、双渲染预览与画面批注

- 新增自有 `video-direction` 和 `review-workflow` 技能：区分图片阅读、口播声音与机制动作节奏，记录稳定镜头 ID、运动用途、停留理由、声音意图和实际检查范围。素材/代码工作流共同引用，杭州 GIS 经验移到代码技能参考文件。四个新建/更新的 Skill 均通过 `quick_validate.py`；没有修改第三方技能子模块。
- 新增 `videocut review` 文件合同与本机审片页。渲染前登记配置/声明输入和不存在的候选；封存前完整解码、计数帧、核对规格/镜头覆盖/输入摘要，成功才切换 latest。批注固定原视频摘要、版本、镜头、帧、预览/工程时间与归一化区域；CLI 加锁领取，完成需引用有变化的新版。网页不执行 Agent、渲染命令或源码写入。工具合同见 [review.md](review.md)。
- `tests/test_review.py` **14 项通过，2.54 秒**。真实本地 FFmpeg/HTTP 覆盖封存与可变输出隔离、旧候选/变更输入拒绝、帧数和未知/重复/缺失 ID、非法时间/区域、旧意见不迁移、错误版本完成、并发领取、同大小媒体与 manifest 篡改、Range/同源写入边界、原生图片渲染输出，以及 codefilm 局部时间与声明输入。未削弱旧断言。
- 真实图片使用现有 `render_backgrounds`，两张本机 Unsplash 咖啡照片组成三个镜头：v1 **6 秒/144 帧**，按意见把第二张从 2 秒延长到 3 秒，第三张顺延，v2 **7 秒/168 帧**；均为 **640×360/24fps**，三个镜头 ID 保留，原版批注引用新版完成。保留照片 credit/license/page。没有把图片迁移成 HTML 动画。
- 太极 V3 使用原有 Three.js、模型和 `codefilm`，在隔离副本实际渲染 **24–26 秒局部片段，640×360/24fps/48 帧**。按意见将相机 FOV 乘以 0.90，重新渲染并发布；源摘要和视频摘要均改变，镜头 ID 不变，旧意见保留，两个版本完整解码校验通过。未修改原太极工程，没有声称重渲染全部 36 秒，未测任意 seek 历史独立性。两类烟测均为无声预览，无语音模型或付费 API，Qwen/审美保持 null。
- Chrome 经 CUA 实际检查播放、镜头跳转、v1/v2 切换、画面区域、提交批注、CLI 领取/回复及待生成提示。修复原生视频点击可能继续播放的问题：定位层避开播放控制，跳转中禁用批注；实测点击后停在 v1 的 2.50 秒。加载过程中仍明确标注已显示旧版；太极显示原工程 24–26 秒范围。独立故意损坏的 v3 负例触发加载失败，画面/下载仍为 v2，失败后不自动反复加载，提供显式重试。
- 首次真实图片验收发现 H.264 side-data 导致 ffprobe 单字段 CSV 返回 `144,`，发布器严格拒绝；改用 JSON stream 字段解析并新增原生渲染回归，仍完整解码且严格计数。失败证据保留在 `outputs/review-workflows-20261103/`，成功双案例、五张 UI 截图、接触表与报告在 `outputs/review-workflows-20261103-02/`；`photos-load-failure-test` 是故意损坏的负例，不能作为交付媒体。
- 先执行 `uv sync --extra download --extra asr`，最终 **`uv run pytest -q`：125 passed，35.14 秒**。保留 588 条既有 MoviePy/NumPy 弃用警告；新模块/测试/烟测通过 Ruff，UI 脚本通过 Node 语法检查，`git diff --check` 通过。入口、合同和技能的 **226 处本地文件链接**无缺失。wheel/sdist 构建成功，确认包内含审片 HTML、源码包含两项新技能及模板；从解压 wheel 的独立目录启动 HTTP，实际返回 UI/token 成功，报告在 `outputs/package-check-20261103-review-final/verification.json`。未修改 ASR/Qwen/sync.py；既有 `.gitignore`、`docs/code-films.md` 与素材改动保留。

## 2026-11-02：动态展示、工作流归档、上游引用与 MIT

- README 新增杭州、机械蝴蝶和太极三张实际成片 GIF，均为三段各 2 秒、480×270、12fps、72 帧无声循环；咖啡原有 5 秒 GIF 改为直接展示。逐张查看六帧接触表，并用 Pillow 解码全部帧核对尺寸、循环与总时长；未据此宣称声学字幕验收。命令与机器报告在 `outputs/readme-gifs-20261102/`，输入/输出摘要和原片范围在 `docs/media/gif-source.json`。
- 自有 `video-workflow`、`codefilm-workflow`、`xiaohongshu-quotes` 统一放在根目录 `skills/`，三个入口均通过 skill-creator 的 `quick_validate.py`。工作流正文从 docs 移出，删除 `docs/workflows/xiaohongshu-quotes.md`，工具合同和导航继续保留；21 份入口、文档和技能 Markdown 的本地文件链接检查无断链。
- `.agents/skills/ffmpeg-skill` 从复制分发改为 Git submodule，仍固定 `f2d90ea603a663711c3d6aa9775d2a2380d83182` / 2.16.1。旧运行文件的 81 项 SHA-256 全部与该提交一致，记录迁到 `docs/ffmpeg-upstream.json`；未修改或升级上游源码。
- 根目录加入 MIT LICENSE，包元数据为 `License-Expression: MIT`，保留上游代码、杭州与太极媒体各自许可。`uv build --out-dir outputs/package-check-20261102-final` 成功生成 sdist，再从该 sdist 构建 wheel；归档检查确认包含自有技能、主项目及上游 LICENSE，排除 Git 数据、node_modules、字节码和上游演示 GIF。wheel 约 818 KiB。
- 将 wheel 解压到独立目录，从该目录加载包，确认使用包内 `_vendor/ffmpeg_skill`、发现 42 个公开工具；真实裁切机械蝴蝶第 3–4 秒到带空格的新文件名，工具验收通过。wheel 内 81 项上游文件摘要仍匹配，报告在 `outputs/package-check-20261102-final/verification.json`。
- 先运行 `uv sync --extra download --extra asr`，再运行 `uv run pytest -q`：**111 passed，34.00s**。588 条警告来自 MoviePy 使用 NumPy 已弃用的 shape 赋值；无失败或跳过验收。

## 2026-11-01：通用图像工具、场景技能与 README 作品展示

- 新增 `videocut images sample / band / index / plan / render / verify`，实现双阶段 seek 候选帧、原像素区域预览、SRT/VTT/同源 ASR 索引、原生/脚本图卡、输出锁、逐卡结果、内容摘要续跑和实际文件检查。原生不重绘字，脚本要求校对声明和文字来源；没有修改独立 ASR、Qwen 或 `sync.py` 的算法/缓存。
- 小红书选题、受众、说话人核实、版式和文案放在独立 `.agents/skills/xiaohongshu-quotes/` 与场景文档中；通用工具无平台字段，不自动调用模型、下载器或发布服务。参考 native-subtitle-quote-image 的工作流，本地独立编写实现，未复制上游脚本。
- `tests/test_images.py` 共 **20 项**，使用真实 FFmpeg 编码视频与 Pillow 像素结果：长 GOP 指定时间抽帧、区域像素保留、等比总览、原生整图统一缩放、实际中文文字像素/边界、越界拒绝、台词审核与来源、缺字字体拒绝、内容/字体/源视频变化失效、同大小损坏修复、重复条失败、部分失败补做、中断后未登记图片保留与恢复、外部工作目录只读计划、滚动字幕索引及合法 `no_speech`。没有弱化、跳过或删除旧断言。
- 新横屏截图测试暴露 FFmpeg 9 对限范围 MJPEG 抽帧的兼容问题，以及低帧率视频最后采样点可能晚于最后一帧的问题；修正为 PNG 中间帧并按帧率约束末尾采样，保持原验收要求。检查图用等比留边替代固定拉伸。失败输出留在本轮会话与 pytest 临时目录。
- 执行 `uv sync --extra download --extra asr` 后，最终完整 **`uv run --no-sync pytest -q`：111 passed，32.21 秒**；588 条既有 MoviePy/NumPy 弃用提示保留。主模块、全部测试和新增图库脚本通过 Ruff，`git diff --check` 通过。Skill 使用 `quick_validate.py` 验证通过；其 PyYAML 依赖使用一次性 `uv run --with pyyaml`，未加入主项目依赖。
- 实际杭州 120 秒成片生成 **15 个相邻候选帧、字幕区域预览、24 条 SRT 索引**；杭州连续四句生成原生图卡，机械蝴蝶实际帧生成 3:4 后期说明图卡。两张均通过 `images verify`，实际 CLI 原生续跑复用 1/1 卡。机器报告保留 `visual_review=pending / semantic_verified=false / subtitle_sync.passed=null`，未把文件检查标成语义或声学字幕验收。证据在 `outputs/image-tools-20261101/`、`outputs/readme-gallery-20261101-v2/`。
- 读取历史会话“制定代码复刻视频方案”“制作机械蝴蝶”“制作太极缠丝劲动画”，以其最终交付路径核对本地 MP4；从编码文件重新提取三份六帧图集。宿主实际查看三张图集和两张成品图卡；当前五张 JPEG 合计约 0.83 MiB，随 README 保存，未复制用户参考音频或大型视频。来源摘要、秒数、许可、原生/后期文字及看图记录见 [展示媒体](media/README.md) 与 [gallery-source.json](media/gallery-source.json)。这轮没有重渲染原三条完整影片、重新调用语音模型、联网平台下载或进行人工听审。
- wheel 和 sdist 构建通过，新图像模块包含于 wheel；隔离目标安装后，从仓库外通过 `python -m videocut images verify` 检查实际脚本图卡成功。打包检查发现原默认 sdist 混入影片依赖/缓存/模型，改用受控包含与排除规则后，源码包从约 **157 MiB 降至 5,477,515 字节**，检查无 `node_modules`、虚拟环境、影片 `data`、GLB、用户声音或 `outputs`；保留通用工具、两类技能、影片源码与来源说明。
- 能力地图、通用图像合同、小红书工作流、README、使用/AI 指南、架构和开源来源已同步；338 处本地文档文件链接无缺失，新增五张图片的摘要均与清单一致。既有未提交的其他影片与文档改动保留。

## 2026-10-30：代码视频工具与制作工作流沉淀

- 新增 `videocut codefilm plan / stills / render / verify`，从杭州脚本抽出本地浏览器捕获、A→B→A 截图检查、无损 PNG 分段编码、输入摘要与缓存校验。`examples/codefilm/` 为两秒 Canvas 示例，杭州改用 `codefilm.json` 与共享入口，影片内容及 GIS 转换仍在 `films/hangzhou/`。未修改 ASR 缓存、Qwen 或 `sync.py`。
- 5 项新增确定性测试使用实际本地 FFmpeg：计划只读及源码摘要变化、实际帧数/格式验收、同大小视频损坏、时间轴缺口、局部片段冒充全片、伪造帧数、严格 JSON 输出解析，以及杭州旁白要求显式输出并保护旧成片。各分支集中于 5 个测试函数，没有通过跳过或削弱原断言换取通过。
- 浏览器烟测实际使用 Apple M4 / ANGLE Metal、Chromium headless shell 与影片锁定的 Playwright 1.63.0：**48 帧、640×360、24fps、4 段**完整输出；重跑复用全部 4 段且视频文件摘要和修改时间不变。故意翻转一段末尾字节，续跑明确拒绝摘要不符，随后恢复测试文件。两个场景静帧、合片后的实际 48 帧与截图均检查通过。证据：`outputs/codefilm-integration-20261030-v2/`。
- 杭州真实模型经新入口完成 **118～119 秒、640×360、24 帧**局部渲染，并通过显式 `--allow-partial` 验收；查看了实际编码帧中的跨江画面、光层和双语字幕。证据：`outputs/hangzhou-codefilm-regression-20261030/`。没有用这个短段冒充重新渲染过全部 4,100 帧。
- 杭州音乐脚本用明确的新输出目录实际重生成原 170.833 秒混音，修复其旧式单行入口遗漏输出参数的问题。后期通过原成片截出的两秒测试夹具（**48 帧、1920×1080、24fps**）验证合片、混音、响度、章节和截图；关键帧取样改为按章节计算。后期重跑不改写最终 MP4；故意修改测试混音后明确拒绝复用旧结果，恢复原混音。平台检查 **0 失败、1 警告**（没有独立语言字幕轨）。实际看板已查看。证据：`outputs/hangzhou-post-regression-20261030-v2/post-smoke-verification.json`。这是后期回归夹具，不是新的完整杭州成片，也未重新跑在线 TTS、GIS 下载或 35 条 OCR。
- 失败与恢复：第一版两秒烟测误用 `join` 默认淡化，改成显式 `transition=none` 后通过。额外完整时长后期回归遇到 **No space left on device**，未交付不完整输出，保留 `outputs/hangzhou-post-regression-20261030/disk-full-*` 日志；只清理本轮生成/复制的可再生测试 WAV，再缩小后期夹具。并行套件当时一项原有 PCM 字幕测试失败，不能仅据此确认与磁盘的因果关系；原断言未改，单独复跑通过，随后完整套件通过。
- 按项目约定先执行 `uv sync --extra download --extra asr`，最终 **`uv run pytest -q`：76 passed，29.44 秒**。保留 MoviePy / NumPy 的 **588 条既有弃用警告**。主模块、新测试/烟测通过 Ruff；影片脚本通过致命错误规则检查，Python 编译、Node 语法和 `git diff --check` 均通过。
- wheel 构建通过，确认包含 `codefilm_runner.mjs` 和固定 `sequence.py` 工具；安装到隔离目标目录，从仓库外运行其 `codefilm plan` 成功。核对本轮涉及文档的 **112 处本地文件链接**，无缺失。新增 [代码视频工作流](code-films.md)，同步首页、使用/AI 指南、架构、来源与杭州复现说明。原杭州交付 MP4 SHA-256 仍为 `0b45beeb09add5d70187299cea75b657e7794b50ac0161e8df37d321fd416e14`。

## 杭州城市白模短片（2026-10-30）

- 新增独立工程 [films/hangzhou](../films/hangzhou/README.md)，使用 Three.js / Canvas 渲染真实杭州建筑、水系与历史区位光层。CMAB 杭州原始文件含 124,455 条记录，取景矩形约 515.82 km²；最终含 75,139 个建筑轮廓，其中 40 个采用明确 OSM 楼高，替换 14 个重叠的 CMAB 部分。原始 ZIP 成员按 HTTP Range 获取并校验长度与 CRC；不是程序随机生成的城市。
- [成片](../outputs/hangzhou-rings-20261030/杭州-一城山水千年生长.mp4)：4,100 帧，视频 170.833333 秒，容器 170.967 秒；1920×1080、24fps、H.264 High / yuv420p / BT.709 视频范围，AAC 双声道 48kHz，12 个章节。容器与视频尾长差异来自音频编码，不增加画面帧数。
- 解说为原创杭州稿，Edge TTS `zh-CN-YunxiNeural`；35 条字幕按真实 PCM 采样数生成 SRT 并回读。配乐与音效由代码合成，所有城市画面来自代码渲染，没有调用生图或生视频模型。
- [字幕 OCR 回读](../outputs/hangzhou-rings-20261030/caption-ocr-verification.json)：35 条中文字幕分别从实际编码视频的字幕中点抽一帧，系统 Vision 独立识别后全部匹配。它是每条字幕的一帧抽样，不是全部帧验收，也不是 Qwen 强制对齐。
- [交付报告](../outputs/hangzhou-rings-20261030/verification.json)：从成片提取音轨，与原始混音比较 9 个波形窗口，测得偏移均为 0，最低相关性约 0.9884。`subtitle_sync.passed=null`，没有把独立检查标作原主链路 `sync.py` 门禁通过；未记录人工听感复核。
- [媒体检查](../outputs/hangzhou-rings-20261030/final-check.json)：0 项失败、1 项提示，测得约 -14.1 LUFS / -1.7 dBTP；黑帧、冻帧和静音检测通过。提示为没有内置可切换字幕轨，双语字幕已烧录，独立 SRT 随工程保留。
- 已查看[真实成片看板](../outputs/hangzhou-rings-20261030/contact-sheet.png)及开场、西湖、跨江、天际线和片尾的编码帧。修正了宽景下近裁面造成的深度条纹，并从 JPEG 中间帧改为无损 PNG，使项目工具明确执行 RGB→BT.709 视频范围转换；没有放宽 yuv420p 或帧数断言。早期全范围输出和工具失败报告留在结果目录，成片使用后来通过检查的版本。
- Node 语法检查、Python 编译、Ruff 的未定义名称/语法规则和 `git diff --check` 通过。主混剪、ASR 缓存和 Qwen 实现未改动；本次没有把历史 51 项测试结果当作本轮完整测试结果。

## 宿主 Agent 创作交接（2026-10-29）

- 新增 `prepare --plan ... --output ...`；写稿、提示词与生图由宿主负责，本地命令只检查计划和文件。AiToEarn 设计参考与固定修订见 [open-source.md](open-source.md#设计参考aitoearn)。
- `tests/test_creation.py` 新增 11 项检查：真实 PNG 从缺失任务到就绪清单，再通过现有素材导入与选片；相对路径、原稿/发布文案隔离、摘要和提示词保留；损坏图片及错误摘要被拦截；无效绑定/类型/空台词/重复 ID 被拒绝；输出目录不能覆盖；外部视频和缺失参考图保持显式任务。禁用 PATH 后，图片准备 CLI 仍能返回正确的 pending/ready 退出码，无需 FFmpeg。
- [实际示例报告](../outputs/creation-handoff-20261029/pending-example/creation-report.json) 为 `pending`，列出宿主生图需求，退出码 2；没有伪造图片或调用远程生成服务。测试图片是程序生成的纯色 PNG，仅验证文件交接，未测试宿主生图质量或外部 AI 视频服务。
- 执行 `uv sync --extra download --extra asr` 后，[完整 pytest](../outputs/creation-handoff-20261029/pytest.txt) **71 项通过，28.94 秒**，保留现有 MoviePy / NumPy 弃用警告。Ruff 对新增模块与测试检查通过，`git diff --check` 通过。原有字幕/音轨验收及 ASR 缓存语义未修改。

[文档导航](README.md) · [当前使用方法](usage.md) · [当前架构](architecture.md)

## 如何阅读这些记录

本页保留各阶段实跑证据，阶段内的“当前”“默认”“最新”指当时状态。阅读当前行为请以使用指南、架构和专项文档为准，尤其不要沿用早期的字幕合并回退策略。

截至 2026-10-25，最近一次完整套件记录为下文“项目内 ffmpeg-skill 扩展”的 **51 项通过**；网页下载、独立转录、字幕和声音控制各自的真实输入与边界分别记录。`outputs/` 下的链接指向本机保留证据，未随 Git 分发。可随仓库查看的展示媒体位于 [media/](media/README.md)。

后续视频号适配验证见下文 2026-10-29 条目；历史套件数字不代表当前测试总数。

按阶段保留实际运行记录。首轮在本机 macOS arm64、Python 3.12、系统 FFmpeg 8.0.1 上运行；后续声音克隆及 IndexTTS 控制实验追加在文末，各阶段环境单独说明。没有使用付费 API；本机算力、流量和存储不等于零成本。

## 2026-10-29：微信视频号下载适配

- 新增可选本地 `wx_channels_download` API 适配，核对版本 **v260907**。已接入捕获列表、明确 ID/精确 URL 匹配、视频详情与 `/play` 解密流，复用原下载预算、摘要缓存、完整解码、素材清单和失败重试。CLI 提供 `--wechat-list`、`--wechat-api`、`--wechat-feed-id`，清单支持每项指定 ID。项目不分发上游二进制或自动修改证书/系统代理。
- 确定性下载测试 `uv run --no-sync pytest tests/test_downloads.py -q`：**21 项通过**，包含本地真实 HTTP 与 FFmpeg。新增用例验证错误视频 ID、未捕获目标、微信页面未连接、服务离线、短边格式选择、尺寸不符、损坏解密流、大小上限、离线缓存/损坏修复、音轨导入、混合批次及 CLI 失败重试。这里的 `/play` 测试替身提供已解密媒体，不代表其自身实现了解密。
- 最终完整套件 `uv run --no-sync pytest -q`：**60 项通过，52.50 秒**；MoviePy 在 NumPy 2.5 下报告 588 条弃用警告，无失败。变更文件通过 Ruff 检查及 `git diff --check`。
- 单独的联网烟测使用本次已保存的真实视频详情作为元数据回放，调用实际 v260907 `/play` 服务进行 CDN 下载与解密；**未重新建立微信捕获连接**。目标为 `https://weixin.qq.com/sph/AhlgazCBkY`，视频 ID `15034134739333679808`，作者“境策通出海”。新适配器选择 `xWT111`，下载与完整解码成功：**26.841995 秒、720×1280、H.264/AAC、4,049,189 字节**，SHA-256 为 `84c76fd640735daa541644ef11268cd8877c83d3c754ac65c5cb7430000f72f5`，与本次先前手工捕获下载的文件一致。该烟测独立于确定性套件，不声称每次平台请求都会成功。
- 平台元数据曾标注 1080×1920、32 MB，而“原始视频”下载实际为 576×1024；明确选择 `xWT111` 后实际为 720×1280。适配器因此只使用显式格式并校验实际尺寸，不依赖原始视频标注。画面字幕不视为独立字幕轨。
- 此次执行环境为 macOS **x86_64**、Python **3.12.13**。先按约定尝试 `uv sync --extra download --extra asr`，锁定的 `onnxruntime==1.31.0` 没有 Intel macOS wheel，无法安装；随后使用 `uv sync --extra download` 并仅在本地测试环境中安装 `faster-whisper`、`auto-editor` 及可用的 `onnxruntime==1.19.2`，以 `--no-sync` 运行测试。未修改依赖锁或语音实现，也未用这一环境验证真实 ASR 模型精度。
- 烟测服务明确关闭代理和证书安装，完成后已停止。逐项对比原网络服务代理设置一致，确认本次临时证书已不存在。签名 CDN 地址、Cookie 与解密密钥未写入项目文档或提交文件。

## 2026-10-25：开发者文档与展示媒体整理

- README 改为能力、真实效果与快速开始入口；原有详细命令迁入 `usage.md`，新增文档导航及 `ai-guide.md`。开源说明区分设计参考、实际调用与直接分发，补充对应代码及版本记录。
- 对照 `cli.py`、`speech.py`、`captions.py` 修正文档中的字幕模式与审计 schema 说明；显式拆条示例同时设置 `caption_switch="audio_clip"`，避免沿用咖啡配置的整句切换策略。
- 展示媒体来自已有 Edge TTS 样片：原样保留六帧接触表，使用 `videocut ffmpeg` 裁出第 5～10 秒并缩小导出无声 GIF。GIF 实际解码为 240×428、60 帧、总计 5000ms；已查看最终 GIF 的六帧接触表。素材归属与原成片摘要保存在 `docs/media/demo-source.json`。
- 核对 10 份文档的 100 处本地链接/锚点、2 个 JSON 示例和 19 个 CLI 帮助入口，均通过。`git diff --check` 通过。检查报告保存在本机 `outputs/docs-refresh-20261025/documentation-check.json`。
- 本轮修改文档与展示媒体，没有修改运行代码，未重跑完整 pytest 或语音模型。下文 51 项通过属于此前 FFmpeg 接入阶段的完整验证，不冒充本轮新测试结果。

## 2026-10-25：网页下载接入与新素材成片

本轮将 yt-dlp 2026.10.21 作为可选依赖接入 `videocut download` 和原有素材清单入口；实际运行使用项目 `.venv` 中的安装包，没有调用测试目录里的源码版，也没有读取浏览器 Cookie。

- 新素材组：[B 站 BV1nx411u79K](https://www.bilibili.com/video/BV1nx411u79K)，80.384 秒、640×360；[TikTok 6984138651336838402](https://www.tiktok.com/@barudakhb_/video/6984138651336838402)，22.667 秒、540×960。两个都通过音视频探测和完整解码，输出可直接用于渲染的素材清单。
- 将代理显式设为不可用的 `127.0.0.1:1` 复跑，两项均命中已校验缓存，没有网络下载。另行下载同一 B 站来源的 M4A，80.384 秒，只有 AAC 音频流，缓存与视频规格独立。
- 另外使用含网页 URL 的素材清单导入，保留自定义 ID 与标签；原有 `examples/materials-preview.json` 的 10 项图片、视频、贴纸和配乐也全部通过，原命令继续可用。
- 使用新的应用入口提取 TikTok 7047596209028074758 的英文字幕；记录平台来源、语言和摘要，不把平台未明确说明的字幕推断为人工制作。
- 通过应用入口导入 B 站播放列表的前两个分 P，分别保存、校验。这里验证的是显式 `--playlist --limit 2`，不冒充本次又下载过整套 23 项。
- 一个成功缓存链接与微信视频号链接组成混合批次：退出码为 1，但成功素材保留在清单；视频号记录 `UNSUPPORTED_URL`。`--retry-failed` 只尝试那个失败链接，结果仍明确失败。
- 用刚下载的两组视频制作[验收样片](../outputs/download-integration-20261025/film/final.mp4)：14.462 秒、480×854、H.264/AAC；3 镜头、3 条字幕、淡入和滑动转场，本机 macOS 配音。音画轨时长差约 4ms，完整解码通过，六帧接触表已检查。该样片采用整句音频文件边界字幕，强制对齐验收状态是未验证，不能把轨长度差当作逐词字幕同步正确的证明。
- [下载演示配置](../examples/download-demo.json)也实际运行，输出保存在 `outputs/download-integration-20261025/example-film/`，可以直接复用下载产生的 `materials.json`。
- 12 项新增自动检查使用真实本地 HTTP 服务与 FFmpeg：含服务器断流及 Range 续传、同大小缓存损坏修复、视频／音频隔离、网页字幕、同名来源隔离、播放列表开关和限量、单项及整批上限、失败项保留的部分文件计入整批预算、无效媒体拒绝与恢复、失败重试、真实 SIGINT 中断后续传并处理未开始链接、本地文件兼容。
- 缓存校验故障注入：临时去掉 SHA-256 检查，缓存损坏验收立即失败；随后恢复原代码。该检查使用同大小损坏数据，不能仅靠文件大小碰巧通过。
- 最终 `pytest -q` 为 **38 passed**；`ruff check videocut tests scripts` 和 `git diff --check` 通过。MoviePy 对 NumPy reshape 的既有弃用警告仍保留，没有修改上游包来隐藏警告。

任务报告、失败重试记录、测试日志和故障注入证据保存在 `outputs/download-integration-20261025/`。本轮没有新增独立 GPT/Claude API、调度服务、长视频分段 ASR 或自动高光剪辑，仍按第一期素材入口范围交付。

## 2026-10-25：独立转录工具（二期）

新增独立 `videocut transcribe`。输入本地音视频后只导出文字、字幕、逐词 JSON 和运行报告，不自动触发资源下载、精剪、混剪或大模型。Whisper 实现移入 `videocut/transcription.py`，原 `cleaning.transcribe` 保留兼容接口和编辑消费检查。

- 用本机 macOS Samantha / Tingting 合成新的中英文测试录音，参考文字仅用于事后检查，没有作为识别提示输入。英文 WAV 与中文 MP4 分别切成 3 个窗口，真实 faster-whisper/base 自动检测为 `en` / `zh`，输出 TXT/SRT/JSON。原始结果保留了英文近音和中文“转路”“教對”等错误，未冒充逐字准确。
- base 与 tiny 分别真实运行；同一输入和分段参数的模型身份、缓存键不同。base 的中文、英文及长样例重跑均复用完整缓存，不加载模型；本次新解码数组长度为 0。
- 1 小时 FLAC 压力样例在开头和结尾放置英文语音，中间主要静音。300 秒分段、两侧各 1 秒上下文，共 12 段；末尾语音仍位于约 59:45，源文件时间没有重置。最大单个 PCM 数组为 4,832,000 个 float32 采样，约 18.4 MiB；这不是总进程内存，不含模型和解码临时缓冲。本例不代表一小时连续讲话的吞吐或识别准确率。
- 另一份冷缓存真实执行长样例，第一段落盘后发送 SIGINT，进程以 -2 退出；重跑复用 1 段并识别剩余 11 段，完整输出成功。
- 复制缓存并损坏其中一段，真实重跑只重识别 1 段、复用 2 段。`--force` 实际重新识别全部 3 段。
- 复制导出结果后修改 TXT；普通重跑以 1 退出并保留修改，显式 `--overwrite` 才替换。模型、语言、源文件或参数变化不会静默覆盖另一份结果；源媒体本身始终禁止覆盖。
- 静音 WAV 的独立转录返回 `no_speech`，空文本和字幕；带静音音轨的视频交给原 `cut` 时仍拒绝缺少词时间的数据，没有生成伪精剪文件。
- 分别执行原有 `cut` 与 `mix`，显式提供独立导出的中文 MP4 转录结果，两次均不重新识别。另实际运行不提供 JSON 的 `cut`，验证其走共享 ASR。混剪回归输出 14.553 秒、320×568、H.264/AAC，完整解码通过，`transcript_source=provided`；本样例没有需要删除的区间，未宣称新增自动高光或剪辑算法。字幕仍是 ASR 估计，未宣称通过强制对齐验收。
- 新增 11 项确定性检查：实际 FFmpeg 窗口读取、全局时间、重叠归属与真实重复词、断点缓存、损坏修复、语言和模型指纹失效、无语音策略、用户校对保护、源媒体保护、错误来源拒绝及 `cut --transcript` 实际命令。后者故意传入不存在的模型路径，确认合法 JSON 直接消费，空 JSON 拒绝而不偷偷运行识别。模型替身仅验证编排，不替代上述真实模型实跑。
- 两次故障注入分别临时移除词时间的全局偏移、缓存内容摘要比较；对应测试均失败，随后恢复原代码。最终全项目 **49 passed**，Ruff 和 `git diff --check` 通过；原 MoviePy/NumPy 弃用警告保留。

全部数据、命令日志和[验收报告](../outputs/transcription-integration-20261025/report.html)保存在 `outputs/transcription-integration-20261025/`。本轮没有建立自动编排服务，工具之间仍通过文件显式衔接。

## 完整素材混剪

- 视频：`outputs/coffee-edge/final.mp4`。
- 真实下载：4 条 Mixkit 视频、2 张 Unsplash 照片、3 个 Twemoji 透明贴纸、1 条 Mixkit 爵士配乐。
- 中文 Edge TTS 逐句生成配音，12 句字幕依据实际 PCM 音频时长定时。
- 6 个镜头；照片缓慢推近；5 次转场，包括淡入淡出、滑动和擦除；6 个浮动/缩放贴纸；配乐淡入淡出；最终响度标准化。
- 实际 41.108 秒、720×1280、24fps、H.264/AAC。
- 视频轨 41.083333 秒、音轨 41.108 秒，尾部长度差约 24.7 毫秒；逐帧时长取整范围内，末句配音完整。
- 全片完整解码通过；六个时间点截图检查过字幕、裁切和贴纸透明度。
- 素材和配音缓存命中后，全流程约 50.43 秒；首次下载和首次配音耗时不包含在该缓存运行数字里。
- 结果与机器报告：`outputs/coffee-edge/verification.json`、`timeline.json`、`sources.json`、`contact-sheet.jpg`。

## 原片精剪后再混剪

测试输入 `outputs/raw-edge/raw.mp4` 是下载的咖啡画面加在线合成旁白，刻意加入停顿和口头禅，不冒充下载的真人口播。

- 原始时长：20.541667 秒。
- base 模型的真实本地识别，启用 VAD；没有把预置台词或 `ground-truth.json` 交给模型/剪辑器。
- 识别到并删除四处配置词：“那个”两处、“就是说”一处、“嗯”一处。
- 同时删除长停顿，保留三个正文句子的声音。
- 自动结果：`outputs/mixed-base/final.mp4`，9.791667 秒；音画轨长度差约 0.667 毫秒，完整解码通过。
- 三句字幕重排；原始视频与素材穿插；原片镜头从剪后相应时间读取，配原声；转场、贴纸和配乐已烧录合成。
- 实际 ASR 把“留一杯”写成“留意杯”。原始输出保留；Codex 校对一个同音字后写入 `outputs/corrected-transcript.json`，用 `--transcript` 重新成片：`outputs/mixed-reviewed/final.mp4`。该版明确标为 `transcript_source=provided`，不冒充又跑过一次识别。
- 审计依据：`outputs/mixed-base/cleaning/transcript.json`、`edit-plan.json`；校对内容与来源校验和在 `outputs/corrected-transcript.json`。

## 上游 Auto-Editor

真实调用 Auto-Editor 29.3.1 的 macOS arm64 发布二进制，对另一个离线配音测试输入粗剪：17.058 秒 → 10.541667 秒。输出 `outputs/auto-editor/cleaned.mp4`。该结果只证明静音粗剪，不能证明模型识别了口头禅。

## 自动验证

`uv run --extra asr pytest -q`：7 个测试通过。包括真实 FFmpeg 音画剪辑、音画时长、16kHz 解码、部分词时间跨越静音时仍保留字幕、字幕时间重排、删除区间合并、完整词匹配和简繁口头词等。

`uvx ruff check videocut tests scripts`：通过。

## 首轮验证时的边界

素材选择按目录标签匹配，示例标签来自素材页面描述；没有假称做过任意上传素材的视觉理解。首轮验证时声音复刻没有接入，后续状态见下文追加记录。气口处理是降噪/轻度噪声门，不是专门的呼吸识别模型。ASR 字幕仍需要校对；该项目交付的是可执行、可检查、可修改的本地流程。

## 追加：F5 参考音色重新成片

使用用户提供的约 11 秒录音作为参考条件，通过独立 Python 3.12 / F5-TTS MLX 环境生成咖啡稿 12 句旁白；未针对用户训练专属模型。完整说明见 [voice-cloning.md](voice-cloning.md)。

- [成片](../outputs/coffee-qianchen-20261024-194215/final.mp4)：60.830 秒、720×1280、H.264/AAC；6 镜头、12 句字幕、6 个贴纸、5 次转场。
- [机器报告](../outputs/coffee-qianchen-20261024-194215/verification.json)：视频轨 60.791667 秒、音轨 60.830 秒，差约 38.3ms；完整解码通过，画面抽查通过。
- 字幕与镜头按新音频真实采样数重算；合成耗时 74.32 秒，已命中生成后的克隆旁白缓存，不包含下载和首次语音生成。
- [旧结果校验](../outputs/coffee-qianchen-20261024-194215/previous-results-verification.json)：此前 268 个输出文件未修改、未缺失。
- 后续试听发现“黑咖啡”词内存在不自然停顿。ASR 可以识别出台词，但没有评估词内节奏，因此不能以文字正确证明语音自然。

## 追加：IndexTTS-2.5 与 SSML 控制实验

macOS arm64、16GB 内存、独立 Python 3.11.14 / PyTorch 2.8.0 MPS 环境，使用同一用户录音。没有重新生成视频，也没有替换 `videocut` 的声音提供方。

- 7 组样例：默认、`duration_factor=0.85`、高兴向量、平静向量、`HANG2`、`XING2`、XML 插入 500ms 静音。
- 默认与稍快样例分别长 4.586 秒、3.901 秒。首个样例生成 112.879 秒，后续样例约 11.5～30.4 秒；这是本机本次短句运行记录，不是完整生产成本或吞吐保证。
- 全部样例完整解码通过；本地 faster-whisper/base 在没有初始提示词的情况下核对实际内容，保留同音字、繁简字识别差异。
- 默认、稍快、高兴、平静四个样例在 ASR 估计的“黑咖啡”词边界内，均未检出达到 80ms 的低能量间隔。检查使用统一响度副本、-35dB 阈值，是启发式验证；不能推广为强制词内零停顿或客观情绪评分。
- XML 停顿适配层实际插入 11,025 个全零采样，22,050Hz 下为 0.5 秒；相邻语音自带留白可能使感知总停顿更长。
- 此前 337 个测试结果文件的校验和未变，参考录音未修改；机器报告另记录了 macOS `.DS_Store` 元数据变化。
- 克隆旁白读取及格式检查加入后，最近一次 `uv run pytest -q` 为 9 项通过；`uvx ruff check videocut scripts tests` 通过。这些单元检查不能替代模型输出与听感验收。

试听顺序、逐样例耗时、下载及复现方式见 [voice-controls.md](voice-controls.md)。实际证据包括 [manifest.json](../outputs/indextts25-controls-20261024-210657/manifest.json)、[speech-qa.json](../outputs/indextts25-controls-20261024-210657/speech-qa.json) 和 [verification.json](../outputs/indextts25-controls-20261024-210657/verification.json)。

该短句实验阶段验证的是原生拼音、情绪向量和语速参数，以及适配层的 XML 拼音转换和停顿拼接。`sub alias` 已实现但未纳入语音实测；当时尚未进行 IndexTTS 视频集成，后续记录见下节。`w`、`emphasis`、词级情绪、SSML 情绪标签和完整 SSML 兼容仍未实现。

## 追加：IndexTTS-2.5 完整视频

通过新增 `--tts indextts` 提供方，将用户参考音色的 12 句新旁白转换为单声道 48kHz PCM16，复用原咖啡素材、转场、贴纸和配乐；按实际采样数重算字幕与镜头时长。前一版 F5 视频及短句控制样例均保留。

- [最终视频](../outputs/coffee-indextts25-20261024-213812/final.mp4)：49.401 秒，720×1280、24fps、H.264/AAC；6 镜头、12 句字幕、6 个贴纸、5 次转场。
- [机器报告](../outputs/coffee-indextts25-20261024-213812/verification.json)：完整解码通过；视频轨 49.375 秒、音轨 49.401 秒，差约 26ms；六个时间点画面抽查通过。
- 原生 22.05kHz 语音通过 FFmpeg 重采样及响度处理进入 48kHz 旁白入口。参考录音与全部模型文件摘要、代码修订和逐句原生参数记录在 [index-manifest.json](../outputs/coffee-indextts25-20261024-213812/speech/index-manifest.json)。
- 采用默认自然语气。对“早晨、开始、出发、愿、从容”等输入应用了原生拼音标注；字幕显示原稿，不显示控制标记。原始尝试与重生成结果均保留，实际配置见 [input-config.json](../outputs/coffee-indextts25-20261024-213812/input-config.json)。
- [最终内容检查](../outputs/coffee-indextts25-20261024-213812/speech-qa.json)对应全部 12 句最终音频；不提供 ASR 初始提示词，保留真实近音、同音及繁简字识别差异。“黑咖啡”在估计词边界内未检出达到 80ms 的低能量间隔；这项检查不代表逐字发音或听感均经人工验收。
- CLI 合成流程 66.67 秒；已命中准备好的 IndexTTS 旁白缓存，不包含首次语音生成、模型加载、纠音重试和中间导出耗时。
- [版本核对](../outputs/coffee-indextts25-20261024-213812/latest-model-check.json)：2.5 本地模型与当时远端修订一致，官方代码 HEAD 与本地已验证修订一致。
- [旧结果检查](../outputs/coffee-indextts25-20261024-213812/previous-results-verification.json)：385 个此前测试结果文件校验一致，未缺失；排除系统 `.DS_Store` 元数据。原始参考录音未修改。
- `uv run pytest -q`：10 项通过；`uvx ruff check videocut scripts tests`：通过。

这一阶段接入的是原生 IndexTTS 配音参数及逐句发音输入，SSML 实验适配层仍未进入视频 CLI。完整使用说明见 [voice-controls.md#完整视频配音](voice-controls.md#完整视频配音)。

## 追加：字幕短语同步修复

原版使用整句 WAV 的边界显示字幕，首尾留白和句内停顿均包含在内。对原版与旁白做分段波形相关性检查，没有发现整体音轨偏移；后续修复字幕显示边界和短语切换，不改变声音。

- [修正版视频](../outputs/coffee-indextts25-subsync-20261024-220357/final.mp4)：49.401 秒、720×1280；12 句原稿拆为 23 条短语字幕。原旁白 WAV 与修正版逐字节一致，原视频保留。
- 根据真实词时间映射原稿，结合声学停顿修正 ASR 偏早的短语边界，避免把首尾静音直接作为字幕显示区间；没有使用固定的整体平移量。
- [同步报告](../outputs/coffee-indextts25-subsync-20261024-220357/synchronization-verification.json)确认 12 个时间点没有测到整体波形偏移，477 个先前结果文件校验未变。[逐短语审计](../outputs/coffee-indextts25-subsync-20261024-220357/caption-alignment.json)与[实际视频帧](../outputs/coffee-indextts25-subsync-20261024-220357/caption-boundary-check.jpg)均保留。
- 完整解码通过；最终重合成复用旁白与背景，30.87 秒，不含排查、首轮修复导出和文档工作。
- `uv run pytest -q`：13 项通过；新增实际 PCM 静音边界、ASR 边界提前以及音频摘要不匹配拒绝复用的检查。Ruff 通过。

上述是早期修复的历史记录。音轨相关性与少量截图不能证明字幕同步正确；当前实现已由以下工作流替换。

## 追加：强制对齐与成片字幕验收

- 默认 IndexTTS 使用中文 CTC 给定原稿逐字对齐，再用 Whisper 给定原稿 tokens 独立对齐交叉检查；两句模型分歧超过 180ms，自动采用整句字幕。没有设置全片提前 1 秒的补丁。
- [正式流程成片](../outputs/coffee-workflow-final-20261024-223131/final.mp4)：49.401 秒、720×1280、21 条字幕、6 个镜头；配音、转场、贴纸和音乐延续原版，未重新生成声音。
- [字幕实际显示验收](../outputs/coffee-workflow-final-20261024-223131/subtitle-sync-verification.json)：读取全部 1185 个编码帧，检测到 21 个字幕显示区间，无多余或碎裂区间；相对声学参考起点，出现提前 40～79ms，消失延后 25～141ms。检查的是成片像素，不是从字幕 JSON 抄时间。
- 最终音轨与独立旁白进行逐字幕高能量窗口相关性检查，最低相关性约 0.970，所有窗口测得偏移为 0；完整解码通过。
- [运行报告](../outputs/coffee-workflow-final-20261024-223131/verification.json)：37.62 秒，包含合成、交叉对齐与验收，命中了已有声音、背景和 CTC 缓存；不包括本轮下载、排查与试跑。
- [旧结果核对](../outputs/coffee-workflow-final-20261024-223131/previous-results-verification.json)：本轮开始前的 521 个结果文件均未修改或缺失，新旧完整旁白的 SHA-256 一致。
- `uv run pytest -q`：19 项通过。新增真正渲染编码的正反例：正确字幕通过；计划与成片字幕同时延后 1 秒，仍被声学参考检查拦截。另覆盖漏字幕、过早消失、CTC 峰值不能充当音节结束、模型分歧退回整句。

验收失败不交付 `final.mp4`，保留候选与失败报告。对齐仍有模型估计误差，不能将这些范围理解为人工逐字标注精度；发音、情绪及素材语义不属于这个同步门禁。复用与首次安装见 [字幕同步工作流](subtitle-sync.md)。

## 最新：先固定分条，首条绑定音频片段起点

用户明确要求逐条切换，故移除此前“分歧时合并整句”的实现。新流程在合成前冻结字幕分条，Qwen 官方强制对齐定位每条的字词时间；每句首条绑定 PCM 音频片段起点，后续字幕默认保留 200ms 阅读提前量。落盘 SRT 是渲染时间的唯一来源，不能再用两份不同精度的时间轴。

- [成片](../outputs/coffee-fixed-lines-20261024-225609/final.mp4)：49.401 秒、23 条字幕，原声音逐字节一致。
- “早晨”：旧 SRT 为 0.180 秒；新 SRT 为 0 秒，实际第一帧已经显示。
- “先给自己”：旧 SRT 为 3.927 秒；新 SRT 为 3.707 秒，实际显示 3.708333 秒，距 PCM 片段起点 3.707479 秒约 0.854ms。
- “喜欢清爽”“就喝一口黑咖啡”分别从 SRT 的 24.219 秒、26.019 秒显示；不再合并。
- [逐条对照](../outputs/coffee-fixed-lines-20261024-225609/timing-comparison.json)记录旧 SRT、新 SRT、真实视频显示时间与模型发声时间。首条从片段起点显示包含片段留白，不应将其称为模型声学时间的零误差。
- [成片验收](../outputs/coffee-fixed-lines-20261024-225609/subtitle-sync-verification.json)：读取 1185 帧，23 个连续字幕区间全部匹配，无额外或碎裂字幕；记录实际 SRT 摘要。最终语音窗口最低相关性约 0.970。
- [运行报告](../outputs/coffee-fixed-lines-20261024-225609/verification.json)：命中声音、背景和 Qwen 对齐缓存后，正式运行 33.16 秒；不包含模型下载、首次运行库加载和排查。
- [旧文件检查](../outputs/coffee-fixed-lines-20261024-225609/previous-results-verification.json)：本轮开始前 584 个结果文件均未修改或缺失。
- 22 项测试通过：用户新规则替换了旧“合并回退”预期；新增分条不可合并、首屏第 0 帧、SRT 回读一致性、原稿完整覆盖、异常对齐报错。真实延后 1 秒的编码视频继续被拒绝。

当前 Qwen 模型的时间刻度为 80ms（配置 `timestamp_segment_time=80`）；SRT 毫秒精度和 24fps 视频帧检测不能把这个模型分辨率变成逐毫秒声学精度。每句首条的 PCM 片段起点则可直接由采样数精确确定。

## 最新：首版显示规则与 IndexTTS 的控制对照

用户指出首版 Edge 既没有拆字幕，也没有使用 IndexTTS，需要区分这两个变量。首版 12 条字幕逐条核对源 WAV 的 PCM 时长，起点误差仅为浮点精度量级。随后固定 IndexTTS 配音，对比整句与拆条：

| 后半句文本 | 整句从何时已可读 | 拆条从何时显示 | 差异 |
| --- | --- | --- | --- |
| 不必一开始就匆忙 | 0 秒 | 0.960 秒 | 0.960 秒 |
| 留一杯咖啡的时间 | 3.707 秒 | 5.747 秒 | 2.040 秒 |
| 慢慢叫醒还没睡醒的你 | 12.643 秒 | 14.363 秒 | 1.720 秒 |

整句版还恢复显示到对应 WAV 结束，避免拆条版按模型末字过早收起后出现额外空白。以上是可复现的展示差异，不能直接称为语音音轨延迟；主观同步感仍需结合实际播放判断。

- [同音频左右对照](../outputs/coffee-sentence-baseline-20261024-231149/same-audio-caption-comparison.mp4)：左为整句，右为上一版拆条，仅播放同一份 IndexTTS 音轨；8.48 秒，完整解码通过。
- [新完整版](../outputs/coffee-sentence-baseline-20261024-231149/coffee-indextts-sentence-captions.mp4)：保留 IndexTTS 参考音色，恢复首版 12 条整句，49.401 秒。字幕逐条文字与首版 Edge 完全一致；两版 IndexTTS 的独立旁白 SHA-256 相同。
- [控制对照记录](../outputs/coffee-sentence-baseline-20261024-231149/controlled-comparison.json)保存三组来源、原版 Edge 的 PCM 核验及句内文本出现差异。
- [成片检查](../outputs/coffee-sentence-baseline-20261024-231149/subtitle-sync-verification.json)：1185 帧、12 个完整字幕区间；字幕相对 PCM 片段起点最大误差约 39.9ms，在 24fps 一帧内。音轨最高测得偏移为 0，窗口相关性最低约 0.987。
- 默认配置明确恢复 `caption_layout="utterance"`；此模式不加载对齐模型，审计为 `pcm-caption-v1`，没有伪造字词发声时间。显式 `phrases` 或 `subtitle_phrases` 才运行对齐。
- 正式运行 32.23 秒，复用声音与背景。24 项测试通过，包含两种模式的真实编码正反例；614 个此前结果文件未改动，原配音未改动。

## 最新：上一句口播结束即显示下一句

用户进一步明确需要“一句话结束，字幕立刻出下一句”。上一轮虽然恢复了整句显示，仍等待下一句文件起点；IndexTTS 首句末字结束约为 3.200 秒，下一份 WAV 从 3.707 秒才开始，因此有约 507ms 的可消除等待。

默认整句切换改为 `caption_switch="previous_speech_end"`：首屏从 0 秒开始，之后按上一句末字结束点切换；相邻 SRT 共用边界，最后一条保持到视频结束。音频、镜头与素材不移动。下一句文字会提前于自身口播出现，属于预读策略；声学模型只用于找上一句结束，当前模型时间刻度为 80ms。

- [新视频](../outputs/coffee-immediate-captions-20261024-233511/coffee-next-caption-immediate.mp4)：49.401 秒、12 条完整字幕，配音保持逐字节一致。
- [SRT](../outputs/coffee-immediate-captions-20261024-233511/captions.srt)中“先给自己，留一杯咖啡的时间。”从 3.200 秒显示；成片实际 3.208333 秒显示，与上一句检测结束点差 8.33ms，不再等到 3.707 秒的下一段文件起点。
- [成片检查](../outputs/coffee-immediate-captions-20261024-233511/subtitle-sync-verification.json)：1185 帧、12 个连续字幕区间、0 个空白字幕帧；音轨测得偏移为 0，相关性最低约 0.987。
- 正式运行 32.73 秒，复用已有音频、背景与 Qwen 原始对齐；不重新生成声音。26 项测试通过，新增末字结束到下一条的无缝切换、真实编码视频无空白帧及延后 1 秒拒绝交付。
- 640 个此前结果文件均未修改或缺失。旧 `caption_switch="audio_clip"` 继续可显式选择，拆条模式也保留，均不能静默改变已确定的分条。

## 追加：项目内 ffmpeg-skill 扩展（2026-10-25）

- 固定 ffmpeg-skill 2.16.1 / `f2d90ea603a663711c3d6aa9775d2a2380d83182`，MIT；运行脚本、技能、模板随项目和 wheel 保存，源文件摘要见 `.agents/skills/ffmpeg-skill/UPSTREAM.json`。新增 `videocut ffmpeg`，42 个公开工具加 `doctor / contract` 可用；运行时不下载或更新代码。
- 安装 Homebrew `ffmpeg-full 9.0.2`。它升级 x265 后，旧精简版 8.0.1 因动态库 ABI 失配无法启动，故将系统精简版升级到 9.0.2_1；保留独立入口，未将完整构建强制链接为全局 FFmpeg。最终[能力检测](../outputs/ffmpeg-integration-20261025/doctor-final.json)为 `ok=true`、42 工具 `usable=yes`，唯一缺少的是可选 Parakeet 引擎。
- 使用 [scripts/verify_ffmpeg_tools.py](../scripts/verify_ffmpeg_tools.py) 生成合成素材：480×854、24fps、6 秒纯色视频、两条中文 SRT、440Hz 脉冲和 1000Hz 背景音；不把脉冲称为真实口播，也没有调用 ASR 或声音模型。
- 实际烧录 Heiti SC 中文字幕。在 0.25、3.0、5.75 秒抽取的编码帧无字幕白色像素；1.5、4.5 秒分别检测到 14,140、11,947 个白色像素。已查看[带时间码拼图](../outputs/ffmpeg-integration-20261025/complete/contact-sheet.png)，中文可读。这是五个时间点的抽样验证，不是原混剪管线的全部帧验收。
- 实际对脉冲侧链执行音乐自动压低，1000Hz 分量在有脉冲窗口比空白窗口低约 10.01dB。合成 10-bit PQ 测试文件经 `color --to-sdr` 输出 H.264 / yuv420p，BT.709 原色、传递和矩阵标记，`hdr=false`；输入已独立核对为 PQ，不使用 `--force` 绕过检查。不代表真实相机 HDR 素材的主观调色验收。
- [YouTube 导出](../outputs/ffmpeg-integration-20261025/complete/youtube.mp4)：6 秒、1920×1080、24fps、H.264 / AAC 48kHz，完整解码通过。平台检查 0 项失败、1 项提示：没有独立可切换的字幕轨，画面内已经烧录中文；保留提示，不将其改为全项 PASS。
- [机器报告](../outputs/ffmpeg-integration-20261025/complete/verification.json)、[实际命令](../outputs/ffmpeg-integration-20261025/complete/commands.json)及每个工具的 JSON/标准错误均保留。合成输入摘要未变。初次能力检查的启动超时保存在 `smoke/`，测试素材缺少 PQ VUI 标记被拒绝的记录保存在 `verified/`；修正编码器标记后在新的 `complete/` 目录重新通过，未放宽断言或覆盖失败证据。
- 系统 FFmpeg 9 的回归发现旧 `-filter_complex_script` 参数已被移除，两个原有精剪测试失败。实现改为 `-/filter_complex` 读取同一份脚本后，两项原断言通过；ASR、剪辑规则及字幕重排语义未改动。
- 最终 `uv sync --extra download --extra asr` 后，升级后的系统环境执行[完整 pytest](../outputs/ffmpeg-integration-20261025/pytest-final.txt)：**51 项通过**，保留原有 MoviePy / NumPy 弃用警告。新增两项覆盖跨工作目录、带空格路径的真实裁切、音画时长、完整解码、预演不写文件、拒绝覆盖、源文件不变和工具帮助无需媒体程序。
- Ruff、`git diff --check`、sdist → wheel 构建通过；wheel 安装到仓库外目录后，通过其内置工具实际探测 3 秒媒体，确认不依赖源码目录。新工具的 `verified` 与平台检查不替代本项目 Qwen 与 `sync.py` 门禁；未声称全部 42 个工具均做过媒体实测。


## 2026-10-30 · 杭州白模与实景混剪：分段与样片（整片待合成）

- 已人工选片并下载12份 Commons 素材：11份照片/古画/资料图，1份塘栖运河实拍视频；逐项保存作者、原页面、许可、尺寸与SHA-256，核对原文件SHA-1。苏堤与良渚初选不够贴题，替换为明确的现场景观；未使用生图或生视频模型。具体条目见[混剪素材署名](../films/hangzhou/MONTAGE-CREDITS.md)。
- `montage-edit.json` 将95秒插入画面、4.833秒片尾映射到原4100帧时间轴。`montage.js` 使用Three.js照片/视频图层，保留原城市相机与双语字幕时间；地图标题先退出，实景标题后进入，避免叠化时两组标题重影。
- 实际完成2396帧、1920×1080/24fps、100个H.264/yuv420p/tv片段；共享`codefilm verify`检查实际文件、摘要、连续帧和格式通过。报告：[native-verification.json](../outputs/hangzhou-montage-20261030/native-verification.json)。这是插入段完整性，不是171秒整片验收。
- 实拍视频另做A→B→A定位检查，同一时刻两次PNG字节一致。三份有声样片实际出片：运河8秒/192帧、苏堤9秒/216帧、钱江新城5秒/120帧，均为960×540/24fps、H.264/AAC立体声；平台/内容检查0失败、2提示（预览分辨率低于720、无可切换字幕轨），未伪称全项PASS。已查看编码后总览及0.333/0.667/7.667秒转场帧。
- 确定性`tests/test_codefilm.py`实际运行5项通过，Python编译与Node语法检查通过。Ruff在当前根环境不可用，未记录为通过；根环境没有SciPy，混剪验收应使用杭州独立环境，未向主项目加GIS/音乐依赖。
- 开始时磁盘只余约280MB，确实出现小文件写入失败。清理本工具上次失败全范围试跑的两份编码中间件269,881,324字节，保留原成功成片、源数据、失败成片与日志，并保存清理记录。随后完成高清插入段，但正式合成前空闲仍约370MB，执行命令被2GB空间检查拒绝；22份片段FFmpeg预演及连续4100帧剪辑计划已保存。当前没有新的171秒完整视频，也未运行新成片35句OCR/9处波形验收。续跑命令见[继续制作](../outputs/hangzhou-montage-20261030/继续制作.md)。


## 2026-10-30 · 杭州快节奏混剪完整交付

- 用户要求加快节奏并最终合为一条片子。空间释放至约24GiB后，新增下载15张照片，人工查看27份素材总览；排除不相关地铁口画面，实际使用22份素材。安排51个实景/片尾窗口，89秒实景，图片主要1.5～2秒，与原Three.js城市运镜交替，增加光扫、推近和白模/实景分屏。
- 改为直接渲染完整时间轴：4100帧、1920×1080/24fps，35个检查过的编码片段。Three.js重复帧检查通过；图像与视频模型调用仍为0。时间轴、来源与脚本保存在杭州工程。
- 最终交付：[杭州-快节奏实景混剪.mp4](../outputs/hangzhou-fast-20261030/delivery/杭州-快节奏实景混剪.mp4)，170.967秒容器、170.833秒视频、H.264/yuv420p/tv、AAC立体声48kHz、12章节。SHA-256 `d208707a32a9cb55f320ae9f735ccdfa3118cb8a6f32b19ea4f7edbfd651ebd3`。
- 新成片35/35句字幕中点OCR匹配，9个波形窗口偏移均为0秒，最小相关系数0.9884。平台/内容检查0失败、1提示（无独立可切换字幕轨；已烧录双语字幕并另交SRT）。响度-14.1 LUFS、真峰值-1.6 dBTP、黑帧0%、最长冻结0.5秒、静音0%。已查看最终编码4×3总览、分屏及片尾静帧。完整报告：[verification.json](../outputs/hangzhou-fast-20261030/delivery/verification.json)。这是抽样OCR/波形验收，Qwen/sync.py仍passed=null，未记录人工听审。
- 初次后期在章节工具试图替换刚生成的同名文件时被防覆盖规则拒绝；失败日志保留。保留该次编码为before-chapters.mp4，再写入不同路径的正式成片并完成检查。`finish_fast_montage.py`已采用不同候选/正式文件名，未放松防覆盖规则。5项codefilm测试通过（0.86秒），Node语法、Python编译和git diff检查通过；未把此前样片检查当作整片验收。


## 2026-10-30 · 默认语音引擎改为 IndexTTS-2.5

- `demo / render / mix / raw-sample` 的语音合成默认值统一为 `indextts`，继续使用现有 IndexTTS-2.5 模型与独立环境；Edge 和 macOS 系统声音可显式选择。生成新旁白需提供参考录音；缺少录音时提前报错。已有录音与 `mix` 保持使用原声。
- 移除 F5 的 `--tts clone`、`--reference-text`、`--clone-model`、`--clone-vocoder`、`--voice-python` 及 CLI 生成分支。复用语音清单仍核对提供方和音频摘要，拒绝将 F5 清单作为 IndexTTS 使用。旧 F5 脚本、依赖锁和实验记录保留为历史材料。
- 新增 CLI 默认选择、旧参数拒绝、缺少参考录音提前失败、默认语音字幕流程、IndexTTS-2.5 请求与已生成 PCM 使用、F5 清单拒绝等回归检查。执行 `uv sync --extra download --extra asr` 后，完整 `uv run pytest -q`：**91 项通过，55.68 秒**；保留 588 条既有 MoviePy/NumPy 弃用警告。
- 实际检查 CLI 帮助仅列出 `indextts / edge / macos`，并显示默认版本 2.5。本次模型调用使用替身及合成 PCM 验证接口，没有新增实际模型推理、听感或视频验收结论。
- 文档整理：当前声音克隆指南集中说明 IndexTTS-2.5 的输入、缓存和验收；F5 命令及结果移至 `voice-cloning-f5-history.md`，使用指南补充引擎选择表。提交前语音相关测试 **18 项通过，0.14 秒**；`git diff --check` 通过。


## 2026-10-30 · 钱陈音色 / Three.js主导 / 两分钟版

- 用户将目标调整为约两分钟、Three.js为主、实景辅助且减少重复，并指定钱陈音色与IndexTTS2。使用已配置的官方IndexTTS-2.5本地运行；原始`钱陈声音.m4a`复制到本地`assets/voices/qianchen/`，SHA-256 `8832c74dc96277795934bb56b34b88e74992b6c1b4030932ea55a183faa0f112`，并保存24kHz单声道参考及索引，目录排除Git。
- 新稿24句、375字（含标点）；逐句生成缓存均验证SHA-256。原始语音合计108.5301875秒；去掉外缘静音、保留120ms保护后按实际PCM组成120秒，本次未做变速。独立base ASR覆盖全部句子，但地名存在多处同音字替换，未将其冒充Qwen记录或据此改写字幕，未记录人工听审。
- 主镜头为98.833秒完整Three.js（82.36%），12份实景各一次、各1.5秒，其中8次以辅助分屏呈现；片尾署名3.167秒。渲染2880帧与24段完整性通过。
- 首次新成片OCR为23/24，年份“一千零九十年”的“一”受亮色白模背景干扰被读为“二”。未改变原稿、匹配规则或断言；在城市和实景字幕上统一添加深色底衬，重新渲染并输出新的delivery-v2。先复查该年份帧正确，再对全片24句重新OCR，24/24通过。
- [正式成片](../outputs/hangzhou-two-minute-qianchen-20261030/delivery-v2/杭州-城市年轮-钱陈音色-两分钟.mp4)：容器和视频均120.0秒，2880帧，1920×1080/24fps，H.264/yuv420p/tv，AAC立体声48kHz，12章节，95,752,723字节。SHA-256 `1bd27b7fbb863730837bb49c75eefb239fdf580669cecd705a97afd779020aaf`。
- 9个波形窗口偏移均0秒，最小相关系数0.99956；-14.0 LUFS、-4.2 dBTP、黑帧0%、最长冻结0.6秒、静音0%。格式/内容0失败1提示（无可切换内嵌字幕轨，画面已烧录并附24条SRT）。已查看实际编码总览、主镜、辅助分屏与年份修正帧。[报告](../outputs/hangzhou-two-minute-qianchen-20261030/delivery-v2/verification.json)与失败证据保留，Qwen/sync.py仍passed=null。
- 5项codefilm测试通过（0.80秒），Node语法、Python编译与git diff检查通过。旧4100帧/35句验收默认保留，新片显式设2880帧/24句，符合用户调整时长的指令。


## 2026-10-31 · 太极缠丝劲图解动画

- 新增 [太极影片工程](../films/taiji-silk/README.md)：36 秒、1920×1080/24fps、864 帧，完整动作、足部剖析、五趾抓地、生根、足底外旋劲意、大腿左缠和整体回看。Three.js 原创程序造型，不调用生图、生视频、语音或付费 API；参考用户动作画的青蓝色调，未直接使用参考图像素。
- [正式成片](../outputs/taiji-silk-20261031/final.mp4)：视频与容器均 36.0 秒，H.264 High / yuv420p / tv / BT.709，AAC 48kHz 立体声。SHA-256 `fdf0b2304e14fddd03f702f31721ec5ed736ae26eb603331e1f8aa0f6e221dc0`。原创标准库合成五声音阶配乐，-20.0 LUFS、-8.5 dBTP。无旁白；交互版不带配乐。
- 最终 codefilm 清单 `e816bda8695a228b2910`：9 段各 96 帧，真实文件帧数与完整性检查通过；全片与分段使用同一源码摘要。最终实际 MP4 的 864 帧检查 passed=true。格式/内容检查 10 项 PASS、1 项 WARN、0 项 FAIL，`ok=true`、`verified=false`；WARN 为没有独立字幕轨，片内说明文字已绘入画面，不将其写成全项 PASS。黑帧 0%、最长冻结 0.8 秒、静音 0%。[帧报告](../outputs/taiji-silk-20261031/delivery-verification.json)、[媒体检查](../outputs/taiji-silk-20261031/delivery-check.json)保留。
- [姿态报告](../outputs/taiji-silk-20261031/qa/pose-verification.json)：144 个时刻承重脚固定，抓地后五个趾腹同处 0.012 模型高度，大腿转向按“从髋向足俯视逆时针”统一；4 组 A→B→A 截图相同，无页面异常。实际测试离线 HTML 的暂停、时间轴定位、本地字体与零外部 HTTP 请求。另有共享渲染器的确定性检查，均通过。
- 人工查看七段构图及实际编码后的 [联系表](../outputs/taiji-silk-20261031/contact-sheet.png)、[19 秒脚部截图](../outputs/taiji-silk-20261031/root-detail.png)。初版地面/台座透明层写深度导致根须被遮挡，修改为不写深度；修正膝部衣服衔接、标注底衬、近景构图以及旋转符号后完整重渲染，未放宽断言。首次初始化发现负数曲线参数错误并修正；中间预览与旧渲染保留。
- Node 语法和 Python 编译检查通过。本次只增加影片源码、工具、字体及文档导航，没有更改主项目模块；未重跑完整 pytest。解剖、树根和旋转传导属于艺术/劲意示意，几何接触检查不能证明生物力学正确；没有语音字幕，Qwen 与 `videocut/sync.py` 不适用，不声明声学字幕同步通过。


## 2026-10-31 · 外部 GLB 人物加载与骨骼姿态试装

- 针对人物造型反馈，实际下载 Grab3D Man Base Mesh 的 CC0 骨骼 GLB：11,354,468 字节、262,348 三角形、24 骨骼，SHA-256 `3038f56e1225d0ef9692189ed19ff688f1424e669281148a4cc6995fed568496`。记录提供方 AI/Meshy 底模、Blender 整理的来源声明，未称真人扫描。下载首次中断后用 HTTP Range 续传，GLB 头部声明长度与实际长度一致，Three.js GLTFLoader 实际加载成功。许可、上游清单与下载事实保存于 `films/taiji-silk/models/man-base/`。
- 新增独立 model-study 入口，测试两段骨骼 IK、网格蒙皮、贴图、环境光和地面接触；没有将低规格模型直接替换原 36 秒图解。资产缺少独立手指与逐趾骨骼、太极服和肌肉层，不能据此宣称完成原片抓地/剖析升级。
- [6 秒技术样片](../outputs/taiji-real-model-study-20261031/real-model-study.mp4)：1920×1080/24fps、144 帧、H.264/yuv420p/tv/BT.709，AAC 48kHz 立体声，复用原创配乐前六秒并淡出，-20.0 LUFS、-7.5 dBTP。最终视频 SHA-256 `59f43b0a353e498ddfbf527e5c696bbf7c2336ebab8a1a830820c60815258dd5`。两段各 72 帧，编码文件完整性 passed=true；共享 A→B→A 像素检查通过。
- 媒体检查 10 PASS、1 WARN、0 FAIL，ok=true、verified=false；WARN 为没有独立字幕轨。黑帧/静音 0%，最长冻结 1.8 秒。实际查看 [样片截图](../outputs/taiji-real-model-study-20261031/real-model.png) 和联系表；该样片用于比较人物材质与比例，动作不是经动捕或教练校验的太极示范。Node 语法与 git diff --check 通过；未修改主项目模块、未运行完整 pytest。


## 2026-10-31 · 太极缠丝劲 V2：逐趾控制与真实解剖网格

- 用户认可外部人物材质后要求完整重做。V2 保留 Grab3D 贴图人物外观，组合 Innerscene / MakeHuman CC0 的 163 骨骼人物脚部，实际确认左右各 14 个趾关节；Z-Anatomy / BodyParts3D 提供 95 个右下肢骨骼/肌肉网格，其中 44 个足部网格。来源、SHA-256、许可与动画适配说明在 [CREDITS-V2](../films/taiji-silk/CREDITS-V2.md) 和 `models/v2-sources.json`，不是把程序纺锤体改名为真实肌肉。
- 全片仍为 36 秒 / 864 帧，先展示真实足部表皮与逐趾屈曲，再显露骨骼、肌腱与肌群，随后生根、拧劲、腿部左缠并回到全身。脚踝用两个原始表面的切口边界拟合过渡网格。解剖模型进行比例匹配和蒙皮转移，属于动画适配，未声明经过生物力学或临床校准。
- 最终 [视频](../outputs/taiji-v2-20261031/delivery/final.mp4)：36.0 秒，1920×1080/24fps，H.264 High/yuv420p/tv/BT.709，AAC 48kHz 立体声，8,701,322 字节，SHA-256 `2ec2fd0d413d39f7b5a4e5bf2899dc64626e04c29a3f594a69779f564b9175fb`。渲染键 `bbda85c70faf5eff622a`，9×96 帧分段与实际最终 MP4 的 864 帧完整性通过。
- [最终姿态验收](../outputs/taiji-v2-20261031/delivery/pose-verification.json)：144 个时刻，五个趾腹以变形网格求解接触，最大高度误差约 0.000001542 模型单位；足跟最低高度 0.004463，全部使用的脚部表面最低高度 0.001493，均在地面之上。踝部最大漂移约 5.09e-16。单独改变第三趾关节后，第三趾尖样本最大位移 0.007945，其他四趾尖样本位移均 0；原趾蹼混合仍保留。解剖顶点权重错误 0，最大归一化误差 4.75e-8。四组 A→B→A 截图一致，无页面异常与外部 HTTP 请求。
- 初次验收发现大腿轴转会把子级小腿和踝部带离锚点；在轴转后重新求解小腿并固定踝部后修正。随后隔离控制测试发现原自动蒙皮的跨趾权重串扰；清理占优势脚趾顶点的跨趾影响、保留趾蹼混合并重归一化后通过同一断言。`qa-final/failure.json`、`qa-fixed/failure.json` 与旧渲染保留，未改宽验收阈值。修正后对最终源码完整重渲染，没有拼接旧版本段。
- 复用本工程原创 36 秒配乐，-20.0 LUFS、-8.5 dBTP。媒体/内容检查 10 PASS、1 WARN、0 FAIL，ok=true、verified=false；唯一 WARN 是没有独立字幕轨，说明文字已入画。黑帧和静音 0%，最长冻结 1.8 秒。实际查看 [联系表](../outputs/taiji-v2-20261031/delivery/contact-sheet.png)、[抓地](../outputs/taiji-v2-20261031/delivery/toe-grip.png)、[解剖](../outputs/taiji-v2-20261031/delivery/anatomy.png)、[生根](../outputs/taiji-v2-20261031/delivery/roots.png) 编码帧。
- Node 语法、git diff --check 和 `tests/test_codefilm.py` 5 项测试通过（0.99 秒）。本次未修改主项目模块、未运行完整 pytest。没有旁白、ASR 或声学字幕验收。输出附完整素材署名及 CC BY-SA 4.0 视频许可。


## 2026-11-02 · 太极脚踝连续表面修复

- 用户指出 V2 的脚与小腿有分离感。移除不同模型之间的脚踝过渡套环，改用 MakeHuman 从短裤遮挡内的大腿到脚趾的一张连续皮肤网格；原人物保留上身和完整短裤。新增左右大腿、小腿共四个表面驱动骨骼，匹配动作长度并平滑膝部权重，保留原生踝部和逐趾控制。
- 新增实际网格拓扑回归：合并 UV 重复顶点后，踝部检查区开放边 **0**，左右足部都与小腿连通；在相同网格上复现旧脚踝切法得到 **84** 条开放边，确认检查能检出原缺陷。原有断言未放宽。[姿态报告](../outputs/taiji-ankle-fix-20261102/delivery/pose-verification.json)的 144 个时刻、五趾接地、单独第三趾控制、权重归一化、A→B→A 截图均通过；最大接触误差 0.000001542、最大踝部漂移 5.09e-16，无页面异常或外部请求。
- 最终 [修复版视频](../outputs/taiji-ankle-fix-20261102/delivery/final.mp4)：36.0 秒、1920×1080/24fps、864 帧、H.264 High/yuv420p/tv/BT.709、AAC 48kHz 立体声，8,183,334 字节。SHA-256 `1288a8bbfc7c9e881882b648f7d215ba12a8dcd4c890f88a19dd9c79d3d9ceb5`。渲染键 `8e967fea963213068b03`，9×96 帧全部重新渲染，分段与最终实际文件完整性通过，旧视频保留。
- 已查看实际编码的 [全片联系表](../outputs/taiji-ankle-fix-20261102/delivery/contact-sheet.png)及 [13.5 秒前后对比（左旧右新）](../outputs/taiji-ankle-fix-20261102/delivery/ankle-before-after.png)，确认脚踝套环消失，连续轮廓贯通小腿与足背。复用原配乐；媒体检查 10 PASS、1 WARN、0 FAIL，ok=true、verified=false；唯一提示为没有独立字幕轨，说明文字已入画。响度 -20.0 LUFS、真峰值 -8.5 dBTP、黑帧/静音 0%、最长冻结 1.9 秒。
- Node 语法、git diff --check 和 `tests/test_codefilm.py` **5 项通过（1.30 秒）**。未修改主项目模块，未重跑完整 pytest；没有旁白、ASR 或 Qwen/sync.py 验收。本次仅验证表面连通、动画控制与最终媒体，不据此声明生物力学正确。


## 2026-11-02 · 太极 V3：抓地先行、根须比喻与肌群细微缠紧

- 按用户新要求重排完整 36 秒动作：9–14 秒实际屈曲五趾抓地，14.3 秒后才分段长出主根与分支；取消足部肌肉与骨骼显示，足部皮肤全程保留。19.4 秒起，小腿、大腿外旋并带动躯干；21.5 秒起开启腿部剖视窗口，展示肌群相对左缠、径向收窄、纵向形变，以及一次 20% 卸载回弹和再次加载。右大腿衣物局部打开窗口，上身、腰带、另一条裤腿保留。没有调用生成模型或付费 API。
- [动作顺序验收](../outputs/taiji-flow-v3-20261102/delivery/motion-order-verification.json)：五趾表面最大位移分别约 0.02537、0.04094、0.03788、0.03679、0.02984 世界单位；肌肉 12,300 个顶点发生可测形变，最大原始坐标位移 0.018379。加载量 1 → 0.8 → 1；腿段外旋为小腿 -0.085、大腿 -0.14 rad，肌群相对左缠峰值 +0.19 rad。脚部剖视遮罩错误 0、全片足部解剖显示数 0、根须提前出现数 0。数值用于动画控制验收，不是人体力学结论。
- 原 [144 姿态验收](../outputs/taiji-flow-v3-20261102/delivery/pose-verification.json)继续通过：最大趾腹高度误差约 5.05e-7，足跟最低 0.004463，足部表面最低 0.001375，踝部漂移最大 7.64e-16；独立第三趾控制不带动其他四趾尖，权重错误 0，脚踝开放边 0，左右足部均与小腿连通。四组 A→B→A 像素一致，无页面异常和外部请求。
- 新抓地验收最初要求每个最低接触点都移动，第三趾的最低点仍被锚定而失败。检查关节和实际表面位移后，将运动测量改为每趾整个表面，继续保留全部原接触断言；最低接触点无需滑动，不能据此判定没有屈曲。预览中还发现透明皮肤排序造成趾甲穿面，恢复皮肤的深度写入，并用材质剖视窗口代替全腿透明；重新预览和验收后才渲染正式片，未复用旧版本片段。
- [最终视频](../outputs/taiji-flow-v3-20261102/delivery/final.mp4)：36.0 秒、1920×1080/24fps、864 帧、H.264 High/yuv420p/tv/BT.709，AAC 48kHz 立体声，5,122,783 字节。SHA-256 `c1239713fc8f4a10d20ee1f1b0ac858547915b1a9d4c91a4460301d588b228cd`。渲染键 `b683c54e849301c70ea1`，最终源码 9×96 帧完整重渲染，分段与实际成片完整性 passed=true；此前成片保留。
- 实际查看编码后的 [全片联系表](../outputs/taiji-flow-v3-20261102/delivery/contact-sheet.png)、[舒展](../outputs/taiji-flow-v3-20261102/delivery/toe-relaxed.png)、[抓稳](../outputs/taiji-flow-v3-20261102/delivery/toe-gripped.png)、[随后生根](../outputs/taiji-flow-v3-20261102/delivery/roots-after-grip.png)与 [肌群缠紧](../outputs/taiji-flow-v3-20261102/delivery/muscle-tension.png)。复用原创配乐，-20.0 LUFS、-8.5 dBTP；媒体检查 10 PASS、1 WARN、0 FAIL，ok=true、verified=false，唯一提示是没有独立字幕轨。黑帧和静音 0%，最长冻结 1.8 秒。
- Node 语法、git diff --check 通过，`tests/test_codefilm.py` **5 项通过（0.92 秒）**。未修改主项目模块或第三方技能，未重跑完整 pytest；无旁白、ASR 或 Qwen/sync.py 验收。来源、视频许可与姿态/时序报告随输出保存。


## 2026-11-02 · README 太极 V3 展示更新

- 动图与六帧总览均改用上述正式 V3 MP4；动图节选 10.5–12.5、15–17、24–26 秒，依次展示抓地、生根与肌群缠紧。实际 GIF 解码全部 72 帧，480×270、6,000ms、无限循环、无音轨，664,364 字节，SHA-256 `e0c06e5e55c050f2372be48829fb3d7b6f2b35c8b35503b58a4a0ec6fcb4a561`。项目 FFmpeg 渲染 verified=true，并查看解码接触表。
- 总览取 3、9.5、13.9、16.6、27.4、33.4 秒，实际 JPEG 1440×588，SHA-256 `041e1c3ba093a5d67386a912a274bab348fd5b4166308c4114dbca364ff82914`；已看图，足部没有旧脚踝套环或足肌剖析。README 文案、生成脚本、来源摘要和许可记录同步，其他作品展示与来源条目保持原样。
- 两份来源清单与实际媒体/原片摘要逐项一致；GIF 帧尺寸、帧数、总时长和循环标记断言通过。两份生成脚本 Python 编译、git diff --check 通过；本次只新增展示产物和文档更新，未重跑动画验收或完整 pytest。
