# 写实解剖版素材与改动

本片用三个独立来源组合：此前认可的贴图人物承担脸、服装和全身动作；MakeHuman 来源的连续腿部网格与逐趾绑定承担下肢；Z-Anatomy 的独立骨骼和肌肉承担剖析。没有宣称下载到了一个同时包含全部外观和解剖结构的单一模型。

- **人物表面**：[Grab3D Man Base Mesh](https://grab3d.com/models/characters/man-base-character/)，CC0-1.0。提供方声明 Meshy AI 底模与贴图经 Blender 清理、缩放和检查。实际下载文件和许可已归档在 `models/man-base/`。
- **逐趾人物 / 脚部**：[Innerscene Male base mesh, Rigged A-pose](https://www.innerscene.com/tools/library/3d-parts/male-base-mesh-3d-person-rigged-a-pose-380e6d89)，由 Innerscene 改编自 MakeHuman CC0 资产，并以 CC0-1.0 发布。GLB 内嵌版权及许可说明。实际模型有 163 骨骼；左右脚各 14 个趾节关节（拇趾两节，其余四趾各三节），足部网格沿用原有绑定，并清理趾尖的跨趾权重串扰，保留趾蹼混合。影片使用其从短裤遮挡处到脚趾的连续下肢表面、指甲与骨骼。2026-11-02 修正脚踝分离感：移除旧的踝部过渡网格，小腿、脚踝和脚部保持同一张原生表面；按人物腿段长度适配四个表面驱动骨骼，模型间的交接位于短裤下方。
- **骨骼和肌肉**：Z-Anatomy — The libre 3D atlas of anatomy，Gauthier Kervyn / Marcin Zielinski，CC BY-SA 4.0；基于 **BodyParts3D © The Database Center for Life Science (DBCLS)，CC BY-SA 2.1 Japan**。原项目：[Z-Anatomy](https://github.com/Z-Anatomy/Models-of-human-anatomy)。使用 [SeemaBansal1 的 Blender 分层导出](https://github.com/SeemaBansal1/3d-human-body-anatomy)中的 `muscles.glb` 和 `skeleton.glb`，由 Three.js 本地 Draco 解码。保留实际肌群和骨骼的命名、形状；只选择右下肢，匹配比例与骨骼姿态并重新着色，增加用于动画的蒙皮与示意缠转。没有使用其器官、神经或其他来源资产。
- **字体**：Noto Sans SC 子集，OFL，`fonts/OFL.txt`。
- **配乐**：本工程 `tools/soundtrack.py` 原创合成，复用首次 36 秒配乐，不含外部采样、旁白或云生成服务。

精确下载地址、字节长度与 SHA-256 在 `models/v2-sources.json`。GLB 是可恢复大文件，由影片本地 `.gitignore` 排除；代码、许可、来源与参数留在仓库。

本片与其解剖衍生表现以 **CC BY-SA 4.0** 提供；分享时保留 Z-Anatomy / BodyParts3D / DBCLS 署名及同许可。原 CC0 模型仍适用其原许可。许可链接：https://creativecommons.org/licenses/by-sa/4.0/

动作及力矩箭头是用户要求的缠丝劲意图解。肌肉网格来自真实解剖建模，但动画匹配、肌群缠转、接触求解和根须均由本片制作；不是经临床验证的人体肌力仿真。

2026-11-02 动作优化 V3：增大趾间关节的抓地屈曲，抓稳后才显示分支生长的根须比喻；足部肌肉与骨骼资产保留但全程隐藏。只在小腿、大腿打开剖视窗口，增加腿段外旋、躯干随动，以及肌肉表面相对左缠、轻微径向收窄、纵向形变和卸载回弹。所有肌肉形变每帧从原始网格重新计算，不修改上游 GLB；原视频保留。
