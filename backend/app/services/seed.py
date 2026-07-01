from sqlalchemy.orm import Session

from ..auth import hash_password
from ..models import ClassMember, ClassRoom, LearningTask, User, UserRole


DEMO_STUDENT_ID = "00000000-0000-0000-0000-000000000001"
DEMO_TEACHER_ID = "00000000-0000-0000-0000-000000000002"
DEMO_TASK_ID = "00000000-0000-0000-0000-000000000101"
DEMO_CLASS_ID = "00000000-0000-0000-0000-000000000201"


def seed_demo_data(db: Session) -> None:
    if not db.get(User, DEMO_STUDENT_ID):
        db.add(
            User(
                id=DEMO_STUDENT_ID,
                username="student",
                password_hash=hash_password("student123"),
                real_name="演示学生",
                role=UserRole.student,
            )
        )
    if not db.get(User, DEMO_TEACHER_ID):
        db.add(
            User(
                id=DEMO_TEACHER_ID,
                username="teacher",
                password_hash=hash_password("teacher123"),
                real_name="演示教师",
                role=UserRole.teacher,
            )
        )
    db.flush()

    student = db.get(User, DEMO_STUDENT_ID)
    teacher = db.get(User, DEMO_TEACHER_ID)
    if student and not student.password_hash.startswith("pbkdf2_sha256$"):
        student.password_hash = hash_password("student123")
    if teacher and not teacher.password_hash.startswith("pbkdf2_sha256$"):
        teacher.password_hash = hash_password("teacher123")

    if not db.get(ClassRoom, DEMO_CLASS_ID):
        db.add(
            ClassRoom(
                id=DEMO_CLASS_ID,
                name="人工智能课程演示班",
                teacher_id=DEMO_TEACHER_ID,
                description="用于 EduGuard 真实业务流程演示的班级。",
            )
        )
        db.flush()
    if not db.get(ClassMember, (DEMO_CLASS_ID, DEMO_STUDENT_ID)):
        db.add(ClassMember(class_id=DEMO_CLASS_ID, student_id=DEMO_STUDENT_ID))
        db.flush()

    demo_task = db.get(LearningTask, DEMO_TASK_ID)
    if not demo_task:
        db.add(
            LearningTask(
                id=DEMO_TASK_ID,
                class_id=DEMO_CLASS_ID,
                created_by=DEMO_TEACHER_ID,
                title="二叉搜索树查找",
                description=(
                    "实现二叉搜索树的 search 方法，并解释平均与最坏时间复杂度。"
                    "请保留自己的思考和调试过程。"
                ),
                task_type="programming",
                knowledge_points=["二叉搜索树", "递归", "时间复杂度"],
                difficulty=2,
            )
        )
    else:
        demo_task.class_id = DEMO_CLASS_ID
        demo_task.is_published = True
    db.commit()
