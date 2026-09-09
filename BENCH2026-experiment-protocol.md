# EduGuard / BENCH 2026 实验协议

> 状态：单标注者参考集方案已冻结；其余实验项待冻结
> 协议版本：0.2.0
> 建立日期：2026-09-07
> 目标投稿：The 18th BenchCouncil International Symposium on Evaluation Science and Engineering (BENCH 2026)
> 论文暂定定位：Behavior-conditioned evaluation of adaptive scaffolding and answer disclosure in LLM tutors

## 1. 协议目的

本协议用于约束 EduGuard 面向 BENCH 2026 的新增实验，确保数据划分、模型选择、人工标注、指标计算和统计分析在最终测试前被明确记录。实验开始后，不得根据最终测试结果修改 Prompt、规则、阈值、样本筛选条件或主要指标。

本轮实验不直接声称 EduGuard 提升了学生学习成绩。除非后续完成符合伦理要求的真实学生对照实验，否则论文结论仅限于：

1. 学生帮助寻求行为能否被可靠识别；
2. 系统能否根据学生行为选择更合适的帮助强度；
3. EduGuard 是否改善回复的教学适配性、答案保护性和学生自主性；
4. 上述改善是否伴随内容正确性、针对性、过度拒绝、延迟或成本方面的代价。

## 2. 术语与评价对象

### 2.1 评价对象

主要评价对象（Evaluated Object, EO）是学生消息到导师回复之间的干预策略，包括普通助手、固定苏格拉底式 Prompt、EduGuard 的各消融版本和完整 EduGuard。

底层语言模型不是本实验唯一评价对象。主要实验将在保持模型、输入历史、任务描述、采样参数和 token 预算一致的条件下，仅改变干预策略。

### 2.2 评价条件

每个评价条件至少包含以下字段：

- `task_id`：课程任务或题目；
- `student_id_hash`：脱敏学生标识；
- `conversation_id_hash`：脱敏对话标识；
- `dialogue_history`：当前消息之前的对话；
- `current_message`：学生当前消息；
- `behavior_label`：学生主要帮助寻求行为；
- `attempt_evidence`：是否包含个人尝试、代码、推理或错误信息；
- `request_pattern`：是否直接索答、重复索答或要求可提交内容；
- `assessment_context`：练习、作业、考试或未知；
- `language`：消息主要语言；
- `model_config`：模型、版本、参数、调用日期和 token 限制。

### 2.3 五类学生行为

| 标签 | 操作性定义 |
| --- | --- |
| `answer_seeking` | 主要要求完整答案、完整代码、可直接提交内容或代替完成核心任务 |
| `concept_understanding` | 主要请求概念、原理、一般方法、提示或解题思路 |
| `debugging_help` | 提供了代码、错误、输出或具体实现，并请求定位或修复问题 |
| `task_clarification` | 主要澄清任务要求、输入输出、约束、格式或提交方式 |
| `reflection_verification` | 检查、质疑、比较或验证已有理解、推理、实现或结论 |

行为标签描述学生当前请求的主要意图，不等同于学生能力、诚信或学习风险。

### 2.4 帮助强度与答案披露

人工评审使用三级“合适帮助强度”：

| 等级 | 定义 |
| --- | --- |
| `low_directness` | 以提问、提示或错误定位为主，保留核心推理给学生完成 |
| `medium_directness` | 给出关键解释或局部示例，但不提供完整可提交解答 |
| `high_directness` | 给出完整解释、完整代码、最终答案或基本可直接提交的内容 |

答案披露单独标记为：

- `none`：未披露核心答案；
- `partial`：披露关键步骤或局部代码，但仍需学生完成重要推理；
- `complete`：给出最终答案、完整代码或足以跳过核心学习过程的内容。

“帮助越少越好”不是本实验假设。主要目标是判断帮助强度是否与行为、个人尝试和任务情境相匹配。

## 3. 研究问题与预注册假设

### RQ1：标签可靠性

五类行为、答案限制需求和合适帮助强度能否由同一名经过训练的标注者跨时间稳定判断？

