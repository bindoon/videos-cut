# 用代码制作视频：工具与城市短片工作流

[文档导航](README.md) · [使用指南](usage.md) · [杭州工程](../films/hangzhou/README.md)

杭州短片把真实建筑与水系变成 Three.js 白模，再用历史光层、相机、字幕和声音讲故事。通用部分已抽成 `videocut codefilm`：本地 HTML/Canvas/WebGL 页面只要提供确定性的 `window.render(t)`，就能做静帧预览、分段渲染、续跑和帧完整性检查。它也适合图解、数据动画和片头，不依赖杭州模型。

城市选题、GIS 获取与建模、相机美术、解说、配乐仍由具体影片工程负责。当前没有“输入任意城市名自动出片”的命令，也没有引入 Remotion；共享时间轴由 JSON 与 `render(t)` 实现。画面不需要调用生图或生视频模型，杭州配音采用在线 Edge TTS。

## 最小工程：先跑两秒再做长片

需要主项目 Python 环境、Node.js 20+，以及影片目录内的 `playwright-core` 和可用 Chromium。Three.js 仅 3D 影片需要，不加入主项目 Python 依赖。

```bash
uv sync
npm ci --prefix examples/codefilm

# 已安装浏览器时，指向实际可执行文件；不要照抄别人的本机路径。
export PLAYWRIGHT_CHROME=/absolute/path/to/chromium

# 不启动浏览器、不编码，也不创建输出；检查输入并列出摘要与总帧数。
uv run videocut codefilm plan --config examples/codefilm/codefilm.json

uv run videocut codefilm stills --config examples/codefilm/codefilm.json \
  --output outputs/codefilm-demo
uv run videocut codefilm render --config examples/codefilm/codefilm.json \
  --output outputs/codefilm-demo
uv run videocut codefilm verify outputs/codefilm-demo/render-manifest.json
```

也可不设置环境变量，让 Playwright 使用与其版本对应的默认 Chromium。需要安装时，在影片目录运行 `npx --package=playwright-core@1.63.0 playwright-core install chromium`。`--browser /path/to/chromium` 优先于环境变量。macOS 默认 ANGLE Metal；其他系统默认浏览器后端，可用 `--angle vulkan/gl/swiftshader/default` 显式调整，实际可用性取决于驱动。软件 GPU 会提示速度较慢。`--timeout` 控制页面准备及单次 `render(t)` 的等待秒数，默认 120。

这条命令输出的是无声画面片段与清单，不会自动写解说、做音乐或把静音预览当成正式成片。完整浏览器烟测（含合片和截图）见文末。

## 配置与页面约定

影片根目录就是配置文件所在目录，路径相对于该目录；输出必须放在独立目录。最小配置：

```json
{
  "schema": "codefilm-v1",
  "entry": "index.html",
  "timeline": "timeline.json",
  "width": 1920,
  "height": 1080,
  "chunk_frames": 120,
  "sources": ["index.html", "main.js", "package-lock.json", "data", "fonts"]
}
```

`timeline.json` 必须提供整数 `fps`、整数 `frames`，以及等于 `frames / fps` 的 `duration`。可选的 `scenes` 含秒数 `start/end`，每个场景抽取一张预览。`examples/codefilm/` 是两秒 Canvas 示例；[杭州配置](../films/hangzhou/codefilm.json)是 Three.js 示例。宽高必须为偶数；`--width 640` 按配置比例生成小尺寸预览。

`sources` 要列全影响像素的本地输入：JS、着色器、字体、模型、时间轴、图片和依赖锁。文件夹会递归计算文件摘要；`entry`、`timeline`、配置本身自动加入。通常列 `package-lock.json` 而不遍历 `node_modules`，并使用 `npm ci` 恢复锁定依赖；手工改动依赖包时应把改动文件也加入输入。工具无法推断任意 JS 的完整依赖图，漏列的本地输入无法保证正确失效。

页面约定：

```javascript
// 先加载数据、字体和着色器；有随机噪声时固定随机种子。
await document.fonts.ready;
window.render = async (seconds) => {
  // 仅由 seconds 算相机、灯光、物体和字幕状态，再完成绘制。
  // 可以返回 Promise；不要依赖上一次调用、真实时钟或 RAF 增量。
};
window.READY = true;
```

