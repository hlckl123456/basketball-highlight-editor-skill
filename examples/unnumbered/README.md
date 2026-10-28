# 无号码测试资料

完整说明见 [无号码案例](../../docs/UNNUMBERED_CASE_STUDY.zh-CN.md)。

- `sources/`：全部五个下载原片及乌克兰旋转派生版。
- `source-registry.json`、`rights/`：原作者、来源、许可、哈希与变换说明。
- `*-calibration.json`：在原画中选择的每人一到两张服饰样本。
- `*-truth.json`、`*-holdout-truth.json`：Codex 视觉标注，`test_operator`，未经独立人工审核。
- `holdout-selection.json`：固定种子、冻结代码哈希和随机时间点。
- `validation/`：统一评分、开发和留出逐项结果、集成版原片重跑、25 项测试。
- `experiment-code/`：冻结实验与失败版本源码，保留给核对方法演变。
- `*-tiled*.json` 或 `.json.gz`：完整人体框与服饰描述，未删除失败提议。JSON gzip 是标准压缩格式。
- `groundtruth-frames/`、`figures/`：原画坐标网格与单独标明的算法／真值覆盖图。
- `university-project/`、`ljubljana-project/`：包含参考裁图、匹配、独立粗剪、复核页和 EDL 的完整项目。确认均为测试操作者，状态为 `awaiting_edit_prompt`。

照片、帧、粗剪、旋转视频和带框图分别继承来源媒体许可。大学为 CC0；Ljubljana 为 CC BY 3.0；莫斯科两段为 CC BY 4.0；乌克兰原片及派生为 CC BY-SA 4.0。作者和原始页面见各份 rights。人物不代表本任务用户，作者没有为本 Skill 背书。

历史 JSON 中 `input_sha256` 指向实验当时的本机原始 JSON；发布时仅移除本机用户名路径并压缩部分 JSON，所以文件字节哈希会改变。原视频和模型不变，公开文件实际哈希统一列在根目录 `MANIFEST.sha256`。重新计算预测、评分与新项目请使用根目录 `scripts/evaluate_unnumbered.py` 和 `scripts/replay_unnumbered.py`。
