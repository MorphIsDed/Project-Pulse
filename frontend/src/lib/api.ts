export type User = {
  id: number;
  email: string;
  display_name: string;
};

export type AuthResponse = {
  user: User;
  csrf_token: string;
};

export type Role = "owner" | "admin" | "editor" | "viewer";
export type ProjectStatus = "active" | "on_hold" | "completed" | "archived";
export type TaskStatus =
  | "not_started"
  | "in_progress"
  | "blocked"
  | "completed";
export type DependencyType = "FS" | "SS" | "FF" | "SF";
export type ConstraintType =
  | "none"
  | "start_no_earlier_than"
  | "start_no_later_than"
  | "must_start_on"
  | "finish_no_earlier_than"
  | "finish_no_later_than"
  | "must_finish_on";

export type Organization = {
  id: number;
  name: string;
  role: Role;
  created_at: string;
  updated_at: string;
};

export type Member = {
  organization_id: number;
  user_id: number;
  role: Role;
  user: User;
  created_at: string;
  updated_at: string;
};

export type Workspace = {
  id: number;
  organization_id: number;
  name: string;
  role?: Role;
  created_at: string;
  updated_at: string;
};

export type Project = {
  id: number;
  workspace_id: number;
  name: string;
  status: ProjectStatus;
  start_date: string | null;
  target_finish: string | null;
  version: number;
  calendar_id: number | null;
  created_by: number | null;
  role?: Role;
  created_at: string;
  updated_at: string;
};

export type CalendarException = {
  date: string;
  name: string;
  working: boolean;
  intervals?: string[][];
};

export type ProjectCalendar = {
  id: number;
  project_id: number;
  name: string;
  timezone: string;
  weekly_rules: Record<string, string[][]>;
  exceptions: CalendarException[];
  created_at: string;
  updated_at: string;
};

export type ProjectCalendarUpdate = {
  version: number;
  name?: string;
  timezone?: string;
  weekly_rules?: Record<string, string[][]>;
  exceptions?: CalendarException[];
};

export type Task = {
  id: number;
  project_id: number;
  parent_task_id: number | null;
  name: string;
  description: string;
  status: TaskStatus;
  duration_work_minutes: number;
  progress: number;
  priority: number;
  constraint_type: ConstraintType;
  constraint_date: string | null;
  estimate_optimistic: number | null;
  estimate_most_likely: number | null;
  estimate_pessimistic: number | null;
  created_at: string;
  updated_at: string;
};

export type Dependency = {
  id: number;
  project_id: number;
  predecessor_task_id: number;
  successor_task_id: number;
  type: DependencyType;
  lag_work_minutes: number;
  created_at: string;
  updated_at: string;
};

export type ScheduleWarning = {
  code: string;
  message: string;
  [key: string]: unknown;
};

export type ScheduleTask = Task & {
  early_start: string;
  early_finish: string;
  early_start_at: string;
  early_finish_at: string;
  late_start: string;
  late_finish: string;
  late_start_at: string;
  late_finish_at: string;
  total_float_work_minutes: number;
  free_float_work_minutes: number;
  critical: boolean;
};

export type ProjectSchedule = {
  project_id: number;
  project_version: number;
  project_start: string;
  requested_start: string;
  start_source: "project" | "today_default";
  target_finish: string | null;
  project_finish: string;
  project_finish_at: string;
  calendar: ProjectCalendar;
  tasks: ScheduleTask[];
  dependencies: Dependency[];
  critical_path: number[];
  warnings: ScheduleWarning[];
};

export type ProjectCreate = {
  name: string;
  start_date?: string | null;
  target_finish?: string | null;
};

export type ProjectUpdate = {
  version: number;
  name?: string;
  status?: ProjectStatus;
  start_date?: string | null;
  target_finish?: string | null;
};

export type TaskCreate = {
  name: string;
  description?: string;
  status?: TaskStatus;
  duration_work_minutes?: number;
  progress?: number;
  priority?: number;
  parent_task_id?: number | null;
  constraint_type?: ConstraintType;
  constraint_date?: string | null;
  estimate_optimistic?: number | null;
  estimate_most_likely?: number | null;
  estimate_pessimistic?: number | null;
};

export type TaskUpdate = Partial<TaskCreate>;

export type DependencyCreate = {
  predecessor_task_id: number;
  successor_task_id: number;
  type?: DependencyType;
  lag_work_minutes?: number;
};

type ErrorBody = {
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
    request_id?: string;
  };
};

export class ApiError extends Error {
  status: number;
  code: string;
  details?: unknown;
  requestId?: string;

