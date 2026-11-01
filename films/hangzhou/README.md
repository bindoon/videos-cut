# 一城山水，千年生长 · 杭州

用真实杭州建筑和水系数据制作的白模投影短片。Three.js 绘制城市、光层、景深与镜头，Canvas 绘制双语字幕和标注，项目内 `videocut ffmpeg` 编码与交付。时间轴来自 35 条解说实际解码后的 PCM 采样数。

## 文件与数据流

```text
CMAB 浙江 ZIP（按范围读取、CRC 校验） → 杭州自然城市 shapefile
OSM 主 API / Nominatim → 西湖、钱塘江、运河、苏堤和可用楼高
                       ↓
tools/prepare_model.py → data/model.json + stats.json
story.json → 项目 Edge TTS → narration.wav + captions.srt → data/timeline.json
timeline.json → tools/make_music.py → music.wav + effects.wav + mix.wav
model + timeline → main.js / city.js → render(t) → 分段图片序列
项目 sequence 工具 → 逐段 MP4 → tools/finish.py → 成片、截图、检查报告
```

- `story.json`：杭州稿件、英文字幕与章节；`facts.json`：历史陈述及来源。
- `city.js`：真实多边形挤出、物理比例、投影着色、灯光和景深。
- `main.js`：确定性的时间轴、连续相机、章节光层、标注与字幕。`window.render(t)` 可任意顺序调用。
- `codefilm.json`：共享浏览器渲染配置及完整的像素输入清单。`tools/render.mjs` 只保留兼容转发，具体捕获、缓存与编码在项目 `videocut codefilm`。每 120 帧无损 PNG 调用项目 `sequence` 工具编码，并核对实际帧数和视频范围，成功后清除该段临时图片。PNG 输入使 RGB→视频范围转换明确执行，避免 JPEG 中间帧继承全范围 YUV 标记。
- `data/`、`node_modules/` 和 Python 环境为可再生成产物，不提交 Git。
- 固定的上游后处理与浏览器参数及 MIT 许可保存在 `vendor/lemo/`。原始数据、配音缓存及成片在仓库忽略目录内。

## 数据语义

模型覆盖杭州主城区一个约 515.8 km² 的取景矩形，比例 1:10,000。面积是本次取景矩形面积，不是杭州行政面积或建成区面积。

CMAB 本身采用模型估算建筑高度。少量有明确 OSM `height` 字段的建筑采用 OSM 几何及标注高度，替换重叠的 CMAB 轮廓，结果写入 `stats.json`。不以楼层猜高度，也不把 CMAB 年代字段当作古代建筑重建记录。

历史段落在现代建筑白模上投射历史区位光层；画面明确标示“历史位置与光层示意”。良渚古城在主模型西北侧，本次取景不包含遗址几何，世界遗产章节单独注明。苏堤位置从实际 OSM 路径导出。

## 复现

从仓库根目录运行，准备 Node 20+、Python 3.12 与本项目已配置的 FFmpeg：

```bash
uv sync --extra download --extra asr
uv venv films/hangzhou/.venv
uv pip install --python films/hangzhou/.venv/bin/python -r films/hangzhou/requirements.txt
npm ci --prefix films/hangzhou

# 设置为实际 Chromium 可执行文件，也可使用 Playwright 默认安装的版本。
export PLAYWRIGHT_CHROME=/absolute/path/to/chromium
# 始终使用本次新目录，不覆盖原交付。
export HANGZHOU_JOB=outputs/hangzhou-next

films/hangzhou/.venv/bin/python films/hangzhou/tools/fetch_data.py
films/hangzhou/.venv/bin/python films/hangzhou/tools/fetch_data.py --osm-direct
films/hangzhou/.venv/bin/python films/hangzhou/tools/prepare_model.py --output "$HANGZHOU_JOB"
uv run python films/hangzhou/tools/make_narration.py --output "$HANGZHOU_JOB"
films/hangzhou/.venv/bin/python films/hangzhou/tools/make_music.py --output "$HANGZHOU_JOB"
uv run videocut codefilm plan --config films/hangzhou/codefilm.json
uv run videocut codefilm stills --config films/hangzhou/codefilm.json --output "$HANGZHOU_JOB"
uv run videocut codefilm render --config films/hangzhou/codefilm.json --output "$HANGZHOU_JOB"
uv run videocut codefilm verify "$HANGZHOU_JOB/render-manifest.json"
uv run python films/hangzhou/tools/finish.py --output "$HANGZHOU_JOB"
films/hangzhou/.venv/bin/python films/hangzhou/tools/verify_delivery.py --output "$HANGZHOU_JOB"
```

`make_narration.py` 使用在线 Edge TTS（`zh-CN-YunxiNeural`），已有且有效的逐句 WAV 会复用；音乐和音效由 NumPy/SciPy 合成，不调用音乐模型。中文和英文字体在 `fonts/`，使用 OFL 许可。

