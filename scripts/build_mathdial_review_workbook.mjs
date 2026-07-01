import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve(import.meta.dirname, "..");
const inputPath = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.join(root, "data", "processed", "mathdial_scaffold_review_300.jsonl");
const outputDir = path.join(root, "output", "spreadsheets");
const outputPath = process.argv[3]
  ? path.resolve(process.argv[3])
  : path.join(outputDir, "MathDial人工复核表.xlsx");

const records = (await fs.readFile(inputPath, "utf8"))
  .split(/\r?\n/)
  .filter(Boolean)
  .map((line) => JSON.parse(line));

function reviewText(value, limit = 5000) {
  const text = String(value ?? "");
  return text.length <= limit
    ? text
    : `${text.slice(0, limit)}\n\n[内容过长，已截断；可按样本ID回查JSONL]`;
}

const strategies = [
  ["probing_question", "探究式追问", "通过问题让学生继续推理，而不是直接讲解答案", "你下一步应该计算什么？"],
  ["error_focus", "聚焦错误", "指出学生推理中的具体错误、遗漏或矛盾", "你为什么认为朋友只有12个轮胎？"],
  ["feedback_prompt", "反馈后追问", "先肯定或反馈已有进展，再提出下一步问题", "开头很好。那么总比例是多少？"],
  ["generic_prompt", "通用提示", "要求学生重试、复查或说明思路，但没有聚焦具体错误", "请再检查一下你的答案。"],
  ["direct_explanation", "直接讲解", "直接解释规则、步骤或结论", "先将总数加回已使用的数量。"],
  ["无法判断", "无法判断", "缺少上下文或同时包含多种策略，无法可靠确定主要策略", "在备注中说明原因"],
];

const workbook = Workbook.create();
const review = workbook.worksheets.add("人工复核");
const guide = workbook.worksheets.add("标注说明");
const progress = workbook.worksheets.add("复核进度");

for (const sheet of [review, guide, progress]) sheet.showGridLines = false;

const headers = [
  "序号",
  "标注状态",
  "数学题目",
  "学生当前回答（判断学生状态）",
  "教师回复（主要复核对象）",
  "自动策略标签",
  "人工复核策略（必填）",
  "自动答案泄露候选",
  "人工判断是否泄露答案（必填）",
  "针对性评分（1-5）",
  "促进思考评分（1-5）",
  "清晰度评分（1-5）",
  "复核备注",
  "MathDial原始教学动作",
  "自动标签来源",
  "数据来源",
  "数据划分",
  "题目ID（匿名）",
  "样本ID",
];

review.getRange("A1:S1").values = [headers];
const rows = records.map((row, index) => [
  index + 1,
  "",
  reviewText(row.problem),
  reviewText(row.student_text),
  reviewText(row.teacher_text),
  row.predicted_strategy,
  row.reviewed_strategy || "",
  row.answer_disclosure_candidate ? "是" : "否",
  row.reviewed_answer_disclosure || "",
  row.pedagogical_relevance_score || "",
  row.promotes_thinking_score || "",
  row.clarity_score || "",
  row.review_notes || "",
  row.source_dialog_act || "无",
  row.strategy_source,
  row.source_file,
  row.split,
  row.problem_id_hash,
  row.sample_id,
]);
review.getRangeByIndexes(1, 0, rows.length, headers.length).values = rows;

for (let row = 2; row <= records.length + 1; row += 1) {
  review.getRange(`B${row}`).formulas = [[
    `=IF(OR(G${row}="",I${row}="",J${row}="",K${row}="",L${row}=""),"未完成",IF(G${row}="无法判断","需二次复核",IF(OR(G${row}<>F${row},I${row}<>H${row}),"已修正","复核完成")))`,
  ]];
}

review.freezePanes.freezeRows(1);
review.freezePanes.freezeColumns(2);
review.getRange(`G2:G${records.length + 1}`).dataValidation = {
  rule: { type: "list", formula1: "'标注说明'!$A$4:$A$9" },
};
review.getRange(`I2:I${records.length + 1}`).dataValidation = {
  rule: { type: "list", values: ["是", "否", "无法判断"] },
};
for (const column of ["J", "K", "L"]) {
  review.getRange(`${column}2:${column}${records.length + 1}`).dataValidation = {
    rule: { type: "whole", operator: "between", formula1: 1, formula2: 5 },
  };
}
review.tables.add(`A1:S${records.length + 1}`, true, "MathDialReviewTable");