  constructor(
    status: number,
    code: string,
    message: string,
    details?: unknown,
    requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

const API_BASE = "/api/v1";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

let csrfToken: string | null = null;
let csrfRequest: Promise<string> | null = null;

async function parseError(response: Response): Promise<ApiError> {
  let body: ErrorBody | null = null;
  try {
    body = (await response.json()) as ErrorBody;
  } catch {
    body = null;
  }

  const error = body?.error;
  return new ApiError(
    response.status,
    error?.code ?? "http_error",
    error?.message ?? "The request could not be completed.",
    error?.details,
    error?.request_id,
  );
}

async function readBody<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

async function fetchCsrfToken(force = false): Promise<string> {
  if (force) {
    csrfToken = null;
  }
  if (csrfToken) {
    return csrfToken;
  }
  if (csrfRequest) {
    return csrfRequest;
  }

  csrfRequest = (async () => {
    const response = await fetch(`${API_BASE}/auth/csrf`, {
      credentials: "same-origin",
    });
    if (!response.ok) {
      throw await parseError(response);
    }
    const body = (await response.json()) as { csrf_token: string };
    csrfToken = body.csrf_token;
    return csrfToken;
  })();

  try {
    return await csrfRequest;
  } finally {
    csrfRequest = null;
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  allowRetry = true,
): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);

  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (!SAFE_METHODS.has(method)) {
    headers.set("X-CSRFToken", await fetchCsrfToken());
  }

  let response = await fetch(`${API_BASE}${path}`, {
    ...init,
    method,
    headers,
    credentials: "same-origin",
  });

  if (response.ok) {
    return readBody<T>(response);
  }

  const error = await parseError(response);
  if (error.code === "csrf_error" && allowRetry && !SAFE_METHODS.has(method)) {
    headers.set("X-CSRFToken", await fetchCsrfToken(true));
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      method,
      headers,
      credentials: "same-origin",
    });
    if (response.ok) {
      return readBody<T>(response);
    }
    throw await parseError(response);
  }

  throw error;
}

export async function getMe(): Promise<User> {
  const body = await request<{ user: User }>("/auth/me");
  return body.user;
}

export async function login(
  email: string,
  password: string,
  remember: boolean,
): Promise<AuthResponse> {
  const body = await request<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password, remember }),
  });
  csrfToken = body.csrf_token;
  return body;
}

export async function register(
  email: string,
  password: string,
  displayName: string,
): Promise<AuthResponse> {
  const body = await request<AuthResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({
      email,
      password,
      display_name: displayName,
    }),
  });
  csrfToken = body.csrf_token;
  return body;
}

export async function logout(): Promise<void> {
  try {
    await request<{ status: string }>("/auth/logout", { method: "POST" });
  } finally {
    csrfToken = null;
  }
}


function queryString(
  params: Record<string, string | number | null | undefined>,
): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const value = search.toString();
  return value ? `?${value}` : "";
}

export async function listOrganizations(): Promise<Organization[]> {
  const body = await request<{ organizations: Organization[] }>(
    "/organizations",
  );
  return body.organizations;
}

export async function createOrganization(name: string): Promise<Organization> {
  const body = await request<{ organization: Organization }>(
    "/organizations",
    { method: "POST", body: JSON.stringify({ name }) },
  );
  return body.organization;
}

export async function updateOrganization(
  organizationId: number,
  name: string,
): Promise<Organization> {
  const body = await request<{ organization: Organization }>(
    `/organizations/${organizationId}`,
    { method: "PATCH", body: JSON.stringify({ name }) },
  );
  return body.organization;
}

export async function deleteOrganization(organizationId: number): Promise<void> {
  await request<void>(`/organizations/${organizationId}`, {
    method: "DELETE",
  });
}

export async function listMembers(organizationId: number): Promise<Member[]> {
  const body = await request<{ members: Member[] }>(
    `/organizations/${organizationId}/members`,
  );
  return body.members;
}

export async function addMember(
  organizationId: number,
  email: string,
  role: Role,
): Promise<Member> {
  const body = await request<{ member: Member }>(
    `/organizations/${organizationId}/members`,
    { method: "POST", body: JSON.stringify({ email, role }) },
  );
  return body.member;
}

export async function updateMemberRole(
  organizationId: number,
  userId: number,
  role: Role,
): Promise<Member> {
  const body = await request<{ member: Member }>(
    `/organizations/${organizationId}/members/${userId}`,
    { method: "PATCH", body: JSON.stringify({ role }) },
  );
  return body.member;
}

export async function removeMember(
  organizationId: number,
  userId: number,
): Promise<void> {
  await request<void>(
    `/organizations/${organizationId}/members/${userId}`,
    { method: "DELETE" },
  );
}

