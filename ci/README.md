# 测试工作流模板

`validate.yml` 是可供审阅的 GitHub Actions 配置，包含公开工件校验、15 项行为测试及 HTML 表单逻辑检查。

发布时的 GitHub OAuth 凭据没有 `workflow` 写入权限，GitHub 拒绝了包含 `.github/workflows/validate.yml` 的推送。因此将同一配置作为普通文件放在 `ci/validate.yml`，没有启用自动 CI。所有已报告的通过结果来自本机实际运行，未冒称 GitHub Actions 已通过。

需要启用时，由有相应权限的维护者在 GitHub 上把该文件放入 `.github/workflows/validate.yml`。本仓库没有要求扩大令牌权限的脚本，也不自动修改账号授权。

本机可直接运行：

```sh
python3 scripts/verify_release.py
python3 -m unittest discover -s skills/basketball-highlight-editor/tests -v
node scripts/test_review_form.js examples/indiana/project/review.html
```
