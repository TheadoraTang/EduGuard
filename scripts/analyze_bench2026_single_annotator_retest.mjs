/** Read-only validation and test–retest analysis of the frozen 40-item pack. */
import fs from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = path.resolve(import.meta.dirname, "..");
const args = process.argv.slice(2);
const positional = args.filter((arg) => !arg.startsWith("--"));
const reportedStartDate = args.find((arg) => arg.startsWith("--reported-retest-start="))?.split("=")[1] ?? null;
const formalPath = positional[0] ?? "D:/Download/EduGuard_BENCH2026_Single_Annotator_Annotated.xlsx";
const retestPath = positional[1] ?? "D:/Download/EduGuard_BENCH2026_Single_Annotator_Retest40.xlsx";
const dataDir = path.join(root, "data/bench2026/human_eval");
const manifestDir = path.join(root, "data/bench2026/manifests");
const outputDir = path.join(root, "output/bench2026/retest40");
const bootstrapIterations = 5000;
const bootstrapSeed = 20260917;
const fields = [
  ["behavior_label", "行为标签", ["answer_seeking", "concept_understanding", "debugging_help", "reflection_verification", "task_clarification"]],
  ["attempt_evidence", "尝试证据", ["yes", "no", "unclear"]],
  ["answer_restriction_needed", "需限制答案", ["yes", "no", "unclear"]],
  ["appropriate_assistance_level", "帮助强度", ["low", "medium", "high"]],
  ["recommended_strategy", "推荐策略", ["guided_question", "concept_explanation", "debugging_scaffold", "verification_prompt", "requirement_clarification", "direct_solution", "refusal_or_boundary", "other"]],
  ["assessment_context", "评价情境", ["practice", "graded_assignment", "exam", "unknown"]],
  ["ambiguity_flag", "歧义标记", ["no", "yes"]],
];
const clean = (value) => value == null ? "" : String(value).trim();
const sha = async (filename) => createHash("sha256").update(await fs.readFile(filename)).digest("hex");
const jsonl = async (filename) => (await fs.readFile(filename, "utf8")).split(/\r?\n/).filter(Boolean).map(JSON.parse);
const safeText = (value, limit = 12000) => {
  const text = String(value ?? "");
  return text.length <= limit ? text : `${text.slice(0, limit)}\n[工作簿显示已截断]`;
};
const contextText = (items) => !items?.length ? "（无此前学生消息）"
  : items.map((item, i) => `[学生-${i + 1}] ${safeText(item, 3000)}`).join("\n\n");

async function workbookRows(filename, sheetName, count) {
  const book = await SpreadsheetFile.importXlsx(await FileBlob.load(filename));
  book.recalculate();
  const values = book.worksheets.getItem(sheetName).getRange(`A5:P${count + 4}`).values;
  const rows = values.map((cells, i) => ({
    row: i + 5, order: cells[0], annotation_id: clean(cells[1]), phase: clean(cells[2]),
    semester: clean(cells[3]), topic: clean(cells[4]),
    prior_student_messages: clean(cells[5]), student_message: clean(cells[6]),
    ...Object.fromEntries(fields.map(([key], j) => [key, clean(cells[j + 7])])),
    review_notes: clean(cells[14]), completion_status: clean(cells[15]),
  }));
  const progress = sheetName === "后测40" ? book.worksheets.getItem("进度").getRange("A4:D7").values : null;
  return { rows, progress };
}

