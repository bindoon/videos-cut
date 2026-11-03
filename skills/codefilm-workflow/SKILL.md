---
name: codefilm-workflow
description: 用本项目 codefilm 和 FFmpeg 组织 Canvas/Three.js 代码影片，从故事、来源和数据、声音时间轴、分镜预览到完整渲染及交付。用于城市白模、机械动画、动作图解等代码出片；不处理普通素材混剪或宣称输入城市名自动生成影片。
---

# 代码影片制作工作流

从仓库根目录操作，先读 `AGENTS.md`。页面协议、环境、配置、分段缓存与验证参数以 [codefilm 工具](../../docs/code-films.md) 为准；[杭州](../../films/hangzhou/README.md)、[机械蝴蝶](../../films/mechanical-butterfly/CINEMATIC.md)和[太极](../../films/taiji-silk/README.md)保存各作品实现。

先运行 `codefilm plan` 核对输入，再用 `stills` 和短范围 `render` 检查机位、遮挡、字幕与标注。预览明确用 `verify --allow-partial`；正式交付必须对最终源码完整渲染并验证，不手工拼接不同源码版本的缓存。

## 共用导演与代码场景

新片或明显调整叙事时先读[共用视频导演](../video-direction/SKILL.md)，确定信息主线、运动用途、节奏与关键帧。声音驱动的时间来自实际音频；动作/机制图解按用户指定的观察方向与动作顺序组织，不套发布片快切阈值。

代码场景保留稳定镜头 ID；相机、美术、标注和模型控制属于 `films/`，通用工具只负责捕获与校验。优先复用已认可场景，暴露确实需要改动的参数，不为了接编辑界面迁移全部渲染代码。

第一次看静帧时检查构图和最难镜头；局部预览检查实际运动与声音。多轮修改使用[审片工作流](../review-workflow/SKILL.md)，记录实际预览版本、镜头、原工程时间和修改依据。

制作城市数据短片时再读[城市影片参考](references/city-films.md)。它保留杭州的史实、GIS 和数据获取经验，不作为机械/动作图解的必做步骤。

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
