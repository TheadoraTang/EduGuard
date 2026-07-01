import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Drawer,
  Empty,
  Flex,
  Form,
  Input,
  List,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message as toast
} from "antd";
import {
  AuditOutlined,
  CheckOutlined,
  TeamOutlined,
  WarningOutlined
} from "@ant-design/icons";
import ReactECharts from "echarts-for-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  downloadSubmission,
  getConversationDiagnoses,
  getDashboard,
  getRiskDetail,
  getTeacherSubmission,
  reviewRisk
} from "../api";
import { behaviorLabels, riskColors, riskLabels, strategyLabels } from "../labels";
import type {
  ConversationDiagnosis,
  Dashboard,
  RiskDetail,
  RiskLevel,
  Submission
} from "../types";
import { RiskBadge } from "../components/RiskBadge";

const { Paragraph, Text, Title } = Typography;

export default function TeacherDashboard() {
  const [dashboard, setDashboard] = useState<Dashboard>();
  const [selectedConversation, setSelectedConversation] = useState<{
    conversation_id: string;
    student_name: string;
    task_title: string;
  }>();
  const [diagnoses, setDiagnoses] = useState<ConversationDiagnosis[]>([]);
  const [submission, setSubmission] = useState<Submission | null>(null);
  const [detail, setDetail] = useState<RiskDetail>();
  const [loading, setLoading] = useState(false);
  const [classFilter, setClassFilter] = useState<string>();
  const [taskFilter, setTaskFilter] = useState<string>();
  const [studentFilter, setStudentFilter] = useState<string>();
  const [form] = Form.useForm();

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    try {
      setDashboard(await getDashboard());
    } catch {
      toast.error("教师看板加载失败，请确认后端已启动。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  async function openRisk(id: string) {
    try {
      setDetail(await getRiskDetail(id));
      form.resetFields();
    } catch {
      toast.error("风险详情加载失败。");
    }
  }

  async function openConversation(row: {
    conversation_id: string;
    student_name: string;
    task_title: string;
  }) {
    try {
      setSelectedConversation(row);
      const [items, currentSubmission] = await Promise.all([
        getConversationDiagnoses(row.conversation_id),
        getTeacherSubmission(row.conversation_id)
      ]);
      setDiagnoses(items);
      setSubmission(currentSubmission);
    } catch {
      setSelectedConversation(undefined);
      setSubmission(null);
      toast.error("对话诊断加载失败。");
    }
  }

  async function submitReview(values: {
    revised_risk_level?: RiskLevel;
    comment?: string;
  }) {
    if (!detail) return;
    if (!values.revised_risk_level && !values.comment?.trim()) {
      toast.warning("请选择新的风险等级，或填写教师备注。");
      return;
    }
    try {
      await reviewRisk(detail.risk.id, values);
      toast.success("教师修改已保存。");
      setDetail(await getRiskDetail(detail.risk.id));
      if (selectedConversation) {
        setDiagnoses(
          await getConversationDiagnoses(selectedConversation.conversation_id)
        );
      }
      await loadDashboard();
    } catch {
      toast.error("修改保存失败。");
    }
  }

  const conversationRows = dashboard?.recent_conversations ?? [];
  const classOptions = useMemo(
    () =>
      Array.from(
        new Map(
          conversationRows
            .filter((item) => item.class_id && item.class_name)
            .map((item) => [
              item.class_id,
              { value: item.class_id as string, label: item.class_name as string }
            ])
        ).values()
      ),
    [conversationRows]
  );
  const taskOptions = useMemo(
    () =>
      Array.from(
        new Map(
          conversationRows.map((item) => [
            item.task_id,
            { value: item.task_id, label: item.task_title }
          ])
        ).values()
      ),
    [conversationRows]
  );
  const studentOptions = useMemo(
    () =>
      Array.from(
        new Set(conversationRows.map((item) => item.student_name))
      ).map((name) => ({ value: name, label: name })),
    [conversationRows]
  );
  const filteredConversations = useMemo(
    () =>
      conversationRows.filter(
        (item) =>
          (!classFilter || item.class_id === classFilter) &&
          (!taskFilter || item.task_id === taskFilter) &&
          (!studentFilter || item.student_name === studentFilter)
      ),
    [classFilter, conversationRows, studentFilter, taskFilter]
  );
  const filteredRiskDistribution = useMemo(
    () =>
      filteredConversations.reduce(
        (acc, item) => {
          (["low", "medium", "high"] as RiskLevel[]).forEach((level) => {
            acc[level] += item.risk_distribution[level] ?? 0;
          });
          return acc;
        },
        { low: 0, medium: 0, high: 0 } as Record<RiskLevel, number>
      ),
    [filteredConversations]
  );
  const filteredBehaviorDistribution = useMemo(
    () =>
      filteredConversations.reduce<Record<string, number>>((acc, item) => {
        Object.entries(item.behavior_distribution).forEach(([behavior, count]) => {
          acc[behavior] = (acc[behavior] ?? 0) + count;
        });
        return acc;
      }, {}),
    [filteredConversations]
  );
  const filteredTeacherUpdates = useMemo(
    () =>
      filteredConversations.reduce(
        (total, item) => total + item.teacher_update_count,
        0
      ),
    [filteredConversations]
  );

  const riskOption = useMemo(
    () => ({
      tooltip: { trigger: "item" },
      series: [
        {
          type: "pie",
          radius: ["52%", "74%"],
          label: { formatter: "{b}\n{c}" },
          data: (["low", "medium", "high"] as RiskLevel[]).map((level) => ({
            name: riskLabels[level],
            value: filteredRiskDistribution[level],
            itemStyle: { color: riskColors[level] }
          }))
        }
      ]
    }),
    [filteredRiskDistribution]
  );

  const behaviorOption = useMemo(() => {
    const rows = Object.entries(filteredBehaviorDistribution);
    return {
      grid: { left: 90, right: 20, top: 10, bottom: 20 },
      xAxis: { type: "value", minInterval: 1 },
      yAxis: {
        type: "category",
        data: rows.map(([name]) => behaviorLabels[name] ?? name)
      },
      series: [
        {
          type: "bar",
          data: rows.map(([, value]) => value),
          itemStyle: { color: "#3457d5", borderRadius: [0, 5, 5, 0] }
        }
      ]
    };
  }, [filteredBehaviorDistribution]);

  const columns = [
    { title: "学生", dataIndex: "student_name" },
    {
      title: "班级",
      dataIndex: "class_name",
      render: (value: string | null) => value ?? "未分配"
    },
    { title: "学习任务", dataIndex: "task_title" },
    {
      title: "诊断次数",
      dataIndex: "diagnosis_count",
      width: 100
    },
    {
      title: "教师操作",
      dataIndex: "teacher_update_count",
      width: 90,
      render: (value: number) => (
        <Tag color={value > 0 ? "blue" : "default"}>{value}</Tag>
      )
    },
    {
      title: "最新风险",
      dataIndex: "latest_risk_level",
      render: (value: RiskLevel | null) =>
        value ? <RiskBadge level={value} /> : <Tag>暂无诊断</Tag>
    },
    {
      title: "开始时间",
      dataIndex: "started_at",
      render: (value: string) => new Date(value).toLocaleString()
    },
    {
      title: "操作",
      key: "action",
      render: (
        _: unknown,
        row: {
          conversation_id: string;
          task_id: string;
          class_id: string | null;
          class_name: string | null;
          student_name: string;
          task_title: string;
        }
      ) => (
        <Button type="link" onClick={() => openConversation(row)}>
          查看对话诊断
        </Button>
      )
    }
  ];

  const diagnosisColumns = [
    {
      title: "轮次",
      dataIndex: "turn_number",
      width: 80,
      render: (value: number | null) => (value ? `第 ${value} 轮` : "-")
    },
    {
      title: "学生内容",
      dataIndex: "trigger_message",
      ellipsis: true
    },
    {
      title: "行为",
      dataIndex: "behavior_type",
      width: 110,
      render: (value: string | null) =>
        value ? behaviorLabels[value] ?? value : "未识别"
    },
    {
      title: "系统风险",
      dataIndex: "system_level",
      width: 100,
      render: (value: RiskLevel) => <RiskBadge level={value} />
    },
    {
      title: "当前风险",
      dataIndex: "level",
      width: 100,
      render: (value: RiskLevel) => <RiskBadge level={value} />
    },
    {
      title: "记录状态",
      dataIndex: "review_status",
      width: 90,
      render: (value: string) => {
        if (value === "recorded") {
          return <Tag color="default">系统已记录</Tag>;
        }
        if (value === "noted") {
          return <Tag color="cyan">教师已备注</Tag>;
        }
        return <Tag color="blue">教师已调整</Tag>;
      }
    },
    {
      title: "操作",
      width: 100,
      render: (_: unknown, row: ConversationDiagnosis) => (
        <Button type="link" onClick={() => openRisk(row.risk_id)}>
          查看与修改
        </Button>
      )
    }
  ];

  return (
    <div className="page-shell">
      <div className="page-heading">
        <div>
          <Text className="eyebrow">TEACHER INSIGHT</Text>
          <Title level={2}>有证据的判断，才值得干预</Title>
          <Paragraph type="secondary">
            从班级趋势进入具体对话，查看系统结论，并按需调整风险或添加备注。
          </Paragraph>
        </div>
        <Button loading={loading} onClick={loadDashboard}>
          刷新数据
        </Button>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={8}>
          <Card className="metric-card" bordered={false}>
            <Statistic
              title="累计学习对话"
              value={filteredConversations.length}
              prefix={<TeamOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card className="metric-card" bordered={false}>
            <Statistic
              title="教师已操作诊断"
              value={filteredTeacherUpdates}
              prefix={<AuditOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card className="metric-card risk-metric" bordered={false}>
            <Statistic
              title="高风险诊断"
              value={filteredRiskDistribution.high}
              prefix={<WarningOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} className="chart-row">
        <Col xs={24} lg={9}>
          <Card className="main-card" bordered={false} title="诊断风险分布">
            <div className="chart-panel">
              <ReactECharts option={riskOption} style={{ height: 280 }} />
            </div>
          </Card>
        </Col>
        <Col xs={24} lg={15}>
          <Card className="main-card" bordered={false} title="提问行为分布">
            <div className="chart-panel">
              {Object.keys(filteredBehaviorDistribution).length ? (
                <ReactECharts option={behaviorOption} style={{ height: 280 }} />
              ) : (
                <Empty description="完成一次学生对话后显示" />
              )}
            </div>
          </Card>
        </Col>
      </Row>

      <Card className="main-card" bordered={false} title="学生学习对话">
        <Flex gap={12} wrap style={{ marginBottom: 16 }}>
          <Select
            allowClear
            placeholder="按班级筛选"
            value={classFilter}
            onChange={setClassFilter}
            options={classOptions}
            style={{ minWidth: 180 }}
          />
          <Select
            allowClear
            placeholder="按题目筛选"
            value={taskFilter}
            onChange={setTaskFilter}
            options={taskOptions}
            style={{ minWidth: 220 }}
          />
          <Select
            allowClear
            showSearch
            placeholder="按学生筛选"
            value={studentFilter}
            onChange={setStudentFilter}
            options={studentOptions}
            optionFilterProp="label"
            style={{ minWidth: 180 }}
          />
          <Button
            onClick={() => {
              setClassFilter(undefined);
              setTaskFilter(undefined);
              setStudentFilter(undefined);
            }}
          >
            清空筛选
          </Button>
        </Flex>
        <Table
          rowKey="conversation_id"
          columns={columns}
          dataSource={filteredConversations}
          pagination={{ pageSize: 6 }}
          scroll={{ x: 820 }}
        />
      </Card>

      <Drawer
        title={
          selectedConversation
            ? `${selectedConversation.student_name} · ${selectedConversation.task_title}`
            : "对话诊断"
        }
        width={900}
        open={Boolean(selectedConversation)}
        onClose={() => {
          setSelectedConversation(undefined);
          setDiagnoses([]);
          setSubmission(null);
        }}
      >
        <Paragraph type="secondary">
          每一轮学生输入都会立即形成诊断并写入数据库。教师可按需查看和修改。
        </Paragraph>
        <Card size="small" title="学生当前作业" style={{ marginBottom: 16 }}>
          {submission ? (
            <Flex justify="space-between" align="center" gap={12}>
              <div>
                <Text strong>{submission.file_name}</Text>
                <br />
                <Text type="secondary">
                  {(submission.file_size / 1024).toFixed(1)} KB ·{" "}
                  {new Date(submission.uploaded_at).toLocaleString()}
                </Text>
              </div>
              <Button onClick={() => void downloadSubmission(submission)}>
                下载查看
              </Button>
            </Flex>
          ) : (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="学生尚未上传作业"
            />
          )}
        </Card>
        <Table
          rowKey="risk_id"
          columns={diagnosisColumns}
          dataSource={diagnoses}
          pagination={false}
          scroll={{ x: 760 }}
        />
      </Drawer>

      <Drawer
        title="风险验证与教师修改"
        width={560}
        open={Boolean(detail)}
        onClose={() => setDetail(undefined)}
      >
        {detail && (
          <Space direction="vertical" size={20} style={{ width: "100%" }}>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="学生">{detail.student_name}</Descriptions.Item>
              <Descriptions.Item label="任务">{detail.task_title}</Descriptions.Item>
              <Descriptions.Item label="行为">
                {detail.selected_behavior
                  ? behaviorLabels[detail.selected_behavior] ?? detail.selected_behavior
                  : "未识别"}
              </Descriptions.Item>
              <Descriptions.Item label="风险">
                系统判断 <RiskBadge level={detail.risk.system_level} />
              </Descriptions.Item>
              <Descriptions.Item label="当前风险">
                <RiskBadge level={detail.risk.level} /> {detail.risk.score}/100
                {detail.risk.level !== detail.risk.system_level && (
                  <Tag color="blue">教师已调整</Tag>
                )}
              </Descriptions.Item>
            </Descriptions>

            <Alert
              type="info"
              showIcon
              message="触发消息"
              description={detail.trigger_message}
            />

            {detail.tutor_decision && (
              <Card size="small" title="EduGuard Tutor 决策链">
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="支架策略">
                    {strategyLabels[detail.tutor_decision.strategy_type] ??
                      detail.tutor_decision.strategy_type}
                  </Descriptions.Item>
                  <Descriptions.Item label="选择理由">
                    {detail.tutor_decision.strategy_reason}
                  </Descriptions.Item>
                  <Descriptions.Item label="回复政策">
                    {detail.tutor_decision.response_policy}
                  </Descriptions.Item>
                  <Descriptions.Item label="生成来源">
                    {detail.tutor_decision.generation_model ??
                      detail.tutor_decision.generated_by}
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            )}


            <Form form={form} layout="vertical" onFinish={submitReview}>
              <Form.Item name="revised_risk_level" label="调整风险等级（可选）">
                <Select
                  allowClear
                  placeholder="不调整则保留当前风险"
                  options={(["low", "medium", "high"] as RiskLevel[]).map(
                    (level) => ({ value: level, label: riskLabels[level] })
                  )}
                />
              </Form.Item>
              <Form.Item name="comment" label="教师备注">
                <Input.TextArea
                  rows={3}
                  placeholder="说明确认、调整或驳回的教学依据"
                />
              </Form.Item>
              <Button type="primary" htmlType="submit" icon={<CheckOutlined />}>
                保存修改
              </Button>
            </Form>

            {detail.reviews.length > 0 && (
              <Card size="small" title="教师操作历史">
                <List
                  dataSource={detail.reviews}
                  renderItem={(item) => (
                    <List.Item>
                      <div>
                        <Text strong>
                          {item.revised_risk_level ? "调整风险" : "添加备注"}
                        </Text>
                        {item.revised_risk_level && (
                          <Tag>{riskLabels[item.revised_risk_level]}</Tag>
                        )}
                        <Paragraph type="secondary">{item.comment || "无备注"}</Paragraph>
                      </div>
                    </List.Item>
                  )}
                />
              </Card>
            )}
          </Space>
        )}
      </Drawer>
    </div>
  );
}
