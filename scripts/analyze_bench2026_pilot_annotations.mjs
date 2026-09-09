import fs from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve(import.meta.dirname, "..");
const sourceA = path.join(root, "output", "spreadsheets", "bench2026", "EduGuard_BENCH2026_Annotator_A.xlsx");
const sourceB = path.join(root, "output", "spreadsheets", "bench2026", "EduGuard_BENCH2026_Annotator_B.xlsx");
const outputDir = path.join(root, "output", "bench2026", "pilot");
const buildXlsx = process.argv.includes("--xlsx");
const bootstrapIterations = 5000;
const bootstrapSeed = 20260908;

const fieldSpecs = [
  {
    key: "behavior_label",
    label: "行为标签",
    scale: "nominal",
    options: ["answer_seeking", "concept_understanding", "debugging_help", "reflection_verification", "task_clarification"],
  },
  { key: "attempt_evidence", label: "尝试证据", scale: "nominal", options: ["yes", "no", "unclear"] },
  { key: "answer_restriction_needed", label: "需限制答案", scale: "nominal", options: ["yes", "no", "unclear"] },
  { key: "appropriate_assistance_level", label: "帮助强度", scale: "ordinal", options: ["low", "medium", "high"] },
  {
    key: "recommended_strategy",
    label: "推荐策略",
    scale: "nominal",
    options: ["guided_question", "concept_explanation", "debugging_scaffold", "verification_prompt", "requirement_clarification", "direct_solution", "refusal_or_boundary", "other"],
  },
  { key: "assessment_context", label: "评价情境", scale: "nominal", options: ["practice", "graded_assignment", "exam", "unknown"] },
  { key: "ambiguity_flag", label: "歧义标记", scale: "nominal", options: ["no", "yes"] },
];

function clean(value) {
  return value === null || value === undefined ? "" : String(value).trim();
}

async function fileRecord(filePath) {
  const bytes = await fs.readFile(filePath);
  return {
    name: path.basename(filePath),
    bytes: bytes.length,
    sha256: createHash("sha256").update(bytes).digest("hex"),
  };
}

async function extractPilot(workbookPath, annotator) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));
  const sheet = workbook.worksheets.getItem("试标50");
  const values = sheet.getRange("A5:P54").values;
  if (!Array.isArray(values) || values.length !== 50) {
    throw new Error(`${annotator} pilot sheet must contain exactly 50 data rows`);
  }
  const rows = values.map((row, index) => ({
    annotator,
    source_row: index + 5,
    order: Number(row[0]),
    annotation_id: clean(row[1]),
    phase: clean(row[2]),
    semester: clean(row[3]),
    topic: clean(row[4]),
    prior_student_messages: clean(row[5]),
    student_message: clean(row[6]),
    behavior_label: clean(row[7]),
    attempt_evidence: clean(row[8]),
    answer_restriction_needed: clean(row[9]),
    appropriate_assistance_level: clean(row[10]),
    recommended_strategy: clean(row[11]),
    assessment_context: clean(row[12]),
    ambiguity_flag: clean(row[13]),
    review_notes: clean(row[14]),
    completion_status: clean(row[15]),
  }));
  const ids = rows.map((row) => row.annotation_id);
  if (ids.some((id) => !id) || new Set(ids).size !== rows.length) {
    throw new Error(`${annotator} has blank or duplicate annotation IDs`);
  }
  return rows;
}

function validateRows(rows) {
  const issues = [];
  for (const row of rows) {
    for (const spec of fieldSpecs) {
      if (!spec.options.includes(row[spec.key])) {
        issues.push({
          annotator: row.annotator,
          annotation_id: row.annotation_id,
          row: row.source_row,
          field: spec.key,
          value: row[spec.key],
          issue: row[spec.key] ? "invalid_value" : "missing_value",
        });
      }
    }
    if ((row.ambiguity_flag === "yes" || row.recommended_strategy === "other") && !row.review_notes) {
      issues.push({
        annotator: row.annotator,
        annotation_id: row.annotation_id,
        row: row.source_row,
        field: "review_notes",
        value: "",
        issue: "required_note_missing",
      });
    }
  }
  return issues;
}

