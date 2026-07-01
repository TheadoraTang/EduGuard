import type { RiskLevel } from "./types";

export const behaviorLabels: Record<string, string> = {
  answer_seeking: "答案索取",
  concept_understanding: "概念理解",
  debugging_help: "调试求助",
  idea_scaffolding: "思路启发",
  reflection_verification: "反思验证",
  critical_questioning: "批判质疑",
  task_clarification: "任务澄清"
};

export const riskLabels: Record<RiskLevel, string> = {
  low: "低风险",
  medium: "中风险",
  high: "高风险"
};

export const riskColors: Record<RiskLevel, string> = {
  low: "#1f9d70",
  medium: "#e89b2c",
  high: "#d84a4a"
};

export const strategyLabels: Record<string, string> = {
  guided_questions: "引导式追问",
  debugging_scaffold: "聚焦错误",
  verification_prompt: "反思验证",
  contrastive_probe: "比较与反例",
  hint: "下一步提示",
  requirement_check: "任务澄清",
  concept_prompt: "概念理解"
};
