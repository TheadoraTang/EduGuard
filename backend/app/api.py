from datetime import datetime
from pathlib import Path
from urllib.parse import quote, unquote
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload

from .auth import (
    create_access_token,
    get_current_user,
    hash_password,
    require_role,
    verify_password,
)
from .db import get_db
from .models import (
    AnalysisMethod,
    AssignmentSubmission,
    BehaviorAnalysis,
    ClassMember,
    ClassRoom,
    Conversation,
    LearningTask,
    Message,
    MessageSender,
    ReviewResult,
    RiskAssessment,
    RiskEvidence,
    RiskLevel,
    ScaffoldIntervention,
    StudentReflection,
    TeacherReview,
    User,
    UserRole,
)
from .schemas import (
    AnalysisOut,
    ClassCreate,
    ClassOut,
    ConversationCreate,
    ConversationCreated,
    ConversationDiagnosisOut,
    ConversationDetail,
    ConversationSummary,
    DashboardSummary,
    InteractionResult,
    LoginRequest,
    LoginResponse,
    MessageCreate,
    MessageOut,
    ReflectionCreate,
    ReflectionOut,
    ReviewCreate,
    ReviewOut,
    RiskDetail,
    RiskOut,
    StudentCreate,
    SubmissionOut,
    TaskCreate,
    TaskOut,
    TaskUpdate,
    TutorDecisionOut,
    UserOut,
)
from .services.analysis import classify_student_message
from .services.eduguard_tutor import run_eduguard_tutor
from .services.risk import assess_risk
from .services.seed import DEMO_STUDENT_ID, DEMO_TEACHER_ID


router = APIRouter()
MAX_SUBMISSION_SIZE = 10 * 1024 * 1024
MAX_TASK_IMAGE_SIZE = 5 * 1024 * 1024
TASK_IMAGE_TYPES = {
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
TASK_IMAGE_DIR = Path(__file__).resolve().parents[2] / "data" / "uploads" / "task-images"


def tutor_decision_out(data: dict | None) -> TutorDecisionOut | None:
    if not data:
        return None
    allowed = TutorDecisionOut.model_fields
    return TutorDecisionOut(**{key: value for key, value in data.items() if key in allowed})


def teacher_owns_conversation(db: Session, teacher_id: str, conversation: Conversation) -> bool:
    task = db.get(LearningTask, conversation.task_id)
    if not task:
        return False
    if task.created_by == teacher_id:
        return True
    classroom = db.get(ClassRoom, task.class_id) if task.class_id else None
    return bool(classroom and classroom.teacher_id == teacher_id)


def student_can_access_task(db: Session, student_id: str, task: LearningTask) -> bool:
    if not task.is_published:
        return False
    membership = db.get(ClassMember, (task.class_id, student_id)) if task.class_id else None
    return membership is not None


@router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    return LoginResponse(access_token=create_access_token(user), user=UserOut.model_validate(user))


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


def get_conversation_or_404(db: Session, conversation_id: str) -> Conversation:
    conversation = db.scalar(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(
            selectinload(Conversation.student),
            selectinload(Conversation.task),
            selectinload(Conversation.messages).selectinload(Message.analyses),
            selectinload(Conversation.risks).selectinload(RiskAssessment.evidences),
            selectinload(Conversation.reflections),
        )
    )
    if not conversation:
        raise HTTPException(404, "conversation not found")
    return conversation


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == UserRole.student:
        class_ids = select(ClassMember.class_id).where(ClassMember.student_id == user.id)
        statement = select(LearningTask).where(
            LearningTask.is_published.is_(True),
            LearningTask.class_id.in_(class_ids),
        )
    else:
        statement = select(LearningTask).where(LearningTask.created_by == user.id)
    return db.scalars(statement.order_by(desc(LearningTask.created_at))).all()


@router.get("/student/conversations", response_model=list[ConversationSummary])
def student_conversations(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.student)),
):
    conversations = db.scalars(
        select(Conversation)
        .where(Conversation.student_id == user.id, Conversation.source == "eduguard")
        .order_by(desc(Conversation.started_at))
    ).all()
    result = []
    for item in conversations:
        task = db.get(LearningTask, item.task_id)
        latest = db.scalar(
            select(RiskAssessment)
            .where(RiskAssessment.conversation_id == item.id)
            .order_by(desc(RiskAssessment.created_at))
            .limit(1)
        )
        result.append(
            ConversationSummary(
                id=item.id,
                task_title=task.title,
                status=item.status,
                started_at=item.started_at,
                latest_risk_level=latest.level.value if latest else None,
            )
        )
    return result