渲染器不再内置作者的浏览器路径，使用 `--browser`、`PLAYWRIGHT_CHROME` 或 Playwright 默认版本。GPU 后端通过 `--angle` 或 `LEMO_ANGLE` 配置。Node / 浏览器准备、局部渲染、缓存与协议详见[通用工作流](../../docs/code-films.md)。`node tools/render.mjs --stills --output ...` 等旧入口仍转发到共享命令，必须明确输出目录。

原始交付保存在 `outputs/hangzhou-rings-20261030/`，成片为 `杭州-一城山水千年生长.mp4`。当前工具要求传 `--output`；建模、旁白与配乐拒绝写入已有成片的目录，后期通过输入摘要与阶段文件摘要决定能否续跑，输入变化时要求新目录。当前 `data/` 仍是本工程编辑态，不要并发改写两个版本。

共享渲染器使用新清单协议与缓存键，不直接信任原始制作阶段的旧报告，也不自动迁移旧 MP4 缓存。原始成片及验证记录保留；新流程应在新输出目录执行。`verify_delivery.py` 的 4,100 帧、12 章节和 35 条字幕是本片固定验收，新故事需要明确制定自己的验收规格。

## 检查边界

逐段编码核对尺寸、帧率、帧数及视频范围，后期核对完整 4,100 帧、音轨、色彩格式与响度，并检查真实成片截图和黑帧、冻帧、静音指标。任意时间点重复渲染的像素一致性另有静帧检查。

`verify_delivery.py` 在 macOS 上使用系统 Vision 从实际编码视频中逐条抽取字幕中点帧，对 35 条中文字幕独立 OCR 回读；另外提取成片音轨，以 9 个波形窗口检查相对原混音的时间偏移。Swift 编译器用于构建小型 OCR 工具。这是每条字幕的一帧抽样，不是全部视频帧的字幕审计。

字幕来自逐句 PCM 区间与 SRT 回读，属于文件区间字幕。独立 ASR 可供内容复核，但不是 Qwen 强制对齐；后期工具检查也不代表通过原混剪管线 `videocut/sync.py` 的字幕门禁。`verification.json` 明确保留此区别。

具体来源与上游归属见 [CREDITS](CREDITS.md)。

## 两分钟版：Three.js为主，钱陈音色

当前版本为120秒、2880帧、1920×1080/24fps。24句新解说使用本地IndexTTS-2.5和钱陈参考录音生成，参考文件及24kHz单声道缓存位于本地`assets/voices/qianchen/`，随`.gitignore`排除。原始录音来源、摘要及本地索引保存在素材库中。

画面中98.833秒为完整Three.js主镜头（82.36%），12份实景各出现一次、每次1.5秒；其中8次以右侧约三分之一的辅助分屏呈现，城市模型继续运动。最后3.167秒为署名。模型景深通过可选`CITY_CLARITY`变得更清晰，原白模入口默认仍使用1；字幕加入深色底衬，避免亮色屋顶干扰数字字形。

```bash
# 从仓库根目录运行；先完成上文模型、语音环境与城市数据准备。
.venv-index/bin/python scripts/index_narration.py \
  --request films/hangzhou/qianchen-request.example.json
.venv-index/bin/python films/hangzhou/tools/build_two_minute.py \
  --output outputs/hangzhou-120
films/hangzhou/.venv/bin/python films/hangzhou/tools/make_music.py \
  --output outputs/hangzhou-120
uv run videocut codefilm render --config films/hangzhou/montage-codefilm.json \
  --output outputs/hangzhou-120/render --workers 1
films/hangzhou/.venv/bin/python films/hangzhou/tools/finish_two_minute.py \
  --output outputs/hangzhou-120
```

`story-two-minute.json`为当前中英文解说；`montage-edit.json`的`at/until`直接对应新旁白时间。建时间轴时检查每句原始生成文件摘要，仅去掉外缘静音并保留120ms保护。本次24句原始音频总长108.53秒，未做变速；按实际采样数和章节留白组成120秒。该工具可选的保音高变速有1.35倍上限，参数写入时间记录，不将其标为Qwen对齐。

`montage-sources.json`固定本地素材的页面、作者、许可与摘要；具体使用的12份素材见[MONTAGE-CREDITS](MONTAGE-CREDITS.md)。旧快节奏版与最初白模版成片保留在各自输出目录，当前配置不再对应旧171秒时间轴。旧紧凑时间轴后期脚本仅保留为前次实验记录。

当前版本重新验收2880帧、12章节、24句字幕中点OCR和9处实际音轨波形。`verify_delivery.main`的旧默认仍为4100帧/35句，新片通过显式参数定义新的验收规格；未删除或放松断言。Qwen/sync.py未运行时继续保留`passed=null`。
