import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve(import.meta.dirname, "..");
const dataDir = path.join(root, "data", "bench2026", "human_eval");
const singleMode = process.argv.includes("--single");
const outputArgument = process.argv.slice(2).find((value) => !value.startsWith("--"));
const outputDir = outputArgument
  ? path.resolve(outputArgument)
  : path.join(root, "output", "spreadsheets", "bench2026");

const behaviorLabels = [
  "answer_seeking",
  "concept_understanding",
  "debugging_help",
  "reflection_verification",
  "task_clarification",
];
const evidenceOptions = ["yes", "no", "unclear"];
const assistanceOptions = ["low", "medium", "high"];
const strategyOptions = [
  "guided_question",
  "concept_explanation",
  "debugging_scaffold",
  "verification_prompt",
  "requirement_clarification",
  "direct_solution",
  "refusal_or_boundary",
  "other",
];
const contextOptions = ["practice", "graded_assignment", "exam", "unknown"];
const ambiguityOptions = ["no", "yes"];

const labelRows = [
  ["answer_seeking", "答案索取", "请求完整答案、完整代码、代写或可直接提交的成品。"],
  ["concept_understanding", "概念理解", "请求概念、原理、步骤提示、思路或示例，主要目标是理解。"],
  ["debugging_help", "调试求助", "提供代码、报错或具体实现，请求定位或修复问题。"],
  ["reflection_verification", "反思验证", "检查已有答案、推理或结论，或主动询问反例、局限与比较。"],
  ["task_clarification", "任务澄清", "澄清题意、范围、输入输出、评分或提交要求。"],
];

async function readJsonl(filename) {
  const raw = await fs.readFile(path.join(dataDir, filename), "utf8");
  return raw.split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
}

function safeText(value, limit = 12000) {
  const text = String(value ?? "");
  return text.length <= limit ? text : `${text.slice(0, limit)}\n[工作簿显示已截断]`;
}

function contextText(items) {
  if (!Array.isArray(items) || items.length === 0) return "（无此前学生消息）";
  return items.map((item, index) => `[学生-${index + 1}] ${safeText(item, 3000)}`).join("\n\n");
}

function setBaseSheetStyle(sheet) {
  sheet.showGridLines = false;
  sheet.getRange("A:P").format.font = { name: "Arial", size: 10, color: "#172033" };
}