@router.post("/teacher/classes", response_model=ClassOut, status_code=201)
def create_class(
    payload: ClassCreate,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_role(UserRole.teacher, UserRole.admin)),
):
    classroom = ClassRoom(
        name=payload.name,
        description=payload.description,
        teacher_id=teacher.id,
    )
    db.add(classroom)
    db.commit()
    db.refresh(classroom)
    return classroom


@router.get("/teacher/classes", response_model=list[ClassOut])
def list_classes(
    db: Session = Depends(get_db),
    teacher: User = Depends(require_role(UserRole.teacher, UserRole.admin)),
):
    return db.scalars(
        select(ClassRoom)
        .where(ClassRoom.teacher_id == teacher.id)
        .order_by(desc(ClassRoom.created_at))
    ).all()


@router.post("/teacher/classes/{class_id}/students", response_model=UserOut, status_code=201)
def add_student(
    class_id: str,
    payload: StudentCreate,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_role(UserRole.teacher, UserRole.admin)),
):
    classroom = db.get(ClassRoom, class_id)
    if not classroom or classroom.teacher_id != teacher.id:
        raise HTTPException(404, "班级不存在")
    if db.scalar(select(User).where(User.username == payload.username)):
        raise HTTPException(409, "用户名已存在")
    student = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        real_name=payload.real_name,
        role=UserRole.student,
    )
    db.add(student)
    db.flush()
    db.add(ClassMember(class_id=class_id, student_id=student.id))
    db.commit()
    db.refresh(student)
    return student


@router.post("/teacher/tasks", response_model=TaskOut, status_code=201)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_role(UserRole.teacher, UserRole.admin)),
):
    classroom = db.get(ClassRoom, payload.class_id)
    if not classroom or classroom.teacher_id != teacher.id:
        raise HTTPException(404, "班级不存在")
    task = LearningTask(
        class_id=payload.class_id,
        created_by=teacher.id,
        title=payload.title,
        description=payload.description,
        task_type=payload.task_type,
        knowledge_points=payload.knowledge_points,
        difficulty=payload.difficulty,
        is_published=payload.is_published,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.patch("/teacher/tasks/{task_id}", response_model=TaskOut)
def update_task(
    task_id: str,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_role(UserRole.teacher, UserRole.admin)),
):
    task = db.get(LearningTask, task_id)
    if not task or task.created_by != teacher.id:
        raise HTTPException(404, "题目不存在")
    updates = payload.model_dump(exclude_unset=True)
    if "class_id" in updates:
        classroom = db.get(ClassRoom, updates["class_id"])
        if not classroom or classroom.teacher_id != teacher.id:
            raise HTTPException(404, "班级不存在")
    for field, value in updates.items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


@router.post("/teacher/task-images")
async def upload_task_image(
    request: Request,
    x_file_name: str = Header(default="image"),
    content_type: str | None = Header(default=None),
    teacher: User = Depends(require_role(UserRole.teacher, UserRole.admin)),
):
    del teacher
    media_type = (content_type or "").split(";")[0].strip().lower()
    if media_type not in TASK_IMAGE_TYPES:
        raise HTTPException(415, "仅支持 PNG、JPG、GIF 或 WebP 图片")
    content = await request.body()
    if not content:
        raise HTTPException(400, "不能上传空图片")
    if len(content) > MAX_TASK_IMAGE_SIZE:
        raise HTTPException(413, "题目图片不能超过 5 MB")
    original = unquote(x_file_name).strip()
    stem = Path(original).stem[:40] or "image"
    safe_stem = "".join(
        char if char.isalnum() or char in {"-", "_"} else "-"
        for char in stem
    ).strip("-") or "image"
    suffix = TASK_IMAGE_TYPES[media_type]
    file_name = f"{datetime.now():%Y%m%d%H%M%S}-{safe_stem}-{uuid4().hex[:8]}{suffix}"
    TASK_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    (TASK_IMAGE_DIR / file_name).write_bytes(content)
    return {"url": f"/uploads/task-images/{file_name}"}