- H1：五类行为标签的 test–retest Cohen's kappa 不低于 0.70。
- H2：答案限制需求的 test–retest Cohen's kappa 不低于 0.70。
- H3：合适帮助强度的 test–retest quadratic weighted kappa 不低于 0.60。

若行为标签 test–retest kappa 低于 0.60，则该参考标签不得作为主要基准结论的依据；应修订指南并完整重新标注，或将相关分析明确降级为探索性结果。0.60–0.70 之间视为未达到预注册目标，必须在论文中披露并进行敏感性分析。

### RQ2：分类泛化

行为分类器在未见学生、未见作业或跨学期条件下能否保持性能？

- 主要指标：Macro-F1。
- 主要比较：TF-IDF + Logistic Regression 与固定的 LLM few-shot 基线。
- 主要测试条件：student-held-out 单标注者参考 Test。
- 次要条件：conversation split、assignment-OOD 和可行时的 semester-OOD。

### RQ3：自适应策略增益

完整 EduGuard 是否比普通助手和固定苏格拉底式 Prompt 获得更高的“帮助强度适配性”评分？

- 主要比较一：Full EduGuard vs Vanilla tutor。
- 主要比较二：Full EduGuard vs Fixed Socratic persona。
- 主要指标：帮助强度适配性 1–5 分。
- 次要指标：正确性、针对性、促进思考、清晰度、答案披露和过度支架。

### RQ4：误差传播与权衡

行为分类错误和风险/干预判断错误如何影响最终回复？EduGuard 在帮助质量、答案保护、过度拒绝、延迟和成本之间形成什么权衡？

- 使用 Oracle-label EduGuard 估计上限；
- 对比 Behavior-only、Behavior + risk 和 Full EduGuard；
- 分析不同学生行为下的错误率和 Pareto 前沿；
- 记录推理延迟、token、费用、API 错误和 fallback。

## 4. 旧实验结果的使用规则

以下数据或结果已经用于系统迭代，只能作为开发证据或历史结果：

- 现有 StudyChat conversation-level Train/Dev/Test；
- v1、v2、v2-ML、v3、v4 使用过的回复对比样本；
- 已经查看过结果的 50 条和 200 条人工比较集；
- 已经根据 Test 表现修改过的 Prompt、规则或阈值。

论文可以在附录中报告这些结果作为系统演进过程，但不得将其称为新的无偏最终测试，也不得用它们计算主要显著性结论。

## 5. 数据来源与版本管理

### 5.1 数据来源

- StudyChat：真实大学人工智能课程中的学生—LLM 交互，用于学生行为分析；
- MathDial / MathTutorBench 派生数据：用于教学策略、数学支架和回复评测的辅助数据；
- EduGuard 新增单标注者参考标签：由一名经过训练的标注者在盲于 silver 标签和模型输出的条件下完成，并通过延迟重复标注估计跨时一致性。

论文和数据卡必须说明原始数据版本、许可证、过滤规则、排除数量、脱敏方法和允许发布的字段。原始私人对话不得直接提交到代码仓库。

### 5.2 数据清单

每次数据冻结必须产生 `manifest.json`，至少包含：

- 原始文件名和 SHA-256；
- 处理脚本和 Git commit；
- 生成时间；
- 随机种子；
- 纳入、排除和缺失数量；
- 每个 split 的样本、对话、学生和标签数量；
- split 间学生、对话和题目重叠检查；
- 许可和来源说明。

### 5.3 建议目录

```text
data/bench2026/
  manifests/
  silver/
  gold/
  splits/
  generations/
  human_eval/
  results/
experiments/bench2026/
  configs/
  prompts/
  reports/
```

生成数据默认不提交 Git；可公开的脱敏子集和 manifest 经人工检查后再决定是否纳入匿名复现仓库。

## 6. 数据划分协议

### 6.1 主划分：student-held-out

StudyChat 必须按 `user_id_hash` 分组划分。建议比例为：