function validate(rows, source, name, issues) {
  if (rows.length !== source.length) issues.push(`${name}: wrong row count`);
  const ids = rows.map((row) => row.annotation_id);
  if (ids.some((id) => !id) || new Set(ids).size !== ids.length) issues.push(`${name}: blank or duplicate IDs`);
  for (let i = 0; i < source.length; i += 1) {
    const row = rows[i];
    if (!row) continue;
    for (const [key, expected] of Object.entries({
      order: source[i].order, annotation_id: source[i].annotation_id, phase: source[i].phase,
      semester: source[i].semester, topic: source[i].topic,
      prior_student_messages: contextText(source[i].prior_student_messages),
      student_message: safeText(source[i].student_message),
    })) if (row[key] !== expected) issues.push(`${name}: ${key} changed at row ${row.row}`);
    for (const [key, , options] of fields) if (!options.includes(row[key])) issues.push(`${name}: invalid ${key} at row ${row.row}`);
    if ((row.ambiguity_flag === "yes" || row.recommended_strategy === "other") && !row.review_notes) issues.push(`${name}: note missing at row ${row.row}`);
    if (row.completion_status !== "完成") issues.push(`${name}: not complete at row ${row.row}`);
  }
}

function matrix(pairs, key, options) {
  const out = options.map(() => options.map(() => 0));
  const index = new Map(options.map((value, i) => [value, i]));
  for (const pair of pairs) out[index.get(pair.formal[key])][index.get(pair.retest[key])] += 1;
  return out;
}

function kappa(pairs, field) {
  const [key, , options] = field;
  const counts = matrix(pairs, key, options);
  const n = pairs.length;
  const rowTotals = counts.map((row) => row.reduce((a, b) => a + b, 0));
  const colTotals = options.map((_, j) => counts.reduce((sum, row) => sum + row[j], 0));
  let observed = 0;
  let expected = 0;
  for (let i = 0; i < options.length; i += 1) for (let j = 0; j < options.length; j += 1) {
    const penalty = key === "appropriate_assistance_level" ? ((i - j) / (options.length - 1)) ** 2 : Number(i !== j);
    observed += penalty * counts[i][j] / n;
    expected += penalty * rowTotals[i] * colTotals[j] / (n * n);
  }
  return expected < 1e-12 ? null : 1 - observed / expected;
}

