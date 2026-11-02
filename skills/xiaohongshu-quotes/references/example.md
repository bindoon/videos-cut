# 字幕图文任务示例

## 让 Agent 使用

> 阅读 `skills/xiaohongshu-quotes/SKILL.md`。把这个访谈视频整理成小红书字幕图文，先读文字稿提名三个主题，每个主题保留原句和时间范围。我需要保留原画面字幕；先检查视频是否有烧录字幕，再挑稳定帧、校准字幕区域，每图四至六句。完成后检查每张实际图片，交付图片、来源、时间点和图文文案。

已有本地文件直接开始；URL 先用 `videocut download`，字幕轨不够时才使用 `videocut transcribe`。具体依赖和平台访问边界沿用[使用指南](../../../docs/usage.md)。

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

实际效果、归属与输入见 [README 展示媒体](../../../docs/media/README.md)。
