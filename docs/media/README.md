# README 展示媒体

[返回项目首页](../../README.md) · [文档导航](../README.md)

这里的文件来自项目**真实渲染结果**，随 Git 保存，便于开发者直接查看。媒体的许可按下方归属说明适用。

| 文件 | 内容 |
| --- | --- |
| [coffee-contact-sheet.jpg](coffee-contact-sheet.jpg) | `outputs/coffee-edge/contact-sheet.jpg` 的原样副本，展示完整短片六个时间点 |
| [coffee-demo.gif](coffee-demo.gif) | 同版成片第 5～10 秒，缩小为 240×428 的 5 秒循环无声预览 |
| [demo-source.json](demo-source.json) | 原成片 SHA-256、原运行参数和素材来源/归属/许可引用 |
| [hangzhou-gallery.jpg](hangzhou-gallery.jpg) | 两分钟杭州 delivery-v2 实际成片的六帧，含 Three.js 与实景辅助分屏 |
| [butterfly-gallery.jpg](butterfly-gallery.jpg) | 机械蝴蝶 V2 的正面、俯视、电机、齿轮、展开与重组六帧 |
| [taiji-gallery.jpg](taiji-gallery.jpg) | 太极 V3 的全身、舒趾、抓稳、生根、肌群缠紧与回归全身六帧 |
| [cards-native.jpg](cards-native.jpg) | 杭州原片连续四句的原生字幕像素拼图，自然比例；[输入](cards-native.json) |
| [cards-script.jpg](cards-script.jpg) | 机械蝴蝶真实帧加本项目编写的后期中文说明，720×960；[输入](cards-script.json) |
| [gallery-source.json](gallery-source.json) | 新增截图的成片身份、时间点、摘要、会话标题、图片摘要及实际看图记录 |

## 本地审片截图

- [review-photos.jpg](review-photos.jpg)：实际图片混剪 v2 的 Chrome 审片页，显示 7 秒视频、三个镜头和旧版意见对应的新版回复。图片来源为本页咖啡素材表中的 Unsplash 照片，沿用 Unsplash License；原创 UI 代码为 MIT。
- [review-taiji.jpg](review-taiji.jpg)：原工程 24–26 秒局部无声预览的 Chrome 审片页，显示改相机后的 v2 与完成回复。太极衍生画面按 CC BY-SA 4.0，保留 Z-Anatomy / BodyParts3D / DBCLS、Grab3D、Innerscene/MakeHuman 的[完整署名](../../films/taiji-silk/CREDITS-V2.md)。

两张 JPEG 均从实际浏览器捕获原样复制，页面播放本次封存的编码视频，未用设计稿替代。它们不代表重新验收完整太极影片、声音或 Qwen 字幕。[review-source.json](review-source.json)保存截图/视频摘要、版本、范围、规格及本机证据路径；本机大文件不随 Git 分发。

## README 动态预览

| 文件 | 原片时间范围 | 规格与许可 |
| --- | --- | --- |
| [hangzhou-demo.gif](hangzhou-demo.gif) | 3–5、20–22、84–86 秒 | 480×270，6 秒/72 帧；CC BY-SA 4.0 |
| [butterfly-demo.gif](butterfly-demo.gif) | 3–5、14–16、24–26 秒 | 480×270，6 秒/72 帧；项目原创画面，MIT |
| [taiji-demo.gif](taiji-demo.gif) | 10.5–12.5、15–17、24–26 秒 | V3：抓地→生根→肌群缠紧；480×270，6 秒/72 帧，CC BY-SA 4.0 |

三张 GIF 都由下表同版实际 MP4 生成，三段直接切换、等比缩小、12fps 调色板编码、无限循环，均无音轨。[gif-source.json](gif-source.json)保存输入和输出摘要、真实时间范围、尺寸与检查记录。逐张查看了六帧接触表，并解码全部 GIF 帧核对尺寸和时长；这不代表声学字幕验收。

