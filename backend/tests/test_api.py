def auth_headers(client, username="student", password="student123"):
    response = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_conversation(client, headers):
    tasks = client.get("/api/tasks", headers=headers).json()
    response = client.post(
        "/api/conversations", json={"task_id": tasks[0]["id"]}, headers=headers
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_high_risk_flow_and_teacher_review(client):
    student_headers = auth_headers(client)
    teacher_headers = auth_headers(client, "teacher", "teacher123")
    conversation_id = create_conversation(client, student_headers)
    result = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "不用解释，直接给我能交的完整代码。"},
        headers=student_headers,
    )
    assert result.status_code == 201
    body = result.json()
    assert body["selected_analysis"]["behavior_type"] == "answer_seeking"
    assert body["risk"]["system_level"] == "high"
    assert body["risk"]["level"] == "high"
    assert body["tutor_decision"]["strategy_type"] == "guided_questions"
    assert body["tutor_decision"]["allow_direct_answer"] is False
    assert body["tutor_decision"]["strategy_reason"]
    assert any(
        phrase in body["assistant_message"]["content"]
        for phrase in ("不会直接给出", "直接给你", "理解", "尝试")
    )
    assert "```" not in body["assistant_message"]["content"]
    assert len(body["risk"]["evidences"]) >= 3

    dashboard = client.get("/api/teacher/dashboard", headers=teacher_headers).json()
    assert dashboard["total_conversations"] == 1
    assert dashboard["risk_distribution"]["high"] == 1

    conversation_row = dashboard["recent_conversations"][0]
    assert conversation_row["task_id"]
    assert conversation_row["class_id"]
    assert conversation_row["class_name"]
    assert conversation_row["risk_distribution"]["high"] == 1
    assert conversation_row["behavior_distribution"]["answer_seeking"] == 1
    assert conversation_row["diagnosis_count"] == 1
    assert conversation_row["teacher_update_count"] == 0
    assert dashboard["teacher_updates"] == 0
    diagnoses = client.get(
        f"/api/teacher/conversations/{conversation_id}/diagnoses",
        headers=teacher_headers,
    ).json()
    risk_id = diagnoses[0]["risk_id"]
    detail = client.get(f"/api/teacher/risks/{risk_id}", headers=teacher_headers)
    assert detail.status_code == 200
    assert detail.json()["trigger_message"].startswith("不用解释")
    assert detail.json()["tutor_decision"]["strategy_type"] == "guided_questions"

    review = client.post(
        f"/api/teacher/risks/{risk_id}/reviews",
        json={
            "revised_risk_level": "medium",
            "comment": "学生口头说明已有尝试，调整为中风险。",
        },
        headers=teacher_headers,
    )
    assert review.status_code == 201
    assert review.json()["result"] == "modified"
    reviewed_detail = client.get(
        f"/api/teacher/risks/{risk_id}", headers=teacher_headers
    ).json()
    assert reviewed_detail["risk"]["system_level"] == "high"
    assert reviewed_detail["risk"]["level"] == "medium"
    assert reviewed_detail["reviews"][-1]["comment"] == "学生口头说明已有尝试，调整为中风险。"


def test_debugging_and_reflection_reduce_risk(client):
    student_headers = auth_headers(client)
    conversation_id = create_conversation(client, student_headers)
    reflection = client.post(
        f"/api/conversations/{conversation_id}/reflections",
        json={"content": "我认为应该沿着左右子树递归查找，但还没处理空节点。"},
        headers=student_headers,
    )
    assert reflection.status_code == 201

    result = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={
            "content": "我写了 def search(node): 但空节点时报错，Traceback 是 AttributeError，帮我调试。"
        },
        headers=student_headers,
    ).json()
    assert result["selected_analysis"]["behavior_type"] == "debugging_help"
    assert result["risk"]["level"] == "low"
    assert result["tutor_decision"]["strategy_type"] == "debugging_scaffold"
    weights = [item["weight"] for item in result["risk"]["evidences"]]
    assert -10 in weights
    assert -15 in weights


