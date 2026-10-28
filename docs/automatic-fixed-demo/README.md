# 固定机位无号码自动识别 demo

[播放 53 秒演示](fixed-automatic-demo.mp4) · [完整案例](../AUTOMATIC_FIXED_CASE.zh-CN.md) · [字幕](demo.srt) · [配音](narration.m4a) · [渲染与来源记录](render-proof.json)

演示录制真实的本地结果回放页，绿框由实际程序输出决定。每次只用当前人物一张参考，切换人物会切换其独立运行结果。页面不做实时模型推理。中文配音为 macOS Tingting 合成，没有冒用用户声音；原片无音轨，没有补造球场原声。

原片 Alejons06，CC0。模型自动选片为 51–54、54–57 秒，共六秒，均远离 13.4 秒参考。高置信是服饰在场门槛，不是得分事实或人工准确率。片头显示参考，后段显示白衣重现；随后换成深蓝参考，白衣保持不确定。结尾展示实际自动导出和新旧数量对照。

## 制作文件

`production/` 保存口播稿、逐句配音 AIFF、时间表、字幕生成与合成脚本、实际浏览器录像、截图、拍摄检查记录和结果展示 HTML。不含模型权重、浏览器二进制、系统字体或运行时。Skill 和必要 Apache-2.0 架构源码在仓库中；模型只提供许可、来源、哈希和显式下载脚本。

重合成已有录屏：在仓库根目录将 `production/` 内容复制到被忽略的 `work/automatic-fixed-demo/`，创建 `outputs/basketball-automatic-fixed/`，安装可用的中文字体并放到工作目录 `fonts/`，然后运行：

```sh
python3 work/automatic-fixed-demo/assemble.py
```

脚本默认样式使用 macOS Heiti SC；其他系统请改为已合法安装的中文字体。不要将商业或系统字体重新分发。输出位于 `outputs/basketball-automatic-fixed/`。`REEL_PATH` 可指定其他位置的本案例实际草稿。

重新配音需要 macOS `say` 与 Tingting。重新录屏需要 Node、Playwright、Chromium；设置 `CASE_DIR` 为本仓库 `examples/fixed-camera-automatic` 绝对路径，`PLAYWRIGHT_MODULE` 和 `CHROME_EXECUTABLE` 指向已有依赖，执行 `capture.cjs`。使用 file URL，脚本验证跳转时间、目标切换、未知状态和页面错误，不依赖不支持 Range 的简单服务器。配音与浏览器依赖不由脚本自动下载。

FFmpeg 合成至 1920×1080、30 fps，字幕与实测逐句配音同步。最终完整解码通过，并检查白衣匹配、深蓝对照、导出草稿和结果表画面。所有素材许可与失败边界参见完整案例。