export async function listWorkspaces(
  organizationId: number,
): Promise<Workspace[]> {
  const body = await request<{ workspaces: Workspace[] }>(
    `/organizations/${organizationId}/workspaces`,
  );
  return body.workspaces;
}

export async function createWorkspace(
  organizationId: number,
  name: string,
): Promise<Workspace> {
  const body = await request<{ workspace: Workspace }>(
    `/organizations/${organizationId}/workspaces`,
    { method: "POST", body: JSON.stringify({ name }) },
  );
  return body.workspace;
}

export async function updateWorkspace(
  workspaceId: number,
  name: string,
): Promise<Workspace> {
  const body = await request<{ workspace: Workspace }>(
    `/workspaces/${workspaceId}`,
    { method: "PATCH", body: JSON.stringify({ name }) },
  );
  return body.workspace;
}

export async function deleteWorkspace(workspaceId: number): Promise<void> {
  await request<void>(`/workspaces/${workspaceId}`, { method: "DELETE" });
}

export async function listProjects(workspaceId: number): Promise<Project[]> {
  const body = await request<{ projects: Project[] }>(
    `/workspaces/${workspaceId}/projects`,
  );
  return body.projects;
}

export async function createProject(
  workspaceId: number,
  payload: ProjectCreate,
): Promise<Project> {
  const body = await request<{ project: Project }>(
    `/workspaces/${workspaceId}/projects`,
    { method: "POST", body: JSON.stringify(payload) },
  );
  return body.project;
}

export async function getProject(projectId: number): Promise<Project> {
  const body = await request<{ project: Project }>(`/projects/${projectId}`);
  return body.project;
}

export async function updateProject(
  projectId: number,
  payload: ProjectUpdate,
): Promise<Project> {
  const body = await request<{ project: Project }>(
    `/projects/${projectId}`,
    { method: "PATCH", body: JSON.stringify(payload) },
  );
  return body.project;
}

export async function deleteProject(projectId: number): Promise<void> {
  await request<void>(`/projects/${projectId}`, { method: "DELETE" });
}

export async function getProjectCalendar(
  projectId: number,
): Promise<ProjectCalendar> {
  const body = await request<{ calendar: ProjectCalendar }>(
    `/projects/${projectId}/calendar`,
  );
  return body.calendar;
}

export async function updateProjectCalendar(
  projectId: number,
  payload: ProjectCalendarUpdate,
): Promise<{ calendar: ProjectCalendar; project: Project }> {
  return request<{ calendar: ProjectCalendar; project: Project }>(
    `/projects/${projectId}/calendar`,
    { method: "PATCH", body: JSON.stringify(payload) },
  );
}

export async function getProjectSchedule(
  projectId: number,
): Promise<ProjectSchedule> {
  const body = await request<{ schedule: ProjectSchedule }>(
    `/projects/${projectId}/schedule`,
  );
  return body.schedule;
}

export async function listTasks(
  projectId: number,
  filters: {
    status?: TaskStatus;
    parent_task_id?: number;
    limit?: number;
    offset?: number;
  } = {},
): Promise<Task[]> {
  const body = await request<{ tasks: Task[] }>(
    `/projects/${projectId}/tasks${queryString(filters)}`,
  );
  return body.tasks;
}

export async function createTask(
  projectId: number,
  payload: TaskCreate,
): Promise<{ task: Task; project_version: number }> {
  return request<{ task: Task; project_version: number }>(
    `/projects/${projectId}/tasks`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export async function updateTask(
  projectId: number,
  taskId: number,
  payload: TaskUpdate,
): Promise<{ task: Task; project_version: number }> {
  return request<{ task: Task; project_version: number }>(
    `/projects/${projectId}/tasks/${taskId}`,
    { method: "PATCH", body: JSON.stringify(payload) },
  );
}

export async function deleteTask(
  projectId: number,
  taskId: number,
): Promise<void> {
  await request<void>(`/projects/${projectId}/tasks/${taskId}`, {
    method: "DELETE",
  });
}

export async function listDependencies(
  projectId: number,
): Promise<Dependency[]> {
  const body = await request<{ dependencies: Dependency[] }>(
    `/projects/${projectId}/dependencies`,
  );
  return body.dependencies;
}

export async function createDependency(
  projectId: number,
  payload: DependencyCreate,
): Promise<{ dependency: Dependency; project_version: number }> {
  return request<{ dependency: Dependency; project_version: number }>(
    `/projects/${projectId}/dependencies`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export async function deleteDependency(
  projectId: number,
  dependencyId: number,
): Promise<void> {
  await request<void>(
    `/projects/${projectId}/dependencies/${dependencyId}`,
    { method: "DELETE" },
  );
}