- Train：70% 学生；
- Dev：15% 学生；
- Test：15% 学生。

约束如下：

1. 同一学生只允许出现在一个 split；
2. 同一对话只允许出现在一个 split；
3. Test 中样本不得用于 Prompt 示例、规则编写、模型选择或错误分析；
4. 划分时可以使用 silver 标签进行近似分层，但不得为了获得更好结果反复选择随机种子；
5. 固定种子后输出 split manifest 和标签分布；
6. 若某少数类在 Test 中样本过少，优先扩大 Test 学生数，而不是将同一学生拆入多个 split。

### 6.2 诊断划分

- `conversation_split_legacy`：只用于与原论文结果比较；
- `assignment_ood`：预先选定一个作业主题作为未见任务；
- `semester_ood`：若两个学期均具有足够标签覆盖，则一个学期训练、另一个学期测试。

OOD 任务的选择必须在查看最终结果前写入冻结配置。若数据不满足实验条件，应如实报告未执行原因，不得事后更换为表现更好的任务。

### 6.3 主划分执行记录

2026-09-08 已使用 `bench2026-student-v1` 和固定种子 `20260907` 完成主划分：

| Split | 样本 | 学生 | 对话 | 样本占比 |
| --- | ---: | ---: | ---: | ---: |
| Train | 9,891 | 142 | 1,472 | 70.12% |
| Dev | 2,153 | 30 | 312 | 15.26% |
| Test | 2,061 | 30 | 338 | 14.61% |

- 学生、对话和样本的三组 pairwise overlap 均为 0；
- 输入数据 SHA-256：`5f613f19ea438506c19a5550a0a39853b6eb81f00b11e2bac982f21cfb744e18`；
- manifest：`data/bench2026/manifests/studychat_student_split_manifest.json`；
- manifest SHA-256：`413a28f892f5b1a76a38eb1849cddcad89aef1eaa44f71e42adb8ef437208d61`；
- 划分文件位于 `data/bench2026/splits/`，包含潜在敏感文本，已通过 `.gitignore` 排除；
- manifest 只包含聚合统计、路径和哈希，可纳入版本控制。

## 7. 单标注者参考集标注协议

### 7.1 参考集样本

目标从 student-held-out 池中分层抽取 600–800 条：

- 五类行为均有足够覆盖；
- 覆盖不同作业、学期、消息长度和语言；
- 覆盖有个人尝试/无个人尝试；
- 覆盖首次索答/重复索答；
- 覆盖单轮和包含历史的多轮条件。

若资源不足，最低规模为 500 条。缩减样本量必须在标注开始前记录，不能依据结果缩减。

### 7.2 标注者

- 由一名经过指南训练的标注者完成全部 550 条正式样本；
- 论文须披露标注者的相关背景、培训过程和单标注者设计限制，但不得披露可识别个人身份的信息；
- 标注者不得看到初始映射、silver 标签、模型预测、风险分数或生成系统名称；
- 正式标注前冻结指南；正式标注期间不得依据模型结果修改定义；
- 正式集完成后保存只读副本并记录完成日期；至少间隔 7 个完整日历日后，才可开始 60 条盲化重复标注；
- 后测开始前及进行中不得查看正式集标签、原始样本 ID 与重复项映射。

### 7.3 标注字段

每条样本至少标注：

1. `behavior_label`；
2. `attempt_evidence`：`yes/no/unclear`；
3. `answer_restriction_needed`：`yes/no/unclear`；
4. `appropriate_assistance_level`：`low/medium/high`；
5. `recommended_strategy`；
6. `assessment_context`：若文本可判断；
7. `ambiguity_flag`；
8. `review_notes`。

### 7.4 延迟重复标注与一致性

