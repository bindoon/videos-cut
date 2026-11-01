# Aurelia B–04 · 机械蝴蝶

**新增 [V2 多机位电影版](CINEMATIC.md)**：32 秒、11 个独立镜头，增加正面、侧面、俯视、电机剖视、齿轮与翼根微距、分层拆装，配乐改用 Scott Buckley 的授权 Synthwave 曲目《Neon》。入口为 `cinematic-codefilm.json`。下文保留初版 26 秒控制台演示及其交互操作。

参照用户提供的 [Nyxera 机械蝎子拆解展示](https://x.com/nyxera0x/status/2116277601794724232)，制作新的机械蝴蝶。借鉴浅色工业仪表台、机芯特写、爆炸拆解及重组的表达；蝴蝶形体、运动模型、分镜和合成声音为本工程新写，未使用参考视频的画面或音频，也未安装其推广的外部技能。

成片为 26 秒、1920×1080、30 fps，四翼框架由金属肋条、半透明翅膜、蝶形后翼尾突构成；机身带分节腹部、传感头、触角、六条收放脚、两片可抬升背甲。展示顺序在 `timeline.json`：唤醒、扑翼、开甲、传动特写、爆炸环绕、重组、起飞。

## 运行与交付

从仓库根目录执行：

```bash
npm ci --prefix films/mechanical-butterfly
uv run videocut codefilm plan --config films/mechanical-butterfly/codefilm.json
uv run videocut codefilm stills --config films/mechanical-butterfly/codefilm.json \
  --output outputs/butterfly-new --width 1280
uv run videocut codefilm render --config films/mechanical-butterfly/codefilm.json \
  --output outputs/butterfly-new --workers 2
python3 films/mechanical-butterfly/tools/soundtrack.py outputs/butterfly-new/soundtrack.wav
uv run videocut ffmpeg loudness outputs/butterfly-new/soundtrack.wav \
  -I -18 --tp -2 -o outputs/butterfly-new/soundtrack-master.wav --json
uv run python films/mechanical-butterfly/tools/finish.py outputs/butterfly-new
node films/mechanical-butterfly/tools/package.mjs outputs/butterfly-new/aurelia-interactive.html
```

浏览器位置可设置 `PLAYWRIGHT_CHROME`，也可在 codefilm 命令上传 `--browser`。每次交付使用新的输出目录。`finish.py` 经 `videocut ffmpeg` 的 Python 模块入口调用已有工具，先验证分段，再无转场合片、替换音轨、验证最终帧数、做格式/内容检查并生成联系表。

独立交互版 `aurelia-interactive.html` 约 0.54 MB，包含 Three.js 和本工程代码，可直接用现代浏览器打开，无网络请求。也可运行 `npm run serve --prefix films/mechanical-butterfly`，访问 `http://127.0.0.1:8766/?interactive=1`。

交互操作：拖动旋转，滚轮缩放；点击 `CARAPACE`、`EXPLODE`、`ASSEMBLED` 拆装；点击频率按钮切换驱动速度；空格暂停，H 隐藏面板；底部进度条定位时间。`AUTO TOUR` 恢复自动分镜，25 秒不操作恢复默认控制状态。

## 模型边界

`model.js` 保存概念参数和纯时间函数。曲柄半径 0.23、连杆长度 0.77、摇臂 0.43、右翼铰点 `(0.66,0.08)`，以两圆交点求出摇臂角度，镜像到左翼。前后翼相差 0.32 rad；示意驱动频率 2.4 Hz，以四分之一速度展示，仪表由相同状态实时绘制。

尺寸是设计用模型单位；没有实际飞行器、材料、扭矩、质量或升力的测量依据。齿轮是视觉传动示意，未进行齿形接触力学分析。外壳抬升和部件间距为讲解用拆装动画，爆炸展开时连杆随对应翼组件移开，两端距离保持不变。该作品不是可制造结构或空气动力学仿真。

渲染页面默认无自主时钟，`window.render(t)` 可任意顺序调用。`?interactive=1` 或打包版才启动实时预览。`main.js` 负责几何、镜头与仪表；`tools/soundtrack.py` 使用标准库确定性合成立体声氛围与机械瞬态，不含旁白、外部采样或付费生成 API。无声学字幕，Qwen / sync.py 不适用。

## 验证

```bash
node films/mechanical-butterfly/tools/verify.mjs outputs/butterfly-new/qa \
  outputs/butterfly-new/aurelia-interactive.html
uv run videocut codefilm verify outputs/butterfly-new/render-manifest.json \
  --video outputs/butterfly-new/final.mp4
```

验证器扫描一个周期的 7201 个相位；每隔 0.2 秒检查真实场景变换后的连杆长度、翼根连接位置和翼膜离地间距，覆盖 131 个姿态；比较 A→B→A 的真实截图；实际点击拆甲、展开、自动恢复、频率与隐藏面板按钮，记录页面异常。这里不宣称检查全部零件之间的碰撞。

本次检查发现原地面高度会裁掉低点翼尖，将地面从 −2.15 降到 −4.2 后，默认时间轴最小翼膜离地距离约 0.702 模型单位。齿轮对增加半齿相位差，避免初始齿尖正对。机芯特写允许翼尖出画。七个分镜静帧和编码后联系表需实际查看；机器检查不能替代视觉判断。

Three.js 0.170.0、Playwright 1.63.0、esbuild 0.25.12 由本目录锁文件固定。完整分段源码摘要包含 `main.js`、`model.js`、页面、时间轴和依赖锁；生成结果与详细报告放在被忽略的 `outputs/`。
