from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import ReviewResult, RiskLevel, UserRole


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TaskOut(ORMModel):
    id: str
    title: str
    description: str
    task_type: str
    knowledge_points: list
    difficulty: int
    class_id: str | None = None
    is_published: bool = True


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(ORMModel):
    id: str
    username: str
    real_name: str
    role: UserRole


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ClassCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=2000)


class ClassOut(ORMModel):
    id: str
    name: str
    description: str | None
    teacher_id: str


class StudentCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=6, max_length=128)
    real_name: str = Field(min_length=2, max_length=100)


class TaskCreate(BaseModel):
    class_id: str
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=5, max_length=10000)
    task_type: str = Field(default="programming", max_length=50)
    knowledge_points: list[str] = []
    difficulty: int = Field(default=2, ge=1, le=5)
    is_published: bool = False


class TaskUpdate(BaseModel):
    class_id: str | None = None
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, min_length=5, max_length=10000)
    task_type: str | None = Field(default=None, max_length=50)
    knowledge_points: list[str] | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    is_published: bool | None = None


class ConversationSummary(BaseModel):
    id: str
    task_title: str
    status: str
    started_at: datetime
    latest_risk_level: str | None


class ConversationCreate(BaseModel):
    task_id: str
    student_id: str | None = None


class ConversationCreated(BaseModel):
    id: str
    student_id: str
    task_id: str
    status: str


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=12000)


class AnalysisOut(ORMModel):
    behavior_type: str
    confidence: float
    method: str
    explanation: str
    evidence_text: str
    is_selected: bool
    needs_review: bool


class MessageOut(ORMModel):
    id: str
    sender: str
    content: str
    sequence_number: int
    created_at: datetime
    analyses: list[AnalysisOut] = []


class EvidenceOut(ORMModel):
    id: str
    evidence_type: str
    description: str
    weight: float
    evidence_data: dict


class RiskOut(ORMModel):
    id: str
    system_level: str
    level: str
    score: float
    reasons: list
    review_status: str
    created_at: datetime
    evidences: list[EvidenceOut] = []


class TutorDecisionOut(BaseModel):
    behavior_type: str
    risk_level: str
    risk_score: float
    intervention_level: int
    strategy_type: str
    strategy_reason: str
    response_policy: str
    allow_direct_answer: bool
    generated_by: str
    generation_model: str | None = None


class ConversationDetail(BaseModel):
    id: str
    status: str
    student_name: str
    task: TaskOut
    messages: list[MessageOut]
    latest_risk: RiskOut | None
    reflections: list[str]
    submission: "SubmissionOut | None" = None


class SubmissionOut(ORMModel):
    id: str
    student_id: str
    task_id: str
    file_name: str
    content_type: str
    file_size: int
    uploaded_at: datetime


class InteractionResult(BaseModel):
    student_message: MessageOut
    assistant_message: MessageOut
    selected_analysis: AnalysisOut
    risk: RiskOut
    intervention_level: int
    tutor_decision: TutorDecisionOut


class ReflectionCreate(BaseModel):
    content: str = Field(min_length=2, max_length=5000)


class ReflectionOut(ORMModel):
    id: str
    content: str
    created_at: datetime


class DashboardSummary(BaseModel):
    total_conversations: int
    teacher_updates: int
    risk_distribution: dict[str, int]
    behavior_distribution: dict[str, int]
    recent_conversations: list[dict]


class ConversationDiagnosisOut(BaseModel):
    risk_id: str
    conversation_id: str
    turn_number: int | None
    trigger_message: str
    behavior_type: str | None
    system_level: str
    level: str
    score: float
    review_status: str
    created_at: datetime


class RiskDetail(BaseModel):
    risk: RiskOut
    conversation_id: str
    student_name: str
    task_title: str
    trigger_message: str
    selected_behavior: str | None
    tutor_decision: TutorDecisionOut | None = None
    reviews: list[dict]


class ReviewCreate(BaseModel):
    revised_risk_level: RiskLevel | None = None
    comment: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_teacher_update(self):
        if self.revised_risk_level is None and not (self.comment or "").strip():
            raise ValueError("risk level or comment is required")
        return self


class ReviewOut(ORMModel):
    id: str
    result: str
    revised_risk_level: str | None
    comment: str | None
    created_at: datetime
