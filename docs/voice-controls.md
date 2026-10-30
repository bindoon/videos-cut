# IndexTTS-2.5 语音控制与 SSML 实验

2026-10-24 已在本机跑通参考音色、语速、情绪向量、中文拼音纠音及 XML 停顿，共生成 7 组短句样例。参考音频为用户提供的录音，生成过程没有调用付费语音 API。

IndexTTS-2.5 是默认语音引擎。当前操作从 [声音克隆快速使用](voice-cloning.md)、[安装与下载](#安装与下载) 和 [完整视频配音](#完整视频配音) 开始；默认字幕还需 [Qwen 对齐环境](subtitle-sync.md)。

本页同时保留 2026-10-24 的 7 组独立音频实验与后续成片记录。SSML 适配器仅用于短句实验，视频使用原生语音参数及拼音标注。[F5 记录](voice-cloning-f5-history.md) 仅供历史查阅。

## 运行流程与职责

```text
参考录音 → FFmpeg 转为单声道 24kHz WAV → IndexTTS-2.5 音色参考
纯文本 + 语速/情绪参数 ───────────────────→ 官方模型生成 22.05kHz 语音
SSML → 实验适配层 → 原生拼音标记 / 分段生成 → 插入指定长度静音
                   ↓
逐样例 WAV + 参数/校验和/时间轴 → 本地 ASR 内容核对与停顿检查 → 试听对比
```

模型原生控制与适配层分工如下：

| 能力 | 实现位置 | 本次验证范围 |
| --- | --- | --- |
| 使用参考录音的音色 | IndexTTS-2.5 `spk_audio_prompt` | 7 组样例使用同一段用户录音；未做客观说话人相似度评分 |
| 语速 | 原生 `duration_factor` | `1.0` 与 `0.85` 对照；后者缩短生成时长，不是直接加速已有 WAV |
| 情绪 | 原生 `emo_vector` | 高兴、平静两个向量；作用于当前生成片段，未验证词级情绪控制 |
| 中文纠音 | 原生 `<字\|拼音>` 标记 | 同一个“行”分别指定 `HANG2`、`XING2` |
| XML 拼音 | `compile_ssml()` 适配层 | 把 `<phoneme alphabet="py" ph="hang2">行</phoneme>` 转为 `<行\|HANG2>` |
| XML 停顿 | 适配层分段生成与拼接 | `<break time="500ms"/>` 实际插入 11,025 个全零采样，采样率 22,050Hz |
| XML 别名替换 | 适配层 `sub alias` | 已实现，未纳入这 7 组语音实测 |

语音生成与 SSML 转换均在 [scripts/test_indextts_controls.py](../scripts/test_indextts_controls.py)。它调用官方实现，没有修改上游模型代码，也没有向不支持的模型直接传入 XML。

## 安装与下载

以下命令从项目根目录执行。实测环境为 macOS arm64、16GB 内存、Python 3.11.14、PyTorch 2.8.0 的 MPS 后端；依赖与剪辑环境分开。

### 1. 独立运行环境

```bash
uv venv --python 3.11 .venv-index
uv pip install --python .venv-index/bin/python -r requirements-index.lock.txt
```

`requirements-index.txt` 是推理所需依赖，`requirements-index.lock.txt` 固定本次实际安装版本。不要把这些依赖装进剪辑用的 `.venv`。

### 2. 官方代码

本机已下载在 `upstream/index-tts-reference`。首次安装到新目录时可使用：

```bash
git clone --depth 1 --filter=blob:none --no-checkout \
  https://github.com/index-tts/index-tts.git upstream/index-tts-reference
git -C upstream/index-tts-reference fetch --depth 1 origin \
  d9e41aac89fd00b3d71497fddb287b7f24613712
git -C upstream/index-tts-reference sparse-checkout init --no-cone
git -C upstream/index-tts-reference sparse-checkout set \
  '/indextts/' '/tools/' '/LICENSE*' '/pyproject.toml' \
  '!/indextts/utils/maskgct/models/codec/facodec/modules/JDC/bst.t7'
git -C upstream/index-tts-reference checkout --detach \
  d9e41aac89fd00b3d71497fddb287b7f24613712
```

稀疏检出省略了本次 2.5 推理不使用的旧模型二进制。已有该目录时先核对版本，不要重新克隆或覆盖自己的修改。

### 3. 主模型与辅助模型

本次使用约 **7.08GB / 6.60GiB** 权重，包括主模型、语义编码器、声纹模型和音频解码器；不包含 Python 环境、下载临时分片与其他试验模型。使用 ModelScope 镜像下载，按照 Hugging Face 元数据中的摘要核对文件。

```bash
uv run python scripts/fetch_clone_model.py \
  --repo IndexTeam/IndexTTS-2.5 --output assets/models/IndexTTS-2.5 \
  --include config.yaml codec.pth gpt.pth s2mel.pth feat1.pt feat2.pt \
    wav2vec2bert_stats.pt multilingual_zh_ja_yue_char_del.tiktoken LICENSE README.md \
  --mirror-repo-url https://modelscope.cn/models/IndexTeam/IndexTTS-2.5

uv run python scripts/fetch_clone_model.py \
  --repo facebook/w2v-bert-2.0 \
  --output assets/models/IndexTTS-2.5/hf_cache/w2v-bert-2.0 \
  --include config.json preprocessor_config.json model.safetensors \
  --mirror-repo-url https://modelscope.cn/models/AI-ModelScope/w2v-bert-2.0

uv run python scripts/fetch_clone_model.py \
  --repo funasr/campplus --output assets/models/IndexTTS-2.5/hf_cache \
  --include campplus_cn_common.bin \
  --mirror-repo-url https://modelscope.cn/models/iic/speech_campplus_sv_zh-cn_16k-common

uv run python scripts/fetch_clone_model.py \
  --repo nvidia/bigvgan_v2_22khz_80band_256x \
  --output assets/models/IndexTTS-2.5/hf_cache/bigvgan \
  --include config.json bigvgan_generator.pt \
  --mirror-repo-url https://modelscope.cn/models/nv-community/bigvgan_v2_22khz_80band_256x
```

每个下载目录的 `source.json` 固定模型仓库修订；主模型本次为 `c39ce5ba981572cb187443877ff559dfb246ce63`。大文件支持分片续传并校验 LFS SHA-256；小文件核对 LFS SHA-256 或 Git blob 摘要。镜像只是下载来源，不代替内容校验。首次在新目录下载会记录当时的模型修订；要复现本次权重，需核对 [本次模型清单](../outputs/indextts25-controls-20261024-210657/model-sources.json)，不能把将来的仓库最新版本当作本次版本。

本次没有下载 `qwen0.6bemo4-merge` 文本情绪模型，初始化明确设置 `use_qwen_emo=False`。因此本实验使用数值情绪向量，未测试 `emo_text` 自然语言情绪描述。

## 生成与修改样例

```bash
PYTORCH_ENABLE_MPS_FALLBACK=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
TOKENIZERS_PARALLELISM=false \
  .venv-index/bin/python scripts/test_indextts_controls.py \
  --reference /absolute/path/reference.m4a \
  --output outputs/my-new-control-test
```

权重备好后启用离线模式，避免推理时再下载模型。`PYTORCH_ENABLE_MPS_FALLBACK=1` 允许不支持的算子回退 CPU；不代表所有计算都在 GPU 上。脚本还支持 `--model`、`--upstream`、`--device` 指定路径或设备，本次只实测了 MPS 路径。

当前脚本固定了 7 组样例，没有 `--ssml-file`、`--text` 或 `--emotion` 参数。自定义时修改脚本的 `cases` 列表，并使用新的输出目录。例如：

```python
{
    "id": "08-my-line",
    "label": "自定义停顿与纠音",
    "text": "去银行办理业务。",
    "ssml": '<speak>去银<phoneme alphabet="py" ph="hang2">行</phoneme>'
            '<break time="300ms"/>办理业务。</speak>',
}
```

存在 `ssml` 时，以它转换后的内容作为模型输入，`text` 是记录中的台词。情绪、语速作为同一条样例的 `emo_vector`、`duration_factor` 字段指定，不写进 XML。情绪向量顺序为：高兴、愤怒、悲伤、害怕、厌恶、忧郁、惊讶、平静；本次高兴、平静对应位置分别填 `0.8`，其余为零。

参考录音会转为单声道 24kHz WAV；每段输出为单声道 22.05kHz PCM16。带 `break` 的句子分段生成，只裁去各段首尾低能量部分并保留约 30ms 边界，再插入静音；不会自动切除词内静音。`manifest.json` 保存实际片段和停顿时间。

重复运行会检查请求设置、样例参数及已有音频 SHA-256。参数变化或遇到未校验的同名输出时会报错；仍应为每次要保留的实验选择新目录。缓存检查发生在模型加载之后，命中缓存也有加载开销。固定随机种子用于记录实验设置，不保证跨设备、跨依赖版本逐采样一致。

## SSML 支持范围

| 输入 | 当前行为 |
| --- | --- |
| `<speak>…</speak>` | 必须作为根节点；不支持根节点属性 |
| `<break time="500ms"/>`、`<break time="0.5s"/>` | 支持 0～10 秒；插入相应数量的全零采样 |
| `<phoneme alphabet="py" ph="hang2">行</phoneme>` | 每字对应一个带数字声调的拼音，转换为官方拼音标记 |
| `<sub alias="实际朗读内容">原文</sub>` | 替换朗读文本；未纳入本次语音实测 |
| `<w>`、`<emphasis>`、`<emotion>`、`<prosody>`、`<s>` | 不支持，报错 |
| 嵌套子标签、未知属性 | 不支持，报错 |

因此不能直接粘贴任意阿里云 SSML 并期待标签全部生效。`<w>黑咖啡</w>` 尚未实现；当前“黑咖啡”更连贯的结果来自模型输出，不是执行了强制连读标签。情绪向量控制当前生成片段，也不等于能对其中某个词独立精确指定情绪。

500ms 实验验证的是**插入了 500ms 数字静音**。相邻语音可能自带换气、轻音或首尾留白，感知到的总停顿不保证恰好 500ms。

## 实测结果与试听

本次目录：[outputs/indextts25-controls-20261024-210657](../outputs/indextts25-controls-20261024-210657)。前四组台词均为“喜欢清爽，就喝一口黑咖啡。”。

| 样例 | 音频时长 | 本次生成耗时 | 控制内容 |
| --- | ---: | ---: | --- |
| 01 默认 | 4.586s | 112.879s | 参考音色、默认表达 |
| 02 稍快 | 3.901s | 30.372s | `duration_factor=0.85` |
| 03 高兴 | 2.833s | 14.900s | 高兴情绪向量 `0.8` |
| 04 平静 | 3.506s | 14.229s | 平静情绪向量 `0.8` |
| 05 háng | 2.554s | 12.040s | `<行\|HANG2>` |
| 06 xíng | 2.508s | 11.497s | `<行\|XING2>` |
| 07 XML 停顿 | 6.166s | 28.709s | 两段生成、插入 500ms 静音并拼接 |

这些是本机这一次运行的数字。首个样例包含首次参考条件计算及运行预热开销，表格不包含此前下载、安装和模型初始化时间；不能当作生产吞吐或完整成本报价。

- [连续对比音频](../outputs/indextts25-controls-20261024-210657/comparison.wav)：旧 F5 → Index 默认 → 稍快 → 高兴 → 平静，段间隔 1 秒；试听副本统一了响度，原始生成音频保留。
- [纠音对照](../outputs/indextts25-controls-20261024-210657/pronunciation-comparison.wav)：同一“行”字，先 háng、后 xíng。
- [XML 停顿音频](../outputs/indextts25-controls-20261024-210657/07-ssml-pause-500ms.wav)及[对应 XML](../outputs/indextts25-controls-20261024-210657/07-ssml-pause-500ms.ssml)。
- [逐样例参数、时间轴与 SHA-256](../outputs/indextts25-controls-20261024-210657/manifest.json)、[内容与停顿检查](../outputs/indextts25-controls-20261024-210657/speech-qa.json)、[验收报告](../outputs/indextts25-controls-20261024-210657/verification.json)。

所有样例完整解码通过。内容核对使用本地 faster-whisper/base，不提供初始提示词，保留真实识别结果及同音字、繁简字差异。前四组“黑咖啡”在估计词边界内均未检出达到 80ms 的低能量间隔；这只是本次启发式检查，不能解释为模型普遍保证词内零停顿。检查使用统一响度后的音频、-35dB 阈值和 ASR 估计词边界；与未经相同处理的停顿数字不可直接比较。

ASR 能检查文字内容，不评判情绪是否自然、音色是否足够相似；这些仍需试听。此前 337 个测试结果文件校验未变；报告另记录了 macOS `.DS_Store` 元数据变化，原始参考录音也保持不变。

输出目录、模型权重和上游源码是本地忽略文件，不随代码自动分发。文档中的试听及机器报告链接需要保留本机输出目录；换机应按上述流程生成新结果。

## 完整视频配音

准备好上述模型、独立环境和 [Qwen 对齐环境](subtitle-sync.md) 后，可使用默认引擎生成完整视频：

```bash
uv run videocut demo \
  --reference-audio /absolute/path/reference.m4a \
  --output outputs/my-new-index-video
```

IndexTTS 不需要参考录音的逐字稿。CLI 通过 `scripts/index_narration.py` 启动 `.venv-index`，生成新稿的逐句语音，经 FFmpeg 重采样和响度处理转为单声道 48kHz PCM16，再复用字幕、选片、转场、贴纸和配乐流程。镜头以新 WAV 的真实采样数重算，默认整句字幕再根据上一句末字结束点切换；原生发音标记不会显示在字幕中。

默认路径及设备可用 `--index-python`、`--index-model`、`--index-upstream`、`--index-device` 指定；分别默认为 `.venv-index/bin/python`、`assets/models/IndexTTS-2.5`、`upstream/index-tts-reference`、`mps`。省略 `--tts` 时默认选择 IndexTTS-2.5；`edge`、`macos` 可显式选择。F5 的 `clone` 选项与专用参数已移除。

视频配置可增加以下可选部分，然后通过 `--config` 指定新的配置文件：

```json
{
  "index_tts": {
    "duration_factor": 1.0,
    "seed": 20261024,
    "line_overrides": {
      "早晨，不必一开始就匆忙。": {
        "tts_text": "<早|ZAO3><晨|CHEN2>，不必一开始就匆忙。"
      }
    }
  }
}
```

这是配置的局部示例，仍需保留原有 `scenes`、画幅等字段。`duration_factor` 默认 `1.0`，允许 `0.5～2.0`；`emo_vector` 可在 `index_tts` 中设置八维向量，默认不额外指定情绪。每句默认随机种子为起始 `seed` 加句子序号。`line_overrides` 按原始整句匹配，可以覆盖该句的 `seed`、`duration_factor`、`emo_vector` 或 `tts_text`。

`tts_text` 是模型实际朗读输入，可以包含原生拼音标注；字幕仍使用 `scenes[].lines` 的原稿。这不是 XML 输入接口，不能在此直接放入 `<speak>`、`<break>` 等 SSML 标签。

每次生成留下 `index-request.json` 和 `speech/index-manifest.json`，记录参考录音、模型文件摘要、官方代码修订、逐句控制参数、原生/48kHz WAV 路径及 SHA-256。逐句缓存同时考虑这些输入；改变某句控制参数只需重生成对应句子。请继续使用新的输出目录保留旧视频。

成片前的 ASR 内容核对和目标词停顿检查，早期由输出目录里的脚本执行；目前 CLI 已内置字幕同步门禁，见 [字幕同步工作流](subtitle-sync.md)，但它不等同于语义、发音或情绪验收。词级重读、强制连读、词级情绪、完整 SSML 视频输入、别名显示映射和异常停顿自动重生成仍未实现。

### 完整视频实跑记录

后续使用同一段用户录音和原咖啡稿重新成片，单独保存到 [outputs/coffee-indextts25-20261024-213812](../outputs/coffee-indextts25-20261024-213812)：

- [最终视频](../outputs/coffee-indextts25-20261024-213812/final.mp4)及[独立旁白](../outputs/coffee-indextts25-20261024-213812/narration.wav)：49.401 秒、720×1280、H.264/AAC；6 镜头、12 句字幕、6 个贴纸和 5 次转场。
- 默认自然语气、`duration_factor=1.0`，未额外指定情绪。对首句和部分句尾词使用了原生拼音输入，字幕仍显示原稿；实际配置见 [input-config.json](../outputs/coffee-indextts25-20261024-213812/input-config.json)。
- [成片验收](../outputs/coffee-indextts25-20261024-213812/verification.json)：完整解码通过，视频轨 49.375 秒、音轨 49.401 秒，差约 26ms；画面抽查通过。CLI 合成耗时 66.67 秒，命中了已生成并核对过的旁白缓存，不包含首次生成、模型加载和纠音重试。
- [逐句内容核对](../outputs/coffee-indextts25-20261024-213812/speech-qa.json)：12 句音频校验和与最终旁白清单对应；“黑咖啡”在估计词边界内未检出达到 80ms 的低能量间隔（-35dB 阈值）。ASR 的近音、同音及繁简字差异按原样保留，不作为逐字人工听感验收。
- [模型版本核对](../outputs/coffee-indextts25-20261024-213812/latest-model-check.json)：运行前确认本地 2.5 权重修订与当时远端仓库一致；官方代码 HEAD 也与已验证的本地修订一致。
- [旧结果核对](../outputs/coffee-indextts25-20261024-213812/previous-results-verification.json)：此前 385 个测试结果文件未修改、未缺失；macOS `.DS_Store` 元数据不纳入测试结果清单。

初始旁白、纠音音频和一次提前启动后停止的导出中间结果均留在这个新目录中。先前 F5 视频和 7 组控制实验没有被替换。最近一次回归为 10 项测试通过，包含 IndexTTS 读取已准备 PCM 语音时不得退回内置音色的检查。

## 字幕同步修复

上述首版 IndexTTS 视频使用整句文件边界显示字幕，包含 WAV 的首尾留白，并把逗号前后放在同一条字幕内。波形对比没有测到整体音轨偏移；字幕看起来跟不上，主要需要改进显示区间和句内短语切换。

IndexTTS 当前默认整句显示，切换规则为 `caption_switch="previous_speech_end"`：上一句末字结束时立即显示下一句，跨过句间留白供预读。Qwen 只负责定位句末，字幕与声音不做整体平移。显式 `audio_clip` 可回到按 WAV 区间显示；显式 `phrases` 或 `subtitle_phrases` 可拆条，不能在异常时改分条。

SRT 是渲染时间的唯一来源；即时切换模式要求全片无空白字幕帧，按上一句检测结束点验收。配置、可选策略与安装见 [字幕同步工作流](subtitle-sync.md)。

早期[修正版视频](../outputs/coffee-indextts25-subsync-20261024-220357/final.mp4)保存在 `outputs/coffee-indextts25-subsync-20261024-220357`，以下是当时记录，不能将其音轨检查解读为字幕同步已正确：

- 保持 49.401 秒，12 句稿子拆成 23 条短语字幕；配音 WAV 与原版 SHA-256 完全一致。
- 原稿文字、镜头、贴纸、转场和配乐保留；未重新生成声音。最终重合成使用已有背景与旁白，耗时 30.87 秒，不含之前的排查、首次修复试跑和文档工作。
- [对齐审计](../outputs/coffee-indextts25-subsync-20261024-220357/caption-alignment.json)记录逐句文件偏移、声学首尾、短语时间及音频摘要；[同步验收](../outputs/coffee-indextts25-subsync-20261024-220357/synchronization-verification.json)记录 12 个时间点的波形偏移测量，均未测到整体偏移。
- [帧边界抽查](../outputs/coffee-indextts25-subsync-20261024-220357/caption-boundary-check.jpg)：0.125 秒未显示字幕，0.375 秒和 0.875 秒显示“早晨”，1.250 秒已切到后半句。
- 完整解码通过，477 个此前结果文件校验未变。新增短语边界、ASR 时间偏早及旧音频时间误用的回归检查，最近一次 13 项测试通过。

上一轮[双模型尝试成片](../outputs/coffee-workflow-final-20261024-223131/final.mp4)为 49.401 秒、21 条字幕。两句句内切点模型分歧超过 180ms，自动退回整句；[成片字幕验收](../outputs/coffee-workflow-final-20261024-223131/subtitle-sync-verification.json)读取全部 1185 帧，21 条均通过出现/消失时间检查。相对声学参考，出现提前约 40～79ms，消失延后约 25～141ms；最终混音语音窗口相关性最低约 0.970，未测到整体偏移。正式运行 37.62 秒，复用配音、背景与 CTC 缓存，包含第二种对齐、合成及验收；不包含本轮排查、下载及试跑。当时 19 项测试通过；该版合并分条的行为已按用户要求移除，不作为当前字幕展示正确的证明。

上一轮[固定分条成片](../outputs/coffee-fixed-lines-20261024-225609/final.mp4)恢复为 23 条字幕。“早晨”在第 0 帧显示，“先给自己”从对应音频片段起点 3.707 秒开始；“喜欢清爽”和“就喝一口黑咖啡”保持独立。SRT 被渲染器直接回读，正式导出与验收耗时 33.16 秒（复用缓存）。详细对照与 22 项回归见 [最新验收记录](verification.md#最新先固定分条首条绑定音频片段起点)。