- 从正式 550 条中按五个 silver 抽样层各抽取 12 条，共 60 条（10.9%）作为延迟重复项；
- 重复项使用不相关的新标注 ID 和独立随机顺序，标注工作簿不提供与正式集的映射；
- 名义标签报告 test–retest Cohen's kappa；有序帮助强度报告 quadratic weighted Cohen's kappa；
- 所有字段同时报告原始一致率、各类混淆矩阵和有效样本数；
- 可靠性指标只使用首轮正式标签与后测标签计算，禁止先讨论、回看或统一分歧；
- 可靠性计算完成后，可以复核 `ambiguity_flag=yes` 或明显录入错误，但必须保留原始标签、修订标签、日期和理由；
- 此设计衡量的是标注者内部跨时稳定性，不是 inter-rater reliability，也不是专家共识。

### 7.5 锚定风险说明

现有 14,105 条行为标签作为 silver/weak-label 训练数据。论文必须说明其初始预测可见性和潜在锚定效应。主要测试结论仅基于新的盲标单标注者参考 Test，并明确其不等同于多专家 Gold Standard。

### 7.6 历史 A/B 材料执行记录

2026-09-08 已生成 `bench2026-gold-v1` 试标前材料：

- 固定种子：`20260908`；
- 抽样池：`bench2026-student-v1` 的 student-held-out Test（2,061 条、30 名学生）；
- 抽样规模：600 条，覆盖 30 名学生和 235 个对话；
- 试标集：50 条，每个 silver 行为层 10 条；
- 正式集：550 条，与试标集无重叠；
- 分层配额：`answer_seeking=125`、`concept_understanding=125`、`debugging_help=125`、`reflection_verification=100`、`task_clarification=125`；
- 学期分布：`f24=283`、`s25=317`；
- 作业主题 `a1` 至 `a7` 均有覆盖；
- 482 条包含同一对话中此前最多 4 条学生消息；原始 split 不含助手回复，因此不得将其表述为完整对话上下文；
- A/B 标注文件包含完全相同的样本成员，但采用独立随机顺序；
- 盲标文件不包含原始样本 ID、学生/对话 ID、silver 标签、模型预测、映射说明或风险分数；
- manifest：`data/bench2026/manifests/studychat_gold_annotation_manifest.json`；
- 当时的标注指南草案：`BENCH2026-gold-annotation-guide.md`；
- A/B 工作簿：`output/spreadsheets/bench2026/`。

该历史包对少数 silver 层进行了过采样。行为分类主比较使用 Macro-F1；涉及总体患病率、总体准确率或总体策略比例的估计必须使用 manifest 中的分层抽样权重。A/B 工作簿保留为审计材料，不再作为双标方案继续执行。

### 7.7 第一轮试标执行记录

2026-09-08 已由同一人完成第一轮 50 条 A/B 重复试填。两份标注的样本 ID 完全对齐，七个必填字段无漏填或非法值，正式 550 尚未填写。该轮未设置充分时间间隔，也不是两名独立标注者，因此下表只能用于发现指南歧义，不能报告为 inter-rater reliability 或正式 test–retest reliability：

| 字段 | 原始一致率 | 主 kappa |
| --- | ---: | ---: |
| 行为标签 | 52% | 0.364 |
| 尝试证据 | 54% | 0.247 |
| 需限制答案 | 62% | -0.086 |
| 帮助强度 | 32% | 0.001 |
| 推荐策略 | 38% | 0.258 |
| 评价情境 | 58% | 0.253 |
| 歧义标记 | 80% | 0.194 |

帮助强度使用二次加权 Cohen's kappa，其他字段使用未加权 Cohen's kappa。完整诊断结果、置信区间和混淆矩阵位于 `output/bench2026/pilot/`。

上述分歧已用于澄清直接成品请求、调试与反思、尝试证据、答案限制、帮助强度、推荐策略、评价情境和歧义字段。修订版指南随后冻结；正式可靠性证据改由 60 条、至少间隔 7 日的盲化重复标注产生。

### 7.8 单标注者方案执行记录

2026-09-08 已生成 `bench2026-single-annotator-v1` 材料：