杭州 GIF 包含城市白模和两处实景辅助：Charlie fong 的 [TangxiinHangzhou.webm](https://commons.wikimedia.org/wiki/File:TangxiinHangzhou.webm)（CC BY-SA 4.0）、David290 的[钱塘江大桥航拍](https://commons.wikimedia.org/wiki/File:Qiantang_River_Bridge_DJI_0579.jpg)（CC BY-SA 4.0）；完整来源和修改说明沿用[杭州混剪署名](../../films/hangzhou/MONTAGE-CREDITS.md)。太极 GIF 沿用下方 Z-Anatomy / BodyParts3D / DBCLS 和人物资产署名。机械蝴蝶 GIF 不含原片配乐。

重建到新目录（需要保留下方三个源视频）：

```bash
uv run python scripts/build_readme_gifs.py --output outputs/readme-gifs-new
```

脚本通过 `videocut ffmpeg render` 生成预演和正式 GIF，再用 `look` 生成接触表。查看三张接触表后再复制 GIF 和来源清单进入本目录；脚本默认视觉状态为 pending。

## 从历史会话补充的作品

2026-11-01 通过可访问的历史会话“制定代码复刻视频方案”“制作机械蝴蝶”“制作太极缠丝劲动画”定位交付结果，再从本地对应的**实际 MP4**重新抽帧。没有将会话里的早期静帧、参考图或失败版本冒充交付截图。

2026-11-02 将太极动图和六帧总览更新为 V3 正式成片：先抓稳，再出现根须比喻，足部不再剖析，随后展示腿部肌群缠紧与回弹。太极来源摘要与实际看图记录同步更新，其余作品展示保持原版。

| 版本 | 实际源文件 | 画面与变换 |
| --- | --- | --- |
| 杭州两分钟 delivery-v2 | `outputs/hangzhou-two-minute-qianchen-20261030/delivery-v2/杭州-城市年轮-钱陈音色-两分钟.mp4` | 120 秒、1920×1080/24fps；六帧等比缩小并加秒数，其中 21.2 秒为运河实景辅助分屏 |
| 机械蝴蝶电影版 V2 | `outputs/mechanical-butterfly-v2-20261031/final.mp4` | 32 秒、1920×1080/30fps；六个不同镜头等比缩小并加秒数 |
| 太极动作优化 V3 | `outputs/taiji-flow-v3-20261102/delivery/final.mp4` | 36 秒、1920×1080/24fps；3、9.5、13.9、16.6、27.4、33.4 秒六帧等比缩小并加秒数 |

三张总览均为 1440×588 JPEG。字幕图卡使用同一批实际成片：原生图按 40.782、45.492、50.906、55.837 秒顺序裁取杭州四句字幕，未识别、翻译或重绘；脚本图的中文是根据机械影片镜头编写的后期说明，不是人物原话。两种图卡通过实际文件摘要/尺寸/文字边界检查，并由宿主 Agent 查看；这不代表第三方访谈选题、自动说话人识别或声学同步验收已经完成。

新增展示图的归属：

- **杭州图片与原生图卡**：随[杭州混剪版](../../films/hangzhou/MONTAGE-CREDITS.md)以 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) 提供。建筑数据为 Zhang, Zhao & Long 的 CMAB（CC BY 4.0），水系/道路为 © OpenStreetMap contributors（ODbL）；图集中运河分屏来自 Charlie fong 的 [TangxiinHangzhou.webm](https://commons.wikimedia.org/wiki/File:TangxiinHangzhou.webm)，CC BY-SA 4.0。变换为取帧、裁切、等比缩放与拼接。详见[城市来源](../../films/hangzhou/CREDITS.md)及[实景署名](../../films/hangzhou/MONTAGE-CREDITS.md)。
- **机械蝴蝶图片与脚本图卡**：画面来自本项目代码机械概念动画；图卡新增作者说明、裁切和等比缩放。静图不含音乐；原视频配乐为 Scott Buckley《Neon》，CC BY 4.0，原视频归属见[电影版说明](../../films/mechanical-butterfly/CINEMATIC.md)。
- **太极图片**：按 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) 提供；Z-Anatomy — Gauthier Kervyn / Marcin Zielinski，基于 BodyParts3D © DBCLS；人物/逐趾脚部来自 Grab3D 与 Innerscene/MakeHuman 的 CC0 资产。截图包含比例适配、重新着色、蒙皮和示意动画，随后取帧、等比缩放和拼接。[完整署名](../../films/taiji-silk/CREDITS-V2.md)。

重建这些展示图（需要本机保留上述原片，所有输出写入新目录）：

```bash
uv run python scripts/build_readme_gallery.py --output outputs/readme-gallery-new
```

脚本输出 `gallery/`、两种图卡 manifest、机器报告和逐帧候选。逐张查看后才把小型展示文件复制进本目录；脚本默认的视觉审核状态为 pending，当前仓库清单记录的是实际看过的本次图片。仅克隆代码不包含原视频；也可按各影片指南重建后修改脚本输入，不能据此声称新结果逐字节等同于历史版本。

## 咖啡历史样片

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
