# 第三方、依赖与素材

自有 Skill、脚本、测试及原创文档使用根目录 MIT 许可。第三方源码、许可文本和媒体保留各自条款，不能用根目录许可替代。

## 随仓库提供的内容

| 内容 | 来源与许可 | 仓库位置 |
| --- | --- | --- |
| BHE 扫描／候选脚本和 Python 算法包 | [BHE v0.1.12](https://github.com/fly7632785/basketball-highlight-editor/tree/v0.1.12)，MIT，保留原版权声明 | `third_party/bhe` |
| 原始篮球视频及衍生帧、裁图、候选和测试剪辑 | [作者 Koavf / Justin Anthony Knapp 的 CC0 文件](https://commons.wikimedia.org/wiki/File:Indiana_Legends_Versus_Indiana_Lyons,_20240224_183141_(165)_(165).webm) | `examples/indiana` |
| Python 及 BHE 包内依赖的许可文本 | 从本次实际使用的包元数据复制，条款以各文件为准 | `third_party/dependency-licenses` |
| FFmpeg 的许可说明与 COPYING 文本 | 来自本次实际执行的本机 FFmpeg 包，仅转存许可文本 | `third_party/dependency-licenses/ffmpeg` |

BHE 固定到提交 `4d78d6fa2da74fa3d5f3c9719ab7189f24c545e3`。所有转存的 Python 源码和 BHE LICENSE 的 Git Blob SHA1 都与公开 tag 一致，逐文件 SHA256 见 [bhe-source-manifest.json](dependencies/bhe-source-manifest.json)。未对转存的第三方源码作功能修改。

案例中的媒体仅用于公开说明和复现辅助剪辑流程。CC0 的版权依据不代表已经获得所有人物、场地、商标、音乐或背书方面的许可，不把画中球员当作任务用户，不建议直接拿案例视频做自己的商业宣传。

## 未重新分发的模型权重

[BHE 官方模型说明](https://github.com/fly7632785/basketball-highlight-editor/blob/v0.1.12/models/README.md)明确要求分别确认权重、训练数据、推理框架和导出格式的授权；没有明确再分发许可时要求使用者自备模型。仓库中保留了这份[上游说明](third_party/bhe/models/UPSTREAM_MODEL_POLICY.md)。

因此没有转存以下权重，也没有把含权重的安装包当作本项目 Release 附件重新发布：

| 实测文件 | SHA256 | 状态 |
| --- | --- | --- |
| `bball_model.static.onnx` | `5d39b28ee312bd8ef90c04a07ccc16115693cfc42edb46f032932cf93c3b06de` | 本次 BHE 实测所用，未取得明确再分发许可，不打包 |
| `bball_model.pt` | `40f3e596652a427ba290b3f72384e49aed12caf1a8ae41beaef4a8fffcf09fa3` | 原运行时内存在，当前适配器实测使用上述 ONNX，未取得明确再分发许可，不打包 |

你可以复用自己有权使用的现有本地运行时，或通过 `--model` 指定有权使用且与 BHE 类别／接口兼容的模型。仓库没有静默下载权重的代码。模型文件缺失时会明确报错，不会伪造检测成功。

## 外部执行环境

Python、FFmpeg／FFprobe、Tesseract 和 Python 包是外部执行依赖，不是本仓库开发的组件。本仓库不镜像整套 1.3 GB Python 环境、系统库或不同平台的安装包。

已公开本次 BHE Python 环境中 **48 个分发包的名称和版本**、可找到的 **237 份许可／NOTICE 文件**及 Python 许可，另列出检测直接依赖和系统工具版本。这样可以看到实际用了什么，而不是只给一个无法核对的“安装依赖”提示。完整观察记录不是已验证的跨平台 pip 锁文件，也不声称对应版本在所有平台都可安装。

| 组件 | 本次观察版本 | 主要来源／许可信息 |
| --- | --- | --- |
| Python | BHE 3.11.16；基础脚本也在 3.13.12 上运行 | [Python](https://www.python.org/)，见所附许可 |
| NumPy | 2.4.6 | [NumPy](https://numpy.org/)，BSD 及所附第三方条款 |
| OpenCV Python | 5.0.0.93；运行时报告 5.0.0 | [opencv-python](https://github.com/opencv/opencv-python)，包元数据标记 Apache 2.0；实际二进制缺少 HOG |
| ONNX Runtime | 1.31.0 | [ONNX Runtime](https://github.com/microsoft/onnxruntime)，MIT |
| Ultralytics | 8.4.189 | [Ultralytics](https://github.com/ultralytics/ultralytics)，观察到的包为 AGPL-3.0；使用者需遵守其适用条款 |
| PyTorch / TorchVision | 2.14.1 / 0.29.1 | [PyTorch](https://github.com/pytorch/pytorch)、[TorchVision](https://github.com/pytorch/vision)，以所附各组件许可为准 |
| Pandas / psutil | 3.1.0 / 7.2.2 | [Pandas](https://github.com/pandas-dev/pandas)、[psutil](https://github.com/giampaolo/psutil) |
| FFmpeg / FFprobe | 8.0.1 | [FFmpeg 法律与许可说明](https://ffmpeg.org/legal.html)；本机构建启用了 GPL、libx264 等选项，不当作纯 LGPL 构建来再分发 |
| Tesseract | 5.5.1 | [Tesseract](https://github.com/tesseract-ocr/tesseract)，号码提示为可选功能 |

`requirements-runtime-observed.txt` 记录完整实测环境，`requirements-features-tested.txt` 记录服饰特征所需版本，`requirements-bhe-tested.txt` 记录直接检测依赖。它们不会自动安装。第三方 AGPL／GPL 依赖不会因为外层脚本 MIT 而失去原有义务；本项目不对重新打包这些二进制给出统一的许可结论。

## 公开导出处理

已去掉工具个人配置、Ultralytics UUID 和本机用户名路径。历史命令的机器路径用占位符保留，公开项目改用相对源路径。原测试的候选、媒体、人工选择与等待状态没有因此改变。原始 v1.0.0 Skill 单独存档，方便对照原测试哈希；新开源版的相对路径支持以 v1.0.1 发布。