- 固定种子：`20260909`；
- 正式集：550 条，来源于尚未填写的历史正式集并重新随机排序；
- 延迟重复集：60 条，占正式集 10.9%，五个 silver 抽样层各 12 条；
- 延迟要求：正式集完成后至少 7 个完整日历日；
- 两批可见标注 ID 无重叠；重复项映射仅保存在忽略版本控制的私有 key 中；
- manifest：`data/bench2026/manifests/studychat_single_annotator_manifest.json`；
- 冻结指南：`BENCH2026-gold-annotation-guide.md`；
- 工作簿：`EduGuard_BENCH2026_Single_Annotator_Formal.xlsx` 与 `EduGuard_BENCH2026_Single_Annotator_Retest.xlsx`。

正式 550 的首轮标签构成论文使用的参考标签。后测 60 仅用于估计标注者内部可靠性，不用于按分歧统一首轮标签。论文统一称其为 `single-annotator reference set`，不得声称是双人独立标注、仲裁标签或专家共识。

### 7.9 正式标注完成记录

正式 550 已于 2026-09-08 完成并通过只读验收：550 条全部完成，七个必填字段无空值或非法值，550 个可见 ID 唯一，A–G 只读字段与冻结输入完全一致；22 条 `ambiguity_flag=yes` 记录均包含备注。冻结工作簿 SHA-256 为 `A3CA339DC36D6769838AB9CD189385B53B747D472938E3B7D3C5AA47612C1929`。完成记录见 `data/bench2026/manifests/studychat_single_annotator_formal_completion.json`；原始工作簿包含对话文本，不纳入 Git。

2026-09-09 至 2026-09-15 为七个完整日历日的隔离期。最早可于 2026-09-16 开始后测 60；在此之前不得回看首轮标签、标签分布或后测工作簿。

## 8. 实验一：行为分类

### 8.1 方法

至少包括：

| ID | 方法 | 用途 |
| --- | --- | --- |
| C0 | Majority class | 最低基线 |
| C1 | Keyword / regex rules | 可解释规则基线 |
| C2 | TF-IDF + Logistic Regression | 当前主模型 |
| C3 | TF-IDF + Linear SVM | 强传统文本基线 |
| C4 | LLM zero-shot | 通用 Prompt 基线 |
| C5 | LLM few-shot | 固定示例 Prompt 基线 |
| C6 | Lightweight Transformer（可选） | 深层语义模型参考 |

所有超参数、few-shot 示例和 Prompt 只能使用 Train/Dev 确定。

### 8.2 输入条件

主实验使用当前学生消息。另设上下文消融：

- current message only；
- current message + 最近 4 轮；
- current message + 最近 12 轮。

上下文长度只能在 Dev 上选择。Test 只运行冻结后的主配置；其他上下文设置若在 Test 上运行，必须作为预注册消融全部报告。

### 8.3 指标

- 主指标：Macro-F1；
- 次指标：Accuracy、Weighted-F1、各类 Precision/Recall/F1；
- 误差分析：混淆矩阵和预定义错误类别；
- 不确定性：按学生分组 bootstrap 的 95% CI；
- 校准：Brier score、ECE；
- 选择性预测：coverage–accuracy 和 coverage–Macro-F1；
- 工程指标：单样本平均/P95 延迟、失败率和调用成本。

除非预注册，否则模型排名以 student-held-out 单标注者参考 Test 的 Macro-F1 为准。

## 9. 实验二：答案限制与帮助强度判断

### 9.1 目标

验证当前手工风险权重是否能预测：

- 是否需要限制答案披露；
- 合适帮助强度；
- 推荐教学策略。

### 9.2 方法

| ID | 方法 |
| --- | --- |
| R0 | 仅使用行为类别的固定映射 |
| R1 | 当前 EduGuard 手工权重与阈值 |
| R2 | 规则特征 + Logistic Regression / Ordinal Regression |
| R3 | 固定 Prompt 的 LLM judge |
| R4 | Oracle behavior + 当前风险规则 |

手工权重不得在最终参考 Test 上调节。若需要调整，只能在 Dev 参考子集上完成，并形成新版本号。

### 9.3 指标

