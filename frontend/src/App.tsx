import {
  BookOutlined,
  DashboardOutlined,
  LogoutOutlined,
  SettingOutlined,
  SafetyCertificateOutlined
} from "@ant-design/icons";
import { Button, ConfigProvider, Layout, Menu, Space, Tag, theme } from "antd";
import { useState } from "react";
import type { User } from "./types";
import LoginPage from "./pages/LoginPage";
import StudentWorkspace from "./pages/StudentWorkspace";
import TeacherDashboard from "./pages/TeacherDashboard";
import TeacherManagement from "./pages/TeacherManagement";
import "./styles.css";

const { Header, Content } = Layout;

export default function App() {
  const [user, setUser] = useState<User | null>(() => {
    const raw = localStorage.getItem("eduguard_user");
    return raw ? JSON.parse(raw) : null;
  });
  const [view, setView] = useState("dashboard");

  function handleLogin(nextUser: User, token: string) {
    localStorage.setItem("eduguard_token", token);
    localStorage.setItem("eduguard_user", JSON.stringify(nextUser));
    setUser(nextUser);
    setView(nextUser.role === "student" ? "student" : "dashboard");
  }

  function logout() {
    localStorage.removeItem("eduguard_token");
    localStorage.removeItem("eduguard_user");
    setUser(null);
  }

  return (
    <ConfigProvider
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: "#3457d5",
          colorInfo: "#3457d5",
          colorSuccess: "#1f9d70",
          colorWarning: "#e89b2c",
          colorError: "#d84a4a",
          borderRadius: 12,
          fontFamily:
            '"Inter", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif'
        }
      }}
    >
      {!user ? (
        <LoginPage onLogin={handleLogin} />
      ) : (
      <Layout className="app-layout">
        <Header className="app-header">
          <div className="brand">
            <span className="brand-mark">
              <SafetyCertificateOutlined />
            </span>
            <div>
              <strong>EduGuard</strong>
              <small>学习交互守护系统</small>
            </div>
            <Tag color="blue">DEMO</Tag>
          </div>
          <Menu
            mode="horizontal"
            selectedKeys={[view]}
            onClick={({ key }) => setView(key)}
            items={
              user.role === "student"
                ? [
                    {
                      key: "student",
                      icon: <BookOutlined />,
                      label: "我的学习空间"
                    }
                  ]
                : [
                    {
                      key: "dashboard",
                      icon: <DashboardOutlined />,
                      label: "教师洞察"
                    },
                    {
                      key: "management",
                      icon: <SettingOutlined />,
                      label: "教学管理"
                    }
                  ]
            }
          />
          <Space>
            <span className="user-name">{user.real_name}</span>
            <Button type="text" icon={<LogoutOutlined />} onClick={logout}>
              退出
            </Button>
          </Space>
        </Header>
        <Content>
          {user.role === "student" ? (
            <StudentWorkspace />
          ) : view === "management" ? (
            <TeacherManagement />
          ) : (
            <TeacherDashboard />
          )}
        </Content>
      </Layout>
      )}
    </ConfigProvider>
  );
}