@router.post("/conversations", response_model=ConversationCreated, status_code=201)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    student: User = Depends(require_role(UserRole.student)),
):
    task = db.get(LearningTask, payload.task_id)
    if not task or not task.is_published:
        raise HTTPException(404, "task not found")
    if not student_can_access_task(db, student.id, task):
        raise HTTPException(403, "你不属于该任务所在班级")
    existing = db.scalar(
        select(Conversation).where(
            Conversation.student_id == student.id,
            Conversation.task_id == payload.task_id,
            Conversation.source == "eduguard",
        )
    )
    if existing:
        return existing
    conversation = Conversation(student_id=student.id, task_id=payload.task_id)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = get_conversation_or_404(db, conversation_id)
    if user.role == UserRole.student and item.student_id != user.id:
        raise HTTPException(403, "无权查看该对话")
    if user.role in (UserRole.teacher, UserRole.admin) and not teacher_owns_conversation(
        db, user.id, item
    ):
        raise HTTPException(403, "无权查看该对话")
    latest_risk = max(item.risks, key=lambda risk: risk.created_at) if item.risks else None
    submission = db.scalar(
        select(AssignmentSubmission).where(
            AssignmentSubmission.student_id == item.student_id,
            AssignmentSubmission.task_id == item.task_id,
        )
    )
    return ConversationDetail(
        id=item.id,
        status=item.status,
        student_name=item.student.real_name,
        task=TaskOut.model_validate(item.task),
        messages=[MessageOut.model_validate(message) for message in item.messages],
        latest_risk=RiskOut.model_validate(latest_risk) if latest_risk else None,
        reflections=[reflection.content for reflection in item.reflections],
        submission=SubmissionOut.model_validate(submission) if submission else None,
    )


@router.put("/tasks/{task_id}/submission", response_model=SubmissionOut)
async def upload_submission(
    task_id: str,
    request: Request,
    x_file_name: str = Header(default="assignment"),
    content_type: str | None = Header(default=None),
    db: Session = Depends(get_db),
    student: User = Depends(require_role(UserRole.student)),
):
    task = db.get(LearningTask, task_id)
    if not task:
        raise HTTPException(404, "task not found")
    if not task.is_published:
        raise HTTPException(403, "作业已关闭，不能再提交")
    if not student_can_access_task(db, student.id, task):
        raise HTTPException(403, "你不属于该任务所在班级")
    content = await request.body()
    if not content:
        raise HTTPException(400, "不能上传空文件")
    if len(content) > MAX_SUBMISSION_SIZE:
        raise HTTPException(413, "作业文件不能超过 10 MB")
    file_name = unquote(x_file_name).strip()[:255] or "assignment"
    submission = db.scalar(
        select(AssignmentSubmission).where(
            AssignmentSubmission.student_id == student.id,
            AssignmentSubmission.task_id == task.id,
        )
    )
    if submission is None:
        submission = AssignmentSubmission(student_id=student.id, task_id=task.id)
        db.add(submission)
    submission.file_name = file_name
    submission.content_type = content_type or "application/octet-stream"
    submission.file_size = len(content)
    submission.content = content
    submission.uploaded_at = datetime.now().astimezone()
    db.commit()
    db.refresh(submission)
    return submission


@router.get("/tasks/{task_id}/submission", response_model=SubmissionOut | None)
def get_student_submission(
    task_id: str,
    db: Session = Depends(get_db),
    student: User = Depends(require_role(UserRole.student)),
):
    task = db.get(LearningTask, task_id)
    if not task or not student_can_access_task(db, student.id, task):
        raise HTTPException(404, "task not found")
    return db.scalar(
        select(AssignmentSubmission).where(
            AssignmentSubmission.student_id == student.id,
            AssignmentSubmission.task_id == task.id,
        )
    )


@router.get("/teacher/conversations/{conversation_id}/submission", response_model=SubmissionOut | None)
def get_teacher_submission(
    conversation_id: str,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_role(UserRole.teacher, UserRole.admin)),
):
    conversation = get_conversation_or_404(db, conversation_id)
    if not teacher_owns_conversation(db, teacher.id, conversation):
        raise HTTPException(403, "无权查看该作业")
    return db.scalar(
        select(AssignmentSubmission).where(
            AssignmentSubmission.student_id == conversation.student_id,
            AssignmentSubmission.task_id == conversation.task_id,
        )
    )


