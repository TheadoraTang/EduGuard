import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve(import.meta.dirname, "..");
const inputPath = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.join(root, "data", "processed", "studychat_review_300.jsonl");
const outputDir = path.join(root, "output", "spreadsheets");
const outputPath = process.argv[3]
  ? path.resolve(process.argv[3])
  : path.join(outputDir, "StudyChat人工复核表.xlsx");

const raw = await fs.readFile(inputPath, "utf8");
const records = raw
  .split(/\r?\n/)
  .filter(Boolean)
  .map((line) => JSON.parse(line));

function reviewText(value) {
  const text = String(value ?? "");
  const limit = 8000;
  return text.length <= limit
    ? text
    : `${text.slice(0, limit)}\n\n[内容过长，复核表中已截断；如确有需要，可按样本ID回查原始JSONL]`;
}

const labelRows = [
  ["answer_seeking", "答案索取", "索要完整答案、完整代码、代写或可直接提交内容", "直接写完整代码给我"],
  ["concept_understanding", "概念理解", "请求解释概念、原理、提示、步骤或解题方向", "递归终止条件是什么？ / 给我第一步提示"],
  ["debugging_help", "调试求助", "提供代码、错误或输出，请求定位具体问题", "这里为什么出现 AttributeError？"],
  ["reflection_verification", "反思验证", "检查、反思或质疑已有理解、结果或结论", "我的复杂度分析对吗？ / 这个结论有反例吗？"],
  ["task_clarification", "任务澄清", "澄清题意、输入输出、作业要求或提交格式", "需要提交哪些文件？"]
];

const workbook = Workbook.create();
const review = workbook.worksheets.add("人工复核");
const guide = workbook.worksheets.add("标签说明");
const progress = workbook.worksheets.add("复核进度");

review.showGridLines = false;
guide.showGridLines = false;
progress.showGridLines = false;

const headers = [
  "序号",
  "标注状态",
  "学生提问（主要判断依据）",
  "初始预测标签",
  "人工复核标签（必填）",
  "复核备注（修正或无法判断时填写）",
  "StudyChat原始标签",
  "映射可信度",
  "原始标签说明",
  "作业主题",
  "学期",
  "数据划分",
  "对话ID（匿名）",
  "学生ID（匿名）",
  "样本ID"
];

review.getRange("A1:O1").values = [headers];
const values = records.map((row, index) => [
  index + 1,
  "",
  reviewText(row.text),
  row.predicted_label,
  row.reviewed_label || "",
  row.review_notes || "",
  row.source_label,
  row.mapping_strength,
  row.source_justification,
  row.topic,
  row.semester,
  row.split,
  row.chat_id_hash,
  row.user_id_hash,
  row.sample_id
]);
review.getRangeByIndexes(1, 0, values.length, headers.length).values = values;

for (let row = 2; row <= records.length + 1; row += 1) {
  review.getRange(`B${row}`).formulas = [
    [`=IF(E${row}="","未标注",IF(E${row}=D${row},"同意初始判断","已修正"))`]
  ];
}

review.freezePanes.freezeRows(1);
review.freezePanes.freezeColumns(2);
review.getRange(`E2:E${records.length + 1}`).dataValidation = {
  rule: {
    type: "list",
    formula1: "'标签说明'!$A$4:$A$8"
  }
};
review.tables.add(`A1:O${records.length + 1}`, true, "StudyChatReviewTable");

review.getRange("A1:O1").format = {
  fill: "#243B64",
  font: { bold: true, color: "#FFFFFF" },
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "outside", style: "thin", color: "#243B64" }
};
review.getRange("A1:O1").format.rowHeight = 36;
review.getRange(`A2:O${records.length + 1}`).format = {
  verticalAlignment: "top",
  borders: {
    insideHorizontal: { style: "thin", color: "#E6EAF0" }
  }
};
review.getRange(`C2:C${records.length + 1}`).format.wrapText = true;
review.getRange(`F2:F${records.length + 1}`).format.wrapText = true;
review.getRange(`I2:I${records.length + 1}`).format.wrapText = true;
review.getRange(`E2:F${records.length + 1}`).format.fill = "#FFF8D9";
review.getRange(`A2:B${records.length + 1}`).format.horizontalAlignment = "center";
review.getRange(`D2:E${records.length + 1}`).format.horizontalAlignment = "center";
review.getRange(`H2:H${records.length + 1}`).format.horizontalAlignment = "center";
review.getRange(`J2:L${records.length + 1}`).format.horizontalAlignment = "center";