function buildAnnotationSheet(sheet, title, subtitle, records, tableName) {
  setBaseSheetStyle(sheet);
  sheet.getRange("A1:P1").merge();
  sheet.getRange("A1").values = [[title]];
  sheet.getRange("A1:P1").format = {
    fill: "#17365D",
    font: { name: "Arial", size: 15, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "left",
    verticalAlignment: "center",
  };
  sheet.getRange("A1:P1").format.rowHeight = 34;

  sheet.getRange("A2:P2").merge();
  sheet.getRange("A2").values = [[subtitle]];
  sheet.getRange("A2:P2").format = {
    fill: "#EAF2F8",
    font: { name: "Arial", size: 10, color: "#17365D", bold: true },
    wrapText: true,
    verticalAlignment: "center",
  };
  sheet.getRange("A2:P2").format.rowHeight = 32;

  sheet.getRange("A3:P3").merge();
  sheet.getRange("A3").values = [[
    "只填写黄色 H:O 列；不要修改 A:G、顺序或标注ID。缺少必要上下文时使用 unclear / unknown，并将歧义标记设为 yes。",
  ]];
  sheet.getRange("A3:P3").format = {
    fill: "#FFF2CC",
    font: { name: "Arial", size: 10, color: "#7F6000" },
    wrapText: true,
    verticalAlignment: "center",
  };
  sheet.getRange("A3:P3").format.rowHeight = 30;

  const headers = [
    "序号",
    "标注ID",
    "阶段",
    "学期",
    "主题",
    "此前学生消息（最多4条；不含助手回复）",
    "当前学生消息",
    "行为标签",
    "尝试证据",
    "需限制答案",
    "帮助强度",
    "推荐策略",
    "评价情境",
    "歧义标记",
    "标注备注",
    "完成状态",
  ];
  sheet.getRange("A4:P4").values = [headers];
  sheet.getRange("A4:P4").format = {
    fill: "#2F5597",
    font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
  };
  sheet.getRange("A4:P4").format.rowHeight = 40;

  const values = records.map((row) => [
    row.order,
    row.annotation_id,
    row.phase,
    row.semester,
    row.topic,
    contextText(row.prior_student_messages),
    safeText(row.student_message),
    row.behavior_label,
    row.attempt_evidence,
    row.answer_restriction_needed,
    row.appropriate_assistance_level,
    row.recommended_strategy,
    row.assessment_context,
    row.ambiguity_flag,
    row.review_notes,
    null,
  ]);
  const firstDataRow = 5;
  const lastDataRow = firstDataRow + records.length - 1;
  sheet.getRangeByIndexes(firstDataRow - 1, 0, records.length, headers.length).values = values;
  for (let row = firstDataRow; row <= lastDataRow; row += 1) {
    sheet.getRange(`P${row}`).formulas = [[
      `=IF(AND(H${row}<>"",I${row}<>"",J${row}<>"",K${row}<>"",L${row}<>"",M${row}<>"",N${row}<>""),"完成","待填写")`,
    ]];
  }

  sheet.getRange(`H${firstDataRow}:H${lastDataRow}`).dataValidation = {
    rule: { type: "list", values: behaviorLabels },
  };
  sheet.getRange(`I${firstDataRow}:J${lastDataRow}`).dataValidation = {
    rule: { type: "list", values: evidenceOptions },
  };
  sheet.getRange(`K${firstDataRow}:K${lastDataRow}`).dataValidation = {
    rule: { type: "list", values: assistanceOptions },
  };
  sheet.getRange(`L${firstDataRow}:L${lastDataRow}`).dataValidation = {
    rule: { type: "list", values: strategyOptions },
  };
  sheet.getRange(`M${firstDataRow}:M${lastDataRow}`).dataValidation = {
    rule: { type: "list", values: contextOptions },
  };
  sheet.getRange(`N${firstDataRow}:N${lastDataRow}`).dataValidation = {
    rule: { type: "list", values: ambiguityOptions },
  };

  sheet.tables.add(`A4:P${lastDataRow}`, true, tableName);
  sheet.freezePanes.freezeRows(4);
  sheet.freezePanes.freezeColumns(2);

  sheet.getRange(`A5:P${lastDataRow}`).format = {
    verticalAlignment: "top",
    borders: { insideHorizontal: { style: "thin", color: "#D9E2F3" } },
  };
  sheet.getRange(`F5:G${lastDataRow}`).format.wrapText = true;
  sheet.getRange(`O5:O${lastDataRow}`).format.wrapText = true;
  sheet.getRange(`H5:O${lastDataRow}`).format.fill = "#FFF8D9";
  sheet.getRange(`A5:E${lastDataRow}`).format.horizontalAlignment = "center";
  sheet.getRange(`H5:N${lastDataRow}`).format.horizontalAlignment = "center";
  sheet.getRange(`P5:P${lastDataRow}`).format.horizontalAlignment = "center";
  sheet.getRange(`A5:P${lastDataRow}`).format.rowHeight = 66;

  sheet.getRange(`P5:P${lastDataRow}`).conditionalFormats.add("containsText", {
    text: "完成",
    format: { fill: "#E2F0D9", font: { color: "#375623", bold: true } },
  });
  sheet.getRange(`P5:P${lastDataRow}`).conditionalFormats.add("containsText", {
    text: "待填写",
    format: { fill: "#F2F2F2", font: { color: "#666666" } },
  });
  sheet.getRange(`N5:N${lastDataRow}`).conditionalFormats.add("containsText", {
    text: "yes",
    format: { fill: "#FCE4D6", font: { color: "#9C0006", bold: true } },
  });

  const widths = {
    A: 7, B: 20, C: 10, D: 9, E: 9, F: 46, G: 58, H: 24,
    I: 14, J: 16, K: 15, L: 25, M: 20, N: 14, O: 38, P: 14,
  };
  for (const [column, width] of Object.entries(widths)) {
    sheet.getRange(`${column}:${column}`).format.columnWidth = width;
  }
  return { firstDataRow, lastDataRow };
}

function buildGuideSheet(sheet, annotatorName) {
  setBaseSheetStyle(sheet);
  sheet.getRange("A1:D1").merge();
  sheet.getRange("A1").values = [[`EduGuard BENCH 2026 Gold 标注说明 · ${annotatorName}`]];
  sheet.getRange("A1:D1").format = {
    fill: "#17365D",
    font: { name: "Arial", size: 15, bold: true, color: "#FFFFFF" },
    verticalAlignment: "center",
  };
  sheet.getRange("A1:D1").format.rowHeight = 34;

  sheet.getRange("A2:D2").merge();
  sheet.getRange("A2").values = [[
    "先独立完成试标50；双方提交后讨论分歧并冻结指南，再开始正式550。正式标注期间不得交流样本判断。详细指南见 BENCH2026-gold-annotation-guide.md。",
  ]];
  sheet.getRange("A2:D2").format = {
    fill: "#EAF2F8",
    font: { name: "Arial", size: 10, color: "#17365D", bold: true },
    wrapText: true,
  };
  sheet.getRange("A2:D2").format.rowHeight = 42;

  sheet.getRange("A4:C4").values = [["行为标签", "中文名称", "判断标准"]];
  sheet.getRange("A5:C9").values = labelRows;
  sheet.getRange("A4:C4").format = {
    fill: "#2F5597",
    font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
  };
  sheet.getRange("A5:C9").format = {
    wrapText: true,
    verticalAlignment: "top",
    borders: { insideHorizontal: { style: "thin", color: "#D9E2F3" } },
  };
  sheet.getRange("A5:C9").format.rowHeight = 38;

  sheet.getRange("A11:D11").values = [["字段", "可选值", "判断重点", "注意事项"]];
  sheet.getRange("A12:D18").values = [
    ["attempt_evidence", "yes / no / unclear", "是否展示可核验的个人尝试", "只说“试过了”通常是 unclear"],
    ["answer_restriction_needed", "yes / no / unclear", "直接回答是否替代应完成的认知工作", "限制不等于拒绝帮助"],
    ["appropriate_assistance_level", "low / medium / high", "合适帮助的直接程度", "不是问题难度"],
    ["recommended_strategy", strategyOptions.join(" / "), "回复的主要教学策略", "other 必须写备注"],
    ["assessment_context", contextOptions.join(" / "), "文本明确呈现的评价场景", "主题代码不能证明是受评任务"],
    ["ambiguity_flag", "no / yes", "缺少上下文是否可能改变判断", "yes 必须写备注"],
    ["review_notes", "自由文本", "记录歧义、other 或关键依据", "其余情况可留空"],
  ];
  sheet.getRange("A11:D11").format = {
    fill: "#2F5597",
    font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
  };
  sheet.getRange("A12:D18").format = {
    wrapText: true,
    verticalAlignment: "top",
    borders: { insideHorizontal: { style: "thin", color: "#D9E2F3" } },
  };
  sheet.getRange("A12:D18").format.rowHeight = 42;

  sheet.getRange("A20:D20").merge();
  sheet.getRange("A20").values = [["建议判定顺序"]];
  sheet.getRange("A20:D20").format = {
    fill: "#D9EAF7",
    font: { name: "Arial", size: 10, bold: true, color: "#17365D" },
  };
  sheet.getRange("A21:D27").values = [
    [1, "主要意图", "解释、调试、验证、澄清还是交付成品？", ""],
    [2, "个人尝试", "是否存在代码、计算、推理、草稿或结果？", ""],
    [3, "答案边界", "直接回答是否替代学生应完成的工作？", ""],
    [4, "帮助强度", "低直接性提示、中等支架还是高直接性解释？", ""],
    [5, "主策略", "选择最匹配的一项推荐策略。", ""],
    [6, "评价情境", "只有文本有证据时才选择非 unknown。", ""],
    [7, "歧义", "缺少上下文是否会改变任一结论？", ""],
  ];
  sheet.getRange("A21:D27").format = {
    wrapText: true,
    verticalAlignment: "top",
    borders: { insideHorizontal: { style: "thin", color: "#D9E2F3" } },
  };
  sheet.getRange("A21:A27").format.horizontalAlignment = "center";
  sheet.freezePanes.freezeRows(2);
  sheet.getRange("A:A").format.columnWidth = 27;
  sheet.getRange("B:B").format.columnWidth = 30;
  sheet.getRange("C:C").format.columnWidth = 65;
  sheet.getRange("D:D").format.columnWidth = 42;
}

function buildProgressSheet(sheet, annotatorName, pilotRows, formalRows) {
  setBaseSheetStyle(sheet);
  sheet.getRange("A1:F1").merge();
  sheet.getRange("A1").values = [[`标注进度 · ${annotatorName}`]];
  sheet.getRange("A1:F1").format = {
    fill: "#17365D",
    font: { name: "Arial", size: 15, bold: true, color: "#FFFFFF" },
    verticalAlignment: "center",
  };
  sheet.getRange("A1:F1").format.rowHeight = 34;
  sheet.getRange("A3:D3").values = [["阶段", "总数", "已完成", "完成率"]];
  sheet.getRange("A4:B5").values = [["试标50", pilotRows], ["正式550", formalRows]];
  sheet.getRange("C4").formulas = [[`=COUNTIF('试标50'!$P$5:$P$${pilotRows + 4},"完成")`]];
  sheet.getRange("C5").formulas = [[`=COUNTIF('正式550'!$P$5:$P$${formalRows + 4},"完成")`]];
  sheet.getRange("D4").formulas = [["=IF(B4=0,0,C4/B4)"]];
  sheet.getRange("D5").formulas = [["=IF(B5=0,0,C5/B5)"]];
  sheet.getRange("D4:D5").format.numberFormat = "0.0%";
  sheet.getRange("A3:D3").format = {
    fill: "#2F5597",
    font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
  };
  sheet.getRange("A4:D5").format = {
    fill: "#F7F9FC",
    horizontalAlignment: "center",
    borders: { insideHorizontal: { style: "thin", color: "#D9E2F3" } },
  };
  sheet.getRange("A7:F7").merge();
  sheet.getRange("A7").values = [[
    "提交门槛：对应阶段完成率达到 100%；ambiguity_flag=yes 或 recommended_strategy=other 的样本必须填写备注。",
  ]];
  sheet.getRange("A7:F7").format = {
    fill: "#FFF2CC",
    font: { name: "Arial", size: 10, color: "#7F6000", bold: true },
    wrapText: true,
  };
  sheet.getRange("A7:F7").format.rowHeight = 38;
  sheet.getRange("A:A").format.columnWidth = 24;
  sheet.getRange("B:D").format.columnWidth = 16;
  sheet.getRange("E:F").format.columnWidth = 18;
}

function buildSingleGuideSheet(sheet, batchName) {
  setBaseSheetStyle(sheet);
  sheet.getRange("A1:D1").merge();
  sheet.getRange("A1").values = [["EduGuard BENCH 2026 单标注者参考集说明"]];
  sheet.getRange("A1:D1").format = {
    fill: "#17365D",
    font: { name: "Arial", size: 15, bold: true, color: "#FFFFFF" },
    verticalAlignment: "center",
  };
  sheet.getRange("A1:D1").format.rowHeight = 34;

  sheet.getRange("A2:D2").merge();
  sheet.getRange("A2").values = [[
    batchName === "正式550"
      ? "本批为首轮正式标注。依据冻结指南独立完成；不要查看 silver 标签或模型预测。完成后记录日期并保存未修改副本。"
      : "本批仅可在正式550完成至少7个完整日历日后开始。标注前及过程中不得查看正式集标签；ID和顺序已盲化。",
  ]];
  sheet.getRange("A2:D2").format = {
    fill: batchName === "正式550" ? "#EAF2F8" : "#FCE4D6",
    font: { name: "Arial", size: 10, color: "#17365D", bold: true },
    wrapText: true,
  };
  sheet.getRange("A2:D2").format.rowHeight = 44;

  sheet.getRange("A4:C4").values = [["行为标签", "中文名称", "判断标准"]];
  sheet.getRange("A5:C9").values = labelRows;
  sheet.getRange("A4:C4").format = {
    fill: "#2F5597",
    font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
  };
  sheet.getRange("A5:C9").format = {
    wrapText: true,
    verticalAlignment: "top",
    borders: { insideHorizontal: { style: "thin", color: "#D9E2F3" } },
  };
  sheet.getRange("A5:C9").format.rowHeight = 40;

  sheet.getRange("A11:D11").values = [["字段", "可选值", "锚点", "注意事项"]];
  sheet.getRange("A12:D18").values = [
    ["attempt_evidence", "yes / no / unclear", "yes=有可核验代码、计算、推理、草稿或结果", "只说“试过了”通常为 unclear"],
    ["answer_restriction_needed", "yes / no / unclear", "直接回答是否替代学生应完成的认知工作", "与行为标签分别判断；限制不等于拒绝帮助"],
    ["appropriate_assistance_level", "low / medium / high", "low=提示；medium=关键支架；high=接近完整解释/方案", "衡量合适的直接程度，不是问题难度"],
    ["recommended_strategy", strategyOptions.join(" / "), "选择回复最主要的教学策略", "other 必须写备注"],
    ["assessment_context", contextOptions.join(" / "), "仅按文本中的评价场景证据判断", "主题代码不能证明是受评任务"],
    ["ambiguity_flag", "no / yes", "缺失上下文是否可能改变任一判断", "yes 必须在备注说明缺什么"],
    ["review_notes", "自由文本", "记录歧义、other 或关键边界依据", "其余情况可留空"],
  ];
  sheet.getRange("A11:D11").format = {
    fill: "#2F5597",
    font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
  };
  sheet.getRange("A12:D18").format = {
    wrapText: true,
    verticalAlignment: "top",
    borders: { insideHorizontal: { style: "thin", color: "#D9E2F3" } },
  };
  sheet.getRange("A12:D14").format.rowHeight = 50;
  sheet.getRange("A15:D15").format.rowHeight = 86;
  sheet.getRange("A16:D16").format.rowHeight = 62;
  sheet.getRange("A17:D18").format.rowHeight = 50;

  sheet.getRange("A20:D20").merge();
  sheet.getRange("A20").values = [["容易混淆的边界"]];
  sheet.getRange("A20:D20").format = {
    fill: "#D9EAF7",
    font: { name: "Arial", size: 10, bold: true, color: "#17365D" },
  };
  sheet.getRange("A21:D25").values = [
    [1, "直接索取可交付成品", "即使没有说“作业”，也优先判 answer_seeking。", ""],
    [2, "debugging vs reflection", "定位/修复具体故障为 debugging；验证已有结论为 reflection。", ""],
    [3, "行为 vs 答案限制", "先判主要意图，再独立判断完整回答是否替代认知工作。", ""],
    [4, "帮助强度", "根据应提供答案的直接程度选择，不根据学生语气或题目难度。", ""],
    [5, "完整规则", "以 BENCH2026-gold-annotation-guide.md 的冻结版本为准。", ""],
  ];
  sheet.getRange("A21:D25").format = {
    wrapText: true,
    verticalAlignment: "top",
    borders: { insideHorizontal: { style: "thin", color: "#D9E2F3" } },
  };
  sheet.getRange("A21:A25").format.horizontalAlignment = "center";
  sheet.freezePanes.freezeRows(2);
  sheet.getRange("A:A").format.columnWidth = 27;
  sheet.getRange("B:B").format.columnWidth = 31;
  sheet.getRange("C:C").format.columnWidth = 66;
  sheet.getRange("D:D").format.columnWidth = 44;
}

function buildSingleProgressSheet(sheet, batchName, rowCount) {
  setBaseSheetStyle(sheet);
  sheet.getRange("A1:F1").merge();
  sheet.getRange("A1").values = [[`标注进度 · ${batchName}`]];
  sheet.getRange("A1:F1").format = {
    fill: "#17365D",
    font: { name: "Arial", size: 15, bold: true, color: "#FFFFFF" },
    verticalAlignment: "center",
  };
  sheet.getRange("A1:F1").format.rowHeight = 34;
  sheet.getRange("A3:D3").values = [["批次", "总数", "已完成", "完成率"]];
  sheet.getRange("A4:B4").values = [[batchName, rowCount]];
  sheet.getRange("C4").formulas = [[`=COUNTIF('${batchName}'!$P$5:$P$${rowCount + 4},"完成")`]];
  sheet.getRange("D4").formulas = [["=IF(B4=0,0,C4/B4)"]];
  sheet.getRange("D4").format.numberFormat = "0.0%";
  sheet.getRange("A3:D3").format = {
    fill: "#2F5597",
    font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
  };
  sheet.getRange("A4:D4").format = {
    fill: "#F7F9FC",
    horizontalAlignment: "center",
  };
  sheet.getRange("A6:B8").values = [
    ["正式集完成日期", "（由标注者填写 YYYY-MM-DD）"],
    ["本批开始日期", "（由标注者填写 YYYY-MM-DD）"],
    ["间隔要求", batchName === "正式550" ? "完成后至少7个完整日历日再做后测60" : "距正式集完成至少7个完整日历日"],
  ];
  sheet.getRange("A6:A8").format = { fill: "#D9EAF7", font: { bold: true, color: "#17365D" } };
  sheet.getRange("B6:B8").format = { fill: "#FFF8D9", wrapText: true };
  sheet.getRange("A10:F10").merge();
  sheet.getRange("A10").values = [[
    "提交门槛：完成率100%；ambiguity_flag=yes 或 recommended_strategy=other 的样本必须填写备注。后测批次不得通过内容搜索或其他方式寻找与正式集的对应关系。",
  ]];
  sheet.getRange("A10:F10").format = {
    fill: "#FFF2CC",
    font: { name: "Arial", size: 10, color: "#7F6000", bold: true },
    wrapText: true,
  };
  sheet.getRange("A10:F10").format.rowHeight = 48;
  sheet.getRange("A:A").format.columnWidth = 24;
  sheet.getRange("B:B").format.columnWidth = 40;
  sheet.getRange("C:D").format.columnWidth = 16;
  sheet.getRange("E:F").format.columnWidth = 18;
}

async function buildSingleWorkbook({
  inputFilename,
  batchName,
  title,
  subtitle,
  tableName,
  outputFilename,
  previewSlug,
}) {
  const records = await readJsonl(inputFilename);
  const workbook = Workbook.create();
  const annotationSheet = workbook.worksheets.add(batchName);
  const guideSheet = workbook.worksheets.add("标签说明");
  const progressSheet = workbook.worksheets.add("进度");

  buildAnnotationSheet(annotationSheet, title, subtitle, records, tableName);
  buildSingleGuideSheet(guideSheet, batchName);
  buildSingleProgressSheet(progressSheet, batchName, records.length);
  workbook.recalculate();

  const checks = [];
  for (const range of [`${batchName}!A1:P10`, "标签说明!A1:D25", "进度!A1:F10"]) {
    const check = await workbook.inspect({
      kind: "table",
      range,
      include: "values,formulas",
      tableMaxRows: 30,
      tableMaxCols: 16,
      tableMaxCellChars: 160,
    });
    checks.push(check.ndjson);
  }
  const errors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
    options: { useRegex: true, maxResults: 300 },
    summary: `${batchName} final formula error scan`,
  });

  const previewDir = path.join(root, "tmp", "bench2026-single-previews", previewSlug);
  await fs.mkdir(previewDir, { recursive: true });
  for (const [sheetName, range, filename] of [
    [batchName, "A1:P10", "annotation.png"],
    ["标签说明", "A1:D25", "guide.png"],
    ["进度", "A1:F10", "progress.png"],
  ]) {
    const rendered = await workbook.render({ sheetName, range, scale: 1, format: "png" });
    await fs.writeFile(path.join(previewDir, filename), new Uint8Array(await rendered.arrayBuffer()));
  }

  await fs.mkdir(outputDir, { recursive: true });
  const outputPath = path.join(outputDir, outputFilename);
  const xlsx = await SpreadsheetFile.exportXlsx(workbook);
  await xlsx.save(outputPath);
  return { outputPath, checks, errors: errors.ndjson };
}

