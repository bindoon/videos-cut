# 通用图像工具

[文档导航](README.md) · [能力分层](capabilities.md) · [小红书工作流](workflows/xiaohongshu-quotes.md)

`videocut images` 负责视频抽帧、文字时间索引、水平区域预览、图卡排版与真实文件检查。工具没有平台字段，不调用模型或网络；访谈选题、翻译、审稿和发布文案由宿主 Agent 与上层技能负责。核心依赖沿用 Python、Pillow、系统 FFmpeg/ffprobe；输出锁使用 macOS/Linux 的 `flock`。

## 抽帧与区域预览

```bash
# 在某句话附近取前、中、后三帧，输出原尺寸 PNG 与等比缩略总览。
uv run videocut images sample input.mp4 --at 12.5 --at 18.2 --around 0.4 \
  --output outputs/candidates-01
# 不指定 --at 时默认均匀取 12 帧；--count 可设 1–48。
uv run videocut images band input.mp4 --at 12.5 --band 0.76 0.96 \
  --output outputs/band-01
```

`band` 输出未改动的 `frame.png`、原像素 `band.png` 和带红色边界的 `preview.png`。区域参数是相对实际显示帧高度的比例。抽帧先跳转至邻近 GOP，再解码至目标位置；时间记录为请求的视频秒数，实际帧取该位置或其后的第一帧，不伪造已测量的帧 PTS。候选帧记录黑暗比例和边缘变化指标，辅助查看，不自动判断人物表情或字的可读性。所有任务要求新输出目录。

## 文字时间索引

```bash
uv run videocut images index source.en.vtt --source input.mp4 \
  --kind platform --generation unspecified --language en --output outputs/index-01.json
uv run videocut images index outputs/transcribed/transcript.json --source input.mp4 \
  --kind asr --generation automatic --output outputs/asr-index-01.json
```

接收 SRT/VTT，以及本项目 `transcript.json`。ASR JSON 必须匹配源视频 SHA-256；不重新识别、不改变原缓存和逐词时间，`no_speech` 可生成空索引。输出保留原轨摘要、语言、来源种类、生成方式与原 cue 序号。平台不能证明人工来源时保持 `unspecified`。

相邻重叠的相同文字或前缀递增字幕会合并，间隔后的重复表达保留；这不是完整的自然语言断句或所有滚动字幕格式的消重。索引给出时间中点作为候选，仍需回看画面。字幕轨和 ASR 都不证明视频有烧录字幕；索引不是 Qwen 强制对齐记录。

## 图卡 manifest

```json
{
  "schema": "image-cards-v1",
  "source": "/absolute/path/input.mp4",
  "mode": "native",
  "style": {"layout": "natural", "width": 1080, "band": [0.76, 0.96]},
  "cards": [{
    "id": "topic-01", "title": "内部主题，不绘入成品",
    "lines": [{"time": 12.5}, {"time": 18.2}, {"time": 23.1}]
  }]
}
```

`source` 和可选 `style.font` 相对 **manifest 所在目录** 解析，也可使用绝对路径；`source_sha256` 可固定输入内容。每卡 `id` 唯一，只允许字母、数字、下划线和连字符，首字符为字母或数字；每卡 2–7 行，时间必须严格递增且小于视频时长。每批最多 100 卡。

| 字段 | 通用行为 |
| --- | --- |
| `mode=native` | 第一帧从顶部保留到字幕区域底边，其余帧只取字幕条；完整拼接后统一等比缩放，不识别或重绘字 |
| `mode=script` | 在真实帧上绘制经校对的台词；第一帧为主图，其余取水平区域作背景 |
| `layout=natural` | 按实际内容决定高度；原生模式默认采用此布局 |
| `layout=fixed` / `aspect=[3,4]` | 固定画布比例；原生完整拼图等比缩小并留边，脚本模式分配主图与字幕条 |
| `width` | 输出宽度 240–4096；放大低清素材会记录提示，不等于增加细节 |
| `band=[top,bottom]` | 字幕或背景条所在的垂直区域 |
| `strip_gap` | 条间背景缝，0–24 输出像素；原生模式回算到源宽再统一缩放，可能有整数舍入 |
| `hero_fraction` | 脚本固定布局的主图高度比例，默认 0.64，范围 0.35–0.85 |
| `font / font_size` | 脚本模式字体和像素字号，默认本地中文字体、40px；明确字体路径参与摘要 |
| `fit=contain/cover` | 脚本区域等比留边/等比裁切；默认 contain；原生只支持 contain |
| `background / text_color / emphasis_color` | 背景、脚本文字及强调色 |

原生行只接受 `time`，拒绝混入 `text`、说话人或字体样式。相邻几乎相同的字幕区域默认失败；确认确需重复时在该卡填写 `duplicate_reason`。它是图像差异启发式，不能证明字幕存在、不同文字或同一说话人。

脚本行示例：

```json
{
  "time": 12.5,
  "text": "已核对的台词或后期说明",
  "speaker": "可选说话人",
  "emphasis": false,
  "reviewed": true,
  "text_source": {"kind": "user", "reference": "稿件文件或原视频时间范围"}
}
```

`text_source.kind` 支持 `user / asr / platform / translation / edited`；`reference` 必填。`reviewed=true` 是调用者声明，渲染器不判断内容真实性。文字按区域换行；放不下时失败，不自动删字、改稿或无限缩字号。脚本模式会绘制深色文字底衬，所有后期文字来源随报告保留。

## 渲染、续跑与验收

```bash
uv run videocut images plan --manifest task/cards.json
uv run videocut images render --manifest task/cards.json --output outputs/cards-01
uv run videocut images verify outputs/cards-01/image-report.json
# 修正某张卡后，只补做变化、缺失或摘要不符的图片。
uv run videocut images render --manifest task/cards.json --output outputs/cards-01 --resume
```

`plan` 只读检查输入并计算摘要。`render` 默认遇错停止；`--keep-going` 保留其他成功卡并记录失败，最终退出码仍为 1。输出包含：

- `<id>-<内容摘要>.jpg`：真实成品，修改内容后采用新文件名，旧版本保留。
- `image-report.json`：当前请求完整快照、每卡摘要、来源、文字框、警告、失败项和复用数量；每完成一张即原子保存。
- `contact-sheet-<任务摘要>.jpg`：仅整批成功后生成本轮总览。失败报告的 `contact_sheet=null`，此前总览仍可能存在，应以当前报告为准。

首次运行拒绝已有目录。`--resume` 只接受本工具已有报告，使用输出锁；成功缓存同时核对内容键、实际文件摘要、可解码性和尺寸。键包括源视频、时间点、台词/来源、全部样式、字体文件和渲染器版本。输入变化触发重做；缺失、损坏的成品可修复。若中断留下未登记图片，续跑保留它，并用带 `recovered` 后缀的新文件完成该卡。

`verify` 重新检查实际文件、源视频与字体摘要、图片尺寸和文字框边界。`mechanical_passed=true` 只代表机械检查通过；`visual_review=pending`、`semantic_verified=false` 明确保留人工/Agent 看图与语义复核。静图检查不替代 Qwen 或主视频字幕音轨验收。