const widths = {
  A: 7, B: 16, C: 68, D: 23, E: 25, F: 42, G: 34, H: 16,
  I: 56, J: 12, K: 10, L: 11, M: 27, N: 27, O: 39
};
for (const [column, width] of Object.entries(widths)) {
  review.getRange(`${column}:${column}`).format.columnWidth = width;
}
review.getRange(`A2:O${records.length + 1}`).format.rowHeight = 54;

review.getRange(`B2:B${records.length + 1}`).conditionalFormats.add(
  "containsText",
  { text: "同意初始判断", format: { fill: "#E6F4EA", font: { color: "#176B3A" } } }
);
review.getRange(`B2:B${records.length + 1}`).conditionalFormats.add(
  "containsText",
  { text: "已修正", format: { fill: "#FFF1CC", font: { color: "#8A5A00" } } }
);
review.getRange(`B2:B${records.length + 1}`).conditionalFormats.add(
  "containsText",
  { text: "未标注", format: { fill: "#F1F3F6", font: { color: "#667085" } } }
);
guide.getRange("A1:D1").merge();
guide.getRange("A1").values = [["StudyChat 人工复核说明"]];
guide.getRange("A1:D1").format = {
  fill: "#243B64",
  font: { bold: true, color: "#FFFFFF", size: 18 },
  horizontalAlignment: "center",
  verticalAlignment: "center"
};
guide.getRange("A1:D1").format.rowHeight = 42;
guide.getRange("A2:D2").merge();
guide.getRange("A2").values = [[
  "你只需要填写“人工复核”表中的黄色两列：E列只能选择五类最终标签；若修改初始标签或暂时无法判断，在F列写明原因。无法判断时先保持E列空白，待二次复核。"
]];
guide.getRange("A2:D2").format = {
  fill: "#EAF0FF",
  font: { color: "#243B64", bold: true },
  wrapText: true,
  verticalAlignment: "center"
};
guide.getRange("A2:D2").format.rowHeight = 42;
guide.getRange("A3:D3").values = [["内部标签", "中文名称", "判断标准", "典型表达"]];
guide.getRange("A4:D8").values = labelRows;
guide.getRange("A3:D3").format = {
  fill: "#486A9A",
  font: { bold: true, color: "#FFFFFF" }
};
guide.getRange("A3:D8").format.wrapText = true;
guide.getRange("A4:D8").format.borders = {
  insideHorizontal: { style: "thin", color: "#D9E0EA" }
};
guide.getRange("A13:D13").merge();
guide.getRange("A13").values = [["复核时重点判断"]];
guide.getRange("A13:D13").format = {
  fill: "#DCE6F5",
  font: { bold: true, color: "#243B64" }
};
guide.getRange("A14:D18").values = [
  ["1", "当前学生主要希望 AI 做什么？", "解释知识、调试代码、直接代做，还是检查自己的结果？", ""],
  ["2", "是否存在个人尝试？", "提供代码或报错通常是调试求助，不应因出现“代码”二字就标为答案索取。", ""],
  ["3", "提示或质疑如何归类？", "提示、步骤和解题方向归入概念理解；质疑、比较、局限和反例归入反思验证。", ""],
  ["4", "是否要求可直接提交内容？", "完整代码、完整报告、代写和按要求生成成品通常属于答案索取。", ""],
  ["5", "消息是否缺少上下文？", "无法单独判断时先保持标签空白并写备注，交由二次复核；这里不判断风险等级。", ""]
];
guide.getRange("A14:D18").format.wrapText = true;
guide.getRange("A:A").format.columnWidth = 24;
guide.getRange("B:B").format.columnWidth = 24;
guide.getRange("C:C").format.columnWidth = 66;
guide.getRange("D:D").format.columnWidth = 34;
guide.freezePanes.freezeRows(3);