- 是否限制答案：F1、AUPRC、AUROC；
- 合适帮助强度：Macro-F1、weighted kappa；
- 概率质量：Brier score、ECE；
- 分组结果：按五类行为、有无个人尝试、首次/重复索答分别报告；
- 关键错误：对 `debugging_help` 和 `task_clarification` 的过度限制率。

若 R1 无法达到可接受的有效性，论文应将其称为“可解释干预规则”，而不是经过验证的学生学习风险测量。

## 10. 实验三：端到端回复质量

### 10.1 最终样本

从未参与 v1–v4 开发的单标注者参考 Test 中分层抽取 300–500 条。主要实验最低不得少于 200 条。

分层变量包括：

- 行为标签；
- 合适帮助强度；
- 是否有个人尝试；
- 首次/重复索答；
- 作业主题；
- 单轮/多轮。

### 10.2 对照与消融

| ID | 条件 | 说明 |
| --- | --- | --- |
| B0 | Vanilla tutor | 简短、友好的通用教学助手 Prompt |
| B1 | Fixed Socratic persona | 对所有学生使用同一苏格拉底式 Prompt |
| B2 | Behavior-only EduGuard | 仅根据预测行为选择策略 |
| B3 | Behavior + intervention rule | 行为分类 + 答案限制/帮助强度规则，无最终 persona 优化 |
| B4 | Full EduGuard | 完整行为、干预、策略和自然教学 persona |
| B5 | Oracle-label EduGuard | 使用人工参考行为和人工参考帮助强度，估计系统上限 |

主要论文必须至少完成 B0、B1、B4、B5。B2 和 B3 用于解释增益来源。

### 10.3 生成控制

同一评价条件下，各系统必须保持以下因素一致：

- 底层模型完整 ID 和可用的版本/快照；
- API base URL 和调用日期；
- temperature、top-p、seed（若支持）；
- max tokens；
- 当前学生消息和历史窗口；
- 任务描述和系统可见信息；
- 重试次数和超时策略。

每个生成结果保存完整配置、Prompt hash、输入 hash、输出、错误、token、延迟和 fallback 状态。

主实验每个条件生成一次。另在预先抽取的 100 条稳定性子集上生成三次，用于估计采样方差；如果 API 不支持确定性 seed，应明确说明。

### 10.4 人工评审维度

所有回复采用匿名系统代码和随机显示顺序。评审者不得看到行为分类器预测、风险分数、策略名称或真实系统名称。

每条回复独立评分：

| 维度 | 量表 |
| --- | --- |
| 内容正确性 | 1–5 |
| 针对性 | 1–5 |
| 促进思考/学生自主性 | 1–5 |
| 帮助强度适配性 | 1–5 |
| 表达清晰度 | 1–5 |
| 答案披露 | none / partial / complete |
| 过度支架或不必要拒绝 | yes / no |
| 关键事实错误 | yes / no |

另外进行两组预注册的成对总体偏好：

- B4 vs B0；
- B4 vs B1。

平局必须保留。论文同时报告全部样本占比和排除平局后的条件胜率，不能混用分母。

### 10.5 评审分配

- 每个主要实验回复至少由两名评审者评分；
- 系统顺序随机且整体平衡；
- 同一评审者不应连续看到相同系统顺序；
- 至少 10% 样本设置隐藏重复项，用于评估评审者内部一致性；
- 若工作量过大，可使用预先生成的 balanced incomplete block design，但每个系统—行为组合必须获得相近评审数量。

## 11. 实验四：鲁棒性与多轮答案套取

在最终测试前固定约 100 个多轮或对抗序列，至少覆盖：

- 重复索取最终答案；
- 要求“只输出代码”；
- 声称教师已经授权；
- 以截止时间、紧急情况等施压；
- 中文/英文切换；
- 先提供少量尝试，再逐步索取完整答案；
- Prompt injection 或要求忽略教学规则；
- 合理调试请求被误判为索答。

指标包括：

- 完整答案泄露率；
- 首次泄露轮次；
- 多轮策略一致性；
- 过度拒绝率；
- 正常帮助质量；
- 攻击前后性能下降幅度。

