import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Input,
  List,
  Row,
  Select,
  Space,
  Tag,
  Typography,
  Upload,
  message as toast
} from "antd";
import {
  BulbOutlined,
  CheckCircleOutlined,
  SendOutlined,
  UploadOutlined
} from "@ant-design/icons";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  createConversation,
  getConversation,
  getSubmission,
  getTasks,
  sendMessage,
  submitReflection,
  uploadSubmission
} from "../api";
import type { Message, Submission, Task } from "../types";
import { MarkdownMessage } from "../components/MarkdownMessage";

const { Text, Title, Paragraph } = Typography;
const { TextArea } = Input;

function temporaryMessage(
  id: string,
  sender: Message["sender"],
  content: string,
  sequenceNumber: number
): Message {
  return {
    id,
    sender,
    content,
    sequence_number: sequenceNumber,
    created_at: new Date().toISOString(),
    analyses: []
  };
}

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export default function StudentWorkspace() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [taskId, setTaskId] = useState<string>();
  const [conversationId, setConversationId] = useState<string>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [reflection, setReflection] = useState("");
  const [sending, setSending] = useState(false);
  const [submission, setSubmission] = useState<Submission | null>(null);
  const [uploading, setUploading] = useState(false);
  const messageListRef = useRef<HTMLDivElement | null>(null);
  const messageEndRef = useRef<HTMLDivElement | null>(null);

  const resumeConversation = useCallback(async (id: string) => {
    const detail = await getConversation(id);
    setConversationId(detail.id);
    setTaskId(detail.task.id);
    setMessages(detail.messages);
    setSubmission(detail.submission);
  }, []);

  const openTaskConversation = useCallback(
    async (selectedTaskId: string) => {
      setTaskId(selectedTaskId);
      setConversationId(undefined);
      setMessages([]);
      setSubmission(null);
      const id = await createConversation(selectedTaskId);
      await resumeConversation(id);
    },
    [resumeConversation]
  );

  useEffect(() => {
    getTasks()
      .then((items) => {
        setTasks(items);
        if (items[0]?.id) {
          void openTaskConversation(items[0].id);
        }
      })
      .catch(() => toast.error("无法加载学习任务，请确认后端已启动。"));
  }, [openTaskConversation]);

  const task = useMemo(
    () => tasks.find((item) => item.id === taskId),
    [taskId, tasks]
  );

  useEffect(() => {
    if (!taskId) {
      setSubmission(null);
      return;
    }
    getSubmission(taskId).then(setSubmission).catch(() => setSubmission(null));
  }, [taskId]);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      if (messageListRef.current) {
        messageListRef.current.scrollTop = messageListRef.current.scrollHeight;
      }
      messageEndRef.current?.scrollIntoView({
        block: "end",
        behavior: "auto"
      });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [messages]);

  async function ensureConversation() {
    if (conversationId) return conversationId;
    if (!taskId) throw new Error("请选择任务");
    const id = await createConversation(taskId);
    setConversationId(id);
    return id;
  }

  async function handleSend() {
    const content = input.trim();
    if (!content) return;
    const studentTempId = `temp-student-${Date.now()}`;
    const assistantTempId = `temp-assistant-${Date.now()}`;
    const nextSequence = messages.length + 1;
    setMessages((current) => [
      ...current,
      temporaryMessage(studentTempId, "student", content, nextSequence),
      temporaryMessage(assistantTempId, "assistant", "", nextSequence + 1)
    ]);
    setInput("");
    setSending(true);
    try {
      const id = await ensureConversation();
      const result = await sendMessage(id, content);
      setMessages((current) =>
        current.map((item) => {
          if (item.id === studentTempId) return result.student_message;
          if (item.id === assistantTempId) {
            return { ...result.assistant_message, content: "" };
          }
          return item;
        })
      );
      const fullText = result.assistant_message.content;
      const step = fullText.length > 180 ? 4 : 2;
      for (let index = step; index <= fullText.length + step; index += step) {
        const partial = fullText.slice(0, index);
        setMessages((current) =>
          current.map((item) =>
            item.id === result.assistant_message.id
              ? { ...item, content: partial }
              : item
          )
        );
        await delay(18);
      }
    } catch {
      setMessages((current) =>
        current.filter(
          (item) => item.id !== studentTempId && item.id !== assistantTempId
        )
      );
      toast.error("消息发送失败，请检查 API 配置。");
    } finally {
      setSending(false);
    }
  }

  async function handleReflection() {
    if (!reflection.trim()) return;
    try {
      const id = await ensureConversation();
      await submitReflection(id, reflection.trim());
      toast.success("反思已保存，后续风险评估会将其作为积极证据。");
      setReflection("");
    } catch {
      toast.error("反思保存失败。");
    }
  }

  function resetTask(value: string) {
    void openTaskConversation(value).catch(() => {
      toast.error("任务对话加载失败。");
    });
  }

  async function handleUpload(file: File) {
    if (!taskId) return false;
    setUploading(true);
    try {
      const saved = await uploadSubmission(taskId, file);
      setSubmission(saved);
      toast.success("作业已保存。再次上传会覆盖当前版本。");
    } catch (error: unknown) {
      const status = (error as { response?: { status?: number } }).response?.status;
      toast.error(
        status === 403
          ? "作业已关闭，不能再提交。"
          : "作业上传失败，文件不能超过 10 MB。"
      );
    } finally {
      setUploading(false);
    }
    return false;
  }

  return (
    <div className="page-shell">
      <div className="page-heading">
        <div>
          <Text className="eyebrow">STUDENT WORKSPACE</Text>
          <Title level={2}>把 AI 变成学习搭档，而不是答案机器</Title>
          <Paragraph type="secondary">
            选择题目后继续对应对话，围绕你的理解、尝试和卡点获得学习支架。
          </Paragraph>
        </div>
        <Select
          className="task-select"
          value={taskId}
          onChange={resetTask}
          options={tasks.map((item) => ({ value: item.id, label: item.title }))}
        />
      </div>

      <Row gutter={[24, 24]} align="stretch" className="student-workbench">
        <Col xs={24} xl={7} lg={8}>
          <Card
            className="main-card task-reading-card"
            bordered={false}
            title="题目阅读"
          >
            {task ? (
              <Space direction="vertical" size={16} style={{ width: "100%" }}>
                <div>
                  <Text type="secondary">当前任务</Text>
                  <Title level={3}>{task.title}</Title>
                </div>
                <Space wrap>
                  {task.knowledge_points.map((point) => (
                    <Tag key={point}>{point}</Tag>
                  ))}
                </Space>
                <div className="task-reading-body">
                  <MarkdownMessage content={task.description} />
                </div>
              </Space>
            ) : (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="暂无可学习题目"
              />
            )}
          </Card>
        </Col>

        <Col xs={24} xl={10} lg={9}>
          <Card
            className="main-card chat-card"
            bordered={false}
            title="学习对话"
          >
            <div className="message-list" ref={messageListRef}>
              {messages.length === 0 ? (
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description="从描述你的理解、尝试或具体卡点开始"
                />
              ) : (
                <List
                  dataSource={messages}
                  renderItem={(item) => (
                    <List.Item className={`message-row ${item.sender}`}>
                      <div className="message-bubble">
                        <Text strong>{item.sender === "student" ? "你" : "EduGuard"}</Text>
                        {item.sender === "assistant" ? (
                          item.content ? (
                            <MarkdownMessage content={item.content} />
                          ) : (
                            <span className="typing-loading">
                              EduGuard 正在生成回复
                              <span />
                            </span>
                          )
                        ) : (
                          <Paragraph className="plain-message">{item.content}</Paragraph>
                        )}
                      </div>
                    </List.Item>
                  )}
                />
              )}
              <div ref={messageEndRef} className="message-end-anchor" />
            </div>

            <div className="composer">
              <TextArea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onPressEnter={(event) => {
                  if (!event.shiftKey) {
                    event.preventDefault();
                    void handleSend();
                  }
                }}
                rows={3}
                placeholder="描述你的问题。附上思路、代码或报错，会得到更准确的帮助。"
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                loading={sending}
                onClick={handleSend}
              >
                发送
              </Button>
            </div>
          </Card>
        </Col>

        <Col xs={24} xl={7} lg={7}>
          <Space direction="vertical" size={20} style={{ width: "100%" }}>
            <Card className="main-card" bordered={false} title="提交作业">
              <Space direction="vertical" style={{ width: "100%" }}>
                <Paragraph type="secondary">
                  每个任务只保留一份当前作业，再次上传会覆盖原文件。最大 10 MB。
                </Paragraph>
                {submission && (
                  <Alert
                    type="success"
                    showIcon
                    message={submission.file_name}
                    description={`已上传：${new Date(
                      submission.uploaded_at
                    ).toLocaleString()}`}
                  />
                )}
                <Upload
                  maxCount={1}
                  showUploadList={false}
                  beforeUpload={(file) => void handleUpload(file)}
                >
                  <Button
                    block
                    icon={<UploadOutlined />}
                    loading={uploading}
                    disabled={!taskId || task?.is_published === false}
                  >
                    {submission ? "重新上传并覆盖" : "上传作业"}
                  </Button>
                </Upload>
              </Space>
            </Card>

            <Card
              className="main-card reflection-card"
              bordered={false}
              title={
                <Space>
                  <BulbOutlined />
                  学习反思
                </Space>
              }
            >
              <Paragraph type="secondary">
                写下你的理解、已经尝试的方法或仍然困惑的地方。
              </Paragraph>
              <TextArea
                rows={4}
                value={reflection}
                onChange={(event) => setReflection(event.target.value)}
                placeholder="例如：我理解递归终止条件应该先判断空节点……"
              />
              <Button
                block
                icon={<CheckCircleOutlined />}
                onClick={handleReflection}
              >
                保存反思
              </Button>
            </Card>
          </Space>
        </Col>
      </Row>
    </div>
  );
}
