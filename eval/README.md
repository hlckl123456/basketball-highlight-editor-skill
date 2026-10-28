# 篮球评测与人工标注

先打开 [review.html](review.html)。应用只有这一个 HTML 文件，CSS、脚本和初始标注都在其中；视频和参考帧是仓库内的本地文件，不需要服务器、联网或 API key。请保持目录结构完整，用新版 Chrome 或 Edge 双击打开。

语料为 10 段，其中 development 7 段、hold-out 3 段。8 段在户外；有室内比赛和运球示范各 1 段。所有来源、作者、许可、SHA256、日期和拍摄条件在 [catalog.json](data/catalog.json)；媒体许可与派生说明在 [RIGHTS.md](data/RIGHTS.md)。同一拍摄组不会跨 split。hold-out 仅预留作后续评测，本轮生成草稿和测试播放，没有对它计算识别指标或调参。

## 早上怎么标

1. 在页面上方填写复核称呼。左侧选视频；要标 hold-out，勾选“显示预留 hold-out 素材”。
2. 先展开“定义球员外观与目标”，把 p1、p2 的自动服饰线索改成可核对的描述，例如“白短袖、黑短裤、红鞋”。颜色区域可能是广告牌或观众，不能直接当作已识别的球员。添加需要的球员，填写要评测的目标 ID。
3. 看每个事件前后各 3 秒，核实事件时间、是否进球、得分者、持球者和可见球员。无法核实的字段保留“未知”。人出现在画面中不代表他投篮或得分。
4. 确认一项按 C；输入框内按 Ctrl Enter。误报按 X 删除，页面会保留一条确认的负例记录。播放原片时发现漏检，按 A 添加草稿，再填写和确认。已确认内容一旦修改，会先退回 draft；也可点“退回草稿”。
5. 看完已有候选不等于看完原片。点“连续看整段”，完整查看指定区间并补漏检。处理完区间内的草稿和未知进球状态后，勾选完整复核声明，再确认区间。评分据此统计未匹配检测的误报。之后添加漏检或修改标注，会使相关区间重新待确认。
6. 按 Ctrl S 导出 JSON。浏览器本地自动保存只用于同一浏览器、同一数据版本，请定期导出备份。载入导出文件可继续标注。导出中包含全部视频状态和校验信息，页面不会直接写回仓库。

快捷键还包括 Space 播放／暂停、J/L 前后 1 秒、左右箭头前后 0.25 秒、N/P 下／上一项、R 重播窗口、T 取当前播放时间、1/2/0 填进球／未进／未知。输入文字时字母快捷键停用。

“可见球员已完整核实”未勾选时，填写的 ID 只证明这些人出现，不能据此推断没填写的人不在画面。勾选后空列表才表示“无人”。得分者和持球者为空表示未知，不能当作识别错误或正确。

## 标完怎么放回仓库

在仓库根目录运行，把路径换成刚下载的 JSON：

```sh
python3 eval/import_review.py --file /path/to/basketball-review.json
python3 eval/build_review.py
python3 eval/score.py --output work/development-scores.json
```

导入器验证应用来源、导出校验、数据集与视频 SHA256、时间范围、球员 ID 和确认来源。它只复制页面上已有的确认，不把 draft 升级。剩余草稿和页面状态进入 `eval/annotations/review-state/`，可评分事实进入 `eval/annotations/confirmed/`，同时更新 `confirmed.lock.json`。本地回滚备份在被忽略的 `eval/.local/import-backups/`。

确认文件被手改、缺失、出现未登记文件或视频原片改变，评分会以非零退出码拒绝运行。评分本身不创建或刷新锁。应先从 Git 或本地备份恢复正确的文件，再回到页面修改、重审、导出和导入；不要为了让报错消失而手工改哈希。

检查改动并提交在你的工作分支上：

```sh
git diff -- eval/annotations
# 检查确认来源和预期改动后再提交；本任务不会自动替你标注。
git add eval/annotations eval/review.html
git commit -m "Import human-reviewed basketball annotations"
```

只有明确要求评测预留集时加参数。开发集和 hold-out 会分别输出，不能混成一个指标：

```sh
python3 eval/score.py --include-holdout --output work/final-scores.json
```

页面的 SHA256 和确认来源提供可审计的本地记录，不是对真实身份的数字签名。任何能编辑源码的人都能仿造普通 JSON；可信依据仍是实际人工 review、导出记录和 Git 历史。自动测试的确认操作仅使用显式合成色卡数据，不能导入正式语料。

## 标注格式

完整结构见 [annotation.schema.json](annotation.schema.json)，严格的语义校验在 [schema.py](schema.py)。每个视频一个文件，球员 ID 只在该视频内有效。

```json
{
  "id": "c0001",
  "time": 12.5,
  "is_score": null,
  "scorer_id": null,
  "ball_handler_id": null,
  "visible_player_ids": null,
  "visibility_complete": false,
  "status": "draft",
  "deleted": false,
  "confirmed_fields": [],
  "confirmation": null
}
```

