import { describe, expect, it } from "vitest";
import { behaviorLabels, riskLabels, strategyLabels } from "./labels";

describe("display labels", () => {
  it("covers all seven internal behavior types", () => {
    expect(Object.keys(behaviorLabels)).toHaveLength(7);
    expect(behaviorLabels.answer_seeking).toBe("答案索取");
    expect(behaviorLabels.reflection_verification).toBe("反思验证");
  });

  it("covers the three risk levels", () => {
    expect(riskLabels).toEqual({
      low: "低风险",
      medium: "中风险",
      high: "高风险"
    });
  });

  it("covers the EduGuard Tutor demo strategies", () => {
    expect(strategyLabels.guided_questions).toBe("引导式追问");
    expect(strategyLabels.debugging_scaffold).toBe("聚焦错误");
    expect(strategyLabels.verification_prompt).toBe("反思验证");
  });
});
