# 公园无号码案例

[36 秒实际成片](project/versions/unnumbered-chronological/reel.mp4) · [完整案例](../../docs/PARK_UNNUMBERED_CASE.zh-CN.md) · [实际复核页](project/review-before-confirm.html)

原片中球员没有号码球衣。目标为白色 T 恤、深红色齐膝短裤、白袜白鞋的球员。两张参考位于 30 秒、210 秒；另有两个服饰对照人物。所有选择与剪辑复核均为 `test_operator`，不代表任务用户逐条确认，也不属于人工评测真值。

## 文件

- `source/`：官方 480p 原片和许可、下载链接、SHA256。
- `analysis/`：本次新运行的全片覆盖窗口、人形检测与 clothing-v2 特征；不是历史案例缓存。
- `references.json`：可重放的操作员参考框。坐标属于案例输入，算法没有针对本片添加规则。
- `review-windows.json`：整理后的八段覆盖窗口，包含三段删除对照。它们不代表自动检测到进球。
- `automatic-selection.json`、`project/people/`：未经手工修改的生产策略输出，保留不确定项。
- `project/rough/`：八段独立粗剪；`project/review-decisions.json`：五留三删的操作员决定。
- `project/confirmed-edl.json`：工作流选片 EDL；文件名来自项目接口，确认主体仍是 `test_operator`，不是人工评测标注。
- `edit-spec.json`、`project/versions/`：本次明确剪辑要求、实际 EDL、片段及 36 秒合并成片。

## 打开复核页面

下载整个仓库，双击 `project/review-before-confirm.html`。浏览器可直接读取本地 MP4。也可在仓库根目录运行 `python3 -m http.server 8768 --bind 127.0.0.1`，再打开 `http://127.0.0.1:8768/examples/park-unnumbered/project/review-before-confirm.html`。无需联网。

## 重放

在仓库根目录执行；`PYTHON` 指向已有 NumPy、OpenCV、ONNX Runtime 的 Python 3.10+ 环境，PATH 中需要 FFmpeg／FFprobe。脚本不安装包或下载权重。

```sh
PYTHON=python3
"$PYTHON" examples/park-unnumbered/replay.py --output work/park-replay --render
```

默认重放本例刚完成并归档的人形扫描，仍重新计算服饰匹配、分组和粗剪。需要全新推理时显式提供自己已有且有权使用的官方模型：

```sh
"$PYTHON" examples/park-unnumbered/replay.py --output work/park-fresh \
  --redetect --model /path/to/authorized/yolox_nano.onnx --render
```

扫描范围为原片 0–391 秒，3 fps。最初扫描到容器时长时，末尾一个请求没有完整可解码视频帧，整个推理没有写出 JSON；重跑显式截止到 391 秒。保留这一限制，不将那次失败写成成功。末尾约 0.7 秒不在扫描内，选用回合均早于 354 秒。没有为这个演示修改检测器、归属阈值、评分器或正式标注。

原片来自 Cocoa PD，Commons 文件页标为美国公有领域 PD Florida。下载脚本见 `download_source.py`，使用系统 Python 标准库，下载后验证精确 SHA256，不跳过 TLS 校验。