新确认项会包含 `confirmation.source: review_page`、页面版本、复核人、会话 ID、确认时间和确认动作。`confirmed_fields` 列明哪些字段被人工复核；空值始终表示未知。误报删除使用 `is_score: false` 和 `deleted: true`，不会从历史中消失。完整复核区间另行记录，不能从“确认过几个候选”自动推导。

唯一历史例外是 `indiana` 原用户确认的两段人物出现事实。其来源诚实保留为 `legacy_indiana_user_review`，指向原始用户决定文件及哈希，绝不伪装成新的页面点击。该例外只允许 c0001、c0003 的 p1 出现事实，不能确认进球、时间或角色，也不能扩展到其他视频。原始 `examples/indiana/project/` 不变。

## 评分定义

只读 `status: confirmed` 且经过哈希锁验证的事实。所有 draft、旧的 agent/test_operator 实验标签和未知字段都被排除。

| 指标 | 定义 |
| --- | --- |
| 事件召回 | 在 ±1 秒内一对一匹配到的已确认进球数 / 已确认进球数 |
| 事件精确率 | TP / (TP + FP)。FP 只来自完整复核区间内的未匹配检测，或明确确认的负例附近 |
| F1 | 精确率和召回的调和均值；所需分母未知时为 null |
| 高置信归属正确率 | 目标身份正确的高置信归属数 / 有人工事实可判断的高置信归属数 |
| 目标事件送审比例 | 目标真实出现／参与的事件被放入该目标的高置信或不确定组的数量 / 该目标已确认事件数 |
| 高置信覆盖率 | 目标事件被正确归到该目标高置信组的数量 / 该目标已确认事件数 |

默认人物指标指 `visible`，即目标在候选中出现。可用 `--player-role scorer` 或 `--player-role handler` 分别测得分者或持球者，不能把可见性冒充得分归属。模型数据位于 `predictions/`，来源、检测时间和高／不确定／排除分组独立于人工标注。新视频在用户校准前没有自动人物归属，不能凭空填高置信。

事件匹配先求最大匹配数，再最小化时间误差，避免贪心配对漏算。重复检测只匹配一次。未完整复核区间内的其他检测单独计为未评判，不能默认当作 FP。标注不全时输出只代表已复核事实，不能声称整段的精确率或召回。

[Indiana baseline](baselines/indiana.json) 成功运行，人物三项指标均为 2/2；它只涉及两个历史确认片段，不是独立泛化测试。进球 P/R/F1 为 null，因为用户当时没有确认进球。若现在给出这三个数值，就必须伪造人工真值。先在本页补齐事件并确认区间，再运行评分即可得到有依据的事件指标。

## 复现自动草稿

全部新草稿由现有 BHE 候选与 `features --no-ocr` 生成，位于 `annotations/drafts/`。各视频的原始检测、失败、特征摘要和处理参数保存在 `data/proposals/`。本轮使用全画面 ROI、CPU、3 fps；没有为了 hold-out 调整 ROI 或阈值。零检测时只加人工查看的覆盖窗口，并保持预测列表为空。

```sh
python3 eval/collect.py --verify-only
# 缺少可下载原片时按固定 URL 和 SHA256 恢复，不下载模型：
python3 eval/collect.py

# 使用你已经有权使用的现有运行时，不安装或转存权重：
/path/to/existing/runtime/python/bin/python3.11 eval/prepare.py \
  --runtime /path/to/existing/runtime --video nabua --refresh
python3 eval/build_review.py
```

重新生成不会覆盖含人工确认的草稿文件。已经导入的人工进度优先从 `review-state/` 恢复；若要比较新模型，保留固定人工真值，另存新预测，使用 `score.py --predictions /path/to/new-predictions`。不要重写 hold-out 真值来改善指标。

## 测试

评分、校验和哈希锁只使用 Python 标准库。原有视觉测试仍需要本机已有 NumPy、OpenCV、ONNX Runtime；基础状态与评分测试不要求安装它们。

```sh
python3 -m unittest discover -s eval/tests -v
python3 -m unittest discover -s skills/basketball-highlight-editor/tests -v
python3 scripts/verify_release.py
python3 scripts/replay_case.py --output work/indiana-replay
node scripts/test_review_form.js examples/indiana/project/review.html
```

离线页面测试使用已有 Node 20+、Playwright 和 Chrome。没有 Browser 插件可用，所以采用常规 Playwright。测试真实语料时只导航和播放，所有确认、修改和导出测试都在隔离的合成视频上进行：

```sh
python3 eval/tests/make_ui_fixture.py --output work/ui-fixture
# Playwright 未安装时先在你的开发环境安装，不必修改正式依赖。
node eval/tests/ui_smoke.cjs eval/review.html work/ui-fixture/eval/review.html work/ui-evidence
```

`PLAYWRIGHT_MODULE` 可指定已有 Playwright 模块路径，`PLAYWRIGHT_CHANNEL` 可指定已安装的浏览器通道。真实页面在桌面 1440×1000 与移动 390×844 检查过，十段视频均可播放，没有外网请求。完整本轮记录见 [goal-1 报告](../docs/reports/goal-1.md)。