工具使用独立的无头浏览器，只服务影片目录中的本地资源，拦截外部网络请求。先把字体、图片、数据下载并归档，再开始渲染。每次任务都会用 A→B→A 三次截图检查同一时刻像素是否相同；这能发现常见的累积状态错误，不能证明所有时间点都确定。

## 预览、续跑与缓存

```bash
# 每章一张图，先检查机位、遮挡、字幕和标注。
uv run videocut codefilm stills --config films/hangzhou/codefilm.json \
  --output outputs/hangzhou-next --width 640

# 精确截取一秒画面；秒数会取到最近的视频帧边界。
uv run videocut codefilm render --config films/hangzhou/codefilm.json \
  --output outputs/hangzhou-next --start 118 --end 119 --workers 1

# 明确按局部预览验收；默认 verify 会拒绝不完整的片段。
uv run videocut codefilm verify outputs/hangzhou-next/render-manifest.json --allow-partial
```

`render` 默认全片、两个页面并行，每段 `chunk_frames` 帧。时间始终使用全片坐标 `frame / fps`，不会在新段从零开始。`--start/--end` 是预览范围；结束帧不包含在内。不同范围只有帧起止都相同的片段才可直接复用。

缓存目录为 `outputs/<job>/renders/<key>/`。键包含声明输入的 SHA-256、尺寸/帧率/分段设置、项目渲染与编码包装代码，以及实际浏览器版本、GPU 渲染器和 ANGLE 后端。当前不按镜头分析源码依赖：改动声明源码或时间轴会产生新的键，整片重新运行时不会自动拼接不同源码版本的镜头。局部渲染用于快速迭代；交付前对最终版本运行完整渲染。

相同输入重跑时，每段重新核对实际 MP4 摘要、探测实际视频帧数和格式，才会显示 `CACHED`。损坏文件直接报错，保留证据；可以换新输出目录重新渲染。不要修改摘要让损坏缓存通过。输出目录加进程锁，防止两个任务同时写入。

每段采用无损 PNG 捕获，再通过项目 `videocut ffmpeg sequence` 编码为 H.264、`yuv420p`、视频范围 `tv`；精确核对尺寸、帧率和实际帧数。临时 PNG 仅在该段编码和探测成功后删除。中断时保留已完成段与失败日志，下次复用完整段；不完整 `.pending.mp4` 由该任务重建。全段成功且输入未变才发布新的顶层清单。完整性检查还会重新读取每段实际文件，拒绝缺口、重复、伪造帧数与局部预览冒充全片。

长片开始前检查可用磁盘空间：并行页面会同时保留各自一段 PNG，后期还会产生合片、响度处理与章节输出等中间文件。成片文件大小不能代表峰值空间需求。本次后期回归实际遇到过磁盘写满，失败证据保留在验证记录中；恢复时仅清理明确属于任务的可再生文件。

主要产物：

| 文件 | 作用 |
| --- | --- |
| `codefilm-request.json` | 本次有效配置、输入摘要和调用参数 |
| `latest-stills.json` | 静帧路径、时刻、摘要与像素重复检查 |
| `render-manifest.json` | 实际范围、总帧数、浏览器/GPU 信息及各段摘要 |
| `renders/<key>/segment-*.mp4` | 成功编码的片段 |
| `*.record.json / *.probe.json / *.stdout / *.stderr` | 缓存身份、实际探测及原始工具输出 |

顶层清单代表最近一次成功任务，范围预览和整片共用这个入口。历史版本清单同时保留在各缓存目录内。不要只凭文件名判断它是否全片。

## 城市短片制作工作流

杭州工程是已完成的案例，换城市时以这些阶段组织工作，不直接替换城市名与数据 ID：

| 阶段 | 落盘产物 | 继续前检查什么 |
| --- | --- | --- |
| 参考与选题 | 参考链接、风格拆解、故事主线、章节 | 区分参考镜头语言、可复用代码与不可直接使用的素材 |
| 史实与解说 | `story.json`、`facts.json`、来源与许可 | 日期有出处，英文字幕与中文稿对应，发布文案不混入解说 |
| 数据获取 | 原始缓存、版本、边界框、校验记录 | 用空间范围确认城市，不能猜不透明的城市编号；缺数据要显式记录 |
| 投影与建模 | `model.json`、`stats.json` | 米制投影、比例、裁剪范围、建筑数、真实水体轮廓、楼高来源 |
| 逐句配音 | 逐句 WAV、`speech-manifest.json`、SRT、时间轴 | 按实际 PCM 采样数累计，SRT 序列化后回读，不按字数猜时长 |
| 声音与画面 | 音乐/音效/混音 WAV、确定性 `render(t)` | 声音和镜头使用同一时间轴，随机种子固定，相机远近裁剪合理 |
| 预览与渲染 | 每章静帧、局部片段、完整清单 | 先低分辨率检查，再全尺寸出片；不得把局部片段用于交付 |
| 后期与交付 | MP4、SRT、章节、接触表、检查与摘要 | 真实编码帧、声音、字幕、平台检查和人工画面/听感复核分别记录 |

