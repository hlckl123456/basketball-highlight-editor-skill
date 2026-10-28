# 测试工作流模板

`validate.yml` 是可供审阅的 GitHub Actions 配置，包含原有发布校验、行为测试、HTML 表单检查、评测测试，以及 13 项快速输入矩阵。

发布时的 GitHub OAuth 凭据没有 `workflow` 写入权限，GitHub 拒绝了包含 `.github/workflows/validate.yml` 的推送。因此将同一配置作为普通文件放在 `ci/validate.yml`，没有启用自动 CI。所有已报告的通过结果来自本机实际运行，未冒称 GitHub Actions 已通过。

需要启用时，由有相应权限的维护者在 GitHub 上把该文件放入 `.github/workflows/validate.yml`。本仓库没有要求扩大令牌权限的脚本，也不自动修改账号授权。

本机可直接运行：

```sh
python3 scripts/verify_release.py
python3 -m unittest discover -s skills/basketball-highlight-editor/tests -v
node scripts/test_review_form.js examples/indiana/project/review.html
```

完整 65 项输入矩阵和 60 分钟性能测试放在可选的 `slow-robustness` job。启用工作流后，通过 workflow_dispatch 将 `slow_robustness` 设为 true 即可运行；它获取完整 Git 历史，以固定 goal-1 提交作性能对照。默认快速测试会安装 `requirements-robustness.txt` 中的 NumPy、OpenCV、ONNX Runtime 和 psutil。

本次只更新配置模板，未推送分支，也未声称 GitHub 上运行过 CI。详细本机命令见 [robustness/README.md](../robustness/README.md)。

HTML 表单检查需要 Node.js 18 以上（使用内置 Blob），不要用旧版系统 Node 跑这个检查。
