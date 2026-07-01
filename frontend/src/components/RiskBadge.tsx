import { Tag } from "antd";
import { riskColors, riskLabels } from "../labels";
import type { RiskLevel } from "../types";

export function RiskBadge({ level }: { level: RiskLevel }) {
  return (
    <Tag color={riskColors[level]} bordered={false}>
      {riskLabels[level]}
    </Tag>
  );
}

