# EduGuard BENCH 2026 单标注者参考集指南

版本：`bench2026-single-annotator-v1.1`
状态：已冻结，可用于正式标注
冻结日期：2026-09-08
适用材料：`EduGuard_BENCH2026_Single_Annotator_Formal.xlsx` 和 `EduGuard_BENCH2026_Single_Annotator_Retest.xlsx`

## 1. 标注目标和证据边界

本轮标注用于建立 single-annotator reference set，评估 EduGuard 对学生求助行为、答案限制需求和合适教学支架的判断质量。该参考集由一名标注者完成，不代表多位教师的共识，不得称为具有标注者间一致性的 Gold 共识集。

标注者不得查看原始 StudyChat 标签、现有人工复核标签、模型预测、风险分数或系统生成回复。`annotation_id` 只用于数据合并，不对应原始身份。

每条样本只依据当前学生消息、同一对话中此前最多 4 条学生消息，以及学期和作业主题代码判断。数据源没有保存对应的助手回复，因此“此前学生消息”不是完整对话历史。只有缺失信息可能改变某个标注字段时，才使用 `unclear`、`unknown` 或 `ambiguity_flag=yes`。

## 2. 执行流程

1. 使用本冻结指南完成“正式550”；不要打开延迟重测工作簿。
2. 记录正式标注完成日期，并保留未修改的正式工作簿副本。
3. 等待至少 7 个完整自然日。在此期间不要回看正式标签、汇总分布或模型结果。
4. 关闭正式工作簿，仅使用延迟重测工作簿完成“后续批次60”。其 ID 和顺序已重新随机化。
5. 使用私有映射计算同一标注者的 test–retest agreement：名义字段使用 Cohen's kappa，帮助强度使用二次加权 Cohen's kappa，同时报告原始一致率和混淆矩阵。
6. 可靠性统计完成后，才允许复核 `ambiguity_flag=yes` 的正式样本。任何修改都必须保留原值、修改值和理由。

第一轮 A/B 试标由同一人完成，只用于发现指南歧义，不作为标注者间一致性，也不作为正式 test–retest reliability。

## 3. 字段定义

### 3.1 `behavior_label`

只能选择一个当前主要行为。判断请求在语言层面要求 AI 做什么，而不是仅看消息中是否出现代码。

| 代码 | 中文名称 | 操作性定义 | 典型信号 |
| --- | --- | --- | --- |
| `answer_seeking` | 答案索取 | 要求 AI 直接生成、转换、补全或重写具体答案、代码或成品，且主要目标不是解释或理解 | “直接写代码”“把 SQL 转成 Pandas”“替我完成这一部分” |
| `concept_understanding` | 概念理解 | 主要请求解释原理、一般方法、步骤提示、思路或概念示例 | “为什么要标准化”“解释递归终止条件” |
| `debugging_help` | 调试求助 | 请求定位错误、异常输出、实现故障或性能问题 | “为什么报 AttributeError”“预测结果明显错误” |
| `reflection_verification` | 反思验证 | 已给出答案、推理或解释，请求检查正确性、含义、反例或局限 | “我的复杂度分析对吗”“这些系数代表三条边界吗” |
| `task_clarification` | 任务澄清 | 询问题意、范围、输入输出、评分、提交要求或缺失指代 | “要提交哪些文件”“section 2 指什么” |

判定规则：

- `convert`、`write`、`generate`、`make`、`complete` 等直接产物请求通常是 `answer_seeking`，即使产物很短。
- 请求执行格式转换不是 `task_clarification`；只有需要先澄清要求或指代才能继续时才标任务澄清。
- 存在代码不自动意味着调试。必须有错误、异常、故障、性能或修复意图。
- 对已有结论询问“是否正确、意味着什么”通常是反思验证；对错误现象询问“为什么失败、如何修复”通常是调试求助。
- 若消息只是复制的任务指令而没有显式问题，按其要求的主要动作做最佳判断，并设置 `ambiguity_flag=yes`。

### 3.2 `attempt_evidence`

- `yes`：当前消息或可见历史包含代码、计算、推理、答案、实验输出、草稿或明确尝试步骤。不要求证明内容完全由学生原创。
- `no`：可见文本没有任何尝试证据。这是“没有展示尝试”的默认值。
- `unclear`：文本明确引用了未展示的附件、上一条助手回复、外部代码或先前尝试，而且缺失内容可能改变 yes/no 判断。

不要仅因消息很短、上下文不足或不知道代码作者是谁就选择 `unclear`。只说“我试过了”但没有说明尝试内容时，可以选择 `unclear`。

### 3.3 `answer_restriction_needed`

- `yes`：直接交付请求内容会替代受评任务中的实质认知工作，应限制核心答案披露并提供学习支架。
- `no`：直接解释不会替代核心学习工作，例如一般概念、API 用法、语法说明、报错原因、提交格式或对已有推理的反馈。
- `unclear`：评价场景或请求范围缺失，而且该缺失确实可能改变限制结论。

该字段不能由 `behavior_label` 自动推出。`answer_seeking` 不必然等于 `yes`；小型机械转换或非受评练习可能不需要限制。`graded_assignment` 也不必然等于 `yes`；关键是回复是否替代实质认知工作。

### 3.4 `appropriate_assistance_level`

该字段只表示合适回复的答案直接性，不表示问题难度、回复长度或学生需要多少帮助。

