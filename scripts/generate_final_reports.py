"""Generate paper-ready Markdown summaries from final evaluation artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def percentage(value: float) -> str:
    return f"{value * 100:.2f}%"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data/final"))
    parser.add_argument("--docs-dir", type=Path, default=Path("docs"))
    args = parser.parse_args()

    stats = load(args.data_dir / "dataset_statistics.json")
    rules = load(args.data_dir / "studychat_rules_test_evaluation.json")
    mapping = load(args.data_dir / "studychat_mapping_test_evaluation.json")
    args.docs_dir.mkdir(parents=True, exist_ok=True)

    study = stats["studychat"]
    math = stats["mathdial"]
    dataset_lines = [
        "# EduGuard 正式标注数据集说明",
        "",
        "## 数据清洗原则",
        "",
        "- StudyChat 以人工复核标签为最终依据。",
        "- 人工标签属于五类之一时保留；人工标签为空时排除并单独归档。",
        "- 初始预测标签为空不等于样本无效：其中仍有 "
        f"{study['retained_samples_with_blank_initial_prediction']} 条经人工确认后被保留。",
        "- 数据划分以完整对话或完整题目为单位，避免同一对话或题目跨集合泄漏。",
        "",
        "## StudyChat",
        "",
        f"- 原始有效提问：{study['source_samples']:,}",
        f"- 最终保留：{study['labeled_samples']:,}",
        f"- 排除：{study['excluded_samples']:,}",
        f"- 保留率：{percentage(study['retention_rate'])}",
        f"- 对话级跨集合泄漏：{study['split_leakage_by_conversation']}",
        "",
        "| 行为标签 | 数量 |",
        "| --- | ---: |",
    ]
    for label, count in study["label_distribution"].items():
        dataset_lines.append(f"| `{label}` | {count:,} |")
    dataset_lines.extend(
        [
            "",
            "| 数据划分 | 数量 |",
            "| --- | ---: |",
        ]
    )
    for split, count in study["split_distribution"].items():
        dataset_lines.append(f"| {split} | {count:,} |")

    dataset_lines.extend(
        [
            "",
            "## MathDial",
            "",
            f"- 教师回复轮次：{math['labeled_samples']:,}",
            f"- 排除：{math['excluded_samples']:,}",
            f"- 题目级跨集合泄漏：{math['split_leakage_by_problem']}",
            f"- 答案泄露率：{percentage(math['answer_disclosure_rate'])}",
            "",
            "| 支架策略 | 数量 |",
            "| --- | ---: |",
        ]
    )
    for label, count in math["strategy_distribution"].items():
        dataset_lines.append(f"| `{label}` | {count:,} |")
    dataset_lines.extend(
        [
            "",
            "| 人工评分维度 | 平均分 |",
            "| --- | ---: |",
            f"| 教学针对性 | {math['mean_scores']['pedagogical_relevance_score']:.3f} |",
            f"| 促进思考 | {math['mean_scores']['promotes_thinking_score']:.3f} |",
            f"| 表达清晰度 | {math['mean_scores']['clarity_score']:.3f} |",
            "",
            "## 可复现文件",
            "",
            "| 文件 | SHA-256 |",
            "| --- | --- |",
        ]
    )
    artifact_names = [
        "studychat_behavior_labeled.jsonl",
        "studychat_behavior_excluded.jsonl",
        "studychat_behavior_train.jsonl",
        "studychat_behavior_dev.jsonl",
        "studychat_behavior_test.jsonl",
        "mathdial_scaffold_labeled.jsonl",
        "mathdial_scaffold_train.jsonl",
        "mathdial_scaffold_dev.jsonl",
        "mathdial_scaffold_test.jsonl",
    ]
    for name in artifact_names:
        file_path = args.data_dir / name
        dataset_lines.append(f"| `{name}` | `{sha256(file_path)}` |")
    (args.docs_dir / "final-dataset-report.md").write_text(
        "\n".join(dataset_lines) + "\n", encoding="utf-8"
    )

    experiment_lines = [
        "# StudyChat 五分类正式基线结果",
        "",
        "正式评测仅使用冻结的 Test 集，包含 "
        f"{rules['samples']:,} 条人工标注样本。",
        "",
        "## 结果汇总",
        "",
        "| 方法 | 覆盖率 | Accuracy | Macro-F1 | Weighted-F1 |",
        "| --- | ---: | ---: | ---: | ---: |",
        (
            "| StudyChat 原始标签映射 | "
            f"{percentage(mapping['coverage'])} | "
            f"{percentage(mapping['accuracy_on_covered'])} | "
            f"{percentage(mapping['macro_f1_on_covered'])} | "
            f"{percentage(mapping['weighted_f1_on_covered'])} |"
        ),
        (
            "| EduGuard 关键词规则 | 100.00% | "
            f"{percentage(rules['accuracy'])} | "
            f"{percentage(rules['macro_f1'])} | "
            f"{percentage(rules['weighted_f1'])} |"
        ),
        "",
        "> 原始标签映射只在有映射结果的样本上计算指标，"
        f"Test集中有 {mapping['missing_predictions']} 条没有初始预测。"
        "此外，人工标注时可见初始预测，因此该结果可能受到标注锚定影响，"
        "只能作为数据来源映射参考，不能作为独立模型性能结论。",
        "",
        "## 规则分类器各类别结果",
        "",
        "| 标签 | Precision | Recall | F1 | Support |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    report = rules["classification_report"]
    for label in rules["labels"]:
        row = report[label]
        experiment_lines.append(
            f"| `{label}` | {percentage(row['precision'])} | "
            f"{percentage(row['recall'])} | {percentage(row['f1-score'])} | "
            f"{int(row['support']):,} |"
        )
    experiment_lines.extend(
        [
            "",
            "## 初步结论",
            "",
            "1. 规则分类器完整覆盖测试集，但Macro-F1较低，不能作为最终分类模型。",
            "2. 规则分类器明显偏向 `concept_understanding`，"
            "对 `task_clarification` 的召回率尤其不足。",
            "3. 后续应在同一冻结Test集上评测通用LLM Prompt、EduGuard Prompt和微调模型。",
            "4. Prompt开发只能使用Train和Dev集，不能再根据Test结果修改方案。",
        ]
    )
    (args.docs_dir / "studychat-final-baseline-results.md").write_text(
        "\n".join(experiment_lines) + "\n", encoding="utf-8"
    )

    print(args.docs_dir / "final-dataset-report.md")
    print(args.docs_dir / "studychat-final-baseline-results.md")


if __name__ == "__main__":
    main()
