# 召回优先的检测实验

这里保存研究工具，不替代生产检测器。所有事件和 ROI 都是 draft，ROI 仍需实际用户确认。实验不读取评测草稿来充当真值，不改 confirmed、评分逻辑或 split。

当前正式语料只有两条历史球员出现事实，没有人工确认的进球或完整复核区间。事件召回、精确率和 F1 均无法估计；没有人工 ROI 真值。未知值不能与目标分数比较，也不能用候选数量增加代替召回提高。

`plans.json` 列出 15 个预先写下的假设。每轮读取 `eval/results.tsv`，修改研究绑定的参数，生成开发集候选，运行门禁，再调用未经修改的评分器。无法评分或没有提高时执行分支内的 `git reset --hard`，从被忽略的工作记录恢复 TSV。实验补丁保存在本地，最终报告会归档被拒绝的参数补丁。

## 复现步骤

使用已有、已授权的 BHE ONNX 模型，不下载或提交权重。需要 NumPy、OpenCV、ONNX Runtime、FFmpeg 和 Node 18 以上。

```sh
python3 eval/score.py --output work/goal-3/baseline.json
python3 experiments/detection/scan.py --model /path/to/existing/bball_model.static.onnx
# 只在专用 goal-3-detection 分支的干净 bootstrap 提交上执行。
# 此命令按授权回滚失败试验，先提交与试验无关的改动。
GOAL3_NODE=/path/to/node python3 experiments/detection/run.py --base BASELINE_COMMIT
```

扫描只使用 catalog 中的 development 来源与原有 evaluation_ranges；12fps、0.03 解码下限用于受控降采样／阈值实验。缓存键绑定视频、模型、范围、参数及扫描代码哈希，实验输出留在 work/。扫描使用 CPU、单批次和已有官方应用的本地模型，不调用 Ultralytics 自动安装器。

`score_dev.py` 给原评分器加文件访问隔离，不改其公式或匹配。开发集进程拒绝打开真实 hold-out 的原片、预览、标注、预测及嵌入全部标注的 review.html。合成单元测试中的 hold-out 是明确的模拟数据，不是正式预留集。

## 门禁范围

每轮执行发布校验、行为测试、评测测试、稳健性测试、本研究测试、HTML 表单检查、Indiana 重放，以及 13 项快速输入矩阵。完整 65 项矩阵和一小时性能测试属于既有可选慢测试；生产输入代码未变，另核对 goal-2 已验证代码哈希。

迭代时 `verify_release.py --development-only` 明确暂不打开 34 个预留集相关文件，保留已冻结发布哈希，其内容校验推迟到最终冻结。这个结果不能冒称完整发布校验。评测单元测试也只推迟一项会读取真实 hold-out 草稿的语料检查；原测试源码和断言保留，最终全部运行。

`run/finalized.json` 表示停止调参。完成 15 轮无提升后，只调用一次真实数据集的 `--include-holdout`，并恢复默认完整发布与语料检查。后续不能根据这次结果继续改参数。

研究停止后的证据与只运行一次的最终评估工具是 `finalize.py`。它要求已生成 15 轮冻结记录，并使用独占创建的哨兵拒绝再次对真实数据集执行 include-holdout。最终案例只是自动挑选的未复核差异，不能直接放入人工真值。
