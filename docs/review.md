# 本地预览与画面批注

[文档导航](README.md) · [审片工作流](../skills/review-workflow/SKILL.md) · [导演技能](../skills/video-direction/SKILL.md)

`videocut review` 给现有素材混剪和 codefilm 增加统一的预览版本与批注合同。它封存实际编码的视频；原工程继续决定如何生成画面。网页提供播放、镜头跳转、历史版本、画面定位与批注，Agent 通过 CLI 领取、修改原配置/源码、生成新版并回复。网页不内置 Agent，也不自动执行渲染命令。

## 输入与版本合同

协议为 `videocut-review-v1`。每个镜头必须有非空、唯一、稳定的 `id`。修改标题、素材、时长或顺序时保留 ID；渲染输出时间轴必须保留这些 ID。素材路线接受已有 `render/mix` 的实际 `timeline.json`；代码路线默认读取 codefilm 的输入时间轴。旧工程不要求迁移，只有接入审片时才需要显式 ID。

`prepare` 在渲染前记录配置快照、声明输入的 SHA-256、规格与一个**尚不存在**的候选路径。素材表必须已解析为本地 `path`，相对路径基于素材表目录；配置文件需在审片工作区外。codefilm 按其 `sources` 声明收集输入；额外影响画面的字体、贴纸、声音和其他文件用重复的 `--source` 声明。目录参数记录登记时已有的文件。它不自动发现动态网络资源或目录中新加的文件，调用方负责完整声明，并在新增输入后重新登记。

`publish` 检查登记输入仍一致，完整解码音视频、计数实际视频帧，核对尺寸、恒定帧率、登记时长和镜头覆盖，再复制到不可变版本目录。媒体或源文件在封存期间变化会被拒绝；成功后才更新 `latest`。旧版保留，失败不把候选冒充新版。输入摘要记录声明内容，不是对任意外部渲染程序的执行证明。

局部预览显式登记 `--offset`（原工程起点）和 `--duration`，时间均为秒；duration 必须是整数帧。批注同时保存预览时间与 `global_time = time + offset`。codefilm 默认时长为从 offset 到工程结尾；素材路线可显式限定预期时长，否则根据实际视频与时间轴检查覆盖。宽高须为正偶数，fps 来源为配置/代码计划。只有恒定帧率视频可进入当前审片合同。

## CLI 参数示例

以下路径为示意，先准备真实输入与对应渲染命令；完整操作步骤只维护在[审片技能](../skills/review-workflow/SKILL.md)。

```bash
# 素材路线：登记未来的候选及渲染器将写入的时间轴。
uv run videocut review prepare outputs/my-review \
  --renderer media --config work/project.json --materials work/materials-local.json \
  --video outputs/render-01/final.mp4 --timeline outputs/render-01/timeline.json \
  --source work/music.wav --label '延长第二张照片'

# codefilm：登记与局部渲染相同的范围和尺寸。
uv run videocut review prepare outputs/my-code-review \
  --renderer codefilm --config films/taiji-silk/realistic-codefilm.json \
  --video outputs/taiji-preview-01/preview.mp4 --width 640 \
  --offset 24 --duration 2 --label '肌群镜头局部预览'

# 现有工具完成对应候选与时间轴后，再封存和打开网页。
uv run videocut review publish outputs/my-review
uv run videocut review serve outputs/my-review --port 4862
uv run videocut review state outputs/my-review
uv run videocut review verify outputs/my-review
```

`publish --draft ID` 可明确指定当前 draft。已有 draft 未结束时不能新建；`abandon WORKSPACE` 仅撤销待生成状态，保留记录及已有视频。输入改过以后应撤销旧 draft，重新登记并实际渲染。不要改摘要来让旧视频通过。

审片页监听 `127.0.0.1`，支持视频 Range 请求。HTTP 只提供 UI、状态、已封存媒体与新增批注，不提供任意文件浏览、源码写入、shell 或 Agent 启动接口。评论写入要求同源请求和会话 token；这是本机工作页，没有多人账号系统。

## 批注与 Agent 交接

```bash
uv run videocut review comments outputs/my-review --claim
uv run videocut review comment outputs/my-review \
  --revision REVISION_ID --time 2.5 --text '第二张多停一秒' \
  --region 0.4 0.3 0.08 0.08
uv run videocut review resolve outputs/my-review --id COMMENT_ID \
  --result-revision NEW_REVISION_ID --note '第二张延长一秒，第三张顺延'
```

`comments --claim` 加锁领取第一条 pending，置为 working；没有可领的条目返回空列表。`comments` 包含原版本配置快照、声明输入及当前已变更文件，便于 Agent 检查旧意见是否仍适用。当前没有超时租约或失败任务自动重领，可通过普通 `comments` 查看 working 条目并继续处理。

每条批注固定保存 revision、视频 SHA-256、source_hash、预览时间、全局时间、帧索引、scene_id、可选归一化 `[x,y,width,height]` 和原文；区域相对视频内容，排除播放器留边。旧版意见不会自动迁移到新版。`resolve` 必须引用比原版更新且来源摘要或视频摘要确有变化的版本；这只能验证有新版，是否满足意见仍由 Agent/用户看片判断。

网页显示版本以媒体实际加载完成为准。加载新版时旧画面保留，批注暂时禁用；失败可重试，下载仍指向当前已显示版本。跳转未完成时禁用定位。点击画面会暂停并生成区域标记；“暂停并留言”只记录时间/镜头。编写意见期间不自动切换新版本。历史版本、源文件已改但尚未重渲染、draft 待生成各有明确提示。

## 工作区文件与校验边界

```text
review.json                         project_id、版本索引及 manifest 摘要、latest、pending
.review.lock                        跨 CLI/HTTP 进程锁
comments.jsonl                      追加式批注/领取/完成事件
drafts/<draft-id>.json               渲染前输入、规格、候选与状态
revisions/<revision-id>/manifest.json 配置快照、输入摘要、场景、媒体规格与检查范围
revisions/<revision-id>/preview.mp4   封存的实际媒体副本
```

不要手动改封存文件。媒体请求和 `verify` 会核对摘要；`verify` 还会完整重新解码并比较实际规格。中断或失败的 `.pending` 目录保留为证据，未登记的目录不会被当成已发布版本。

`integrity.passed` 只说明文件完整性。`subtitle_sync`、内容与审美未运行时保持 null；review 不替代 ASR 来源合同、Qwen/`sync.py`、作品动作验证或正常速度的整片观看。当前无逐对象 Three.js 拾取、图层恢复、拖动剪辑或声音事件合成器；区域是给 Agent 的画面定位线索。

真实图片与 Three.js 改片烟测脚本为 [verify_review_workflows.py](../scripts/verify_review_workflows.py)。它要求本地素材和可选太极模型/浏览器，输出到全新目录，不下载或调用付费 API；实跑证据见[验证记录](verification.md)。
