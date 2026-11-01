# 根 · 缠丝 / Rooted in Spiral

**写实解剖版 V2**：入口 `realistic-codefilm.json`，完整 36 秒，采用贴图人物、MakeHuman 逐趾脚部和 Z-Anatomy 真正的骨骼/肌肉网格。详见文末与 [来源署名](CREDITS-V2.md)。初版与 6 秒试装均保留。

36 秒的原创 Three.js 太极劲意图解，1920×1080、24 fps、864 帧。参考用户提供的浅蓝太极动作画，以浅色背景、青蓝服装、解剖红、金色拧劲和青色缠转组织镜头；没有把参考图直接贴入视频。沿用杭州和机械蝴蝶工程的确定性 `render(t)`、共享 codefilm 捕获与项目 FFmpeg 后期。

镜头顺序：完整云手式动作 → 推近承重脚 → 表皮淡出、显露跗跖骨与肌腱肌群 → 五个趾腹下压、根须向地下伸展 → 脚底向外拧劲 → 镜头上移，大腿肌群缓慢向左缠转 → 拉回整体，显示由足至手的连续线。

## 表达边界与方向

这是用户指定“抓地—外旋劲意—大腿左缠”的艺术图解，程序几何和肌群分束是简化造型，不是医学解剖模型、真实肌肉纤维分布或动力学仿真。树根只表示扎根感；螺旋线只表示劲意。没有把某一根足肌标为直接旋转大腿的原因。

影片选择人物右脚承重。脚底金色箭头表示拧地的力矩意向，脚的位置和朝向保持不变。大腿的“左旋”明确为**从髋向足俯视时的逆时针**；肌群和青色箭头使用同一右手坐标系，小幅转动为讲解夸张，并不表示应在膝关节强拧。左旋属于这里固定的观察方向，不等同于所有姿态下的解剖学内旋。

