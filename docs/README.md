# 文档导航

[返回项目首页](../README.md)

## 从这里开始

| 你要做什么 | 阅读入口 |
| --- | --- |
| 了解项目能力和效果 | [README](../README.md) |
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
| [声音克隆](voice-cloning.md) | Apple Silicon 上的 F5-TTS MLX、参考逐字稿与逐句旁白 |
| [IndexTTS 控制](voice-controls.md) | IndexTTS-2.5 安装、语速/情绪/拼音、完整视频与 SSML 实验边界 |
| [FFmpeg 工具](ffmpeg-tools.md) | 42 个工具的常用命令、后期处理、平台导出和原管线边界 |
| [展示媒体](media/README.md) | README 实际截图和 GIF 的来源、归属与复现方法 |

## 文档与文件分别代表什么

- `README.md` 是项目介绍，`usage.md` 与 `ai-guide.md` 说明当前怎么用，`architecture.md` 说明当前怎么工作。
- `open-source.md` 记录本项目的集成方式与来源，确切包版本以依赖锁文件为准。
- `verification.md` 是按阶段保存的历史证据。早期字幕策略可能已被替换，应以当前专项指南和代码为准。
- `examples/*.json` 是可运行的示例输入；`docs/asr-*-lock.json` 是历史 ASR 模型元数据，不是用户配置。
- 大型视频、模型和详细机器报告在忽略的 `outputs/`、`assets/` 等目录，仅克隆仓库不会带上。展示截图与 GIF 例外，保存于 `docs/media/`。

开发或修改项目之前另读根目录 [AGENTS.md](../AGENTS.md)，其中保留项目约定和容易误用的边界。
