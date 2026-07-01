import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def uuid_str() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now().astimezone()


class UserRole(str, enum.Enum):
    student = "student"
    teacher = "teacher"
    admin = "admin"


class MessageSender(str, enum.Enum):
    student = "student"
    assistant = "assistant"
    system = "system"


class AnalysisMethod(str, enum.Enum):
    rule = "rule"
    llm = "llm"
    ml = "ml"
    manual = "manual"


class RiskLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class ReviewResult(str, enum.Enum):
    confirmed = "confirmed"
    modified = "modified"
    rejected = "rejected"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uuid_str)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(Text, default="demo-only")
    real_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ClassRoom(Base):
    __tablename__ = "classes"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(150))
    teacher_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id"), index=True
    )
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )

    teacher: Mapped[User] = relationship()
    members: Mapped[list["ClassMember"]] = relationship(
        back_populates="classroom", cascade="all, delete-orphan"
    )


class ClassMember(Base):
    __tablename__ = "class_members"

    class_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("classes.id"), primary_key=True
    )
    student_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id"), primary_key=True, index=True
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    classroom: Mapped[ClassRoom] = relationship(back_populates="members")
    student: Mapped[User] = relationship()


class LearningTask(Base):
    __tablename__ = "learning_tasks"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uuid_str)
    class_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("classes.id"), index=True
    )
    created_by: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    task_type: Mapped[str] = mapped_column(String(50))
    knowledge_points: Mapped[list] = mapped_column(JSON, default=list)
    difficulty: Mapped[int] = mapped_column(Integer, default=2)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )

    classroom: Mapped[ClassRoom | None] = relationship()


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uuid_str)
    source: Mapped[str] = mapped_column(String(50), index=True)
    source_version: Mapped[str] = mapped_column(String(30), default="unknown")
    file_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), default="running")
    records_seen: Mapped[int] = mapped_column(Integer, default=0)
    records_created: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("source", "external_record_id", name="uq_conversation_source_external"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uuid_str)
    student_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id"), index=True)
    task_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("learning_tasks.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="active")
    source: Mapped[str] = mapped_column(String(50), default="eduguard")
    external_record_id: Mapped[str | None] = mapped_column(String(255))
    import_batch_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("import_batches.id")
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    student: Mapped[User] = relationship()
    task: Mapped[LearningTask] = relationship()
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.sequence_number",
    )
    reflections: Mapped[list["StudentReflection"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    risks: Mapped[list["RiskAssessment"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class AssignmentSubmission(Base):
    __tablename__ = "assignment_submissions"
    __table_args__ = (
        UniqueConstraint("student_id", "task_id", name="uq_submission_student_task"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uuid_str)
    student_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id"), index=True
    )
    task_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("learning_tasks.id"), index=True
    )
    file_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(150), default="application/octet-stream")
    file_size: Mapped[int] = mapped_column(Integer)
    content: Mapped[bytes] = mapped_column(LargeBinary)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    student: Mapped[User] = relationship()
    task: Mapped[LearningTask] = relationship()


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "sequence_number", name="uq_message_sequence"),
        UniqueConstraint("source", "external_record_id", name="uq_message_source_external"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uuid_str)
    conversation_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("conversations.id"), index=True
    )
    sender: Mapped[MessageSender] = mapped_column(Enum(MessageSender))
    content: Mapped[str] = mapped_column(Text)
    sequence_number: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(50), default="eduguard")
    external_record_id: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    analyses: Mapped[list["BehaviorAnalysis"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )


class BehaviorAnalysis(Base):
    __tablename__ = "behavior_analyses"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uuid_str)
    message_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("messages.id"), index=True
    )
    behavior_type: Mapped[str] = mapped_column(String(50), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    method: Mapped[AnalysisMethod] = mapped_column(Enum(AnalysisMethod))
    explanation: Mapped[str] = mapped_column(Text)
    evidence_text: Mapped[str] = mapped_column(Text, default="")
    model_name: Mapped[str | None] = mapped_column(String(100))
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    message: Mapped[Message] = relationship(back_populates="analyses")


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uuid_str)
    conversation_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("conversations.id"), index=True
    )
    trigger_message_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("messages.id")
    )
    system_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel))
    level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), index=True)
    score: Mapped[float] = mapped_column(Float)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    assessment_version: Mapped[str] = mapped_column(String(30), default="v1")
    review_status: Mapped[str] = mapped_column(String(30), default="recorded")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    conversation: Mapped[Conversation] = relationship(back_populates="risks")
    evidences: Mapped[list["RiskEvidence"]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["TeacherReview"]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan"
    )


class RiskEvidence(Base):
    __tablename__ = "risk_evidences"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uuid_str)
    risk_assessment_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("risk_assessments.id"), index=True
    )
    message_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("messages.id")
    )
    evidence_type: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text)
    weight: Mapped[float] = mapped_column(Float)
    evidence_data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    assessment: Mapped[RiskAssessment] = relationship(back_populates="evidences")


class ScaffoldIntervention(Base):
    __tablename__ = "scaffold_interventions"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uuid_str)
    conversation_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("conversations.id"), index=True
    )
    trigger_message_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("messages.id")
    )
    intervention_level: Mapped[int] = mapped_column(Integer)
    strategy_type: Mapped[str] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text)
    generated_by: Mapped[str] = mapped_column(String(30), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class StudentReflection(Base):
    __tablename__ = "student_reflections"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uuid_str)
    conversation_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("conversations.id"), index=True
    )
    student_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    conversation: Mapped[Conversation] = relationship(back_populates="reflections")


class TeacherReview(Base):
    __tablename__ = "teacher_reviews"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uuid_str)
    risk_assessment_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("risk_assessments.id"), index=True
    )
    teacher_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id"))
    result: Mapped[ReviewResult] = mapped_column(Enum(ReviewResult))
    revised_risk_level: Mapped[RiskLevel | None] = mapped_column(Enum(RiskLevel))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    assessment: Mapped[RiskAssessment] = relationship(back_populates="reviews")
