# AI 操作指南

这里提供任务描述和技能入口。实际制作步骤统一维护在根目录 `skills/`，工具参数、配置和验收合同仍在 `docs/`。所有命令从仓库根目录执行。

[文档导航](README.md) · [完整使用方法](usage.md) · [项目约定](../AGENTS.md)

## 给 AI 的任务描述

至少给出输入文件或来源、期望的处理、声音选择和输出目标。可以直接复制下面的模板：

```text
请在这个仓库中完成视频任务，先阅读 AGENTS.md、docs/ai-guide.md，
再阅读 skills/video-workflow/SKILL.md，按任务补读工具指南或专门技能。

输入：/absolute/path/input.mp4
目标：竖屏口播混剪，保留原声，删除长停顿与“嗯、呃”，搭配咖啡素材。
素材：examples/materials.json；可从 examples/coffee.json 复制并修改配置。
输出：outputs/my-talking-<本次时间戳>，保留原文件和此前结果。

先检查输入媒体、素材和依赖，选择已有 CLI 入口执行。
完成后检查实际画面、字幕、音轨及机器报告。
交付成片路径、截图、关键参数、删除记录和仍需人工确认的内容。
```

其他常见任务：

| 任务 | 可以这样描述 |
| --- | --- |
| 只要转录 | “把这个本地视频转成中文 TXT、SRT 和逐词 JSON，到此结束。” |
| 从剧本出片 | “基于咖啡示例改成我的稿子，保留系统中文音色，先出 480 宽预览，确认画面后出完整版。” |
| 下载素材 | “导入这些链接，剪辑清晰度，保留平台可用字幕，输出素材目录和失败报告。” |
| 克隆声音 | “用这段参考录音的音色朗读新稿，选择 IndexTTS，先核对模型与 Qwen 环境，再生成视频。” |
| 只改字幕 | “复用上次的逐句旁白和背景，保持声音不变，把字幕改为整句、上句结束即显示下句。” |
| 独立后期 | “把现有视频改为 9:16 模糊背景，保留完整画面，导出新文件并查看截图。” |

预览与正式版是两个明确阶段；用户只要求预览时，完成预览后停在该阶段。

## 按任务加载技能

| 任务 | 技能入口 | 工具合同 |
| --- | --- | --- |
| 剧本短片、原声精剪/混剪、旁白和字幕复用 | [视频制作工作流](../skills/video-workflow/SKILL.md) | [使用指南](usage.md)、[字幕同步](subtitle-sync.md) |
| 城市、机械和动作图解等代码影片 | [代码影片工作流](../skills/codefilm-workflow/SKILL.md) | [codefilm 工具](code-films.md) |
| 小红书访谈字幕图文 | [小红书图文](../skills/xiaohongshu-quotes/SKILL.md) | [图像工具](image-tools.md) |
| 裁切、改画幅、调音、转码等独立后期 | [上游 ffmpeg-skill](../.agents/skills/ffmpeg-skill/SKILL.md) | [FFmpeg 集成](ffmpeg-tools.md) |

第三方技能通过 Git submodule 固定上游提交；克隆后先运行 `git submodule update --init --recursive`。本项目工作流不需要单独安装到全局技能目录，Agent 可直接读取以上 `SKILL.md`。

## 修改代码时

按照 [AGENTS.md](../AGENTS.md) 保留验收断言和各工具边界。完整测试前运行：

```bash
uv sync --extra download --extra asr
uv run pytest -q
```

确定性套件使用本地 HTTP 和 FFmpeg；平台联网和真实模型 smoke 单独记录。新增能力同步对应使用指南和架构；实际跑过的结果写入验证记录。测试失败先查实现，不通过削弱要求换取通过。