杭州的数据获取经验：CMAB 浙江 ZIP 很大，可按 HTTP Range 读取所需城市条目，验证响应范围、条目长度和 CRC；城市身份通过几何边界确认。OSM 公共 Overpass 超时后，改走 Nominatim、OSM 主 API 的对象与几何接口；应保存实际来源及未取得部分，不凭空补轮廓。OSM 的明确楼高替换对应建筑；其余 CMAB 高度保留估算属性。

本次矩形覆盖约 515.82 km²，从 124,455 条原始记录筛出 75,139 个建筑部分。这个面积不是行政面积，建筑部分数也不是人口或住户数。现代白模上的历史光层标为示意，不把估计年代当作古建筑复原；良渚遗址在取景矩形外，单独说明。下载端点、版本和许可证见杭州 [CREDITS](../films/hangzhou/CREDITS.md)。

项目与影片工程的职责：`videocut` 提供通用渲染、既有配音入口与 FFmpeg 文件工具；`films/<city>/` 拥有数据下载与转换、史实、相机和声音设计。当前杭州脚本不是通用 GIS SDK。`data/` 是该影片当前编辑态，不要并发改写两个版本；源码、锁文件、数据和声音快照应随正式交付归档。

## 后期、验收与已知边界

合片前执行 `codefilm verify`，只有完整清单才能交给后期；后期可用项目的 `ffmpeg render` JSON 一次安排无转场合段、替换混音、响度和导出。无缝逐帧片段应显式设置 `transition.type=none`，避免默认淡化改变帧数。章节写入另一个文件，不能输入输出同名。杭州 `tools/finish.py --output ...` 是实际范例，复用前还要核对该影片特定的 1080p/24fps 与音频要求。

```bash
# 对最终编码文件同时核对画面规格与总帧数。
uv run videocut codefilm verify outputs/hangzhou-next/render-manifest.json \
  --video outputs/hangzhou-next/杭州-一城山水千年生长.mp4 \
  --report outputs/hangzhou-next/manifest-verification.json
```

共享 `verify` 只验画面文件完整性，不判断解说正确、配音自然、音乐好听、字幕声学同步或史实可信。`ffmpeg check` 的 `ok`、失败/警告行与 `verified` 是不同字段，需如实记录；不能只看退出码。杭州另外做了每条字幕中点帧 OCR 和九处音轨波形窗口检查，仍不是全帧 OCR，更不是 Qwen 强制对齐。没有经过 `sync.py` 声学门禁时，`subtitle_sync.passed` 保持 `null`。

实拍或他人录音走独立 `transcribe`；本工程逐句生成语音的文件区间无需假装成 ASR 或强制对齐记录。人耳听感、叙事节奏和美术验收不能被帧数检查替代。最终应交付视频、字幕、看板、来源、复现说明、依赖锁和验证报告；有条件时附原始配音/混音，避免在线语音服务未来变化影响复现。

## 开发验证

```bash
# 确定性 suite：本地 FFmpeg，无浏览器或外网平台依赖。
uv sync --extra download --extra asr
uv run pytest -q

# 可选：本机真实 Chromium/PNG/FFmpeg、续跑及故障注入。
npm ci --prefix examples/codefilm
uv run python scripts/verify_codefilm.py --output outputs/codefilm-smoke-new
```

烟测会输出 48 帧两秒动画，重跑验证四段复用；再故意损坏一段同大小文件，确认续跑拒绝，最后恢复测试文件、合片、核对实际视频并导出截图。需要 `PLAYWRIGHT_CHROME` 或默认安装的浏览器，输出目录必须是新目录。杭州大模型实跑、GIS 联网和真实 TTS 单独记录，不能用这个两秒样例冒充。实际运行证据见[验证记录](verification.md)。
