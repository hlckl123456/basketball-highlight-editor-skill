# 无号码公园夜场使用演示

[播放／下载操作演示](unnumbered-workflow.mp4) · [先看 36 秒实际成片](../../examples/park-unnumbered/project/versions/unnumbered-chronological/reel.mp4) · [完整案例](../PARK_UNNUMBERED_CASE.zh-CN.md) · [口播稿](口播稿.md) · [字幕](demo.srt)

操作演示约 1 分 14 秒，1920×1080、30 fps、H.264/AAC，中文 AI 旁白来自本机 macOS Tingting。原始篮球画面是官方 480p 转码，放进 1080p 演示不会增加原始细节。原片由 Cocoa PD 制作，Commons 标为美国公有领域 PD Florida；[来源和精确 SHA256](../../examples/park-unnumbered/source/rights.json)随案例保存。保留发布者已有水印。

这次用全新公园素材重做，没有复用 Indiana 的候选或成片。选的是白 T 恤、深红色短裤、白袜白鞋的球员，没有用号码或人脸识别。自动匹配结果为高置信 0 段、不确定 8 段；逐段对照参考后，测试操作员保留五段、删除三段。视频明确展示这个结果，不充当自动识别准确率评测。

## 画面来自哪里

- 开头、参考与结果场景是演示说明画面，直接播放本次原片、实际参考裁图和真实导出 MP4。
- 复核与填表场景录制真实 `project/review-before-confirm.html`。录屏中增大字体、增加底部留白，并覆盖 `test_operator` 标记；没有伪造产品按钮或识别结果。
- 表单只演示填写，没有点击下载或以 `user` 提交。实际决定由 CLI 按 `test_operator` 保存；[录屏记录](capture-proof.json)及[表单重录记录](capture-proof-decide.json)保留八条实际值。
- 结果场景展示成片开头的一部分，完整五回合请看单独的 36 秒成片。
- 配音、字幕、片头说明由本次制作；没有模仿任务用户的声音。

## 可重做的制作素材

[production/](production/) 保存演示 HTML、录屏与合成脚本、口播分句和实测时间、每句 AIFF 旁白、五段原始浏览器录屏及截图。系统字体、Chrome、FFmpeg、Python 环境和模型权重不打包。已录好的画面与旁白足够重新合成本次演示，无需重新访问网页或调用 TTS。

以下是在 macOS、仓库根目录执行的重合成示例。需要已有 Python 3、FFmpeg（含 libass）和本机 Heiti SC 字体；字体只在本机使用，不再分发：

```sh
mkdir -p work/unnumbered-demo/fonts outputs/basketball-unnumbered-demo
cp -R docs/unnumbered-demo/production/. work/unnumbered-demo/
ln -s ../../examples/park-unnumbered work/unnumbered-demo/case
cp '/System/Library/Fonts/STHeiti Medium.ttc' work/unnumbered-demo/fonts/
python3 work/unnumbered-demo/assemble.py
```

其他系统需要用本机可用的中文字体替换合成脚本中的 `Heiti SC`。重录浏览器画面还需要已有 Playwright 与 Chrome：设置 `PLAYWRIGHT_MODULE` 为 Playwright 模块位置、`CHROME_EXECUTABLE` 为已有浏览器可执行文件。先运行 `python3 -m http.server 8768 --bind 127.0.0.1 --directory work/unnumbered-demo`，然后在另一个终端运行 `node work/unnumbered-demo/capture.cjs`。脚本使用隔离无登录浏览器，不连接外部服务。可用 `DEMO_ONLY=decide` 单独重录填表场景。

## 核验

[ui-check.json](ui-check.json) 记录八段 MP4 实际加载并推进播放、零页面脚本错误。[render-proof.json](render-proof.json) 记录每段录屏修剪与渲染时长。另做整片解码、五个场景截图检查和音频峰值检查。项目重放、新案例脚本、原 Skill 单元测试及原 Indiana 重放结果见[交付核验记录](validation.json)。

正文写法沿用用户已有的 Kailai 口播习惯，封面用本次真实参考图排版。没有使用生成的人物照片，也没有把录屏注解说成产品自带界面。
