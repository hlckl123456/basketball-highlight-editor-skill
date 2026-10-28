# 可重复的输入测试

所有测试从仓库已有的 CC0 Indiana 视频生成变体。生成的视频、缓存和测试项目都留在被忽略的 `work/`，不会改动 `eval/` 或原用户项目。

## 运行

需要 Python 3.10 以上、FFmpeg／FFprobe、NumPy 和 OpenCV。性能测量另需 psutil，人物推理检查需要 ONNX Runtime。优先复用已有环境；CI 的依赖清单在 `ci/requirements-robustness.txt`。

在仓库根目录运行：

```sh
python3 -m unittest discover -s robustness/tests -v
python3 robustness/matrix.py --suite smoke
python3 robustness/matrix.py --suite full --include-long \
  --generated work/goal-2/full-variants --output work/goal-2/full-results
python3 robustness/people_matrix.py --generated work/goal-2/full-variants
python3 robustness/performance.py --output work/goal-2/performance
```

快速矩阵含 13 项。完整矩阵含 65 项，其中有 60 分钟和 120 分钟的视频。完整测试需要数 GB 空间和数分钟到数十分钟；实际耗时取决于 CPU 和编码器。性能测试会另外生成一段带音轨的 60 分钟视频。

`generate.py` 可单独生成素材。`matrix.py --only rotation-90 --suite full` 可只测一个变体。中断后可用相同参数加 `--resume`，跳过已通过项目；代码变动后必须换一个输出目录，避免拿旧结果冒充新结果。

## 矩阵与判定

| 项目 | 输入 |
| --- | --- |
| 分辨率 | 854×480、1280×720、1920×1080、3840×2160 |
| 帧率 | 24、30、60、VFR；VFR 的实际 PTS 在 60fps 与 20fps 之间变化 |
| 编码 | H.264/MP4、HEVC/MOV、VP9/WebM，与上两行完整交叉 |
| 手机方向 | 竖屏、真实 90° 和 180° display matrix |
| 音轨 | 无音轨、完整音轨、短音轨、VFR/VP9 加短 Opus 音轨 |
| 画质 | 抖动、低光、过曝、固定种子的噪点、90kb/s 压缩后画面 |
| 错误 | 缺 moov 的截断文件、保留 moov 的尾部截断、零时长导出、纯音频 |
| 长度 | 60 分钟、120 分钟，在开始、中点和末尾放独立时间码 |

每个有效输入都完整运行两次独立项目：init、缓存候选、features、test_operator 标注与选人、rough、test_operator 确认、独立的后续测试剪辑指令、渲染、重新读取项目。第二次运行必须命中检测缓存。项目 JSON、确认 EDL、版本 EDL 必须逐字节相同。

格式测试导入预声明的时间窗口，不把测试窗口说成检测到的进球。所有球员路由标签都标为不确定，所有确认都用 `test_operator`。检测缓存另有外部 BHE 命令的契约测试，命中时禁止再次调用检测脚本。矩阵不测模型识别准确率。`people_matrix.py` 另外对 61 个有效输入各跑一个真实 YOLOX 样本和服饰匹配，核对显示尺寸、时长及采样时间；机械测试区域不代表球员身份。

时间码是加在派生画面上的二进制帧序号。测试直接读取每个粗剪和版本片段的首尾画面，对照源视频 PTS。起止误差均不得超过一个源帧，片段与整条成片的时长误差不得超过一个输出帧。VFR 的源帧容差取该窗口实际的相邻 PTS 间隔，同时报告帧序号误差和秒数。低码率画面先按 90kb/s 压缩，再加测量条，防止把时间码损坏当成剪切偏移；带测量条的文件总码率会高于 90kb/s。

旋转素材同时验证实际 display matrix 和显示尺寸。FFmpeg 6 使用旧 rotate metadata 接口，支持 display_rotation 的新版本使用输入显示变换接口，避免生成没有真实旋转信息的测试文件。

## 缓存与可复现模式

CLI 的 `detect` 默认将内容缓存写入项目旁的 `.basketball-cache/`。缓存键包含视频 SHA256、检测参数、适配器／媒体读写代码、FFmpeg 版本、模型／BHE 脚本与 src 源码哈希。导入模式另含候选清单哈希。可用 `--cache-dir` 指定位置，`--no-cache` 禁用，`--refresh-cache` 重算。项目引用源视频时仍核对其哈希，缓存内容被改动会报错并提示删除该条重算。

```sh
python3 skills/basketball-highlight-editor/scripts/highlight.py detect work/project \
  --backend manifest --manifest work/ranges.json --cache-dir work/detection-cache
```

`init --reproducible --epoch 946684800` 只供自动测试使用。它记录固定测试时钟并限制为 `test_operator`，普通项目仍记录真实操作时间。不要在真实用户确认流程中启用该模式。

## 性能测量的工作量

`performance.py` 固定使用 480p、30fps、带音轨的 60 分钟输入，分布在整段时间上的 120 个两秒窗口，生成全部 240 秒粗剪，最终保留并渲染 60 秒。它比较 goal-1 的固定提交与当前脚本；旧版本导入已有候选，新版本真正命中候选缓存，两者都不含推理时间，输出均为 720p/30fps。

测量从新进程启动计时，包含源文件哈希和下游步骤。每 20 毫秒汇总主进程及其子进程 RSS，记录峰值。脚本强制检查当前版本低于 300 秒、低于 2GiB。不同候选数量、保留时长和硬件要重新测量，不能据此保证任意整场比赛都在五分钟内处理完。

如果系统禁止读取进程树，性能脚本会明确失败，不会把漏测的内存记作达标。已生成素材可通过 `--source` 复用；旧脚本可通过 `--before-script` 指定。默认旧版来自本仓库 goal-1 提交，需要保留该 Git 历史。

实际结果、版本和未覆盖范围见 [goal-2 报告](../docs/reports/goal-2.md)。