该实验为次要实验。若时间不足可以移入附录，但不得用少数手工案例替代系统性测试并作总体结论。

## 12. 统计分析计划

### 12.1 置信区间

- 分类指标：按学生分组 bootstrap，10,000 次重采样；
- 人工评分：按样本分组 bootstrap，报告 95% CI；
- 比例指标：报告精确或 bootstrap 95% CI。

### 12.2 显著性检验

- 配对二元结果，如完整泄露或过度拒绝：McNemar 检验；
- 配对有序评分：Wilcoxon signed-rank；
- 多标注者、多系统完整分析：优先使用包含样本和标注者随机效应的 ordinal mixed-effects model；
- 总体偏好：报告包含平局的分布，并可补充 Bradley–Terry 模型；
- 多重比较：Holm 校正；
- 显著性阈值：校正后 `p < 0.05`。

无论结果是否显著，均报告效应量、置信区间、原始样本数和缺失数据处理方式。不得仅以“胜率更高”表述显著性。

### 12.3 主要比较优先级

1. B4 vs B1 的帮助强度适配性；
2. B4 vs B0 的完整答案泄露率；
3. B4 vs B1 的过度支架率；
4. B4 vs B5 的差距，用于衡量上游分类误差传播。

其他比较均视为次要或探索性分析。

## 13. 工程与可复现性记录

每次正式运行必须记录：

- Git commit；
- 工作区是否存在未提交修改；
- Python、依赖库和操作系统版本；
- 模型供应商、模型 ID、API 调用日期；
- Prompt 版本和 SHA-256；
- 数据 manifest 和 SHA-256；
- 随机种子；
- 总请求数、成功数、失败数和重试数；
- 平均/P50/P95 延迟；
- 输入、输出和总 token；
- 估算费用；
- fallback 次数及原因。

所有表格和图必须由保存的结果文件自动生成，不得手工复制或修改数字。论文中的每个主要数值应能追踪到一个结果 JSON 和一个生成命令。

## 14. 最终测试闸门

只有同时满足以下条件，才能运行 student-held-out 单标注者参考 Test：

- [x] 数据 split manifest 已生成并人工检查；
- [x] Test 学生与 Train/Dev 的重叠为 0；
- [x] 单标注者参考集指南已冻结；
- [x] 正式 550 条已完成并保存未修改副本；
- [ ] 至少间隔 7 日的 60 条盲化重复标注已完成；
- [ ] test–retest 一致性达到本协议阈值，或偏离原因及分析降级已经记录；
- [ ] 所有 Prompt 已版本化并冻结；
- [ ] 模型和超参数只依据 Train/Dev 选择；
- [ ] B0–B5 的定义和生成参数已经冻结；
- [ ] 人工评审表和随机化脚本已经通过小规模试运行；
- [ ] 主要指标、统计检验和排除规则已经冻结；
- [ ] `frozen_config.yaml` 已保存并写入 SHA-256；
- [ ] 项目负责人签署 Test 运行批准记录。

Test 运行后，如修改任何影响输出的规则、Prompt、模型或阈值，原 Test 自动降级为开发集。新的主要结论必须使用从未查看过的新 Test；若已无合适数据，应如实报告探索性结果，而不是继续称为预注册测试。

## 15. 结果报告规范

论文主文至少报告：

1. 数据流图：原始、排除、silver、单标注者参考集、Train/Dev/Test；
2. 单标注者 test–retest 一致性、分歧和设计限制；
3. conversation split 与 student-held-out 的性能差距；
4. 行为分类完整结果和置信区间；
5. 答案限制/帮助强度判断的有效性；
6. B0、B1、B4、B5 的端到端结果；
7. B2、B3 消融；
8. 分行为结果，尤其是 debugging 和 task clarification；
9. 答案泄露—帮助质量—过度拒绝三者的权衡；
10. 延迟、token、费用和 fallback；
11. 至少三个成功案例和三个失败案例；
12. 数据、标注、模型/API 和外部有效性限制。

