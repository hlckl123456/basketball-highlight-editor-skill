# 个人篮球集锦 Skill

把本地篮球录像整理成一个可复核、可继续编辑的个人集锦项目。先找候选回合，再展示人物特征让用户选人；粗剪与人工确认完成后，保存项目和 EDL，等待下一条剪辑指令。

A local, review-first basketball highlight skill for Codex. Includes runnable scripts, tests, a licensed real-video case and evidence replay. Player identity is evidence-backed and reviewable, not an autonomous recognition guarantee.

**本仓库已经用真实公开许可视频跑通过流程。它还不是可靠识别整场无号码比赛的模型。**

![公开测试视频的候选画面](examples/indiana/project/frames/c0003_f001.jpg)

## 完整案例

先看 **[真实案例 walkthrough](docs/CASE_STUDY.zh-CN.md)**。文档展示原始视频、失败的全画面检测、ROI 修正、4 个候选、服饰／号码线索、用户选人、二次删选、保存状态和测试版本，并给出可点击的图片、视频及 JSON。

- [原始 CC0 视频](examples/indiana/source/indiana-cc0.webm)
- [可直接打开的复核页面](examples/indiana/project/review.html)，下载仓库后在本地打开，GitHub 不运行其中的脚本。
- [真实用户确认后的项目](examples/indiana/project/project.json)和 [EDL](examples/indiana/project/confirmed-edl.json)
- [6 秒测试版](examples/indiana/test-versions/test-short/reel.mp4)和 [完整顺序测试版](examples/indiana/test-versions/test-long/reel.mp4)，仅用于验证后续版本能力。

## 工作流程

1. 用户提供有权本地处理的比赛视频。
2. BHE 公开源码 CLI 找疑似穿框事件；也可以导入已有候选，或使用明确标为低精度的覆盖窗口。
3. 本地脚本提取服饰颜色区域、可选号码 OCR、完整参考帧。提议可能包含广告牌和观众，不能直接当作球员身份。
4. 用户选择视觉参考球员。没有号码时，先确认一张或几张服饰样本。
5. 根据证据整理高置信归属与不确定项，生成独立粗剪。人物在场、实际持球者和得分者分开记录。
6. 用户保留／删除片段。确认后写入 `awaiting_edit_prompt`，保留原视频引用、项目、EDL 和粗剪，不自动合并成片。
7. 用户再给新 prompt，按确认的素材顺序和时长生成独立版本，删除项不会重新混入。

## 先不准备模型，复核完整案例

需要 Python 3.10 以上，以及 PATH 中的 FFmpeg／FFprobe。不需要联网、API key 或安装 Python 包。

```sh
git clone https://github.com/hlckl123456/basketball-highlight-editor-skill.git
cd basketball-highlight-editor-skill
python3 scripts/verify_release.py
python3 -m unittest discover -s skills/basketball-highlight-editor/tests -v
python3 scripts/replay_case.py --output work/replay
```

重放会读取**已归档的 BHE 候选和特征证据**，重新生成粗剪，并以 `test_operator` 记录测试选择及确认。它不是新一轮 BHE 检测，不会冒充新的人类确认。结束时仍停在等待剪辑 prompt 的状态。

要验证两份不同的测试剪辑规格，可明确加上：

```sh
python3 scripts/replay_case.py --output work/replay-versions --render-test-versions
```

如果已经有 NumPy／OpenCV，可用 `--features` 重新提取服饰特征；该选项默认跳过号码 OCR，适合测试无号码路径。

## 安装 Skill

把 `skills/basketball-highlight-editor` 整个目录放到 Codex 的技能发现目录，例如用户级 `~/.agents/skills/`。如果已经有同名 Skill，先备份再更新，避免保留两个同名副本。已有 `~/.codex/skills/` 工作环境也可沿用其已配置位置。

然后对 Codex 说：