@router.get("/teacher/submissions/{submission_id}/download")
def download_submission(
    submission_id: str,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_role(UserRole.teacher, UserRole.admin)),
):
    submission = db.get(AssignmentSubmission, submission_id)
    if not submission:
        raise HTTPException(404, "submission not found")
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.student_id == submission.student_id,
            Conversation.task_id == submission.task_id,
            Conversation.source == "eduguard",
        )
    )
    if not conversation or not teacher_owns_conversation(db, teacher.id, conversation):
        raise HTTPException(403, "无权下载该作业")
    return Response(
        content=submission.content,
        media_type=submission.content_type,
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{quote(submission.file_name)}"
            )
        },
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=InteractionResult,
    status_code=201,
)
def add_message(
    conversation_id: str,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    student: User = Depends(require_role(UserRole.student)),
):
    conversation = get_conversation_or_404(db, conversation_id)
    if conversation.student_id != student.id:
        raise HTTPException(403, "无权向该对话发送消息")
    sequence = len(conversation.messages) + 1
    student_message = Message(
        conversation_id=conversation.id,
        sender=MessageSender.student,
        content=payload.content.strip(),
        sequence_number=sequence,
    )
    db.add(student_message)
    db.flush()

    recent_context = [
        message.content
        for message in conversation.messages
        if message.sender == MessageSender.student
    ]
    selected = classify_student_message(student_message.content, recent_context)
    analysis = BehaviorAnalysis(
        message_id=student_message.id,
        behavior_type=selected.behavior_type,
        confidence=selected.confidence,
        method=AnalysisMethod(selected.method),
        explanation=selected.explanation,
        evidence_text=selected.evidence_text,
        model_name=selected.model_name,
        is_selected=True,
        needs_review=False,
        raw_result=selected.raw_result,
    )
    db.add(analysis)

    previous_answer_count = 0
    for prior_message in reversed(conversation.messages):
        if prior_message.sender != MessageSender.student:
            continue
        prior_selected = next(
            (analysis for analysis in prior_message.analyses if analysis.is_selected),
            None,
        )
        if not prior_selected or prior_selected.behavior_type != "answer_seeking":
            break
        previous_answer_count += 1
    risk_result = assess_risk(
        student_message.content,
        selected.behavior_type,
        previous_answer_count,
        bool(conversation.reflections),
    )
    assessment = RiskAssessment(
        conversation_id=conversation.id,
        trigger_message_id=student_message.id,
        system_level=RiskLevel(risk_result.level),
        level=RiskLevel(risk_result.level),
        score=risk_result.score,
        reasons=[item.description for item in risk_result.evidences],
    )
    db.add(assessment)
    db.flush()
    for evidence in risk_result.evidences:
        db.add(
            RiskEvidence(
                risk_assessment_id=assessment.id,
                message_id=student_message.id,
                evidence_type=evidence.evidence_type,
                description=evidence.description,
                weight=evidence.weight,
                evidence_data=evidence.data,
            )
        )

    tutor_decision = run_eduguard_tutor(
        conversation.task.title,
        conversation.task.description,
        [*conversation.messages, student_message],
        selected,
        risk_result.level,
        risk_result.score,
    )
    assistant_message = Message(
        conversation_id=conversation.id,
        sender=MessageSender.assistant,
        content=tutor_decision.generated_response,
        sequence_number=sequence + 1,
        metadata_json=tutor_decision.metadata(),
    )
    db.add(assistant_message)
    db.flush()
    db.add(
        ScaffoldIntervention(
            conversation_id=conversation.id,
            trigger_message_id=student_message.id,
            intervention_level=tutor_decision.intervention_level,
            strategy_type=tutor_decision.strategy_type,
            content=tutor_decision.generated_response,
            generated_by=tutor_decision.generated_by,
        )
    )
    db.commit()

    db.refresh(student_message)
    db.refresh(assistant_message)
    db.refresh(assessment)
    return InteractionResult(
        student_message=MessageOut.model_validate(student_message),
        assistant_message=MessageOut.model_validate(assistant_message),
        selected_analysis=AnalysisOut.model_validate(
            analysis
        ),
        risk=RiskOut.model_validate(assessment),
        intervention_level=tutor_decision.intervention_level,
        tutor_decision=tutor_decision_out(
            tutor_decision.metadata()["eduguard_tutor"]
        ),
    )


@router.post(
    "/conversations/{conversation_id}/reflections",
    response_model=ReflectionOut,
    status_code=201,
)
def add_reflection(
    conversation_id: str,
    payload: ReflectionCreate,
    db: Session = Depends(get_db),
    student: User = Depends(require_role(UserRole.student)),
):
    conversation = get_conversation_or_404(db, conversation_id)
    if conversation.student_id != student.id:
        raise HTTPException(403, "无权修改该对话")
    reflection = StudentReflection(
        conversation_id=conversation.id,
        student_id=student.id,
        content=payload.content.strip(),
    )
    db.add(reflection)
    db.commit()
    db.refresh(reflection)
    return reflection


