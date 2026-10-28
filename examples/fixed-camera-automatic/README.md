# 固定机位、无号码、自动选人

[打开自动结果回放页](recognition.html) · [完整案例说明](../../docs/AUTOMATIC_FIXED_CASE.zh-CN.md) · [模型自动导出的 6 秒草稿](project/versions/automatic-draft-v2/reel.mp4)

原片为 Alejons06 的 CC0 校园篮球录像，固定视角，四个人穿便装，没有球衣号码。原片和许可沿用 `examples/unnumbered/` 已公开文件；本次重新提取人形和纹理，不沿用老方法的身份判断。

## 怎样看

下载完整仓库，直接双击 `recognition.html`。页面内嵌自动结果，不依赖网络。原片时间、参考图与自动框同步；每秒五帧，未通过的采样点不画框。可切换人物、播放暂停，左右方向键按 0.2 秒步进。每个人分别只用其本人一张参考运行。白衣有远离参考的通过区间；另外三位目前仅参考附近通过，不隐去失败。

页面明确标为“预先在本地推理的结果回放”。演示固定裁图只放大观看，不修改识别输入。不支持字节范围的简单 HTTP 服务器可能无法精确跳转大视频，推荐直接打开本地文件。

## 自动选片如何复现

默认只使用目标人物在 13.4 秒的一张参考，不需要其他人物的人工参考：

```sh
python3 examples/fixed-camera-automatic/replay.py --output work/fixed-one-reference --render
```

需要已有 NumPy、OpenCV、ONNX Runtime、FFmpeg。默认重放带哈希的实际模型输出向量，重新计算当前匹配与选片，不需要权重、PyTorch、联网或手改高置信编号。脚本在新目录里操作，不修改这个案例。

轮换四个目标、每次只给该目标一张参考，重新计算回放页对照：

```sh
python3 examples/fixed-camera-automatic/compare_targets.py --output work/fixed-four-single-runs
```

下列模式重放归档的四参考对照实验（主演示与回放页采用分别单参考运行）：

```sh
python3 examples/fixed-camera-automatic/replay.py \
  --output work/fixed-all-cards --all-reference-cards --render
```

单张目标参考产生两个后段高置信窗口；四人物对照卡版本产生三个，其中一个靠近参考，被自动排除。**两种设置都自动导出同样的后段两个相邻窗口，共 6 秒。** 不把相邻窗口当成两场独立实验或两个得分回合。

`--render` 为本次明确授权的自动效果演示记录 `test_operator` 导出测试，不是用户逐段复核。真实使用仍需要用户看高置信和不确定片段。去掉 `--render` 会停在粗剪复核阶段。

若要全新推理，用已经有权使用的本地权重，并选择已有 PyTorch 的 Python：

```sh
python3 examples/fixed-camera-automatic/replay.py --output work/fixed-fresh \
  --model /path/to/authorized/dinov2_vits14_pretrain.pth --redetect --render
```

`--redetect` 还需要已有的官方 YOLOX-Nano 权重。模型准备命令、许可和 SHA256 见 [Skill 纹理入口](../../skills/basketball-highlight-editor/references/appearance.md)。不提交权重。

## 保存了什么

- `coverage.json`：完整覆盖原片的 21 个窗口，包括最后不足三秒的窗口，不是进球真值。
- `reference-inputs.json`：前 15 秒内的参考选择，全部 `test_operator`。
- `project/people/`：本次 303 帧、492 个检测框及服饰向量，旧颜色与新纹理结果使用相同输入。
- `baseline-selection.json`、`comparison.json`：白衣单参考：旧策略 0 个高置信；新策略 2 个。统计为程序输出数量，不是准确率。
- `single-target-suite.json`：每人分别只给一张参考的对照，没有其他人物的人工参考。
- `automatic-selection.json`：机器计算的导出规则和结果，排除目标参考前后三秒。
- `project/rough/`：全部高置信和不确定窗口，均可复核。
- `project/versions/automatic-draft-v2/`：当前自动草稿及 EDL。当前版明确按渲染结束时间不包含端点计算证据；四参考实验保存在 `four-card-project/`。
- `independent-check/`：不同 ROI 与覆盖窗口的独立试用记录，状态为草稿。
- `supplement/`：另一个无号码球局的成功匹配，以及夜间移动机位仍然失败的结果。这些镜头有移动，不当作固定机位验证。

所有参考、自动判断、导出测试与视觉检查均非人工评测真值；没有生成或修改 `eval/` 的 confirmed 标注。`supported_time_ranges` 是证据的包络范围，`support_times` 和 `unresolved_times` 区分通过与未通过的具体采样点。