function joinRows(rowsA, rowsB) {
  const mapB = new Map(rowsB.map((row) => [row.annotation_id, row]));
  const idsA = new Set(rowsA.map((row) => row.annotation_id));
  const missingInB = [...idsA].filter((id) => !mapB.has(id));
  const extraInB = rowsB.map((row) => row.annotation_id).filter((id) => !idsA.has(id));
  if (missingInB.length || extraInB.length) {
    throw new Error(`A/B membership mismatch: missing_in_b=${missingInB.length}, extra_in_b=${extraInB.length}`);
  }
  return rowsA.map((a) => {
    const b = mapB.get(a.annotation_id);
    if (a.student_message !== b.student_message) {
      throw new Error(`Student message mismatch for ${a.annotation_id}`);
    }
    return { annotation_id: a.annotation_id, a, b };
  });
}

function confusionMatrix(pairs, key, options) {
  const matrix = options.map(() => options.map(() => 0));
  const index = new Map(options.map((value, i) => [value, i]));
  for (const pair of pairs) {
    matrix[index.get(pair.a[key])][index.get(pair.b[key])] += 1;
  }
  return matrix;
}

function rawAgreement(pairs, key) {
  if (!pairs.length) return null;
  return pairs.filter((pair) => pair.a[key] === pair.b[key]).length / pairs.length;
}

function cohenKappa(pairs, key, options) {
  if (!pairs.length) return null;
  const matrix = confusionMatrix(pairs, key, options);
  const n = pairs.length;
  const rowTotals = matrix.map((row) => row.reduce((sum, value) => sum + value, 0));
  const colTotals = options.map((_, col) => matrix.reduce((sum, row) => sum + row[col], 0));
  const observed = matrix.reduce((sum, row, i) => sum + row[i], 0) / n;
  const expected = rowTotals.reduce((sum, value, i) => sum + value * colTotals[i], 0) / (n * n);
  return Math.abs(1 - expected) < 1e-12 ? null : (observed - expected) / (1 - expected);
}

function weightedKappa(pairs, key, options, weighting) {
  if (!pairs.length) return null;
  const matrix = confusionMatrix(pairs, key, options);
  const n = pairs.length;
  const k = options.length;
  const rowTotals = matrix.map((row) => row.reduce((sum, value) => sum + value, 0));
  const colTotals = options.map((_, col) => matrix.reduce((sum, row) => sum + row[col], 0));
  let observed = 0;
  let expected = 0;
  for (let i = 0; i < k; i += 1) {
    for (let j = 0; j < k; j += 1) {
      const distance = Math.abs(i - j) / Math.max(k - 1, 1);
      const penalty = weighting === "quadratic" ? distance * distance : distance;
      const agreementWeight = 1 - penalty;
      observed += agreementWeight * matrix[i][j] / n;
      expected += agreementWeight * rowTotals[i] * colTotals[j] / (n * n);
    }
  }
  return Math.abs(1 - expected) < 1e-12 ? null : (observed - expected) / (1 - expected);
}