progress.getRange("A1:F1").merge();
progress.getRange("A1").values = [["StudyChat 复核进度"]];
progress.getRange("A1:F1").format = {
  fill: "#243B64",
  font: { bold: true, color: "#FFFFFF", size: 18 },
  horizontalAlignment: "center",
  verticalAlignment: "center"
};
progress.getRange("A1:F1").format.rowHeight = 42;
progress.getRange("A3:B7").values = [
  ["指标", "数量"],
  ["样本总数", records.length],
  ["已完成", null],
  ["未完成", null],
  ["完成率", null]
];
progress.getRange("B5").formulas = [[`=COUNTIF('人工复核'!$E$2:$E$${records.length + 1},"?*")`]];
progress.getRange("B6").formulas = [[`=B4-B5`]];
progress.getRange("B7").formulas = [["=IF(B4=0,0,B5/B4)"]];
progress.getRange("B7").format.numberFormat = "0.0%";
progress.getRange("A3:B3").format = {
  fill: "#486A9A",
  font: { bold: true, color: "#FFFFFF" }
};
progress.getRange("A4:B7").format = {
  fill: "#F7F9FC",
  borders: { insideHorizontal: { style: "thin", color: "#D9E0EA" } }
};
progress.getRange("A:A").format.columnWidth = 24;
progress.getRange("B:B").format.columnWidth = 18;

progress.getRange("D3:F3").values = [["人工复核标签", "数量", "占比"]];
progress.getRange("D3:F3").format = {
  fill: "#486A9A",
  font: { bold: true, color: "#FFFFFF" }
};
const progressLabels = labelRows.map((row) => row[0]);
progress.getRange(`D4:D${3 + progressLabels.length}`).values =
  progressLabels.map((label) => [label]);
for (let row = 4; row < 4 + progressLabels.length; row += 1) {
  progress.getRange(`E${row}`).formulas = [
    [`=COUNTIF('人工复核'!$E$2:$E$${records.length + 1},D${row})`]
  ];
  progress.getRange(`F${row}`).formulas = [[`=IF($B$5=0,0,E${row}/$B$5)`]];
}
progress.getRange(`F4:F${3 + progressLabels.length}`).format.numberFormat = "0.0%";
progress.getRange(`D4:F${3 + progressLabels.length}`).format.borders = {
  insideHorizontal: { style: "thin", color: "#D9E0EA" }
};
progress.getRange("D:D").format.columnWidth = 28;
progress.getRange("E:F").format.columnWidth = 14;

await fs.mkdir(outputDir, { recursive: true });

const reviewPreview = await workbook.render({
  sheetName: "人工复核",
  range: "A1:I8",
  scale: 1,
  format: "png"
});
await fs.writeFile(
  path.join(outputDir, "studychat-review-preview.png"),
  new Uint8Array(await reviewPreview.arrayBuffer())
);
const guidePreview = await workbook.render({
  sheetName: "标签说明",
  range: "A1:D18",
  scale: 1,
  format: "png"
});
await fs.writeFile(
  path.join(outputDir, "studychat-guide-preview.png"),
  new Uint8Array(await guidePreview.arrayBuffer())
);
const progressPreview = await workbook.render({
  sheetName: "复核进度",
  range: "A1:F12",
  scale: 1,
  format: "png"
});
await fs.writeFile(
  path.join(outputDir, "studychat-progress-preview.png"),
  new Uint8Array(await progressPreview.arrayBuffer())
);

const check = await workbook.inspect({
  kind: "table",
  range: "人工复核!A1:I6",
  include: "values,formulas",
  tableMaxRows: 6,
  tableMaxCols: 9,
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
