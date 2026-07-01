import axios from "axios";
import type {
  Dashboard,
  ClassRoom,
  ConversationDiagnosis,
  ConversationDetail,
  ConversationSummary,
  InteractionResult,
  RiskDetail,
  RiskLevel,
  Submission,
  Task,
  User
} from "./types";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 25000
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("eduguard_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("eduguard_token");
      localStorage.removeItem("eduguard_user");
    }
    return Promise.reject(error);
  }
);

export async function login(
  username: string,
  password: string
): Promise<{ access_token: string; user: User }> {
  return (await api.post("/auth/login", { username, password })).data;
}

export async function getMe(): Promise<User> {
  return (await api.get<User>("/auth/me")).data;
}

export async function getTasks(): Promise<Task[]> {
  return (await api.get<Task[]>("/tasks")).data;
}

export async function createConversation(taskId: string): Promise<string> {
  return (await api.post("/conversations", { task_id: taskId })).data.id;
}

export async function getStudentConversations(): Promise<ConversationSummary[]> {
  return (await api.get<ConversationSummary[]>("/student/conversations")).data;
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  return (await api.get<ConversationDetail>(`/conversations/${id}`)).data;
}

export async function sendMessage(
  conversationId: string,
  content: string
): Promise<InteractionResult> {
  return (
    await api.post<InteractionResult>(
      `/conversations/${conversationId}/messages`,
      { content }
    )
  ).data;
}

export async function submitReflection(
  conversationId: string,
  content: string
): Promise<void> {
  await api.post(`/conversations/${conversationId}/reflections`, { content });
}

export async function getSubmission(taskId: string): Promise<Submission | null> {
  return (await api.get<Submission | null>(`/tasks/${taskId}/submission`)).data;
}

export async function uploadSubmission(
  taskId: string,
  file: File
): Promise<Submission> {
  return (
    await api.put<Submission>(`/tasks/${taskId}/submission`, file, {
      headers: {
        "Content-Type": file.type || "application/octet-stream",
        "X-File-Name": encodeURIComponent(file.name)
      }
    })
  ).data;
}

export async function getTeacherSubmission(
  conversationId: string
): Promise<Submission | null> {
  return (
    await api.get<Submission | null>(
      `/teacher/conversations/${conversationId}/submission`
    )
  ).data;
}

export async function downloadSubmission(submission: Submission): Promise<void> {
  const response = await api.get(`/teacher/submissions/${submission.id}/download`, {
    responseType: "blob"
  });
  const url = URL.createObjectURL(response.data);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = submission.file_name;
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function getDashboard(): Promise<Dashboard> {
  return (await api.get<Dashboard>("/teacher/dashboard")).data;
}

export async function getConversationDiagnoses(
  conversationId: string
): Promise<ConversationDiagnosis[]> {
  return (
    await api.get<ConversationDiagnosis[]>(
      `/teacher/conversations/${conversationId}/diagnoses`
    )
  ).data;
}

export async function getRiskDetail(riskId: string): Promise<RiskDetail> {
  return (await api.get<RiskDetail>(`/teacher/risks/${riskId}`)).data;
}

export async function reviewRisk(
  riskId: string,
  payload: {
    revised_risk_level?: RiskLevel;
    comment?: string;
  }
): Promise<void> {
  await api.post(`/teacher/risks/${riskId}/reviews`, payload);
}

export async function getClasses(): Promise<ClassRoom[]> {
  return (await api.get<ClassRoom[]>("/teacher/classes")).data;
}

export async function createClass(payload: {
  name: string;
  description?: string;
}): Promise<ClassRoom> {
  return (await api.post<ClassRoom>("/teacher/classes", payload)).data;
}

export async function createStudent(
  classId: string,
  payload: { username: string; password: string; real_name: string }
): Promise<User> {
  return (
    await api.post<User>(`/teacher/classes/${classId}/students`, payload)
  ).data;
}

export async function createTask(payload: {
  class_id: string;
  title: string;
  description: string;
  task_type: string;
  knowledge_points: string[];
  difficulty: number;
  is_published: boolean;
}): Promise<Task> {
  return (await api.post<Task>("/teacher/tasks", payload)).data;
}

export async function updateTask(
  taskId: string,
  payload: Partial<Task>
): Promise<Task> {
  return (await api.patch<Task>(`/teacher/tasks/${taskId}`, payload)).data;
}

export async function uploadTaskImage(file: File): Promise<{ url: string }> {
  return (
    await api.post<{ url: string }>("/teacher/task-images", file, {
      headers: {
        "Content-Type": file.type || "application/octet-stream",
        "X-File-Name": encodeURIComponent(file.name)
      }
    })
  ).data;
}
