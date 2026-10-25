# README 展示媒体

[返回项目首页](../../README.md) · [文档导航](../README.md)

这里的文件来自项目**真实渲染结果**，随 Git 保存，便于开发者直接查看。

| 文件 | 内容 |
| --- | --- |
| [coffee-contact-sheet.jpg](coffee-contact-sheet.jpg) | `outputs/coffee-edge/contact-sheet.jpg` 的原样副本，展示完整短片六个时间点 |
| [coffee-demo.gif](coffee-demo.gif) | 同版成片第 5～10 秒，缩小为 240×428 的 5 秒循环无声预览 |
| [demo-source.json](demo-source.json) | 原成片 SHA-256、原运行参数和素材来源/归属/许可引用 |

原片：41.108 秒、720×1280、24fps、H.264 / AAC，6 个镜头、12 句字幕、5 次转场、6 个贴纸。配音来自显式选择的 Edge TTS，使用咖啡示例配置；该展示不含用户的参考录音或克隆音色。

这是基础合成链路的历史样片，其字幕按每句音频文件的实际 PCM 时长显示，不是默认 IndexTTS 的句末预读展示。截图和动图不作为 Qwen 强制对齐验收的证明；当前字幕规则与真实验收另见[字幕同步](../subtitle-sync.md)和[验证记录](../verification.md)。

## 素材归属

原片使用的素材对应以下来源，确切 URL、SHA-256 和许可引用见清单：

| 类型 | 来源 | 归属与许可引用 |
| --- | --- | --- |
| 视频 | Mixkit 4982、41865、236、4992 | Mixkit；素材清单记录 Mixkit Stock Video Free License |
| 照片 | Unsplash `photo-1495474472287-4d71bcdd2085`、`photo-1442512595331-e89e73853f31` | Unsplash；素材清单记录 Unsplash License |
| 贴纸 | Twemoji ☕、✨、💛 | Twemoji graphics / Twitter and contributors；[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)，在原图基础上缩放、透明度及动画合成 |
| 原片音乐 | Mixkit 493 | Mixkit；素材清单记录 Mixkit Stock Music Free License；GIF 不含声音 |

展示画面经过裁切、运镜、调色及文字/贴纸叠加。这里分发的是渲染画面的截图和节选，原始下载素材与完整视频继续留在忽略的本地目录。

## 复现方法

在仓库根目录运行，使用新输出目录：

```bash
uv sync
uv run videocut demo --tts edge --output outputs/readme-demo
```

在线声音、依赖环境和远程素材可能变化，因此新生成的视频不承诺与历史样片逐字节一致；`demo-source.json` 固定的是本次展示的来源身份。

截取和导出展示片段时使用项目内 FFmpeg 工具：

```bash
mkdir -p outputs/readme-media
uv run videocut ffmpeg probe outputs/readme-demo/final.mp4 --json
uv run videocut ffmpeg cut outputs/readme-demo/final.mp4 \
  --start 5 --end 10 --accurate -o outputs/readme-media/excerpt.mp4 --json-brief
uv run videocut ffmpeg fit outputs/readme-media/excerpt.mp4 \
  --width 240 -o outputs/readme-media/small.mp4 --json-brief
uv run videocut ffmpeg export outputs/readme-media/small.mp4 \
  --preset gif --no-scale -o outputs/readme-media/preview.gif --json-brief
uv run videocut ffmpeg look outputs/readme-media/preview.gif --tiles 3x2 \
  -o outputs/readme-media/contact-sheet.png --json-brief
```

打开实际接触表检查后，再挑选展示媒体更新到本目录。完整视频和排查中间文件不需要提交。
