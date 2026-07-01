import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = path.resolve(import.meta.dirname, "..");
const workbookPath = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.join(root, "output", "spreadsheets", "MathDial全量人工标注表_已标注.xlsx");
const sourcePath = process.argv[3]
  ? path.resolve(process.argv[3])
  : path.join(root, "data", "annotation", "mathdial_scaffold_full.jsonl");
const outputDir = process.argv[4]
  ? path.resolve(process.argv[4])
  : path.join(root, "data", "final");

const sourceRows = (await fs.readFile(sourcePath, "utf8"))
  .split(/\r?\n/)
  .filter(Boolean)
  .map((line) => JSON.parse(line));
const sourceById = new Map(sourceRows.map((row) => [row.sample_id, row]));

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));
const sheet = workbook.worksheets.getItem("人工复核");
const values = sheet.getRange(`A2:S${sourceRows.length + 1}`).values;

const validStrategies = new Set([
  "probing_question",
  "error_focus",
  "feedback_prompt",
  "generic_prompt",
  "direct_explanation",
]);
const kept = [];
const excluded = [];
const seen = new Set();

for (const row of values) {
  const sampleId = String(row[18] ?? "").trim();
  if (!sampleId) continue;
  if (seen.has(sampleId)) throw new Error(`工作簿中存在重复样本ID：${sampleId}`);
  seen.add(sampleId);

  const source = sourceById.get(sampleId);
  if (!source) throw new Error(`找不到原始样本：${sampleId}`);

  const strategy = String(row[6] ?? "").trim();
  const disclosure = String(row[8] ?? "").trim();
  const scores = [row[9], row[10], row[11]].map((value) => Number(value));
  const notes = String(row[12] ?? "").trim();

  if (
    !strategy ||
    !disclosure ||
    scores.some((score) => !Number.isInteger(score)) ||
    strategy === "无法判断" ||
    disclosure === "无法判断"
  ) {
    excluded.push({
      ...source,
      reviewed_strategy: strategy,
      reviewed_answer_disclosure: disclosure,
      pedagogical_relevance_score: row[9] ?? "",
      promotes_thinking_score: row[10] ?? "",
      clarity_score: row[11] ?? "",
      review_notes: notes,
      exclusion_reason: notes || "人工复核字段不完整或无法判断",
    });
    continue;
  }
  if (!validStrategies.has(strategy)) {
    throw new Error(`样本 ${sampleId} 的支架策略无效：${strategy}`);
  }
  if (!["是", "否"].includes(disclosure)) {
    throw new Error(`样本 ${sampleId} 的答案泄露判断无效：${disclosure}`);
  }
  if (scores.some((score) => score < 1 || score > 5)) {
    throw new Error(`样本 ${sampleId} 的评分必须为1到5。`);
  }
  kept.push({
    ...source,
    reviewed_strategy: strategy,
    reviewed_answer_disclosure: disclosure === "是" ? "yes" : "no",
    pedagogical_relevance_score: scores[0],
    promotes_thinking_score: scores[1],
    clarity_score: scores[2],
    review_notes: notes,
  });
}

if (seen.size !== sourceRows.length) {
  throw new Error(`工作簿读取到 ${seen.size} 条，原始数据有 ${sourceRows.length} 条。`);
}

async function writeJsonl(filePath, rows) {
  await fs.writeFile(
    filePath,
    rows.map((row) => JSON.stringify(row)).join("\n") + (rows.length ? "\n" : ""),
    "utf8",
  );
}

await fs.mkdir(outputDir, { recursive: true });
await writeJsonl(path.join(outputDir, "mathdial_scaffold_labeled.jsonl"), kept);
await writeJsonl(path.join(outputDir, "mathdial_scaffold_excluded.jsonl"), excluded);
for (const split of ["train", "dev", "test"]) {
  await writeJsonl(
    path.join(outputDir, `mathdial_scaffold_${split}.jsonl`),
    kept.filter((row) => row.split === split),
  );
}

console.log(JSON.stringify({
  workbook: workbookPath,
  source_samples: sourceRows.length,
  exported_samples: kept.length,
  excluded_samples: excluded.length,
  output_dir: outputDir,
}, null, 2));