function mulberry32(seed) {
  let state = seed >>> 0;
  return () => {
    state += 0x6D2B79F5;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function percentile(sorted, probability) {
  if (!sorted.length) return null;
  const index = (sorted.length - 1) * probability;
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  if (lower === upper) return sorted[lower];
  return sorted[lower] + (sorted[upper] - sorted[lower]) * (index - lower);
}

function bootstrapCI(pairs, statistic, seed) {
  const rng = mulberry32(seed);
  const values = [];
  for (let iteration = 0; iteration < bootstrapIterations; iteration += 1) {
    const sampled = [];
    for (let i = 0; i < pairs.length; i += 1) {
      sampled.push(pairs[Math.floor(rng() * pairs.length)]);
    }
    const value = statistic(sampled);
    if (Number.isFinite(value)) values.push(value);
  }
  values.sort((a, b) => a - b);
  return [percentile(values, 0.025), percentile(values, 0.975)];
}

function countValues(rows, key, options) {
  const counts = Object.fromEntries(options.map((value) => [value, 0]));
  for (const row of rows) counts[row[key]] += 1;
  return counts;
}

function buildMetrics(pairs) {
  return fieldSpecs.map((spec, specIndex) => {
    const agreement = rawAgreement(pairs, spec.key);
    const kappa = cohenKappa(pairs, spec.key, spec.options);
    const result = {
      field: spec.key,
      label: spec.label,
      scale: spec.scale,
      n: pairs.length,
      agreements: pairs.filter((pair) => pair.a[spec.key] === pair.b[spec.key]).length,
      disagreements: pairs.filter((pair) => pair.a[spec.key] !== pair.b[spec.key]).length,
      raw_agreement: agreement,
      raw_agreement_ci95: bootstrapCI(
        pairs,
        (sample) => rawAgreement(sample, spec.key),
        bootstrapSeed + specIndex * 10 + 1,
      ),
      cohen_kappa: kappa,
      cohen_kappa_ci95: bootstrapCI(
        pairs,
        (sample) => cohenKappa(sample, spec.key, spec.options),
        bootstrapSeed + specIndex * 10 + 2,
      ),
      distribution_a: countValues(pairs.map((pair) => pair.a), spec.key, spec.options),
      distribution_b: countValues(pairs.map((pair) => pair.b), spec.key, spec.options),
      options: spec.options,
      confusion_matrix_rows_a_columns_b: confusionMatrix(pairs, spec.key, spec.options),
    };
    if (spec.scale === "ordinal") {
      result.linear_weighted_kappa = weightedKappa(pairs, spec.key, spec.options, "linear");
      result.linear_weighted_kappa_ci95 = bootstrapCI(
        pairs,
        (sample) => weightedKappa(sample, spec.key, spec.options, "linear"),
        bootstrapSeed + specIndex * 10 + 3,
      );
      result.quadratic_weighted_kappa = weightedKappa(pairs, spec.key, spec.options, "quadratic");
      result.quadratic_weighted_kappa_ci95 = bootstrapCI(
        pairs,
        (sample) => weightedKappa(sample, spec.key, spec.options, "quadratic"),
        bootstrapSeed + specIndex * 10 + 4,
      );
    }
    return result;
  });
}

function buildDisagreements(pairs) {
  return pairs
    .map((pair) => {
      const fields = fieldSpecs
        .filter((spec) => pair.a[spec.key] !== pair.b[spec.key])
        .map((spec) => spec.key);
      return {
        annotation_id: pair.annotation_id,
        disagreement_fields: fields,
        disagreement_count: fields.length,
        semester: pair.a.semester,
        topic: pair.a.topic,
        prior_student_messages: pair.a.prior_student_messages,
        student_message: pair.a.student_message,
        annotator_a: Object.fromEntries(fieldSpecs.map((spec) => [spec.key, pair.a[spec.key]])),
        annotator_b: Object.fromEntries(fieldSpecs.map((spec) => [spec.key, pair.b[spec.key]])),
        notes_a: pair.a.review_notes,
        notes_b: pair.b.review_notes,
      };
    })
    .filter((row) => row.disagreement_count > 0)
    .sort((left, right) => right.disagreement_count - left.disagreement_count || left.annotation_id.localeCompare(right.annotation_id));
}

function formatPercent(value) {
  return value === null ? "n.a." : `${(value * 100).toFixed(1)}%`;
}

function formatNumber(value) {
  return value === null ? "n.a." : value.toFixed(3);
}

function formatCI(interval, formatter = formatNumber) {
  return `[${formatter(interval[0])}, ${formatter(interval[1])}]`;
}

function markdownReport(result) {
  const lines = [
    "# EduGuard BENCH 2026 试标一致性报告",
    "",
    `生成时间：${result.generated_at_utc}`,
    "",
    `- 对齐样本：${result.sample_count}`,
    `- 任一字段存在分歧的样本：${result.samples_with_any_disagreement}`,
    `- A/B 值域或必填错误：${result.validation_issues.length}`,
    `- Bootstrap：${bootstrapIterations} 次按样本有放回重采样，固定种子 ${bootstrapSeed}`,
    "",
    "## 指标",
    "",
    "| 字段 | 原始一致率 | Cohen's κ | 95% CI | 备注 |",
    "| --- | ---: | ---: | --- | --- |",
  ];
  for (const metric of result.metrics) {
    const primaryKappa = metric.scale === "ordinal" ? metric.quadratic_weighted_kappa : metric.cohen_kappa;
    const primaryCI = metric.scale === "ordinal" ? metric.quadratic_weighted_kappa_ci95 : metric.cohen_kappa_ci95;
    lines.push(
      `| ${metric.label} | ${formatPercent(metric.raw_agreement)} | ${formatNumber(primaryKappa)} | ${formatCI(primaryCI)} | ${metric.scale === "ordinal" ? `二次加权；未加权 κ=${formatNumber(metric.cohen_kappa)}，线性加权 κ=${formatNumber(metric.linear_weighted_kappa)}` : "名义变量"} |`,
    );
  }
  lines.push("", "## 判读原则", "");
  lines.push("- 试标用于发现指南歧义，不计入正式 Gold Test。", "- 不应只看 κ：同时检查原始一致率、类别边际分布和具体分歧。", "- 指南修订与仲裁规则必须在开始正式550之前冻结。", "- 可靠性阈值沿用实验协议；未达到阈值的字段应继续讨论或追加试标。", "");
  return `${lines.join("\n")}\n`;
}

function setCommonStyle(sheet, range = "A:Z") {
  sheet.showGridLines = false;
  sheet.getRange(range).format.font = { name: "Arial", size: 10, color: "#172033" };
}

function addTitle(sheet, title, subtitle, endColumn) {
  sheet.getRange(`A1:${endColumn}1`).merge();
  sheet.getRange("A1").values = [[title]];
  sheet.getRange(`A1:${endColumn}1`).format = {
    fill: "#17365D",
    font: { name: "Arial", size: 15, bold: true, color: "#FFFFFF" },
    verticalAlignment: "center",
  };
  sheet.getRange(`A1:${endColumn}1`).format.rowHeight = 34;
  sheet.getRange(`A2:${endColumn}2`).merge();
  sheet.getRange("A2").values = [[subtitle]];
  sheet.getRange(`A2:${endColumn}2`).format = {
    fill: "#EAF2F8",
    font: { name: "Arial", size: 10, color: "#17365D", bold: true },
    wrapText: true,
  };
  sheet.getRange(`A2:${endColumn}2`).format.rowHeight = 34;
}

async function buildReportWorkbook(result, pairs, disagreements) {
  const workbook = Workbook.create();
  const summary = workbook.worksheets.add("一致性摘要");
  const confusion = workbook.worksheets.add("混淆矩阵");
  const disagreementSheet = workbook.worksheets.add("分歧样本");
  const complete = workbook.worksheets.add("完整标注");

  setCommonStyle(summary, "A:H");
  addTitle(
    summary,
    "EduGuard BENCH 2026 试标一致性",
    "50 条试标；A/B 独立标注。帮助强度以二次加权 Cohen's kappa 为主，其余字段使用未加权 Cohen's kappa。",
    "H",
  );
  summary.getRange("A4:D8").values = [
    ["质量检查", "结果", "解释", "处理建议"],
    ["对齐样本", result.sample_count, "A/B 标注ID完全一致", "通过"],
    ["任一字段有分歧", result.samples_with_any_disagreement, "至少一个必填字段不同", "查看“分歧样本”"],
    ["值域/必填错误", result.validation_issues.length, "非法选项、漏填或必要备注缺失", result.validation_issues.length ? "修正后重算" : "通过"],
    ["正式集填写数", 0, "两份正式550仍为空", "冻结指南后开始"],
  ];
  summary.getRange("A4:D4").format = {
    fill: "#2F5597",
    font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
  };
  summary.getRange("A5:D8").format.borders = { insideHorizontal: { style: "thin", color: "#D9E2F3" } };

  const metricHeaders = ["字段", "尺度", "一致数", "分歧数", "原始一致率", "主 kappa", "kappa 95% CI", "补充指标"];
  summary.getRange("A11:H11").values = [metricHeaders];
  const metricRows = result.metrics.map((metric) => {
    const primary = metric.scale === "ordinal" ? metric.quadratic_weighted_kappa : metric.cohen_kappa;
    const interval = metric.scale === "ordinal" ? metric.quadratic_weighted_kappa_ci95 : metric.cohen_kappa_ci95;
    return [
      metric.label,
      metric.scale === "ordinal" ? "有序" : "名义",
      metric.agreements,
      metric.disagreements,
      metric.raw_agreement,
      primary,
      formatCI(interval),
      metric.scale === "ordinal" ? `未加权=${formatNumber(metric.cohen_kappa)}；线性加权=${formatNumber(metric.linear_weighted_kappa)}` : "",
    ];
  });
  summary.getRangeByIndexes(11, 0, metricRows.length, metricHeaders.length).values = metricRows;
  summary.tables.add(`A11:H${11 + metricRows.length}`, true, "PilotAgreementMetrics");
  summary.getRange("A11:H11").format = {
    fill: "#2F5597",
    font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
  };
  summary.getRange(`E12:F${11 + metricRows.length}`).format.numberFormat = "0.000";
  summary.getRange(`E12:E${11 + metricRows.length}`).format.numberFormat = "0.0%";
  summary.getRange("A:A").format.columnWidth = 22;
  summary.getRange("B:B").format.columnWidth = 12;
  summary.getRange("C:D").format.columnWidth = 12;
  summary.getRange("E:F").format.columnWidth = 16;
  summary.getRange("G:G").format.columnWidth = 24;
  summary.getRange("H:H").format.columnWidth = 34;
  summary.freezePanes.freezeRows(2);

  setCommonStyle(confusion, "A:J");
  addTitle(confusion, "A/B 混淆矩阵", "行是 Annotator A，列是 Annotator B；每个矩阵的总和均为 50。", "J");
  let rowCursor = 4;
  for (const metric of result.metrics) {
    confusion.getRange(`A${rowCursor}:J${rowCursor}`).merge();
    confusion.getRange(`A${rowCursor}`).values = [[`${metric.label} · 原始一致率 ${formatPercent(metric.raw_agreement)}`]];
    confusion.getRange(`A${rowCursor}:J${rowCursor}`).format = {
      fill: "#D9EAF7",
      font: { name: "Arial", size: 10, bold: true, color: "#17365D" },
    };
    rowCursor += 1;
    const size = metric.options.length;
    confusion.getRangeByIndexes(rowCursor - 1, 0, 1, size + 1).values = [["A \\ B", ...metric.options]];
    const matrixRows = metric.options.map((option, index) => [option, ...metric.confusion_matrix_rows_a_columns_b[index]]);
    confusion.getRangeByIndexes(rowCursor, 0, size, size + 1).values = matrixRows;
    confusion.getRangeByIndexes(rowCursor - 1, 0, 1, size + 1).format = {
      fill: "#2F5597",
      font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
      horizontalAlignment: "center",
    };
    confusion.getRangeByIndexes(rowCursor, 1, size, size).format.horizontalAlignment = "center";
    confusion.getRangeByIndexes(rowCursor, 0, size, size + 1).format.borders = {
      insideHorizontal: { style: "thin", color: "#D9E2F3" },
    };
    rowCursor += size + 2;
  }
  confusion.getRange("A:A").format.columnWidth = 30;
  confusion.getRange("B:J").format.columnWidth = 24;
  confusion.freezePanes.freezeRows(2);

  const detailHeaders = [
    "标注ID", "分歧字段", "分歧数", "学期", "主题", "当前学生消息",
    "A行为", "B行为", "A尝试", "B尝试", "A限制", "B限制", "A强度", "B强度",
    "A策略", "B策略", "A情境", "B情境", "A歧义", "B歧义", "A备注", "B备注",
  ];
  function detailRow(row) {
    return [
      row.annotation_id,
      row.disagreement_fields.join(", "),
      row.disagreement_count,
      row.semester,
      row.topic,
      row.student_message,
      row.annotator_a.behavior_label,
      row.annotator_b.behavior_label,
      row.annotator_a.attempt_evidence,
      row.annotator_b.attempt_evidence,
      row.annotator_a.answer_restriction_needed,
      row.annotator_b.answer_restriction_needed,
      row.annotator_a.appropriate_assistance_level,
      row.annotator_b.appropriate_assistance_level,
      row.annotator_a.recommended_strategy,
      row.annotator_b.recommended_strategy,
      row.annotator_a.assessment_context,
      row.annotator_b.assessment_context,
      row.annotator_a.ambiguity_flag,
      row.annotator_b.ambiguity_flag,
      row.notes_a,
      row.notes_b,
    ];
  }

  setCommonStyle(disagreementSheet, "A:V");
  addTitle(disagreementSheet, "试标分歧样本", "仅用于试标讨论与指南修订。讨论时先看分歧字段，再回看消息文本和双方备注。", "V");
  disagreementSheet.getRange("A4:V4").values = [detailHeaders];
  disagreementSheet.getRangeByIndexes(4, 0, disagreements.length, detailHeaders.length).values = disagreements.map(detailRow);
  disagreementSheet.tables.add(`A4:V${4 + disagreements.length}`, true, "PilotDisagreements");
  disagreementSheet.getRange("A4:V4").format = {
    fill: "#2F5597",
    font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    wrapText: true,
  };
  disagreementSheet.getRange(`B5:B${4 + disagreements.length}`).format.wrapText = true;
  disagreementSheet.getRange(`F5:F${4 + disagreements.length}`).format.wrapText = true;
  disagreementSheet.getRange(`U5:V${4 + disagreements.length}`).format.wrapText = true;
  disagreementSheet.getRange(`A5:V${4 + disagreements.length}`).format.verticalAlignment = "top";
  disagreementSheet.getRange(`A5:V${4 + disagreements.length}`).format.rowHeight = 64;
  disagreementSheet.freezePanes.freezeRows(4);
  disagreementSheet.freezePanes.freezeColumns(1);
  disagreementSheet.getRange("A:A").format.columnWidth = 20;
  disagreementSheet.getRange("B:B").format.columnWidth = 34;
  disagreementSheet.getRange("C:E").format.columnWidth = 10;
  disagreementSheet.getRange("F:F").format.columnWidth = 60;
  disagreementSheet.getRange("G:T").format.columnWidth = 22;
  disagreementSheet.getRange("U:V").format.columnWidth = 38;

  const allRows = pairs.map((pair) => {
    const fields = fieldSpecs.filter((spec) => pair.a[spec.key] !== pair.b[spec.key]).map((spec) => spec.key);
    return detailRow({
      annotation_id: pair.annotation_id,
      disagreement_fields: fields,
      disagreement_count: fields.length,
      semester: pair.a.semester,
      topic: pair.a.topic,
      student_message: pair.a.student_message,
      annotator_a: Object.fromEntries(fieldSpecs.map((spec) => [spec.key, pair.a[spec.key]])),
      annotator_b: Object.fromEntries(fieldSpecs.map((spec) => [spec.key, pair.b[spec.key]])),
      notes_a: pair.a.review_notes,
      notes_b: pair.b.review_notes,
    });
  });
  setCommonStyle(complete, "A:V");
  addTitle(complete, "试标完整对照", "50 条试标的 A/B 原始标签对照；此页不包含仲裁结果。", "V");
  complete.getRange("A4:V4").values = [detailHeaders];
  complete.getRangeByIndexes(4, 0, allRows.length, detailHeaders.length).values = allRows;
  complete.tables.add(`A4:V${4 + allRows.length}`, true, "PilotCompleteComparison");
  complete.getRange("A4:V4").format = {
    fill: "#2F5597",
    font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    wrapText: true,
  };
  complete.getRange("B5:B54").format.wrapText = true;
  complete.getRange("F5:F54").format.wrapText = true;
  complete.getRange("U5:V54").format.wrapText = true;
  complete.getRange("A5:V54").format.verticalAlignment = "top";
  complete.getRange("A5:V54").format.rowHeight = 58;
  complete.freezePanes.freezeRows(4);
  complete.freezePanes.freezeColumns(1);
  complete.getRange("A:A").format.columnWidth = 20;
  complete.getRange("B:B").format.columnWidth = 34;
  complete.getRange("C:E").format.columnWidth = 10;
  complete.getRange("F:F").format.columnWidth = 60;
  complete.getRange("G:T").format.columnWidth = 22;
  complete.getRange("U:V").format.columnWidth = 38;

  workbook.recalculate();
  const inspectRanges = [
    "一致性摘要!A1:H18",
    "混淆矩阵!A1:J18",
    `分歧样本!A1:V${Math.min(10, 4 + disagreements.length)}`,
    "完整标注!A1:V10",
  ];
  for (const range of inspectRanges) {
    const inspected = await workbook.inspect({
      kind: "table",
      range,
      include: "values,formulas",
      tableMaxRows: 20,
      tableMaxCols: 22,
      tableMaxCellChars: 140,
    });
    console.log(inspected.ndjson);
  }
  const errors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
    options: { useRegex: true, maxResults: 300 },
    summary: "pilot agreement final formula error scan",
  });
  console.log(errors.ndjson);

  const previewDir = path.join(root, "tmp", "bench2026-pilot-report-previews");
  await fs.mkdir(previewDir, { recursive: true });
  const previews = [
    ["一致性摘要", "A1:H18", "summary.png"],
    ["混淆矩阵", "A1:J18", "confusion.png"],
    ["分歧样本", `A1:V${Math.min(10, 4 + disagreements.length)}`, "disagreements.png"],
    ["完整标注", "A1:V10", "complete.png"],
  ];
  for (const [sheetName, range, filename] of previews) {
    const image = await workbook.render({ sheetName, range, scale: 1, format: "png" });
    await fs.writeFile(path.join(previewDir, filename), new Uint8Array(await image.arrayBuffer()));
  }

  const outputPath = path.join(outputDir, "EduGuard_BENCH2026_Pilot_Agreement.xlsx");
  const xlsx = await SpreadsheetFile.exportXlsx(workbook);
  await xlsx.save(outputPath);
  return outputPath;
}

