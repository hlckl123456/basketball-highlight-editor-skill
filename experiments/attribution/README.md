# 归属评估与诚实置信度

本目录不修改 `eval/score.py`、人工事实、锁或开发／hold-out 划分。三个角色分别调用原评分函数。没有角色事实时输出 `null`，不能算成 100%。合成测试只验证程序边界，不是人工 ground truth。

## 固定输入的开发比较

```sh
python3 experiments/attribution/benchmark.py prepare
python3 experiments/attribution/benchmark.py baseline
python3 experiments/attribution/benchmark.py quality
python3 experiments/attribution/benchmark.py final
```

需要已有的 NumPy、OpenCV、ONNX Runtime、FFmpeg 和已授权模型。命令不下载、不安装。模型不提交 Git。缓存、匹配大文件和复制的历史代码都在被忽略的 `work/goal-4/benchmark/`。

`prepare` 只读取开发集 confirmed 文件，先校验其锁定哈希。直接使用人工事件；没有真正的事件时间时，仅使用原确认片段作为“在场”窗口，绝不造一个得分时间。当前只有一个历史确认目标及一张实际用户确认的参考图。模拟操作记为 test_operator，参考图所在的整个片段从评分中排除。无确认参考图的目标不自动猜框。

旧匹配代码从固定 Git 提交 `778641c` 复制，保证之后重跑 baseline 不会误用新策略。`quality` 对同一批固定检测框计算质量，不重新检测、不改框或服饰描述子。新旧比较使用同一人工事实、同一评分函数、同一目标和相同校准排除规则。开发过程装有 hold-out 文件访问保护；不得通过原生子进程绕过它。

当前数据只能评估一个独立片段的已确认在场事实，没有负样本、完整身份框、得分者或持球者事实。不能轮换出更多“已确认球员”，也不能根据它验证野球场的错认率。历史 operator/agent 草稿不并入人工事实。报告见 [goal-4](../../docs/reports/goal-4.md)。

## 验证

```sh
python3 experiments/attribution/validate.py --node node
# 重新测所有输入及 60 分钟性能，不复用旧代码的达标结论：
python3 experiments/attribution/validate.py --slow --node node
```

串行执行原有行为、评测、媒体测试、检测实验、安全契约、HTML 表单和 replay。开发阶段只延期一项会打开真实 hold-out 草稿的完整语料测试，原测试不删改。最终冻结后再运行它和完整发布校验。传入支持 Blob 的现代 Node；这里使用 Node 24。

hold-out 最终评分单独记录一次执行凭据，禁止用于选阈值。没有人工确认的 hold-out 事实时，结论是不可评估，不是达标。