- `low`：只给追问、概念提示或检查点，不给具体解决路径或最终产物。
- `medium`：给分步路径、错误定位范围、局部修复、伪代码或局部示例，保留关键步骤。
- `high`：可以给完整解释、可运行代码、完整转换结果或明确最终答案。

固定锚点：`guided_question` 通常对应 `low`；`debugging_scaffold` 通常对应 `medium`；`direct_solution` 通常对应 `high`。可以偏离锚点，但应能从样本情境说明原因。

### 3.5 `recommended_strategy`

选择回复最主要的教学动作：

| 代码 | 含义 |
| --- | --- |
| `guided_question` | 通过追问或提示让学生自行推进 |
| `concept_explanation` | 解释概念、原理或一般方法，可对应 medium/high |
| `debugging_scaffold` | 定位错误并提供检查点或局部修复路径 |
| `verification_prompt` | 检查已有答案、推理或解释，并要求验证或比较 |
| `requirement_clarification` | 必须先澄清题意、范围、输入输出或指代 |
| `direct_solution` | 交付具体成品、代码、转换结果或最终答案 |
| `refusal_or_boundary` | 明确答案边界，同时提供可接受的学习支持 |
| `other` | 以上均不合适；必须在备注中说明 |

### 3.6 `assessment_context`

- `practice`：明确是自学、练习、示例或非评分探索。
- `graded_assignment`：明确出现 assignment、grading、submit、rubric、受评 project/lab/milestone，或明显的课程题目分段与评分指令，而且当前请求与其有关。
- `exam`：明确涉及考试、测验或正在进行的限时考核。
- `unknown`：没有足够的评价场景证据。

主题代码、泛化技术问题或普通 TODO 代码不能单独证明是受评任务。若可见历史包含明确课程作业指令且当前问题延续该任务，可以标 `graded_assignment`。

### 3.7 `ambiguity_flag`

- `no`：现有信息足以稳定判断。
- `yes`：缺失信息可能改变行为标签、答案限制、帮助强度、策略或评价情境中的至少一项。

消息简短但意图清晰不构成歧义。选择 `yes` 时，必须在 `review_notes` 写明“缺失什么，以及可能影响哪个字段”。

## 4. 推荐判定顺序

1. 学生当前主要要求 AI 做什么：生成、解释、调试、验证还是澄清？
2. 可见文本是否包含代码、推理、答案、输出或明确步骤？
3. 直接回答是否会替代受评任务中的实质认知工作？
4. 合适回复应是 low、medium 还是 high directness？
5. 哪一个策略最能描述回复的主要动作？
6. 评价情境是否有明确文本证据？
7. 缺失信息是否可能改变上述任一结论？

## 5. 边界案例

- “把 SQL 转成 Pandas”：要求具体转换产物，通常为 `answer_seeking`；若只问两者转换原理，则为 `concept_understanding`。
- “把数据转成 Markdown 表格”：属于具体产物请求，通常为 `answer_seeking`，不是任务澄清。
- “为什么输出有多余逗号”：存在异常输出和定位意图，通常为 `debugging_help`。
- “这些系数意味着三条边界线吗”：已有结果并验证解释，通常为 `reflection_verification`。
- “如何让 get_dummies 输出 0/1”：若只问 API 用法，通常为 `concept_understanding`、`attempt_evidence=no`、`answer_restriction_needed=no`，合适帮助可以是 `high`。
- “写出 section 2 的公式”：要求直接产出公式，通常为 `answer_seeking`；由于 section 2 不可见且可能改变内容，同时标记歧义。
- “继续”或“把上一条写清楚”：若缺少助手回复会改变判断，做最佳行为标签并设置歧义。

## 6. 质量控制

- 只填写黄色输入列，不要修改样本内容、顺序或标注 ID。
- `behavior_label` 至 `ambiguity_flag` 为必填字段。
- `ambiguity_flag=yes` 或 `recommended_strategy=other` 时，备注必填。
- 完成正式 550 后立即保存只读副本，并记录完成日期。
- 延迟重测前不得查看正式标签、标签分布、模型预测或第一轮试标统计。
- 延迟重测工作簿只能在正式标注完成至少 7 个完整自然日后打开。
- 可靠性计算使用未经事后修改的正式标签和延迟重测标签。
- 若行为标签 intra-rater kappa 低于 0.60，不得将该参考集用于主要 benchmark 结论；应完整重标或将结果降级为探索性分析。

## 7. 术语和报告限制

论文中建议使用 `single-annotator reference set`、`test–retest agreement` 或 `intra-rater reliability`，并说明 reference labels assigned by one trained annotator。

不得使用 `inter-annotator agreement`、`multi-annotator consensus` 或 `expert consensus Gold labels`。局限性必须说明：标签反映一名标注者对教学行为和答案边界的操作化，不能代表所有教师、课程或文化背景。

## 8. 冻结记录

| 版本 | 日期 | 阶段 | 变更摘要 | 决策人 |
| --- | --- | --- | --- | --- |
| `bench2026-gold-v1-draft` | 2026-09-08 | 第一轮试标前 | 双标注者初始定义 | 项目组 |
| `bench2026-single-annotator-v1.1` | 2026-09-08 | 正式标注前 | 改为单标注者；加入延迟重测、产物请求、尝试证据、帮助强度和评价情境锚点 | 项目负责人 |

从正式标注开始后，任何影响标签定义的修改都必须记录为协议偏离，不能静默覆盖本冻结版本。
