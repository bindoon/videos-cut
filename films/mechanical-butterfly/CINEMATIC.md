# 机械蝴蝶 V2 · 多机位拆解展示

这一版回应“音乐不好听、看起来只有一个镜头”的反馈，改为 32 秒、11 个明确剪切的镜头，保留旧版成片。重拍画面全屏展示机械体，只保留小型镜头标题、部件引线和驱动读数。

| 时间 | 镜头与内容 |
| --- | --- |
| 0–3 s | 传感头微距，缓慢显现 |
| 3–5.5 s | 正面，左右对称扑翼 |
| 5.5–8 s | 侧面，观察机身厚度与翅膀行程 |
| 8–10.5 s | 真正俯视，观察蝶形与翼脉 |
| 10.5–13 s | 背甲抬升、固定螺栓旋出 |
| 13–16 s | 翼组件移开，电机向右抽出，剖切外壳展示转子、铜线圈、输出轴 |
| 16–19 s | 齿轮组微距 |
| 19–22 s | 曲柄连杆与翼根微距 |
| 22–26 s | 分层展开：背甲、传动层、电机、控制板、电池 |
| 26–29 s | 各层归位，背甲锁合 |
| 29–32 s | 整机振翅展示及结束淡出 |

相机运动只在当前镜头内插值，镜头边界直接切换；不会把整个分镜表串成一条连续环绕路径。正面与侧面观测方向相差约 91.1°，正面与俯视相差约 77.5°。

## 参考和配乐

镜头参考为 Tanzim Rahat 的 [Luxury Swiss Watch CGI Animation](https://tanzimrahat.com/work/luxury-swiss-watch-cgi-animation)。实际查看其爆炸展开和机芯细节关键帧，借鉴“外层移开 → 内部细节占满画面 → 归位展示”的顺序。参考图仅放在交付目录 `references/`，没有混入成片。

配乐使用 Scott Buckley 的 [Neon](https://www.scottbuckley.com.au/library/neon/)，来源文件为作者提供的 `sb_neon.mp3`。作者页面明确为 CC-BY 4.0，可在署名条件下使用，包括商业项目。这里使用原曲 52.000–84.000 秒，裁为 32 秒，做 0.35 秒淡入、1.25 秒淡出，母带目标 −15 LUFS、真峰值上限 −1.5 dBTP。没有继续使用第一版的程序音调配乐。

署名已经嵌入画面页脚，并在交付目录 `CREDITS.txt` 留存。发布视频时保留以下署名到说明文字：

> 'Neon' by Scott Buckley - released under CC-BY 4.0. www.scottbuckley.com.au

曲目页：https://www.scottbuckley.com.au/library/neon/
许可证：https://creativecommons.org/licenses/by/4.0/
改编说明：截取、淡入淡出和响度处理。

## 文件和复现

`cinematic.html` 是独立影片入口；`cinematic.js` 复用 `main.js` 的机械体和姿态计算，增加真实的转子、铜线圈、控制板、电池、独立螺栓、剖切材质及镜头控制。`main.js` 中的 `poseModel(s)` 只更新机械姿态，原控制台页面继续调用它。新层叠机构仅在电影入口创建。

```bash
# 仓库根目录；输出必须使用新的目录。
node films/mechanical-butterfly/tools/verify-cinematic.mjs outputs/butterfly-v2-new/qa
uv run videocut codefilm stills --config films/mechanical-butterfly/cinematic-codefilm.json \
  --output outputs/butterfly-v2-new --width 1280
uv run videocut codefilm render --config films/mechanical-butterfly/cinematic-codefilm.json \
  --output outputs/butterfly-v2-new --workers 2
# 将授权音乐的剪辑母带 soundtrack-master.wav 放到相同输出目录后：
uv run python films/mechanical-butterfly/tools/finish-cinematic.py outputs/butterfly-v2-new
```

`finish-cinematic.py` 将无转场合片、替换音轨、流复制交付与内容检查写入 `post-project.json`，通过项目内 `videocut ffmpeg render` 执行。随后重新验最终帧数，按目标规格检查并生成实际编码文件的 4×3 联系表。

验证器检查 11 个机位、183 个姿态（每 0.2 秒以及剪切点前后）、真实变换后的连杆长度和翼根端点、翼膜离地距离、层间距、剖切镜头与不同顺序访问同一时刻的像素一致性。检查中修复了原剖视镜头被翼梁遮挡、背甲升起出画、世界空间剖切面未跟随抽出电机的问题。没有宣称整个模型经过制造验证或全零件碰撞求解。