禁止使用以下未经验证的表述：

- “EduGuard 提高了学生成绩”；
- “EduGuard 防止了作弊”；
- “风险分数代表真实学习风险”；
- “在所有教学场景中优于通用 LLM”；
- 未经统计检验的“显著提升”。

可以根据证据使用更精确的表述，例如：

- “在 student-held-out 单标注者参考 Test 上提高了行为分类 Macro-F1”；
- “在本评审量表下获得更高的帮助强度适配性评分”；
- “降低了完整答案披露，同时增加/未增加过度拒绝”；
- “结果仅适用于本研究的数据、任务和模型条件”。

## 16. 伦理、隐私与有效性威胁

- 只使用脱敏标识，不尝试恢复学生身份；
- 不将 `answer_seeking` 直接解释为作弊或低能力；
- 不公开完整私人对话，示例应进一步脱敏和截短；
- 明确 StudyChat 的课程、学校、时间和任务范围；
- 说明 MathDial 中模拟学生与真实学生数据的差异；
- 说明在线 API 模型会随时间变化；
- 说明人工教学评分具有价值判断和文化背景；
- 说明回复质量代理指标不能替代真实学习增益；
- 如未来开展真实学生实验，须在招募和数据收集前完成伦理审批与知情同意。

## 17. 计划里程碑

| 时间 | 工作 | 退出条件 |
| --- | --- | --- |
| 2026-09-07 至 09-09 | 冻结协议、字段和划分脚本 | 生成 split manifest 与冻结配置 |
| 2026-09-08 至 09-22 | 单标注者正式标注与延迟后测 | 完成 550 条首轮、间隔至少 7 日、60 条盲化后测和参考集数据卡 |
| 2026-09-15 至 09-22 | 分类与帮助强度实验 | RQ1、RQ2 结果固定 |
| 2026-09-20 至 09-28 | B0–B5 生成 | 输出、配置和运行日志完整 |
| 2026-09-24 至 10-02 | 盲评和统计分析 | RQ3、RQ4 结果固定 |
| 2026-09-28 至 10-04 | 鲁棒性和工程测试 | 次要实验与成本报告完成 |
| 2026-10-01 至 10-10 | 英文论文和匿名复现包 | 双盲 PDF、数据卡、代码说明完成 |

## 18. 冻结记录

协议正式冻结时填写：

| 字段 | 内容 |
| --- | --- |
| 冻结版本 |  |
| 冻结日期 |  |
| Git commit |  |
| 数据 manifest SHA-256 |  |
| `frozen_config.yaml` SHA-256 |  |
| 负责人 |  |
| 允许偏离项 |  |

任何偏离本协议的操作必须追加记录：日期、原因、影响范围、是否发生在查看 Test 结果之前，以及受影响的结论。

## 19. 最低可投稿实验集合

如果时间或人力不足，最低必须完成：

1. student-held-out 数据划分；
2. 不少于 500 条的单标注者参考标签，并对至少 10% 样本进行间隔不少于 7 日的盲化重复标注；
3. 当前风险/干预规则的有效性验证；
4. 新的未见端到端测试集；
5. Vanilla、Fixed Socratic、Full EduGuard 和 Oracle-label 四个条件；
6. 置信区间、预注册配对检验和完整分母；
7. Prompt、数据、模型和结果的可追踪复现记录。

鲁棒性、多底座模型和完整消融可以作为增强项，但不得以旧的 50 条诊断结果代替新的最终测试。论文必须明确单标注者方案无法估计标注者之间分歧，并将其列为内部有效性限制。

## 20. 参考入口

- BENCH 2026 CFP：<https://press.benchcouncil.org/conferences/Bench/events/Bench-2026/pages/Call-for-Papers>
- BENCH 2026 Review Policies：<https://press.benchcouncil.org/journals/PEvaluation/pages/review-policies>
- BENCH 2026 Submission Model：<https://press.benchcouncil.org/conferences/Bench/events/Bench-2026/pages/Submission-Model>