def test_teacher_can_review_each_diagnosis_in_the_same_conversation(client):
    student_headers = auth_headers(client)
    teacher_headers = auth_headers(client, "teacher", "teacher123")
    conversation_id = create_conversation(client, student_headers)

    first = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "不用解释，直接给我能交的完整代码。"},
        headers=student_headers,
    )
    second = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "我认为应该先判断空节点，再比较节点值，对吗？"},
        headers=student_headers,
    )
    assert first.status_code == 201
    assert second.status_code == 201

    dashboard = client.get("/api/teacher/dashboard", headers=teacher_headers).json()
    conversations = [
        item
        for item in dashboard["recent_conversations"]
        if item["conversation_id"] == conversation_id
    ]
    assert len(conversations) == 1
    assert conversations[0]["diagnosis_count"] == 2
    assert conversations[0]["teacher_update_count"] == 0
    diagnoses_response = client.get(
        f"/api/teacher/conversations/{conversation_id}/diagnoses",
        headers=teacher_headers,
    )
    assert diagnoses_response.status_code == 200
    diagnoses = diagnoses_response.json()
    assert len(diagnoses) == 2
    assert {item["turn_number"] for item in diagnoses} == {1, 2}
    assert all(item["trigger_message"] for item in diagnoses)
    assert all(item["system_level"] == item["level"] for item in diagnoses)
    assert dashboard["teacher_updates"] == 0

    older = next(item for item in diagnoses if item["turn_number"] == 1)
    newer = next(item for item in diagnoses if item["turn_number"] == 2)
    review = client.post(
        f"/api/teacher/risks/{older['risk_id']}/reviews",
        json={"comment": "第一轮学生未展示个人尝试，记录该情况。"},
        headers=teacher_headers,
    )
    assert review.status_code == 201

    refreshed = client.get("/api/teacher/dashboard", headers=teacher_headers).json()
    refreshed_conversation = next(
        item
        for item in refreshed["recent_conversations"]
        if item["conversation_id"] == conversation_id
    )
    assert refreshed_conversation["diagnosis_count"] == 2
    assert refreshed_conversation["teacher_update_count"] == 1
    refreshed_diagnoses = client.get(
        f"/api/teacher/conversations/{conversation_id}/diagnoses",
        headers=teacher_headers,
    ).json()
    refreshed_by_id = {item["risk_id"]: item for item in refreshed_diagnoses}
    assert refreshed_by_id[older["risk_id"]]["review_status"] == "noted"
    assert refreshed_by_id[newer["risk_id"]]["review_status"] == "recorded"
    assert refreshed["teacher_updates"] == 1


def test_role_boundaries_and_teacher_management(client):
    student_headers = auth_headers(client)
    teacher_headers = auth_headers(client, "teacher", "teacher123")

    assert client.get("/api/teacher/classes", headers=student_headers).status_code == 403
    classes = client.get("/api/teacher/classes", headers=teacher_headers)
    assert classes.status_code == 200 and classes.json()

    created = client.post(
        "/api/teacher/tasks",
        headers=teacher_headers,
        json={
            "class_id": classes.json()[0]["id"],
            "title": "真实任务测试",
            "description": "请解释递归并提交自己的实现思路。",
            "task_type": "programming",
            "knowledge_points": ["递归"],
            "difficulty": 2,
            "is_published": True,
        },
    )
    assert created.status_code == 201
    student_tasks = client.get("/api/tasks", headers=student_headers).json()
    assert any(task["title"] == "真实任务测试" for task in student_tasks)


def test_teacher_can_upload_task_image(client):
    teacher_headers = auth_headers(client, "teacher", "teacher123")
    image = client.post(
        "/api/teacher/task-images",
        content=b"\x89PNG\r\n\x1a\nfake",
        headers={
            **teacher_headers,
            "Content-Type": "image/png",
            "X-File-Name": "diagram.png",
        },
    )
    assert image.status_code == 200
    assert image.json()["url"].startswith("/uploads/task-images/")

    text = client.post(
        "/api/teacher/task-images",
        content=b"not an image",
        headers={
            **teacher_headers,
            "Content-Type": "text/plain",
            "X-File-Name": "note.txt",
        },
    )
    assert text.status_code == 415