> 用 basketball-highlight-editor 处理这个本地比赛视频。先分析候选和人物特征，让我选要剪的人；粗剪给我二次筛选，确认后先保存项目，等我下一条剪辑指令。

普通 CLI 使用步骤见 [workflow.md](skills/basketball-highlight-editor/references/workflow.md)。

## 重新运行 BHE 检测

优先复用已在本机、且你有权使用的 BHE 运行时。检测适配器只调用公开源码脚本，不调用私有 GUI 或修改 BHE 数据库。

本仓库也转存了这次实际使用的 BHE MIT 源码子集，位于 `third_party/bhe`。其中源码与公开 v0.1.12 Git Blob 已逐个核对；没有打包模型权重或整套二进制运行时。

```sh
CLI=skills/basketball-highlight-editor/scripts/highlight.py
python3 "$CLI" init work/new-game --video examples/indiana/source/indiana-cc0.webm --rights examples/indiana/source/rights.json
python3 "$CLI" detect work/new-game --backend bhe \
  --runtime /path/to/authorized/BHE/runtime \
  --roi 0 0 700 700 --fps 15 --device cpu
```

上面的 ROI 只对应本案例，真实比赛必须检查篮筐位置。也可通过 `--runtime third_party/bhe --python /path/to/python --model /path/to/authorized/model.onnx` 复用转存的源码和自己有权使用的兼容模型。这个入口会检查本地文件，不自动下载模型或安装依赖。

## 哪些东西一起公开了

| 内容 | 位置 |
| --- | --- |
| Skill、UI 元信息、命令文档 | `skills/basketball-highlight-editor/` |
| 所有自有脚本、行为测试、案例重放与校验脚本 | `skills/.../scripts/`、`skills/.../tests/`、`scripts/` |
| 公开许可原视频、全部候选、16 张完整帧、639 个特征裁图、参考样本 | `examples/indiana/` |
| 真实确认项目／EDL、原始检测结果、失败对照、测试版本和运行记录 | `examples/indiana/` |
| 用到的 BHE MIT 源码及原许可 | `third_party/bhe/` |
| 实测依赖版本、第三方许可、模型哈希和明确的未打包说明 | `dependencies/`、`THIRD_PARTY_NOTICES.md` |

完整清单和来源见 [第三方与依赖说明](THIRD_PARTY_NOTICES.md)。根目录 MIT 许可覆盖自有代码和原创说明；测试视频遵循作者 CC0，第三方内容保留各自许可。

**BHE 官方明确没有让模型权重自动继承源码 MIT 许可。** 因此本仓库不转存授权不明确的 `.pt`／`.onnx` 权重，也不把含模型的 DMG 换名重新发布。模型哈希、缺失原因与自备模型的接口都已公开。Python、FFmpeg 和第三方包作为外部依赖提供版本与官方来源，不镜像整套系统环境。

## 已验证的范围

- 原始实验的 14 项行为测试通过；开源版另加了跨目录相对路径渲染测试。
- 相同视频、ROI、模型和 CPU 参数重复生成相同的 4 个事件时间点。
- 4 段粗剪、两个有音轨测试版本及静音输入均可解码。
- 正式项目经过真实用户确认，仍在 `awaiting_edit_prompt`，无自动生成的正式成片。
- 无号码的参考样本、跳过 OCR、短时光流与不确定项机制已运行。真实无号码整场比赛的识别准确率尚未验证。

当前渲染器支持横版直接剪切、排序和时长上限。音乐、字幕、智能竖屏跟拍、慢动作与剪映／CapCut 原生工程不在已验证能力中。完整实测边界见 [validation.md](skills/basketball-highlight-editor/references/validation.md)。

## CI 配置

测试工作流作为 [ci/validate.yml](ci/validate.yml) 模板上传。当前发布凭据没有 GitHub `workflow` 写入权限，所以未启用自动 CI；通过结果均为本机实测。权限与启用方法见 [ci/README.md](ci/README.md)。
