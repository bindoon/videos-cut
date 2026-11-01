# 小红书字幕图文工作流

[能力分层](../capabilities.md) · [通用图像工具](../image-tools.md) · [项目技能](../../.agents/skills/xiaohongshu-quotes/SKILL.md)

这是基础工具上的场景工作流：把访谈、播客或讲解视频整理成“一张主画面＋连续字幕条”的图片。通用工具负责抽帧、拼图与检查；小红书技能负责受众、选题、句子组合、版式与发布文案。它不依赖 Creao，不新增写稿 API，也不自动发布。

## 让 Agent 使用

> 阅读 `.agents/skills/xiaohongshu-quotes/SKILL.md`。把这个访谈视频整理成小红书字幕图文，先读文字稿提名三个主题，每个主题保留原句和时间范围。我需要保留原画面字幕；先检查视频是否有烧录字幕，再挑稳定帧、校准字幕区域，每图四至六句。完成后检查每张实际图片，交付图片、来源、时间点和图文文案。

已有本地文件直接开始；URL 先用 `videocut download`，字幕轨不够时才使用 `videocut transcribe`。具体依赖和平台访问边界沿用[使用指南](../usage.md)。

## 一次完整任务

推荐任务结构：

```text
task/
  source/              视频、字幕轨和下载来源报告
  index.json           通用文字时间索引
  topics.json          Agent 的主题、原句、上下文、说话人依据和候选时间
  candidates/          候选 PNG 与总览
  band/                字幕裁切区域预览
  cards.json           最终模式、时间点、样式、后期文字来源
  output/              实际 JPG、image-report.json 和当前总览
  publication.json     独立发布文案（需要时生成）
  review.md            实际逐图检查结论与未决项
```

1. **理解与选题**。用 `images index` 整理 SRT/VTT 或同源 ASR JSON；Agent 根据受众读取内容。每个主题保留上下文和原句，不能只保留改写后的金句。工具的声能高光不是语义选题。
2. **确认字幕模式**。关闭播放器 CC 后，真实帧仍有字幕才可用原生模式；否则选择用户需要的后期脚本模式。原生字来自像素，翻译和改写来自明确来源的后期文字。
3. **定位画面**。对每句话采样附近帧，确认字幕已完整显示且说话人对应；`images band` 预览边界，至少看开头、中段、结尾是否一致。
4. **计划与渲染**。复制技能的[原生模板](../../.agents/skills/xiaohongshu-quotes/assets/native.json)或[脚本模板](../../.agents/skills/xiaohongshu-quotes/assets/script.json)，填真实路径和时间点。脚本模板故意使用 `reviewed=false`，核对后再改为 true。原生版可选自然比例或固定 3:4；固定画布保留等比留边，不拉伸字幕。
5. **验收与交付**。运行机械检查，再逐张看实际图。用户需要文案时另写标题、正文、标签和来源署名；不能把传播量、涨粉或固定五分钟交付写成保证。

```bash
uv run videocut images index task/source/captions.vtt --source task/source/video.mp4 \
  --output task/index.json
uv run videocut images sample task/source/video.mp4 --at 12.5 --at 18.2 --around 0.4 \
  --output task/candidates
uv run videocut images band task/source/video.mp4 --at 12.5 --band 0.76 0.96 \
  --output task/band
uv run videocut images plan --manifest task/cards.json
uv run videocut images render --manifest task/cards.json --output task/output
uv run videocut images verify task/output/image-report.json
```

每次只改某张图时更新 `cards.json`，以 `--resume` 继续。修改时间、文字、字体或样式会使对应缓存失效；旧图片留存，当前有效图片以报告列出的文件为准。部分失败时报告返回非零、当前总览为空；修正后继续即可。

## 复核边界

原生字幕可以本来就是来源视频的后期翻译，不代表官方字幕或人物逐字原话。ASR 与平台字幕可作定位索引，但原生出图以实际画面为准。说话人、翻译、上下文完整性和素材使用权限需要依据来源核对；机械校验不能证明这些事项。

本项目的实际效果例子使用已有杭州城市讲解片，示范原字幕拼图和后期脚本排版，不冒充访谈选题实测。图片、参数和来源见 [README 展示媒体](../media/README.md)。