function rng(seed) {
  let state = seed >>> 0;
  return () => {
    state += 0x6D2B79F5;
    let t = Math.imul(state ^ state >>> 15, state | 1);
    t ^= t + Math.imul(t ^ t >>> 7, t | 61);
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

function confidenceInterval(pairs, field, seed) {
  const random = rng(seed);
  const samples = [];
  for (let b = 0; b < bootstrapIterations; b += 1) {
    const sample = Array.from({ length: pairs.length }, () => pairs[Math.floor(random() * pairs.length)]);
    const value = kappa(sample, field);
    if (Number.isFinite(value)) samples.push(value);
  }
  samples.sort((a, b) => a - b);
  const pct = (p) => {
    if (!samples.length) return null;
    const pos = (samples.length - 1) * p;
    return samples[Math.floor(pos)] + (samples[Math.ceil(pos)] - samples[Math.floor(pos)]) * (pos - Math.floor(pos));
  };
  return { ci95: [pct(0.025), pct(0.975)], valid_resamples: samples.length };
}

function calculateMetrics(pairs) {
  return fields.map((field, index) => {
    const [key, label, options] = field;
    const counts = matrix(pairs, key, options);
    const agreements = counts.reduce((sum, row, i) => sum + row[i], 0);
    return {
      field: key, label, n: pairs.length, agreements, raw_agreement: agreements / pairs.length,
      kappa_type: key === "appropriate_assistance_level" ? "quadratic_weighted_cohen" : "cohen",
      kappa: kappa(pairs, field), bootstrap_kappa: confidenceInterval(pairs, field, bootstrapSeed + index),
      options, confusion_matrix_rows_formal_columns_retest: counts,
    };
  });
}

function markdown(result) {
  const v = result.validation;
  const fmt = (number) => number == null ? "n.a." : number.toFixed(3);
  const lines = [
    "# BENCH 2026 单标注者延迟后测验收与一致性", "",
    `生成时间：${result.generated_at_utc}`, "",
    `- 首轮工作簿 SHA-256：${result.sources.formal_workbook_sha256}`,
    `- 后测工作簿 SHA-256：${result.sources.retest_workbook_sha256}`,
    `- 验收：${v.passed ? "通过" : `${v.issues.length} 个问题`}`,
    `- 完成：${v.completed_rows}/40；必填备注：${v.required_notes_filled}/${v.required_notes_total}`,
    `- 后测开始日期：${v.retest_start_date_recorded ? "工作簿已填写" : "工作簿未填写"}${v.retest_start_date_self_reported_local ? `；标注者自述 ${v.retest_start_date_self_reported_local} 开始（非独立证据）` : "；尚待标注者确认"}`, "",
    "| 字段 | 原始一致率 | κ | 95% bootstrap CI | 一致/总数 |",
    "| --- | ---: | ---: | --- | ---: |",
  ];
  for (const m of result.metrics ?? []) lines.push(`| ${m.label}${m.kappa_type.startsWith("quadratic") ? "（二次加权）" : ""} | ${(m.raw_agreement * 100).toFixed(1)}% | ${fmt(m.kappa)} | [${m.bootstrap_kappa.ci95.map(fmt).join(", ")}] | ${m.agreements}/${m.n} |`);
  if (result.metrics) {
    lines.push("", "## 预设目标判读", "");
    for (const [key, hypothesis, threshold] of [
      ["behavior_label", "H1", 0.70],
      ["answer_restriction_needed", "H2", 0.70],
      ["appropriate_assistance_level", "H3", 0.60],
    ]) {
      const m = result.metrics.find((item) => item.field === key);
      lines.push(`- ${m.label} ${hypothesis}：κ 点估计 ${fmt(m.kappa)}，${m.kappa >= threshold ? "达到" : "未达到"}预设目标 ${threshold.toFixed(2)}。`);
    }
    lines.push("", "## 混淆矩阵", "", "行是首轮正式标签，列是延迟后测标签。", "");
  }
  for (const m of result.metrics ?? []) {
    lines.push(`### ${m.label}`, "", `| 首轮 \\ 后测 | ${m.options.join(" | ")} |`, `| --- | ${m.options.map(() => "---:").join(" | ")} |`);
    for (let i = 0; i < m.options.length; i += 1) lines.push(`| ${m.options[i]} | ${m.confusion_matrix_rows_formal_columns_retest[i].join(" | ")} |`);
    lines.push("");
  }
  lines.push("置信区间使用固定种子、5000 次按配对样本有放回重采样的百分位法。后测按五个 silver 层各选 8 条，不是对正式 550 的简单随机抽样；样本仅 40 条，稀有类别的稳定性证据尤其有限。", "", "该指标是同一标注者的跨时一致性，不是标注者间一致性或专家共识。首轮标签未按分歧修订。", "");
  if (v.issues.length) lines.push("## 验收问题", "", ...v.issues.map((issue) => `- ${issue}`), "");
  return `${lines.join("\n")}\n`;
}

async function main() {
  const completion = JSON.parse(await fs.readFile(path.join(manifestDir, "studychat_single_annotator_formal_completion.json"), "utf8"));
  const amendment = JSON.parse(await fs.readFile(path.join(manifestDir, "studychat_single_annotator_retest40_amendment.json"), "utf8"));
  const filenames = {
    formal_jsonl: path.join(dataDir, "single_annotator_formal_550.jsonl"),
    retest_jsonl: path.join(dataDir, "single_annotator_retest_40.jsonl"),
    mapping_jsonl: path.join(dataDir, "single_annotator_retest_40_private_key.jsonl"),
  };
  const issues = [];
  const hashes = Object.fromEntries(await Promise.all(Object.entries(filenames).map(async ([key, filename]) => [key, await sha(filename)])));
  for (const [key, expected] of [
    ["formal_jsonl", amendment.inputs.formal.sha256],
    ["retest_jsonl", amendment.outputs.retest_40.sha256],
    ["mapping_jsonl", amendment.outputs.retest_40_private_mapping.sha256],
  ]) if (hashes[key] !== expected) issues.push(`${key}: hash differs from frozen manifest`);
  const formalHash = await sha(formalPath);
  const retestHash = await sha(retestPath);
  if (formalHash.toUpperCase() !== completion.annotated_workbook.sha256.toUpperCase()) issues.push("Formal workbook differs from frozen SHA-256");
  const [formalSource, retestSource, mapping] = await Promise.all(Object.values(filenames).map(jsonl));
  const formal = await workbookRows(formalPath, "正式550", 550);
  const retest = await workbookRows(retestPath, "后测40", 40);
  validate(formal.rows, formalSource, "formal", issues);
  validate(retest.rows, retestSource, "retest", issues);
  const formalById = new Map(formal.rows.map((row) => [row.annotation_id, row]));
  const mappingById = new Map(mapping.map((row) => [row.retest_annotation_id, row]));
  if (mappingById.size !== 40 || retest.rows.some((row) => !mappingById.has(row.annotation_id))) issues.push("Private mapping is incomplete or has duplicate IDs");
  if (retest.rows.some((row) => formalById.has(row.annotation_id))) issues.push("Formal/retest visible ID overlap");
  const pairs = retest.rows.map((row) => ({ formal: formalById.get(mappingById.get(row.annotation_id)?.formal_annotation_id), retest: row }));
  if (pairs.some((pair) => !pair.formal)) issues.push("A retest alias does not map to a frozen formal row");
  const progress = retest.progress;
  if (clean(progress?.[0]?.[0]) !== "后测40" || progress[0][1] !== 40 || progress[0][2] !== 40 || progress[0][3] !== 1) issues.push("Progress summary differs from 40/40 (100%)");
  const startDate = clean(progress[3][1]);
  if (reportedStartDate && !/^\d{4}-\d{2}-\d{2}$/.test(reportedStartDate)) issues.push("Reported retest start date must be YYYY-MM-DD");
  const requiredNotes = retest.rows.filter((row) => row.ambiguity_flag === "yes" || row.recommended_strategy === "other");
  const result = {
    version: "bench2026-single-annotator-retest40-analysis-v1", generated_at_utc: new Date().toISOString(),
    sources: { formal_workbook_sha256: formalHash, retest_workbook_sha256: retestHash, ...hashes },
    validation: {
      passed: issues.length === 0, issues,
      completed_rows: retest.rows.filter((row) => row.completion_status === "完成").length,
      required_notes_total: requiredNotes.length,
      required_notes_filled: requiredNotes.filter((row) => row.review_notes).length,
      retest_start_date_recorded: /^\d{4}-\d{2}-\d{2}$/.test(startDate),
      retest_start_date_self_reported_local: reportedStartDate,
      minimum_delay_condition_met_from_self_report: reportedStartDate !== null && reportedStartDate >= "2026-09-16",
      start_date_independently_verified: false,
      source_file_modified_at_utc: (await fs.stat(retestPath)).mtime.toISOString(),
    },
    bootstrap: { iterations: bootstrapIterations, seed: bootstrapSeed, method: "paired percentile resampling" },
    metrics: issues.length ? null : calculateMetrics(pairs),
  };
  await fs.mkdir(outputDir, { recursive: true });
  await fs.writeFile(path.join(outputDir, "validation_and_agreement.json"), `${JSON.stringify(result, null, 2)}\n`);
  await fs.writeFile(path.join(outputDir, "validation_and_agreement.md"), markdown(result));
  console.log(JSON.stringify({ validation: result.validation, metrics: result.metrics?.map((m) => ({ field: m.field, agreements: m.agreements, raw_agreement: m.raw_agreement, kappa: m.kappa, ci95: m.bootstrap_kappa.ci95 })) }, null, 2));
  if (issues.length) process.exitCode = 2;
}

await main();