review.getRange("A1:S1").format = {
  fill: "#25465F",
  font: { bold: true, color: "#FFFFFF" },
  verticalAlignment: "center",
  horizontalAlignment: "center",
  wrapText: true,
  borders: { preset: "outside", style: "thin", color: "#25465F" },
};
review.getRange("A1:S1").format.rowHeight = 42;
review.getRange(`A2:S${records.length + 1}`).format = {
  verticalAlignment: "top",
  borders: { insideHorizontal: { style: "thin", color: "#E1E7EB" } },
};
review.getRange(`C2:E${records.length + 1}`).format.wrapText = true;
review.getRange(`M2:M${records.length + 1}`).format.wrapText = true;
review.getRange(`G2:M${records.length + 1}`).format.fill = "#FFF7D6";
review.getRange(`H2:H${records.length + 1}`).format.fill = "#EAF2F8";
review.getRange(`A2:B${records.length + 1}`).format.horizontalAlignment = "center";
review.getRange(`F2:L${records.length + 1}`).format.horizontalAlignment = "center";
review.getRange(`N2:Q${records.length + 1}`).format.horizontalAlignment = "center";
review.getRange(`A2:S${records.length + 1}`).format.rowHeight = 72;

const widths = {
  A: 7, B: 15, C: 50, D: 62, E: 48, F: 22, G: 24, H: 18, I: 26,
  J: 17, K: 19, L: 15, M: 38, N: 20, O: 19, P: 28, Q: 11, R: 21, S: 35,
};
for (const [column, width] of Object.entries(widths)) {
  review.getRange(`${column}:${column}`).format.columnWidth = width;
}

const statusRange = review.getRange(`B2:B${records.length + 1}`);
statusRange.conditionalFormats.add("containsText", {
  text: "复核完成",
  format: { fill: "#E3F4E8", font: { color: "#176B3A" } },
});
statusRange.conditionalFormats.add("containsText", {
  text: "已修正",
  format: { fill: "#FFF0C7", font: { color: "#8A5A00" } },
});
statusRange.conditionalFormats.add("containsText", {
  text: "未完成",
  format: { fill: "#F0F2F5", font: { color: "#667085" } },
});
statusRange.conditionalFormats.add("containsText", {
  text: "需二次复核",
  format: { fill: "#FDE6E3", font: { color: "#B42318" } },
});

