# 项目能力：工具、技能与作品

[项目首页](../README.md) · [使用指南](usage.md) · [AI 操作指南](ai-guide.md) · [架构](architecture.md)

本项目用三层组织能力：基础工具执行媒体处理，场景技能决定怎样组合工具完成任务，影片工程保存某次作品的数据、脚本与具体实现。新平台工作流优先增加技能和配置；可复用的处理逻辑进入通用工具。

```text
宿主 Agent：理解需求、读稿选题、校对、设计分镜、查看结果
     ↓ 采用场景技能，写出可检查的 JSON
基础工具：download / transcribe / prepare / cut / mix / render / images / ffmpeg / codefilm / review
     ↓
实际作品：短片、字幕图卡、代码动画、交互 HTML、来源与检查报告
```

## 基础工具

| 能力 | 入口与产物 | 当前边界 |
| --- | --- | --- |
| 网页/本地素材导入 | `download` → 媒体、字幕轨、`materials.json`、来源与摘要 | yt-dlp 支持的平台取决于站点；视频号需独立本地捕获服务；不自动读取浏览器 Cookie |
| 本地转录 | `transcribe` → TXT、SRT、逐词 JSON、分段缓存与报告 | faster-whisper 识别；可 `no_speech`；不是给定稿件的 Qwen 对齐 |
| 创作素材交接 | `prepare` → 缺失素材任务或可渲染配置 | 宿主负责写稿/生图；准备器不联网或调用模型；AI 视频仅列外部需求 |
| 口播精剪 | `cut / rough-cut` → 音画同切、删除区间与字幕重排 | 指定口头词/长停顿或静音粗剪；没有专门呼吸分类 |
| 混剪与合成 | `render / mix` → 旁白、视频/照片、运镜、转场、贴纸、配乐与字幕 | 素材按标签或显式 ID 选择；不做任意视频视觉打标 |
| 参考音色与控制 | 默认 IndexTTS-2.5；显式 Edge/macOS | 参考音色、原生语速/情绪/拼音；模型隔离；完整 SSML 未接入 |
| 语音字幕验收 | Qwen + `sync.py` → 固定展示计划、SRT 回读、全部编码帧及音轨偏移 | 只有实际运行的对应门禁可标通过；普通 ASR/文件区间字幕保留未验证 |
| 视频图像处理 | `images sample / band / index / plan / render / verify` → 候选帧、索引、原生/脚本图卡、内容缓存和报告 | 不自动选题、翻译、识别说话人；原生字保留像素，后期文字必须声明来源 |
| 独立 FFmpeg 后期 | `ffmpeg` 的 42 个工具 → 画幅、音频、字幕、HDR、平台导出、批处理与时间线 | 固定上游工具；平台检查不替代 Qwen；声能高光不等于理解内容 |
| 本机预览与画面批注 | `review prepare/publish/serve/comments/resolve/verify` → 封存视频、版本/镜头时间轴和区域意见 | 双渲染路线；Agent 经 CLI 改原工程；无内置 AI、拖动剪辑、MP4 图层恢复或三维对象拾取；完整性不等于内容/审美通过 |
| 确定性代码动画 | `codefilm` → Canvas/Three.js 静帧、分段、成片帧数与摘要验证 | 页面实现 `render(t)`；依赖工程内 Node/Playwright；不负责叙事、GIS、模型建模和配音 |

[本地审片](review.md)、[通用图像工具](image-tools.md)、[FFmpeg 工具](ffmpeg-tools.md)、[代码视频](code-films.md)分别维护各自合同。工具可以单独用，也可以通过文件组合；主项目不引入数据库、任务队列或云端大模型服务。

## 场景技能与工作流

| 场景 | 用哪些基础能力 | 在哪里维护 |
| --- | --- | --- |
| 视频信息与运动节奏 | 按图片/口播/机制等内容选节奏 → 创作计划 → 关键帧和整片复核 | [视频导演](../skills/video-direction/SKILL.md)；不以静止/运动阈值评审美 |
| 审片改片 | 原工程输入 → 封存预览 → 定位意见 → Agent 修改 → 新版回复 | [审片工作流](../skills/review-workflow/SKILL.md)；稳定镜头 ID 与原版本上下文 |
| 小红书访谈/讲解字幕图文 | 导入/转录 → Agent 选题 → 候选帧 → 原生/脚本图卡 → 逐图检查与文案 | [项目技能](../skills/xiaohongshu-quotes/SKILL.md) |
| 剧本短片与原声混剪 | prepare、配音/ASR、render/mix、字幕与成片检查 | [视频工作流技能](../skills/video-workflow/SKILL.md)；参数与配置在使用指南 |
| 城市数据动画、机械拆解、动作图解 | 工程数据/Three.js → codefilm → FFmpeg → 作品专用检查 | [代码影片技能](../skills/codefilm-workflow/SKILL.md)；工具合同在代码视频指南，具体美术和模型属于 `films/` |

小红书的图卡比例、选句习惯和文案不写入通用渲染器。后续增加知识卡、课程摘要或其他平台图文，可复用同一份 `image-cards-v1` 合同，另加技能与模板。

## 已完成作品与证据

| 作品 | 已产出的效果 | 复现与证据 |
| --- | --- | --- |
| 咖啡竖屏短片 | 41.108 秒、720×1280，照片运镜、素材、字幕、贴纸、转场与音乐 | [示例配置](../examples/coffee.json)、[展示媒体](media/README.md)；历史 Edge 版本 |
| 杭州城市片 | 120 秒、1080p/24fps，真实建筑/水系、Three.js 主镜、少量实景与参考音色 | [杭州工程](../films/hangzhou/README.md)；当前展示为 delivery-v2，抽样字幕 OCR/波形检查不等于 Qwen 门禁 |
| 机械蝴蝶 V2 | 32 秒、1080p/30fps，11 个机位、机芯剖视、分层拆装、授权配乐 | [电影版](../films/mechanical-butterfly/CINEMATIC.md)；机械概念动画，不是制造或气动仿真 |
| 太极缠丝劲 V2 | 36 秒、1080p/24fps，外部人物、逐趾控制、骨骼肌群与示意动画 | [太极工程](../films/taiji-silk/README.md)；艺术/劲意图解，素材署名与 CC BY-SA 4.0 随附 |
| 字幕图卡 | 以杭州成片的真实帧演示原字幕连续条与后期脚本图卡 | [图像工具](image-tools.md)、[展示媒体](media/README.md)；不把自有讲解片当作第三方访谈案例 |

README 只分发小型实际截图和 GIF；大型媒体、模型与详细报告在忽略的本地目录。历史会话用于定位作品，源码、实际成片、摘要和验收记录才是能力证据。最近一次完整验证及本轮记录见 [verification.md](verification.md)。