@router.get("/teacher/dashboard", response_model=DashboardSummary)
def teacher_dashboard(
    db: Session = Depends(get_db),
    teacher: User = Depends(require_role(UserRole.teacher, UserRole.admin)),
):
    task_ids = select(LearningTask.id).where(LearningTask.created_by == teacher.id)
    conversation_ids = select(Conversation.id).where(
        Conversation.task_id.in_(task_ids),
        Conversation.source == "eduguard",
    )
    conversations = db.scalars(
        select(Conversation)
        .where(Conversation.id.in_(conversation_ids))
        .options(
            selectinload(Conversation.student),
            selectinload(Conversation.task).selectinload(LearningTask.classroom),
            selectinload(Conversation.risks),
        )
        .order_by(desc(Conversation.started_at))
    ).all()
    ordered_risks = db.scalars(
        select(RiskAssessment)
        .where(RiskAssessment.conversation_id.in_(conversation_ids))
        .order_by(desc(RiskAssessment.created_at))
    ).all()
    risk_distribution = {level.value: 0 for level in RiskLevel}
    for risk in ordered_risks:
        risk_distribution[risk.level.value] += 1

    behavior_rows = db.execute(
        select(BehaviorAnalysis.behavior_type, func.count(BehaviorAnalysis.id))
        .join(Message)
        .where(
            BehaviorAnalysis.is_selected.is_(True),
            Message.conversation_id.in_(conversation_ids),
        )
        .group_by(BehaviorAnalysis.behavior_type)
    ).all()
    conversation_behavior_rows = db.execute(
        select(
            Message.conversation_id,
            BehaviorAnalysis.behavior_type,
            func.count(BehaviorAnalysis.id),
        )
        .join(Message)
        .where(
            BehaviorAnalysis.is_selected.is_(True),
            Message.conversation_id.in_(conversation_ids),
        )
        .group_by(Message.conversation_id, BehaviorAnalysis.behavior_type)
    ).all()
    behavior_by_conversation: dict[str, dict[str, int]] = {}
    for conversation_id, behavior_type, count in conversation_behavior_rows:
        behavior_by_conversation.setdefault(conversation_id, {})[behavior_type] = count
    recent_conversations = []
    for conversation in conversations:
        risks = sorted(
            conversation.risks,
            key=lambda item: item.created_at,
            reverse=True,
        )
        latest_risk = risks[0] if risks else None
        conversation_risk_distribution = {level.value: 0 for level in RiskLevel}
        for risk in risks:
            conversation_risk_distribution[risk.level.value] += 1
        recent_conversations.append(
            {
                "conversation_id": conversation.id,
                "task_id": conversation.task_id,
                "class_id": conversation.task.class_id,
                "class_name": (
                    conversation.task.classroom.name
                    if conversation.task.classroom
                    else None
                ),
                "student_name": conversation.student.real_name,
                "task_title": conversation.task.title,
                "diagnosis_count": len(risks),
                "teacher_update_count": sum(
                    risk.review_status != "recorded" for risk in risks
                ),
                "risk_distribution": conversation_risk_distribution,
                "behavior_distribution": behavior_by_conversation.get(
                    conversation.id, {}
                ),
                "latest_risk_level": (
                    latest_risk.level.value if latest_risk else None
                ),
                "latest_risk_score": latest_risk.score if latest_risk else None,
                "last_diagnosed_at": (
                    latest_risk.created_at.isoformat() if latest_risk else None
                ),
                "started_at": conversation.started_at.isoformat(),
            }
        )
    return DashboardSummary(
        total_conversations=db.scalar(
            select(func.count(Conversation.id)).where(Conversation.id.in_(conversation_ids))
        )
        or 0,
        teacher_updates=db.scalar(
            select(func.count(RiskAssessment.id)).where(
                RiskAssessment.review_status != "recorded",
                RiskAssessment.conversation_id.in_(conversation_ids),
            )
        )
        or 0,
        risk_distribution=risk_distribution,
        behavior_distribution={name: count for name, count in behavior_rows},
        recent_conversations=recent_conversations,
    )