guide.getRange("A1:D1").merge();
guide.getRange("A1").values = [["MathDial 支架策略人工复核说明"]];
guide.getRange("A1:D1").format = {
  fill: "#25465F",
  font: { bold: true, color: "#FFFFFF", size: 18 },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
guide.getRange("A1:D1").format.rowHeight = 42;
guide.getRange("A2:D2").merge();
guide.getRange("A2").values = [[
  "只填写“人工复核”表中的黄色区域：G列策略、I列答案泄露、J-L列三项评分；有歧义、修正或选择“无法判断”时在M列说明。",
]];
guide.getRange("A2:D2").format = {
  fill: "#E7F0F5",
  font: { bold: true, color: "#25465F" },
  wrapText: true,
  verticalAlignment: "center",
};
guide.getRange("A2:D2").format.rowHeight = 44;
guide.getRange("A3:D3").values = [["内部标签", "中文名称", "判断标准", "典型回复"]];
guide.getRange("A4:D9").values = strategies;
guide.getRange("A3:D3").format = {
  fill: "#47728C",
  font: { bold: true, color: "#FFFFFF" },
};
guide.getRange("A3:D9").format.wrapText = true;
guide.getRange("A4:D9").format.borders = {
  insideHorizontal: { style: "thin", color: "#D7E1E7" },
};

guide.getRange("A11:D11").merge();
guide.getRange("A11").values = [["评分与答案泄露判断"]];
guide.getRange("A11:D11").format = {
  fill: "#D9E8EF",
  font: { bold: true, color: "#25465F" },
};
guide.getRange("A12:D18").values = [
  ["项目", "1分", "3分", "5分"],
  ["针对性", "基本没有回应学生当前错误", "部分相关，但比较泛化", "准确针对学生当前错误或困惑"],
  ["促进思考", "直接代替学生完成推理", "有一定提示，但学生参与有限", "通过适当问题或提示促进学生继续推理"],
  ["清晰度", "表达混乱或难以理解", "基本清楚但可进一步精炼", "表达明确、简洁且适合学生"],
  ["答案泄露：是", "直接给出最终答案，或完整给出核心计算，使学生无需继续推理", "", ""],
  ["答案泄露：否", "只给问题、局部提示或错误定位，学生仍需完成关键推理", "", ""],
  ["无法判断", "上下文不足时选择，并在备注中说明缺少什么信息", "", ""],
];
guide.getRange("A12:D12").format = {
  fill: "#47728C",
  font: { bold: true, color: "#FFFFFF" },
};
guide.getRange("A12:D18").format.wrapText = true;
guide.getRange("A:A").format.columnWidth = 25;
guide.getRange("B:B").format.columnWidth = 38;
guide.getRange("C:C").format.columnWidth = 38;
guide.getRange("D:D").format.columnWidth = 42;
guide.freezePanes.freezeRows(3);

progress.getRange("A1:F1").merge();
progress.getRange("A1").values = [["MathDial 复核进度"]];
progress.getRange("A1:F1").format = {
  fill: "#25465F",
  font: { bold: true, color: "#FFFFFF", size: 18 },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
progress.getRange("A1:F1").format.rowHeight = 42;
progress.getRange("A3:B7").values = [
  ["指标", "数量"],
  ["样本总数", records.length],
  ["已完成", null],
  ["未完成", null],
  ["完成率", null],
];
progress.getRange("B5").formulas = [[
  `=COUNTIF('人工复核'!$B$2:$B$${records.length + 1},"复核完成")+COUNTIF('人工复核'!$B$2:$B$${records.length + 1},"已修正")`,
]];
progress.getRange("B6").formulas = [["=B4-B5"]];
progress.getRange("B7").formulas = [["=IF(B4=0,0,B5/B4)"]];
progress.getRange("B7").format.numberFormat = "0.0%";
progress.getRange("A3:B3").format = {
  fill: "#47728C",
  font: { bold: true, color: "#FFFFFF" },
};
progress.getRange("A4:B7").format = {
  fill: "#F5F8FA",
  borders: { insideHorizontal: { style: "thin", color: "#D7E1E7" } },
};

progress.getRange("D3:F3").values = [["人工复核策略", "数量", "占比"]];
progress.getRange("D3:F3").format = {
  fill: "#47728C",
  font: { bold: true, color: "#FFFFFF" },
};
const strategyLabels = strategies.map((row) => row[0]);
progress.getRange(`D4:D${3 + strategyLabels.length}`).values =
  strategyLabels.map((label) => [label]);
for (let row = 4; row < 4 + strategyLabels.length; row += 1) {
  progress.getRange(`E${row}`).formulas = [[
    `=COUNTIF('人工复核'!$G$2:$G$${records.length + 1},D${row})`,
  ]];
  progress.getRange(`F${row}`).formulas = [["=IF($B$5=0,0,E" + row + "/$B$5)"]];
}
progress.getRange(`F4:F${3 + strategyLabels.length}`).format.numberFormat = "0.0%";
progress.getRange(`D4:F${3 + strategyLabels.length}`).format.borders = {
  insideHorizontal: { style: "thin", color: "#D7E1E7" },
};

progress.getRange("A10:B14").values = [
  ["质量指标", "平均分"],
  ["针对性", null],
  ["促进思考", null],
  ["清晰度", null],
  ["答案泄露率", null],
];
progress.getRange("B11").formulas = [[`=IFERROR(AVERAGE('人工复核'!$J$2:$J$${records.length + 1}),0)`]];
progress.getRange("B12").formulas = [[`=IFERROR(AVERAGE('人工复核'!$K$2:$K$${records.length + 1}),0)`]];
progress.getRange("B13").formulas = [[`=IFERROR(AVERAGE('人工复核'!$L$2:$L$${records.length + 1}),0)`]];
progress.getRange("B14").formulas = [[
  `=IFERROR(COUNTIF('人工复核'!$I$2:$I$${records.length + 1},"是")/COUNTIF('人工复核'!$I$2:$I$${records.length + 1},"<>"),0)`,
]];
progress.getRange("B11:B13").format.numberFormat = "0.00";
progress.getRange("B14").format.numberFormat = "0.0%";
progress.getRange("A10:B10").format = {
  fill: "#47728C",
  font: { bold: true, color: "#FFFFFF" },
};
progress.getRange("A11:B14").format = {
  fill: "#F5F8FA",
  borders: { insideHorizontal: { style: "thin", color: "#D7E1E7" } },
};
progress.getRange("A:A").format.columnWidth = 24;
progress.getRange("B:B").format.columnWidth = 18;
progress.getRange("D:D").format.columnWidth = 28;
progress.getRange("E:F").format.columnWidth = 14;

await fs.mkdir(outputDir, { recursive: true });

for (const [sheetName, range, fileName] of [
  ["人工复核", "A1:M7", "mathdial-review-preview.png"],
  ["标注说明", "A1:D18", "mathdial-guide-preview.png"],
  ["复核进度", "A1:F14", "mathdial-progress-preview.png"],
]) {
  const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(
    path.join(outputDir, fileName),
    new Uint8Array(await preview.arrayBuffer()),
  );
}

const check = await workbook.inspect({
  kind: "table",
  range: "人工复核!A1:M6",
  include: "values,formulas",
  tableMaxRows: 6,
  tableMaxCols: 13,
});
console.log(check.ndjson);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "formula error scan",
});
console.log(errors.ndjson);

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(outputPath);
console.log(outputPath);