async function buildWorkbook(annotatorKey, annotatorName) {
  const pilot = await readJsonl(`annotator_${annotatorKey}_pilot_50.jsonl`);
  const formal = await readJsonl(`annotator_${annotatorKey}_formal_550.jsonl`);
  const workbook = Workbook.create();
  const pilotSheet = workbook.worksheets.add("试标50");
  const formalSheet = workbook.worksheets.add("正式550");
  const guideSheet = workbook.worksheets.add("标签说明");
  const progressSheet = workbook.worksheets.add("进度");

  buildAnnotationSheet(
    pilotSheet,
    `EduGuard Gold 试标 · ${annotatorName}`,
    "请先独立完成这 50 条。双方都提交后再讨论分歧；试标不计入主 Gold Test。",
    pilot,
    `Pilot${annotatorName.replace("Annotator ", "")}Table`,
  );
  buildAnnotationSheet(
    formalSheet,
    `EduGuard Gold 正式标注 · ${annotatorName}`,
    "仅在试标讨论完成、指南冻结后开始。正式标注期间不要查看或讨论另一名标注者的判断。",
    formal,
    `Formal${annotatorName.replace("Annotator ", "")}Table`,
  );
  buildGuideSheet(guideSheet, annotatorName);
  buildProgressSheet(progressSheet, annotatorName, pilot.length, formal.length);

  workbook.recalculate();
  const checks = [];
  for (const range of ["试标50!A1:P9", "正式550!A1:P9", "标签说明!A1:D27", "进度!A1:F8"]) {
    const check = await workbook.inspect({
      kind: "table",
      range,
      include: "values,formulas",
      tableMaxRows: 30,
      tableMaxCols: 16,
      tableMaxCellChars: 160,
    });
    checks.push(check.ndjson);
  }
  const errors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
    options: { useRegex: true, maxResults: 300 },
    summary: `${annotatorName} final formula error scan`,
  });

  const slug = annotatorKey.toUpperCase();
  const previewDir = path.join(root, "tmp", "bench2026-xlsx-previews", slug);
  await fs.mkdir(previewDir, { recursive: true });
  const previews = [
    ["试标50", "A1:P10", "pilot.png"],
    ["正式550", "A1:P10", "formal.png"],
    ["标签说明", "A1:D27", "guide.png"],
    ["进度", "A1:F8", "progress.png"],
  ];
  for (const [sheetName, range, filename] of previews) {
    const image = await workbook.render({ sheetName, range, scale: 1, format: "png" });
    await fs.writeFile(
      path.join(previewDir, filename),
      new Uint8Array(await image.arrayBuffer()),
    );
  }

  await fs.mkdir(outputDir, { recursive: true });
  const outputPath = path.join(outputDir, `EduGuard_BENCH2026_Annotator_${slug}.xlsx`);
  const xlsx = await SpreadsheetFile.exportXlsx(workbook);
  await xlsx.save(outputPath);
  return { outputPath, checks, errors: errors.ndjson };
}

