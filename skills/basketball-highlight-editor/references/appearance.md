# 无号码球员的自动服饰匹配

先让用户选参考人物，再由程序比较各时间点的人形框。这里判断的是同一套服饰所支持的“目标在场”，不是脸部身份、持球者或得分者。

## 使用

使用已有的 OpenCV、NumPy、ONNX Runtime、FFmpeg 环境。首次提取纹理另需已有 PyTorch；当前实测为 CPU PyTorch 2.14.1。后续可以用归档特征重放，不需要 PyTorch 或模型权重。

```sh
python3 scripts/highlight.py people PROJECT --stream --fps 5 --tile 320
python3 scripts/highlight.py sample PROJECT --player target --time SECONDS \
  --bbox X1 Y1 X2 Y2 --description '上衣、裤子和鞋袜' \
  --reviewer-kind user --confirmed-by '实际用户选择的来源'
python3 scripts/highlight.py match-people PROJECT --player target --role visible \
  --appearance-model /path/to/authorized/dinov2_vits14_pretrain.pth --apply
python3 scripts/highlight.py select PROJECT --player target --role visible --selected-by '实际选人来源'
python3 scripts/highlight.py rough PROJECT
```

这些路径相对于 Skill 目录。测试选择必须使用 `test_operator`；不能把示例命令中的“实际用户选择”填成没有发生过的确认。

`people --stream` 在一次解码中按视频呈现时间采样，VFR、旋转和非零视频时间原点已有回归检查；原来逐次解码的入口仍可用。ROI 必须来自当前原片，示例中的参考框和时间不属于算法配置。

若明确获准下载模型，可单独运行：

```sh
python3 scripts/fetch_appearance_model.py \
  --output assets/dinov2/dinov2_vits14_pretrain.pth
```

只下载 Meta 官方经典 DINOv2 ViT-S/14 LVD142M，验证固定 SHA256。代码及该模型为 Apache-2.0；不使用许可不同的 Cell-DINO 或 XRay-DINO。权重不进 Git。许可和原始源码位于 `assets/dinov2/`，源文件哈希位于 `assets/dinov2/provenance.json`。该目录含完整推理所需的上游架构子集，因此复制整个 Skill 时不会依赖仓库外的 Python 源文件。

若上述默认路径已经有合法且通过哈希校验的权重，`match-people` 自动选择纹理后端；命令不会自动下载或安装。`--clothing-only` 明确重放旧颜色策略。未准备模型时，旧入口仍可用，但不要将其不确定输出描述成已经自动识别成功。跨环境复现时显式传入模型或归档特征路径。

## 算法输出是什么

- 人形框顶部 22% 不进入纹理裁图，随后提取整体、上半服饰和下半服饰的 DINOv2 特征。它是通用视觉模型，不是训练过的篮球身份模型；不用号码 OCR 或人脸识别。
- 同时检查服饰颜色、裁图质量、局部纹理差异、其他参考人物和同画面其他人的实际间隔。颜色相同并不自动算作同一个人。
- 每个高置信在场区间需要同一短轨迹至少四个合格观测、跨度至少 0.8 秒。遮挡和歧义帧不获传播的身份；轨迹中发生身份冲突会切断区间。
- 一个候选内存在合格区间，才能标为高置信在场。`supported_time_ranges` 给出具体时间；不宣称整段所有画面都完成识别。与该区间无关的其他不确定画面不抹除已存在的在场证据。
- `scorer` 与 `handler` 一律仍需独立回合证据。另一人的出现、无匹配或离开画面都不会自动把目标事件删除。
- 距离和间隔是工程门槛，不是校准后的身份概率。自动扩充参考仍是独立草稿，不进入人工参考集。

查看 `people/matches.json` 的 `policy_version`、逐帧证据与 `segments`，以及 `people/candidate-proposals.json` 中的时间区间。需要看原帧和粗剪后再确认。

## 缓存与无权重重放

特征按视频 SHA256、人形框与时间、模型 SHA256 和预处理版本缓存。修改参考图不需要重算整段录像的人形纹理，但会重算匹配。源、框、模型或特征文件哈希不一致时不会复用旧结果。

```sh
python3 scripts/highlight.py match-people PROJECT --player target --role visible \
  --appearance-bundle /path/to/appearance-bundle.json --apply
```

Bundle 含归档的服饰向量和参考向量，不含模型权重或人工真值。读取时核对源、参考选择、观测框／时间及两个向量文件的哈希。它重算当前算法的分组，不是把已保存的高置信编号直接塞回项目。

## 当前验证范围

固定机位校园公开视频中的参考只取前 15 秒。后段重新出现的白衣球员由程序给出支持区间；主演示导出时排除参考附近窗口。四位人物均报告结果，无法通过门槛的仍是不确定。具体自动窗口、失败项、模型与输入哈希见开源仓库的新固定机位案例。它不是整场比赛准确率承诺；没有把程序输出或操作员看图记录变成 confirmed 评测标注。
