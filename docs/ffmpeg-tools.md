# FFmpeg 扩展工具

项目内提供 [ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill) 2.16.1 的 42 个本地文件处理工具。它们补充现有混剪管线，适用于处理素材、后期音频和导出新版本。既有 `download / transcribe / render / mix / cut` 保持各自入口和验收规则。

[文档导航](README.md) · [使用指南](usage.md) · [AI 操作指南](ai-guide.md)

## 安装与发现

```bash
git submodule update --init --recursive
uv sync
# macOS；Linux / Windows 安装含 libass、drawtext、zscale、vidstab 的 FFmpeg。
brew install ffmpeg-full
uv run videocut ffmpeg doctor --json
uv run videocut ffmpeg --list
uv run videocut ffmpeg audio --help
uv run videocut ffmpeg contract --json --static
```

源码工作区通过 Git submodule 直接引用上游，不维护复制文件；首次运行需初始化子模块。安装已构建的 wheel 时工具已在包内，不需要 Git 或 `npx`。项目技能位于 `.agents/skills/ffmpeg-skill/SKILL.md`，AI 应先阅读其工作流，再通过 CLI 调用。`doctor` 检查当前构建的滤镜、编码器、字体和逐工具可用性，不执行完整视频验收。必需能力缺失时返回非零；可选的 Parakeet/Whisper 引擎无需为普通视频处理安装。

Homebrew 的 `ffmpeg-full` 为 keg-only。上游工具检测到 PATH 上的 Homebrew 精简版 FFmpeg 后，自动使用同一前缀的完整版本及 ffprobe，无需 `brew link --force` 或修改 shell 配置。其他来源的 FFmpeg 沿用其 PATH 设置；需要切换时，可以只为本次命令设置 PATH。原有混剪命令仍沿用系统入口。

Homebrew 会升级共享依赖。本机原有 FFmpeg 8.0.1 在 x265 升级后因缺少旧 ABI 动态库而无法启动，需要同时 `brew upgrade ffmpeg`；这与安装完整构建后是否修改 PATH 无关。安装后分别检查 `ffmpeg -version` 和 `videocut ffmpeg doctor`，并重跑项目测试。FFmpeg 版本变化会改变现有 ASR 缓存身份，历史输出文件保持原样。

