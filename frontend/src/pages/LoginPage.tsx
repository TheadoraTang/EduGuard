import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  Space,
  Typography,
  message
} from "antd";
import {
  LockOutlined,
  SafetyCertificateOutlined,
  UserOutlined
} from "@ant-design/icons";
import { useState } from "react";
import { login } from "../api";
import type { User } from "../types";

const { Paragraph, Text, Title } = Typography;

export default function LoginPage({
  onLogin
}: {
  onLogin: (user: User, token: string) => void;
}) {
  const [loading, setLoading] = useState(false);

  async function submit(values: { username: string; password: string }) {
    setLoading(true);
    try {
      const result = await login(values.username, values.password);
      onLogin(result.user, result.access_token);
    } catch {
      message.error("用户名或密码错误，或后端尚未启动。");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-copy">
        <span className="brand-mark login-mark">
          <SafetyCertificateOutlined />
        </span>
        <Text className="eyebrow">EDUGUARD</Text>
        <Title>让每一次 AI 对话，都留下学习发生的证据</Title>
        <Paragraph>
          学生获得有边界的智能辅导，教师看见真实的学习过程，并可按需修订系统判断。
        </Paragraph>
      </div>
      <Card className="login-card" bordered={false}>
        <Space direction="vertical" size={4}>
          <Title level={3}>登录系统</Title>
          <Text type="secondary">系统将根据账号角色进入学生端或教师端。</Text>
        </Space>
        <Form layout="vertical" onFinish={submit} size="large">
          <Form.Item
            name="username"
            label="用户名"
            rules={[{ required: true, message: "请输入用户名" }]}
          >
            <Input prefix={<UserOutlined />} autoComplete="username" />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码"
            rules={[{ required: true, message: "请输入密码" }]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              autoComplete="current-password"
            />
          </Form.Item>
          <Button block type="primary" htmlType="submit" loading={loading}>
            登录
          </Button>
        </Form>
        <Alert
          type="info"
          showIcon
          message="演示账号"
          description={
            <div>
              教师：teacher / teacher123
              <br />
              学生：student / student123
            </div>
          }
        />
      </Card>
    </div>
  );
}
