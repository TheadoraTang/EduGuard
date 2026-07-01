import {
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  List,
  Modal,
  Row,
  Select,
  Space,
  Switch,
  Tabs,
  Tag,
  Typography,
  Upload,
  message
} from "antd";
import {
  EditOutlined,
  PictureOutlined,
  PlusOutlined,
  TeamOutlined
} from "@ant-design/icons";
import { useCallback, useEffect, useState } from "react";
import {
  createClass,
  createStudent,
  createTask,
  getClasses,
  getTasks,
  updateTask,
  uploadTaskImage
} from "../api";
import type { ClassRoom, Task } from "../types";
import { MarkdownMessage } from "../components/MarkdownMessage";

const { Paragraph, Text, Title } = Typography;

export default function TeacherManagement() {
  const [classes, setClasses] = useState<ClassRoom[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [modal, setModal] = useState<"class" | "student" | "task" | null>(null);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [form] = Form.useForm();

  const load = useCallback(async () => {
    try {
      const [classRows, taskRows] = await Promise.all([getClasses(), getTasks()]);
      setClasses(classRows);
      setTasks(taskRows);
    } catch {
      message.error("教学数据加载失败。");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function open(type: typeof modal) {
    form.resetFields();
    setEditingTask(null);
    if (type === "task") {
      form.setFieldsValue({
        task_type: "programming",
        difficulty: 2,
        is_published: true
      });
    }
    setModal(type);
  }

  function openEditTask(task: Task) {
    form.resetFields();
    setEditingTask(task);
    form.setFieldsValue({
      class_id: task.class_id,
      title: task.title,
      description: task.description,
      task_type: task.task_type,
      knowledge_points: task.knowledge_points.join("，"),
      difficulty: task.difficulty,
      is_published: task.is_published
    });
    setModal("task");
  }

  async function submit(values: Record<string, unknown>) {
    try {
      if (modal === "class") {
        await createClass(values as { name: string; description?: string });
      } else if (modal === "student") {
        const { class_id, ...student } = values as {
          class_id: string;
          username: string;
          password: string;
          real_name: string;
        };
        await createStudent(class_id, student);
      } else if (modal === "task") {
        const taskValues = values as {
          class_id: string;
          title: string;
          description: string;
          task_type: string;
          knowledge_points?: string;
          difficulty: number;
          is_published: boolean;
        };
        const payload = {
          ...taskValues,
          knowledge_points: (taskValues.knowledge_points ?? "")
            .split(/[,，]/)
            .map((item) => item.trim())
            .filter(Boolean)
        };
        if (editingTask) {
          await updateTask(editingTask.id, payload);
        } else {
          await createTask(payload);
        }
      }
      message.success("保存成功");
      setModal(null);
      setEditingTask(null);
      await load();
    } catch {
      message.error("保存失败，请检查用户名是否重复或字段是否完整。");
    }
  }

  async function insertTaskImage(file: File) {
    try {
      const { url } = await uploadTaskImage(file);
      const current = String(form.getFieldValue("description") ?? "");
      const markdown = `\n\n![${file.name}](${url})`;
      form.setFieldValue("description", `${current}${markdown}`);
      message.success("图片已插入题目内容");
    } catch {
      message.error("图片上传失败，仅支持 5 MB 内的 PNG、JPG、GIF 或 WebP。");
    }
    return false;
  }

  return (
    <div className="page-shell">
      <div className="page-heading">
        <div>
          <Text className="eyebrow">TEACHING MANAGEMENT</Text>
          <Title level={2}>班级、学生与学习任务</Title>
          <Paragraph type="secondary">
            教师创建真实任务并发布给班级，学生登录后只会看到自己班级的内容。
          </Paragraph>
        </div>
        <Space wrap>
          <Button icon={<PlusOutlined />} onClick={() => open("class")}>
            新建班级
          </Button>
          <Button icon={<TeamOutlined />} onClick={() => open("student")}>
            添加学生
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => open("task")}>
            发布题目
          </Button>
        </Space>
      </div>

      <Row gutter={[18, 18]}>
        <Col xs={24} lg={9}>
          <Card className="main-card" bordered={false} title="我的班级">
            <List
              dataSource={classes}
              locale={{ emptyText: "尚未创建班级" }}
              renderItem={(item) => (
                <List.Item>
                  <List.Item.Meta
                    title={item.name}
                    description={item.description || "暂无班级说明"}
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col xs={24} lg={15}>
          <Card className="main-card" bordered={false} title="学习任务">
            <List
              dataSource={tasks}
              locale={{ emptyText: "尚未创建题目" }}
              renderItem={(item) => (
                <List.Item
                  actions={[
                    <Button
                      key="edit"
                      icon={<EditOutlined />}
                      onClick={() => openEditTask(item)}
                    >
                      编辑
                    </Button>,
                    <Switch
                      key="publish"
                      checked={item.is_published}
                      checkedChildren="已发布"
                      unCheckedChildren="草稿"
                      onChange={async (checked) => {
                        await updateTask(item.id, { is_published: checked });
                        await load();
                      }}
                    />
                  ]}
                >
                  <List.Item.Meta
                    title={item.title}
                    description={
                      <Space direction="vertical" size={3}>
                        <MarkdownMessage content={item.description} />
                        <Space wrap>
                          {item.knowledge_points.map((point) => (
                            <Tag key={point}>{point}</Tag>
                          ))}
                        </Space>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>

      <Modal
        open={Boolean(modal)}
        title={
          modal === "class"
            ? "新建班级"
            : modal === "student"
              ? "添加学生账号"
              : editingTask
                ? "编辑学习任务"
                : "创建学习任务"
        }
        onCancel={() => {
          setModal(null);
          setEditingTask(null);
        }}
        onOk={() => form.submit()}
        destroyOnHidden
      >
        <Form form={form} layout="vertical" onFinish={submit}>
          {modal === "class" && (
            <>
              <Form.Item name="name" label="班级名称" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
              <Form.Item name="description" label="班级说明">
                <Input.TextArea rows={3} />
              </Form.Item>
            </>
          )}
          {modal === "student" && (
            <>
              <Form.Item name="class_id" label="所属班级" rules={[{ required: true }]}>
                <Select
                  options={classes.map((item) => ({
                    value: item.id,
                    label: item.name
                  }))}
                />
              </Form.Item>
              <Form.Item name="real_name" label="学生姓名" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
              <Form.Item name="username" label="登录用户名" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
              <Form.Item
                name="password"
                label="初始密码"
                rules={[{ required: true, min: 6 }]}
              >
                <Input.Password />
              </Form.Item>
            </>
          )}
          {modal === "task" && (
            <>
              <Form.Item name="class_id" label="发布班级" rules={[{ required: true }]}>
                <Select
                  options={classes.map((item) => ({
                    value: item.id,
                    label: item.name
                  }))}
                />
              </Form.Item>
              <Form.Item name="title" label="题目标题" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
              <Form.Item
                label="题目内容（支持 Markdown）"
                required
                style={{ marginBottom: 12 }}
              >
                <Tabs
                  className="task-editor-tabs"
                  items={[
                    {
                      key: "edit",
                      label: "编辑题目",
                      children: (
                        <>
                          <Form.Item
                            name="description"
                            noStyle
                            rules={[{ required: true }]}
                          >
                            <Input.TextArea rows={10} />
                          </Form.Item>
                          <Upload
                            accept="image/png,image/jpeg,image/gif,image/webp"
                            maxCount={1}
                            showUploadList={false}
                            beforeUpload={(file) => void insertTaskImage(file)}
                          >
                            <Button
                              className="task-image-button"
                              icon={<PictureOutlined />}
                            >
                              插入图片
                            </Button>
                          </Upload>
                        </>
                      )
                    },
                    {
                      key: "preview",
                      label: "预览效果",
                      children: (
                        <Form.Item shouldUpdate noStyle>
                          {() => (
                            <div className="task-preview-pane">
                              {form.getFieldValue("description") ? (
                                <MarkdownMessage
                                  content={String(form.getFieldValue("description"))}
                                />
                              ) : (
                                <Text type="secondary">
                                  在编辑区输入题目内容后显示预览。
                                </Text>
                              )}
                            </div>
                          )}
                        </Form.Item>
                      )
                    }
                  ]}
                />
              </Form.Item>
              <Form.Item name="knowledge_points" label="知识点（逗号分隔）">
                <Input />
              </Form.Item>
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item name="task_type" label="任务类型">
                    <Select
                      options={[
                        { value: "programming", label: "编程题" },
                        { value: "math", label: "数学题" },
                        { value: "reading", label: "阅读与论述" }
                      ]}
                    />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="difficulty" label="难度">
                    <InputNumber min={1} max={5} style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item name="is_published" label="立即发布" valuePropName="checked">
                <Switch />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>
    </div>
  );
}