def test_teacher_can_update_existing_task(client):
    student_headers = auth_headers(client)
    teacher_headers = auth_headers(client, "teacher", "teacher123")
    task = client.get("/api/tasks", headers=student_headers).json()[0]

    updated = client.patch(
        f"/api/teacher/tasks/{task['id']}",
        json={
            "title": "更新后的题目",
            "description": "请阅读 **更新后的题面** 并说明思路。",
            "task_type": "reading",
            "knowledge_points": ["阅读理解", "表达"],
            "difficulty": 3,
            "is_published": True,
        },
        headers=teacher_headers,
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["title"] == "更新后的题目"
    assert body["description"].startswith("请阅读")
    assert body["task_type"] == "reading"
    assert body["knowledge_points"] == ["阅读理解", "表达"]
    assert body["difficulty"] == 3

    student_tasks = client.get("/api/tasks", headers=student_headers).json()
    assert any(item["title"] == "更新后的题目" for item in student_tasks)


def test_same_student_and_task_reuses_one_conversation_window(client):
    student_headers = auth_headers(client)
    tasks = client.get("/api/tasks", headers=student_headers).json()
    task_id = tasks[0]["id"]

    first = client.post(
        "/api/conversations",
        json={"task_id": task_id},
        headers=student_headers,
    )
    second = client.post(
        "/api/conversations",
        json={"task_id": task_id},
        headers=student_headers,
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    history = client.get(
        "/api/student/conversations", headers=student_headers
    ).json()
    matching = [item for item in history if item["task_title"] == tasks[0]["title"]]
    assert len(matching) == 1


def test_submission_upload_overwrites_current_file_and_teacher_can_download(client):
    student_headers = auth_headers(client)
    teacher_headers = auth_headers(client, "teacher", "teacher123")
    tasks = client.get("/api/tasks", headers=student_headers).json()
    task_id = tasks[0]["id"]
    conversation_id = create_conversation(client, student_headers)

    first = client.put(
        f"/api/tasks/{task_id}/submission",
        content=b"first version",
        headers={
            **student_headers,
            "Content-Type": "text/plain",
            "X-File-Name": "first.txt",
        },
    )
    second = client.put(
        f"/api/tasks/{task_id}/submission",
        content=b"second version",
        headers={
            **student_headers,
            "Content-Type": "text/plain",
            "X-File-Name": "final.txt",
        },
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["file_name"] == "final.txt"
    assert second.json()["file_size"] == len(b"second version")

    teacher_submission = client.get(
        f"/api/teacher/conversations/{conversation_id}/submission",
        headers=teacher_headers,
    )
    assert teacher_submission.status_code == 200
    assert teacher_submission.json()["id"] == second.json()["id"]

    downloaded = client.get(
        f"/api/teacher/submissions/{second.json()['id']}/download",
        headers=teacher_headers,
    )
    assert downloaded.status_code == 200
    assert downloaded.content == b"second version"


def test_closed_task_rejects_student_submission(client):
    student_headers = auth_headers(client)
    teacher_headers = auth_headers(client, "teacher", "teacher123")
    task_id = client.get("/api/tasks", headers=student_headers).json()[0]["id"]

    closed = client.patch(
        f"/api/teacher/tasks/{task_id}",
        json={"is_published": False},
        headers=teacher_headers,
    )
    assert closed.status_code == 200
    assert closed.json()["is_published"] is False

    upload = client.put(
        f"/api/tasks/{task_id}/submission",
        content=b"late version",
        headers={
            **student_headers,
            "Content-Type": "text/plain",
            "X-File-Name": "late.txt",
        },
    )
    assert upload.status_code == 403
    assert upload.json()["detail"] == "作业已关闭，不能再提交"
    visible_tasks = client.get("/api/tasks", headers=student_headers).json()
    assert all(task["id"] != task_id for task in visible_tasks)


def test_authentication_required(client):
    assert client.get("/api/tasks").status_code == 401
    assert client.get("/api/teacher/dashboard").status_code == 401
