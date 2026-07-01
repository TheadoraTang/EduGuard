import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = path.resolve(import.meta.dirname, "..");
const workbookPath = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.join(root, "output", "spreadsheets", "StudyChat全量人工标注表_已标注.xlsx");
const sourcePath = process.argv[3]
  ? path.resolve(process.argv[3])
  : path.join(root, "data", "annotation", "studychat_behavior_full.jsonl");
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
const values = sheet.getRange(`A2:O${sourceRows.length + 1}`).values;

const validLabels = new Set([
  "concept_understanding",
  "answer_seeking",
  "debugging_help",
  "task_clarification",
  "reflection_verification",
]);

const kept = [];
const excluded = [];
const seen = new Set();

for (const row of values) {
  const sampleId = String(row[14] ?? "").trim();
  if (!sampleId) continue;
  if (seen.has(sampleId)) throw new Error(`工作簿中存在重复样本ID：${sampleId}`);
  seen.add(sampleId);

  const source = sourceById.get(sampleId);
  if (!source) throw new Error(`找不到原始样本：${sampleId}`);

  const reviewedLabel = String(row[4] ?? "").trim();
  const reviewNotes = String(row[5] ?? "").trim();
  if (!reviewedLabel) {
    excluded.push({
      ...source,
      reviewed_label: "",
      review_notes: reviewNotes,
      exclusion_reason: reviewNotes || "人工复核标签为空：内容不足或与教学行为分类无关",
    });
    continue;
  }
  if (!validLabels.has(reviewedLabel)) {
    throw new Error(`样本 ${sampleId} 的人工标签无效：${reviewedLabel}`);
  }
  kept.push({
    ...source,
    reviewed_label: reviewedLabel,
    review_notes: reviewNotes,
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
await writeJsonl(path.join(outputDir, "studychat_behavior_labeled.jsonl"), kept);
await writeJsonl(path.join(outputDir, "studychat_behavior_excluded.jsonl"), excluded);
for (const split of ["train", "dev", "test"]) {
  await writeJsonl(
    path.join(outputDir, `studychat_behavior_${split}.jsonl`),
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