精剪的 `cut.ffscript` 改用 `-/filter_complex` 文件读取语法，兼容 FFmpeg 9 移除旧参数 `-filter_complex_script` 的变化；FFmpeg 8 已支持这种语法，见 [官方选项说明](https://github.com/FFmpeg/FFmpeg/blob/n8.0/doc/fftools-common-opts.texi)。剪辑区间、词时间和字幕重排规则没有变化。

## 常用操作

以下输入都由调用者提供。输出写新文件；先查看对应工具 `--help`，必要时加 `--dry-run --json` 预演。`--json-brief` 返回摘要，`--json` 返回命令、探测与审计详情。已有输出默认拒绝覆盖，仅在明确要替换时传 `--overwrite`。

`--dry-run` 在分析工具中仍可能运行探测和测量；上游 `verify` 接受但忽略此参数，仍执行验证步骤。预演也不会让 FFmpeg 实际解析完整滤镜图，不能代替一次成功编码。

```bash
mkdir -p outputs/ffmpeg

# 精确截取，保留音画。
uv run videocut ffmpeg cut input.mp4 --start 0:10 --end 0:25 --accurate \
  -o outputs/ffmpeg/cut.mp4 --json-brief

# 竖屏模糊背景；主体整幅保留。
uv run videocut ffmpeg fit input.mp4 --aspect 9:16 --fit blur \
  -o outputs/ffmpeg/vertical.mp4 --json-brief

# 使用已有 SRT 烧录中文字幕；macOS 可显式指定系统中文字体。
uv run videocut ffmpeg caption input.mp4 --srt captions.srt \
  --font 'Heiti SC' --fonts-dir /System/Library/Fonts \
  -o outputs/ffmpeg/captioned.mp4 --json-brief

# 说话时自动压低背景音乐；写新文件。
uv run videocut ffmpeg audio input.mp4 --music music.wav --duck --fade-out 1 \
  -o outputs/ffmpeg/music.mp4 --json-brief

# HDR 转 SDR，需要 zscale。
uv run videocut ffmpeg color hdr.mov --to-sdr \
  -o outputs/ffmpeg/sdr.mp4 --json-brief

# 双遍响度处理及平台检查。
uv run videocut ffmpeg loudness input.mp4 -I -16 --tp -1.5 \
  -o outputs/ffmpeg/normalized.mp4 --json-brief
uv run videocut ffmpeg export input.mp4 --preset youtube --normalize \
  -o outputs/ffmpeg/youtube.mp4 --json-brief
uv run videocut ffmpeg check outputs/ffmpeg/youtube.mp4 --platform youtube --json

# 查看实际编码画面；图片需要实际打开检查。
uv run videocut ffmpeg look outputs/ffmpeg/captioned.mp4 --tiles 3x2 \
  -o outputs/ffmpeg/contact-sheet.png --json
```

其他工具包括 `sync` 外置录音同步及漂移校正、`multicam` 多机位、`stabilize` 防抖、`scenes` 场景检测、`redact` 已知区域遮挡、`batch` 批量处理。支持范围和参数以项目内各脚本 `--help` 和 [上游技能](../.agents/skills/ffmpeg-skill/SKILL.md) 为准。Apple Silicon 可对支持的重编码工具显式加 `--hw`，实际编码器和回退情况由结果报告记录。

三步及以上编辑可保存为上游项目文件，复用中间阶段或导出到剪辑软件：

```bash
uv run videocut ffmpeg render --init outputs/ffmpeg/project.json
# 按生成的模板编辑 project.json 后运行。
uv run videocut ffmpeg render outputs/ffmpeg/project.json --cache outputs/ffmpeg/cache
uv run videocut ffmpeg render outputs/ffmpeg/project.json \
  --export-timeline outputs/ffmpeg/edit.fcpxml
```

## 与现有管线衔接

- 已有 `captions.srt` 可作为烧录或软字幕输入；字幕文案和时间由输入文件决定。工具本身不做本项目的 Qwen 给稿强制对齐。
- 调整带烧录字幕的成片画幅，会一起缩放字幕。需要保持字号或重新排版时，使用未烧录字幕的画面和原 SRT 重新叠加，并查看成片。
- 上游 `sync` 对齐多份录音；本项目 `videocut/sync.py` 检查字幕像素和音轨偏移，两者职责不同。
- `check` 的格式/平台检查和上游 `verified` 不能替代本项目 `sync.py` 的字幕逐帧验收。后处理输出不自动继承原视频的验收报告。
- 中文口头词精剪继续使用现有 `videocut cut`；上游没有内置中文口头词表。其 `--transcribe` 是独立可选入口，不使用 `videocut/transcription.py` 的分段缓存、输入身份或时间归属规则。
- 不自动把成片送到平台，不接入云服务或付费 API。平台模板是工具内的固定规则，实际上传要求仍应按目标平台核对。

## 来源与更新

本机完整构建的可复现验证：

```bash
uv run python scripts/verify_ffmpeg_tools.py --output outputs/ffmpeg-smoke
```

该脚本要求新的输出目录，生成纯色视频、中文 SRT、440Hz 脉冲、1000Hz 背景音和带 PQ 标记的 10-bit 测试图。它检查实际编码帧中字幕按时出现/消失、背景音在脉冲期间确实变小、PQ 转 SDR 的运行及输出标记、平台导出检查和完整解码，并保存命令、日志和 `verification.json`。这是合成输入的功能验收，不代表真人语音、任意字体、HDR 主观观感或全部 42 个工具均经素材实测。默认字体使用 macOS Heiti SC；其他系统可通过 `--font`、`--fonts-dir` 指定已安装的中文字体。

运行脚本固定于上游提交 `f2d90ea603a663711c3d6aa9775d2a2380d83182`（2.16.1），MIT 许可证保留在子模块。仓库 [`.gitmodules`](../.gitmodules) 记录来源 URL，父仓库的 gitlink 固定提交；[ffmpeg-upstream.json](ffmpeg-upstream.json)保留迁移前同版本工具的文件摘要，便于核对。项目入口不在运行时安装或更新代码。

升级时在子模块检出明确提交，检查新参数与集成边界，通过项目测试和实际工具烟测后提交新的 gitlink。不要用 `git submodule update --remote` 隐式追踪最新版，也不要在本项目修改上游源码；需要修复时向上游提交，或明确引用修复后的 fork。

```bash
git -C .agents/skills/ffmpeg-skill fetch origin
git -C .agents/skills/ffmpeg-skill checkout <已审核的提交>
uv sync --extra download --extra asr
uv run pytest -q
uv build
# 审核通过后，提交父仓库中的子模块指针变更。
git add .agents/skills/ffmpeg-skill
```

构建 wheel/sdist 前必须初始化子模块。构建配置只收录运行脚本、技能、模板、参考资料、工具文档、MCP 和 LICENSE，不收录上游 Git 数据、测试或演示媒体。sdist 带上这些固定文件，因此从源码包重建 wheel 不依赖 GitHub；这属于构建产物，不产生需要维护的第二份源码。GitHub 自动下载的源码 ZIP 通常不包含子模块内容，开发和构建请使用递归克隆或项目构建的 sdist。