const results = [];
if (singleMode) {
  results.push(await buildSingleWorkbook({
    inputFilename: "single_annotator_formal_550.jsonl",
    batchName: "正式550",
    title: "EduGuard 单标注者参考集 · 正式550",
    subtitle: "依据冻结指南完成首轮标签。不要查看 silver 标签或模型预测；完成后记录日期、保存未修改副本，并等待至少7个完整日历日。",
    tableName: "SingleFormalTable",
    outputFilename: "EduGuard_BENCH2026_Single_Annotator_Formal.xlsx",
    previewSlug: "formal",
  }));
  results.push(await buildSingleWorkbook({
    inputFilename: "single_annotator_retest_60.jsonl",
    batchName: "后测60",
    title: "EduGuard 单标注者参考集 · 延迟后测60",
    subtitle: "仅在正式550完成至少7个完整日历日后开始。不得查看正式标签或映射；样本ID和顺序已独立盲化。",
    tableName: "SingleRetestTable",
    outputFilename: "EduGuard_BENCH2026_Single_Annotator_Retest.xlsx",
    previewSlug: "retest",
  }));
} else {
  results.push(await buildWorkbook("a", "Annotator A"));
  results.push(await buildWorkbook("b", "Annotator B"));
}
for (const result of results) {
  console.log(JSON.stringify({ outputPath: result.outputPath }));
  for (const check of result.checks) console.log(check);
  console.log(result.errors);
}