@router.get(
    "/teacher/conversations/{conversation_id}/diagnoses",
    response_model=list[ConversationDiagnosisOut],
)
def get_conversation_diagnoses(
    conversation_id: str,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_role(UserRole.teacher, UserRole.admin)),
):
    conversation = get_conversation_or_404(db, conversation_id)
    if not teacher_owns_conversation(db, teacher.id, conversation):
        raise HTTPException(403, "无权查看该对话诊断")
    risks = db.scalars(
        select(RiskAssessment)
        .where(RiskAssessment.conversation_id == conversation.id)
        .order_by(RiskAssessment.created_at)
    ).all()
    diagnoses = []
    for risk in risks:
        trigger_message = db.get(Message, risk.trigger_message_id)
        selected_behavior = db.scalar(
            select(BehaviorAnalysis.behavior_type).where(
                BehaviorAnalysis.message_id == risk.trigger_message_id,
                BehaviorAnalysis.is_selected.is_(True),
            )
        )
        diagnoses.append(
            ConversationDiagnosisOut(
                risk_id=risk.id,
                conversation_id=conversation.id,
                turn_number=(
                    (trigger_message.sequence_number + 1) // 2
                    if trigger_message
                    else None
                ),
                trigger_message=trigger_message.content if trigger_message else "",
                behavior_type=selected_behavior,
                system_level=risk.system_level.value,
                level=risk.level.value,
                score=risk.score,
                review_status=risk.review_status,
                created_at=risk.created_at,
            )
        )
    return diagnoses


@router.get("/teacher/risks/{risk_id}", response_model=RiskDetail)
def get_risk_detail(
    risk_id: str,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_role(UserRole.teacher, UserRole.admin)),
):
    risk = db.scalar(
        select(RiskAssessment)
        .where(RiskAssessment.id == risk_id)
        .options(
            selectinload(RiskAssessment.evidences),
            selectinload(RiskAssessment.reviews),
        )
    )
    if not risk:
        raise HTTPException(404, "risk assessment not found")
    conversation = db.get(Conversation, risk.conversation_id)
    if not teacher_owns_conversation(db, teacher.id, conversation):
        raise HTTPException(403, "无权查看该风险记录")
    message = db.get(Message, risk.trigger_message_id)
    selected = db.scalar(
        select(BehaviorAnalysis).where(
            BehaviorAnalysis.message_id == message.id,
            BehaviorAnalysis.is_selected.is_(True),
        )
    )
    assistant_message = db.scalar(
        select(Message).where(
            Message.conversation_id == conversation.id,
            Message.sequence_number == message.sequence_number + 1,
            Message.sender == MessageSender.assistant,
        )
    )
    stored_decision = (
        assistant_message.metadata_json.get("eduguard_tutor")
        if assistant_message and assistant_message.metadata_json
        else None
    )
    return RiskDetail(
        risk=RiskOut.model_validate(risk),
        conversation_id=conversation.id,
        student_name=db.get(User, conversation.student_id).real_name,
        task_title=db.get(LearningTask, conversation.task_id).title,
        trigger_message=message.content,
        selected_behavior=selected.behavior_type if selected else None,
        tutor_decision=tutor_decision_out(stored_decision),
        reviews=[
            {
                "id": review.id,
                "result": review.result.value,
                "revised_risk_level": (
                    review.revised_risk_level.value
                    if review.revised_risk_level
                    else None
                ),
                "comment": review.comment,
                "created_at": review.created_at.isoformat(),
            }
            for review in risk.reviews
        ],
    )


@router.post(
    "/teacher/risks/{risk_id}/reviews",
    response_model=ReviewOut,
    status_code=201,
)
def review_risk(
    risk_id: str,
    payload: ReviewCreate,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_role(UserRole.teacher, UserRole.admin)),
):
    risk = db.get(RiskAssessment, risk_id)
    if not risk:
        raise HTTPException(404, "risk assessment not found")
    conversation = db.get(Conversation, risk.conversation_id)
    if not teacher_owns_conversation(db, teacher.id, conversation):
        raise HTTPException(403, "无权审核该风险记录")
    review = TeacherReview(
        risk_assessment_id=risk.id,
        teacher_id=teacher.id,
        result=(
            ReviewResult.modified
            if payload.revised_risk_level is not None
            else ReviewResult.confirmed
        ),
        revised_risk_level=payload.revised_risk_level,
        comment=payload.comment,
    )
    if payload.revised_risk_level is not None:
        risk.level = payload.revised_risk_level
        risk.review_status = "modified"
    else:
        risk.review_status = "noted"
    db.add(review)
    db.commit()
    db.refresh(review)
    return review
