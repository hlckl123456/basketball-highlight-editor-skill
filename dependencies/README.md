# 依赖记录

- `bhe-source-manifest.json`：已转存 MIT 源码的上游提交、Git Blob 和 SHA256。
- `bhe-release.json`：上游公开发行包元数据，仅用于来源核验，不表示本项目再分发包内权重。
- `bhe-upstream-requirements.txt`：上游 v0.1.12 的直接依赖范围。
- `tested-python-packages.json`：直接相关包的本机版本与元数据。
- `tested-runtime-all-packages.json`：本次 BHE Python 中 48 个分发包及所附许可文件路径。
- `requirements-runtime-observed.txt`：观察到的完整包版本，不是跨平台安装承诺。
- `requirements-features-tested.txt`：本次特征提取所用 NumPy／OpenCV 版本。
- `requirements-bhe-tested.txt`：本次检测所用直接包版本。

基础状态管理、粗剪、版本渲染和行为测试使用 Python 标准库及外部 FFmpeg／FFprobe，不要求安装这些 Python 包。重新提取特征需要 NumPy／OpenCV；Tesseract 可选。重新运行 BHE 还需要自己的授权兼容模型和检测依赖，或已有的授权 BHE 运行时。

优先复用本机已有环境。安装任何新依赖前先审阅用途和许可；这些文件不会被启动脚本自动执行。许可及明确未打包项见仓库根目录 `THIRD_PARTY_NOTICES.md`。
