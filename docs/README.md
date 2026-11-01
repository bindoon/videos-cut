# 文档导航

[返回项目首页](../README.md)

## 从这里开始

| 你要做什么 | 阅读入口 |
| --- | --- |
| 了解项目能力和效果 | [README](../README.md) |
| 区分基础工具、场景技能和已有作品 | [能力地图](capabilities.md) |
| 安装并用自己的内容出片 | [使用指南](usage.md) |
| 让 AI 选择命令、执行并检查结果 | [AI 操作指南](ai-guide.md) |
| 用宿主 Agent 写稿/生图，再交给本地渲染 | [创作计划与素材交接](usage.md#宿主-agent-创作与本地素材交接) |
| 理解模块、数据、缓存与验收边界 | [架构与运行方式](architecture.md) |
| 查清参考了谁、实际集成了什么 | [开源来源与集成说明](open-source.md) |
| 查看已经实际跑过的证据 | [验证记录](verification.md) |

## 专项指南

| 文档 | 内容 |
| --- | --- |
| [字幕同步](subtitle-sync.md) | 整句预读、显式拆条、Qwen 安装、SRT 回读与全部帧验收 |
| [声音克隆](voice-cloning.md) | 默认 IndexTTS-2.5 参考音色、输入、缓存与验收 |
| [IndexTTS 控制](voice-controls.md) | IndexTTS-2.5 安装、语速/情绪/拼音、完整视频与 SSML 实验边界 |
| [FFmpeg 工具](ffmpeg-tools.md) | 42 个工具的常用命令、后期处理、平台导出和原管线边界 |
| [通用图像工具](image-tools.md) | 精确候选帧、字幕区域、文字时间索引、原生/脚本图卡、内容缓存与真实文件校验 |
| [小红书字幕图文](workflows/xiaohongshu-quotes.md) | 上层场景技能：选题、选句、版式、逐图检查及独立发布文案 |
| [代码视频与城市短片工作流](code-films.md) | `codefilm` 配置、逐帧渲染、缓存验收，以及从真实数据、解说到交付的制作步骤 |
| [展示媒体](media/README.md) | README 实际截图和 GIF 的来源、归属与复现方法 |
| [杭州白模短片](../films/hangzhou/README.md) | 真实杭州建筑、水系与代码光层，Three.js 逐帧渲染及复现方法 |
| [太极缠丝劲动画](../films/taiji-silk/README.md) | 太极动作、足部剖析、五趾抓地、生根与腿部螺旋的 36 秒图解 |
| [机械蝴蝶电影版](../films/mechanical-butterfly/CINEMATIC.md) | 11 个机位、机芯剖视和分层拆装的 32 秒代码动画 |

## 文档与文件分别代表什么

- `README.md` 是项目介绍，`usage.md` 与 `ai-guide.md` 说明当前怎么用，`architecture.md` 说明当前怎么工作。
- `open-source.md` 记录本项目的集成方式与来源，确切包版本以依赖锁文件为准。
- [F5 声音克隆历史实验](voice-cloning-f5-history.md) 保存已停用链路的命令和结果，不作为当前操作入口。
- `verification.md` 是按阶段保存的历史证据。早期字幕策略可能已被替换，应以当前专项指南和代码为准。
- `examples/*.json` 是可运行的示例输入；`docs/asr-*-lock.json` 是历史 ASR 模型元数据，不是用户配置。
- 大型视频、模型和详细机器报告在忽略的 `outputs/`、`assets/` 等目录，仅克隆仓库不会带上。展示截图与 GIF 例外，保存于 `docs/media/`。

开发或修改项目之前另读根目录 [AGENTS.md](../AGENTS.md)，其中保留项目约定和容易误用的边界。
