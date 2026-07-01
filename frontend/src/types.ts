export type RiskLevel = "low" | "medium" | "high";
export type UserRole = "student" | "teacher" | "admin";

export interface User {
  id: string;
  username: string;
  real_name: string;
  role: UserRole;
}

export interface ClassRoom {
  id: string;
  name: string;
  description: string | null;
  teacher_id: string;
}

export interface Task {
  id: string;
  title: string;
  description: string;
  task_type: string;
  knowledge_points: string[];
  difficulty: number;
  class_id: string | null;
  is_published: boolean;
}

export interface Analysis {
  behavior_type: string;
  confidence: number;
  method: string;
  explanation: string;
  evidence_text: string;
  is_selected: boolean;
  needs_review: boolean;
}

export interface Message {
  id: string;
  sender: "student" | "assistant" | "system";
  content: string;
  sequence_number: number;
  created_at: string;
  analyses: Analysis[];
}

export interface Evidence {
  id: string;
  evidence_type: string;
  description: string;
  weight: number;
  evidence_data: Record<string, unknown>;
}

export interface Risk {
  id: string;
  system_level: RiskLevel;
  level: RiskLevel;
  score: number;
  reasons: string[];
  review_status: string;
  created_at: string;
  evidences: Evidence[];
}

export interface InteractionResult {
  student_message: Message;
  assistant_message: Message;
  selected_analysis: Analysis;
  risk: Risk;
  intervention_level: number;
  tutor_decision: TutorDecision;
}

export interface TutorDecision {
  behavior_type: string;
  risk_level: RiskLevel;
  risk_score: number;
  intervention_level: number;
  strategy_type: string;
  strategy_reason: string;
  response_policy: string;
  allow_direct_answer: boolean;
  generated_by: string;
  generation_model: string | null;
}

export interface ConversationSummary {
  id: string;
  task_title: string;
  status: string;
  started_at: string;
  latest_risk_level: RiskLevel | null;
}

export interface ConversationDetail {
  id: string;
  status: string;
  student_name: string;
  task: Task;
  messages: Message[];
  latest_risk: Risk | null;
  reflections: string[];
  submission: Submission | null;
}

export interface Submission {
  id: string;
  student_id: string;
  task_id: string;
  file_name: string;
  content_type: string;
  file_size: number;
  uploaded_at: string;
}

export interface Dashboard {
  total_conversations: number;
  teacher_updates: number;
  risk_distribution: Record<RiskLevel, number>;
  behavior_distribution: Record<string, number>;
  recent_conversations: Array<{
    conversation_id: string;
    task_id: string;
    class_id: string | null;
    class_name: string | null;
    student_name: string;
    task_title: string;
    diagnosis_count: number;
    teacher_update_count: number;
    risk_distribution: Record<RiskLevel, number>;
    behavior_distribution: Record<string, number>;
    latest_risk_level: RiskLevel | null;
    latest_risk_score: number | null;
    last_diagnosed_at: string | null;
    started_at: string;
  }>;
}

export interface ConversationDiagnosis {
  risk_id: string;
  conversation_id: string;
  turn_number: number | null;
  trigger_message: string;
  behavior_type: string | null;
  system_level: RiskLevel;
  level: RiskLevel;
  score: number;
  review_status: string;
  created_at: string;
}

export interface RiskDetail {
  risk: Risk;
  conversation_id: string;
  student_name: string;
  task_title: string;
  trigger_message: string;
  selected_behavior: string | null;
  tutor_decision: TutorDecision | null;
  reviews: Array<{
    id: string;
    result: string;
    revised_risk_level: RiskLevel | null;
    comment: string | null;
    created_at: string;
  }>;
}