足部和胫骨的耦合取决于姿态、关节与运动条件，不能把外旋必然导致大腿反向转动当作事实。[体外运动学研究](https://pubmed.ncbi.nlm.nih.gov/2731838/)在特定实验条件下观察了足旋后与胫骨外旋的耦合；[足踝闭链运动教学资料](https://www.ouhsc.edu/bserdac/dthompso/web/gait/KNMATICS/STJCLOSE.HTM)说明胫骨旋转、距骨与足部运动的关系。这些材料用于限制本片的表述，并不验证太极劲意模型。

## 复现

从仓库根目录执行；输出目录应新建，保留此前成片。

```bash
npm ci --prefix films/taiji-silk
uv run videocut codefilm plan --config films/taiji-silk/codefilm.json
uv run videocut codefilm stills --config films/taiji-silk/codefilm.json \
  --output outputs/taiji-next --width 1280
uv run videocut codefilm render --config films/taiji-silk/codefilm.json \
  --output outputs/taiji-next --workers 2
python3 films/taiji-silk/tools/soundtrack.py outputs/taiji-next/soundtrack.wav
uv run python films/taiji-silk/tools/finish.py outputs/taiji-next
node films/taiji-silk/tools/package.mjs outputs/taiji-next/taiji-interactive.html
node films/taiji-silk/tools/verify.mjs outputs/taiji-next/qa \
  outputs/taiji-next/taiji-interactive.html
```

Chrome 路径通过 `--browser`、`PLAYWRIGHT_CHROME` 或 Playwright 默认安装传入；影片 `main.js` 没有浏览器路径。`npm run serve --prefix films/taiji-silk` 后访问 `http://127.0.0.1:8768/?interactive=1` 可播放、暂停、拖动时间轴。独立 HTML 内嵌 Three.js、代码与字体，离线可用。交互版没有配乐，MP4 有原创合成器五声音阶配乐；无旁白、外部音乐采样或生成 API。

`fonts/` 复用杭州工程的 Noto Sans SC 子集，OFL 许可随附。Three.js 0.170.0、Playwright 1.63.0、esbuild 0.25.12 在本目录锁定。所有画面输入在 `codefilm.json` 声明。

## 验证

共享 codefilm 每次检查 A→B→A 同帧像素一致，分段实际编码帧数，以及完整成片的 864 帧、尺寸和 fps。影片验证脚本扫描 144 个时间点，确认承重脚不滑动、抓地后五个趾腹保持在同一接触高度，肌群实际转向与标注一致；另复核四组跨章节重复截图和离线播放器的暂停、定位、字体、外部请求情况。这里的接触验证是程序几何验证，不能证明人体生物力学正确。

后期检查实际 MP4 规格、黑帧、冻帧、静音指标与响度，并抽取实际成片联系表供人工查看。片内文字是镜头标注，没有语音字幕；没有运行 Qwen 或 `videocut/sync.py`，不声明声学字幕同步通过。报告与大文件在忽略的 `outputs/`，不修改主项目 ASR、字幕和渲染模块。


## 外部人物模型试装（6 秒技术样片）

针对程序人物过于简化的反馈，新增 `model-study.html` / `model-study.js` / `model-study.json`。通过 Three.js `GLTFLoader` 真正加载带贴图、蒙皮和骨骼的外部 GLB，使用两段骨骼 IK 制作低姿态，直接设置时间重算姿态。这里是验证资产路线的独立 6 秒样片，尚未替换前面的 36 秒正式图解。

素材来自 [Grab3D Man Base Mesh](https://grab3d.com/models/characters/man-base-character/)，CC0-1.0。实际文件 11,354,468 字节、262,348 三角形、24 个骨骼节点，内置 walk/run，未使用这两个动作作为太极。提供方说明底模/贴图经 Meshy 生成后在 Blender 整理；这不是人体扫描或医学模型。许可、上游清单、实际 SHA-256 和下载 URL 归档在 `models/man-base/`。大文件 GLB 被影片本地 `.gitignore` 排除，需按 `source.json` 的 URL 恢复并验证摘要。

该模型穿 T 恤、短裤，且缺少独立手指/逐趾骨骼。它可验证人物材质与比例的提升，**不能直接承担原片的逐趾抓地和肌肉剖析**。完整改版需要太极服、细分脚趾控制与独立解剖网格，不能靠把皮肤材质设为透明自动生成。

```bash
uv run videocut codefilm render --config films/taiji-silk/model-study.json \
  --output outputs/taiji-model-next --workers 2
```

试装预览在 `outputs/taiji-real-model-study-20261031/`；旧太极成片保持原样。


## 写实解剖版 V2：完整 36 秒

`realistic.js` 拥有七段镜头、标注、地面、树根与力矩导向；`character-v2.js` 组合此前认可的人物外观、MakeHuman 的 163 骨骼人物脚部与 Z-Anatomy 的右下肢真实网格。肌腱、短屈肌、短伸肌、骨间肌、跗骨、跖骨与趾骨不再由球体或纺锤体代替。人物仍穿便服；没有承诺或生成太极服。

- 五趾使用 14 个独立关节，拇趾两节、其余四趾各三节。9–14 秒先展示皮肤表面抓地；跖趾关节补偿趾间关节屈曲，以实际变形网格的趾腹最低点求接触，足跟维持接地。对自动蒙皮中占优势脚趾顶点去除跨趾串扰，保留趾蹼的混合权重。
- 14–19 秒显露真实解剖网格，19–24 秒伸展根须并标出向外拧劲，24–30.5 秒露出腿部肌群并小幅左缠，30.5–36 秒回到全身。旋转方向仍为从髋向足俯视逆时针，不能当成外旋必然导致大腿反旋的普遍力学结论。
- 解剖源的比例先匹配 MakeHuman 静态姿态，再由附近皮肤权重驱动；趾骨按具体趾节绑定。人物和脚部不同来源，脚踝之间用其真实切口边界拟合窄网格过渡。大腿缠转后重新约束小腿与踝部，避免层级旋转导致脚底滑移。形变属于动画适配，不代表解剖标本经过生物力学校准。
- 模型 URL、SHA-256、字节长度和许可见 `models/v2-sources.json` 与 `CREDITS-V2.md`。只下载代码不包含 GLB，需要按清单恢复大文件。原始动画、试装和本版使用不同输出目录。

```bash
npm ci --prefix films/taiji-silk
uv run videocut codefilm stills --config films/taiji-silk/realistic-codefilm.json \
  --output outputs/taiji-v2-next --width 1280
node films/taiji-silk/tools/verify-realistic.mjs outputs/taiji-v2-next/qa
uv run videocut codefilm render --config films/taiji-silk/realistic-codefilm.json \
  --output outputs/taiji-v2-next --workers 2
python3 films/taiji-silk/tools/soundtrack.py outputs/taiji-v2-next/soundtrack.wav
uv run python films/taiji-silk/tools/finish.py outputs/taiji-v2-next
```

V2 交付目录为 `outputs/taiji-v2-20261031/delivery/`，姿态报告在同级 QA 目录；后期复用原版 36 秒原创配乐。验证器扫描 144 个时刻，检查五趾接触、足跟、踝部锚定、所有解剖顶点权重、单独改变第三趾控制时其他趾尖保持不动，以及四组 A→B→A 同帧像素相同。共享 codefilm 另验真实编码文件 864 帧。机器检查和实际成片截图分别保存；没有旁白或声学字幕同步结论。