await fs.mkdir(outputDir, { recursive: true });
const rowsA = await extractPilot(sourceA, "A");
const rowsB = await extractPilot(sourceB, "B");
const validationIssues = [...validateRows(rowsA), ...validateRows(rowsB)];
const pairs = joinRows(rowsA, rowsB);
const metrics = buildMetrics(pairs);
const disagreements = buildDisagreements(pairs);
const result = {
  analysis_version: "bench2026-pilot-agreement-v1",
  generated_at_utc: new Date().toISOString(),
  source_files: [await fileRecord(sourceA), await fileRecord(sourceB)],
  sample_count: pairs.length,
  samples_with_any_disagreement: disagreements.length,
  bootstrap: { iterations: bootstrapIterations, seed: bootstrapSeed, unit: "annotation item" },
  validation_issues: validationIssues,
  metrics,
};

await fs.writeFile(path.join(outputDir, "pilot_agreement.json"), `${JSON.stringify(result, null, 2)}\n`, "utf8");
await fs.writeFile(
  path.join(outputDir, "pilot_disagreements.jsonl"),
  disagreements.map((row) => JSON.stringify(row)).join("\n") + (disagreements.length ? "\n" : ""),
  "utf8",
);
await fs.writeFile(path.join(outputDir, "pilot_agreement_report.md"), markdownReport(result), "utf8");

let workbookPath = null;
if (buildXlsx) workbookPath = await buildReportWorkbook(result, pairs, disagreements);
console.log(JSON.stringify({
  sample_count: result.sample_count,
  validation_issue_count: validationIssues.length,
  samples_with_any_disagreement: disagreements.length,
  metrics: metrics.map((metric) => ({
    field: metric.field,
    raw_agreement: metric.raw_agreement,
    primary_kappa: metric.scale === "ordinal" ? metric.quadratic_weighted_kappa : metric.cohen_kappa,
  })),
  workbook_path: workbookPath,
}, null, 2));
