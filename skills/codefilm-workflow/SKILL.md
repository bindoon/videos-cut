---
name: codefilm-workflow
description: 用本项目 codefilm 和 FFmpeg 组织 Canvas/Three.js 代码影片，从故事、来源和数据、声音时间轴、分镜预览到完整渲染及交付。用于城市白模、机械动画、动作图解等代码出片；不处理普通素材混剪或宣称输入城市名自动生成影片。
---

# 代码影片制作工作流

从仓库根目录操作，先读 `AGENTS.md`。页面协议、环境、配置、分段缓存与验证参数以 [codefilm 工具](../../docs/code-films.md) 为准；[杭州](../../films/hangzhou/README.md)、[机械蝴蝶](../../films/mechanical-butterfly/CINEMATIC.md)和[太极](../../films/taiji-silk/README.md)保存各作品实现。

先运行 `codefilm plan` 核对输入，再用 `stills` 和短范围 `render` 检查机位、遮挡、字幕与标注。预览明确用 `verify --allow-partial`；正式交付必须对最终源码完整渲染并验证，不手工拼接不同源码版本的缓存。

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

本次矩形覆盖约 515.82 km²，从 124,455 条原始记录筛出 75,139 个建筑部分。这个面积不是行政面积，建筑部分数也不是人口或住户数。现代白模上的历史光层标为示意，不把估计年代当作古建筑复原；良渚遗址在取景矩形外，单独说明。下载端点、版本和许可证见杭州 [CREDITS](../../films/hangzhou/CREDITS.md)。

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
