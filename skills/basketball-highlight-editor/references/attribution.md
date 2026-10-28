# 归属范围与置信度

`match-people --role scorer` 默认检查得分者归属。衣服、鞋子和短轨迹只能支持“人在场”，所以 scorer、handler 自动保持不确定。`--role visible` 才允许合格的在场证据进入高置信。`select` 沿用最近应用的角色，可用 `--role` 明确指定；旧的纯手工项目默认 visible，HTML 和 CSV 显示范围。保留片段的确认不会自动确认得分者。

高置信不是概率。它要求清晰、大小足够、未被边缘截断的参考及检测框，上衣／下装等区域分别一致，在真实同场人物或其他已保存球员样本中有区分证据，并且同一条短轨迹至少有三个时间点、跨越 0.5 秒、间隔不超过 0.71 秒。发现相似人物、参考冲突或某区域矛盾时降级。没有比较对象时，margin 是未知 `null`，不会写成 1。工程阈值尚未经过充分人工数据校准。

`people/matches.json` 的安全结果在 `records`，每个匹配附 `confidence_evidence` 和原因。旧算法的未经验证提议留在 `raw_hypotheses` 及带 legacy_ 前缀的审计字段，其 margin/anchor 不能用作概率或高置信依据；轨迹摘要的 margin 保持 null，明确标为未验证身份。旧扫描缺少质量字段时保守降级，请重新运行 `people`。候选的 `presence_certainty`、`role_certainty` 和 `reason_codes` 分开保存。

同一人物建议保存 1–3 张清晰的人工参考。每个服饰组最多融合三个不同样本；反复复制同一时间和框不增加证据。更换衣服后，另加参考，指定 `sample --appearance new-outfit --valid-from S --valid-until E`。时间区间只表示该服饰适用范围；自动程序不会确认换衣服前后是同一个人。未确认的空档保留不确定。没有人脸、体型身份或肤色分类模型；框几何只检查是否残缺／合并。服饰分区可能混入皮肤或背景，不能据此声称光膀子场景可靠。

`people/reference-proposals.json` 是自动扩充建议，始终为 draft、local_model、requires_user_review，不写入项目 samples，也不提升高置信。用户必须看过原图并明确选中之后，才能通过正常 sample 流程保存；无人值守测试只记录 test_operator。

手工 `annotate` 的高置信仍须原来的号码或保存参考图证据。若要确认事件角色，额外记录：

```json
{
  "verified_roles": ["scorer"],
  "role_evidence": {
    "role": "scorer",
    "detail": "实际看过的回合证据和时间点",
    "authorization_reference": "真实复核记录的位置"
  }
}
```

reviewer 必须是实际 user 或明确的 test_operator，模型和 agent_visual_review 不得写 verified_roles。上述示例不是确认记录。

没有认出目标、认出了其他人或旧的笼统 `other` 标签，都进入不确定组，不能静默删除目标事件。只有人工明确核验目标不在该候选中，记录 `certainty: other`、`absence_verified: true`、`exclusion_for: 目标ID` 及 reviewer，才进入 other。确认选片后仍按原流程停在 awaiting_edit_prompt。
