import { render, screen, waitFor, within, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  type Dependency,
  type Member,
  type Organization,
  type Project,
  type ProjectCalendar,
  type ProjectSchedule,
  type Task,
  type Workspace,
} from "../lib/api";
import WorkspacePage from "./WorkspacePage";

const apiMocks = vi.hoisted(() => ({
  listOrganizations: vi.fn(),
  listWorkspaces: vi.fn(),
  listMembers: vi.fn(),
  listProjects: vi.fn(),
  getProject: vi.fn(),
  listTasks: vi.fn(),
  listDependencies: vi.fn(),
  getProjectCalendar: vi.fn(),
  getProjectSchedule: vi.fn(),
  getProjectSummary: vi.fn(),
  updateTask: vi.fn(),
  deleteTask: vi.fn(),
  updateProjectCalendar: vi.fn(),
  createOrganization: vi.fn(),
  createWorkspace: vi.fn(),
  createProject: vi.fn(),
  createTask: vi.fn(),
  createDependency: vi.fn(),
  deleteDependency: vi.fn(),
}));

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return {
    ...actual,
    ...apiMocks,
  };
});

const createdAt = "2026-01-01T00:00:00Z";

const owner: Organization = {
  id: 1,
  name: "Demo Org",
  role: "owner",
  created_at: createdAt,
  updated_at: createdAt,
};

const viewer: Organization = {
  ...owner,
  role: "viewer",
};

const workspace: Workspace = {
  id: 10,
  organization_id: 1,
  name: "Delivery",
  created_at: createdAt,
  updated_at: createdAt,
};

const member: Member = {
  organization_id: 1,
  user_id: 7,
  role: "owner",
  user: {
    id: 7,
    email: "owner@example.com",
    display_name: "Demo Owner",
  },
  created_at: createdAt,
  updated_at: createdAt,
};

const project: Project = {
  id: 100,
  workspace_id: 10,
  name: "Demo Project",
  status: "active",
  start_date: null,
  target_finish: null,
  version: 1,
  calendar_id: 5,
  created_by: 7,
  created_at: createdAt,
  updated_at: createdAt,
};

const secondProject: Project = {
  ...project,
  id: 101,
  name: "Second Project",
  calendar_id: 6,
};

const calendar: ProjectCalendar = {
  id: 5,
  project_id: 100,
  name: "Standard",
  timezone: "UTC",
  weekly_rules: { mon: [["09:00", "17:00"]] },
  exceptions: [],
  created_at: createdAt,
  updated_at: createdAt,
};

function makeTask(id: number, name: string): Task {
  return {
    id,
    project_id: 100,
    parent_task_id: null,
    name,
    description: "",
    status: "not_started",
    duration_work_minutes: 0,
    progress: 0,
    priority: 3,
    constraint_type: "none",
    constraint_date: null,
    estimate_optimistic: null,
    estimate_most_likely: null,
    estimate_pessimistic: null,
    created_at: createdAt,
    updated_at: createdAt,
  };
}

const alpha = makeTask(1, "Alpha");
const beta = makeTask(2, "Beta");

const dependency: Dependency = {
  id: 20,
  project_id: 100,
  predecessor_task_id: 1,
  successor_task_id: 2,
  type: "FS",
  lag_work_minutes: 0,
  created_at: createdAt,
  updated_at: createdAt,
};

const schedule: ProjectSchedule = {
  project_id: 100,
  project_version: 1,
  project_start: "2026-01-05",
  requested_start: "2026-01-05",
  start_source: "project",
  target_finish: null,
  project_finish: "2026-01-06",
  project_finish_at: "2026-01-06T17:00+00:00",
  calendar,
  tasks: [
    {
      ...alpha,
      early_start: "2026-01-05",
      early_finish: "2026-01-05",
      early_start_at: "2026-01-05T09:00+00:00",
      early_finish_at: "2026-01-05T17:00+00:00",
      late_start: "2026-01-05",
      late_finish: "2026-01-05",
      late_start_at: "2026-01-05T09:00+00:00",
      late_finish_at: "2026-01-05T17:00+00:00",
      total_float_work_minutes: 0,
      free_float_work_minutes: 0,
      critical: true,
    },
    {
      ...beta,
      early_start: "2026-01-06",
      early_finish: "2026-01-06",
      early_start_at: "2026-01-06T09:00+00:00",
      early_finish_at: "2026-01-06T17:00+00:00",
      late_start: "2026-01-06",
      late_finish: "2026-01-06",
      late_start_at: "2026-01-06T09:00+00:00",
      late_finish_at: "2026-01-06T17:00+00:00",
      total_float_work_minutes: 0,
      free_float_work_minutes: 0,
      critical: true,
    },
  ],
  dependencies: [dependency],
  critical_path: [1, 2],
  warnings: [],
};

function stubOwnerProject() {
  apiMocks.listOrganizations.mockResolvedValue([owner]);
  apiMocks.listWorkspaces.mockResolvedValue([workspace]);
  apiMocks.listMembers.mockResolvedValue([member]);
  apiMocks.listProjects.mockResolvedValue([project]);
  apiMocks.getProject.mockResolvedValue(project);
  apiMocks.listTasks.mockResolvedValue([alpha, beta]);
  apiMocks.listDependencies.mockResolvedValue([dependency]);
  apiMocks.getProjectCalendar.mockResolvedValue(calendar);
  apiMocks.getProjectSchedule.mockResolvedValue(schedule);
  apiMocks.getProjectSummary.mockResolvedValue({ project_version: 1, task_count: 2, completed_task_count: 0, completion_percent: 0, status_counts: { not_started: 2, in_progress: 0, blocked: 0, completed: 0 }, duration_stats: null });

}

beforeEach(() => {
  Object.values(apiMocks).forEach((mock) => mock.mockReset());
  stubOwnerProject();
});

describe("WorkspacePage", () => {
  it("loads summary and tasks, then exposes Gantt in Timeline", async () => {
    const user = userEvent.setup(); render(<WorkspacePage />);
    await screen.findByRole("button", { name: /Alpha/ });
    expect(screen.getByText("Total tasks")).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: /Gantt/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Timeline" }));
    expect(await screen.findByRole("img", { name: /Gantt chart/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Export calendar" })).toHaveAttribute("href", "/api/v1/projects/100/export.ics");
    expect(apiMocks.listTasks).toHaveBeenCalledWith(100);
    expect(apiMocks.getProjectSummary).toHaveBeenCalledWith(100);
  });

  it("creates an organization through its management dialog", async () => {
    const user = userEvent.setup(); render(<WorkspacePage />);
    await screen.findByRole("button", { name: /Alpha/ });
    apiMocks.createOrganization.mockResolvedValue({ ...owner, id: 2, name: "New Org" });
    await user.click(screen.getByRole("button", { name: "Manage organizations" }));
    await user.type(screen.getByLabelText("New organization"), "New Org");
    await user.click(screen.getByRole("button", { name: "Create organization" }));
    await waitFor(() => expect(apiMocks.createOrganization).toHaveBeenCalledWith("New Org"));
    await waitFor(() => expect(screen.getByLabelText("Current organization")).toHaveValue("2"));
  });

  it("creates a project in the selected workspace", async () => {
    const user = userEvent.setup(); render(<WorkspacePage />);
    await screen.findByRole("button", { name: /Alpha/ });
    apiMocks.createProject.mockResolvedValue(secondProject);
    apiMocks.getProject.mockResolvedValue(secondProject);
    await user.click(screen.getByRole("button", { name: /New project/ }));
    await user.type(screen.getByRole("textbox", { name: "New project" }), "Second Project");
    await user.click(screen.getByRole("button", { name: "Create project" }));
    await waitFor(() => expect(apiMocks.createProject).toHaveBeenCalledWith(10, { name: "Second Project", start_date: null, target_finish: null }));
    expect(await screen.findByRole("heading", { name: "Second Project" })).toBeInTheDocument();
  });

  it("creates a task and refreshes insights", async () => {
    const user = userEvent.setup(); render(<WorkspacePage />);
    await screen.findByRole("button", { name: /Alpha/ });
    await user.click(screen.getByRole("button", { name: "Add task" }));
    const dialog = screen.getByRole("dialog");
    await user.type(within(dialog).getByLabelText("New task name"), "Gamma");
    await user.click(within(dialog).getByRole("button", { name: "Add task" }));
    await waitFor(() => expect(apiMocks.createTask).toHaveBeenCalledWith(100, { name: "Gamma", parent_task_id: null, duration_work_minutes: 0, priority: 3 }));
    await waitFor(() => expect(apiMocks.getProjectSummary).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("edits a task, preserves failed input, and supports retry", async () => {
    const user = userEvent.setup(); render(<WorkspacePage />);
    await user.click(await screen.findByRole("button", { name: /Alpha/ }));
    const input = screen.getByLabelText("Task name");
    await user.clear(input); await user.type(input, "Updated name");
    apiMocks.updateTask.mockRejectedValueOnce(new ApiError(409, "conflict", "Conflict"));
    await user.click(screen.getByRole("button", { name: "Save task" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Conflict");
    expect(input).toHaveValue("Updated name");
    apiMocks.updateTask.mockResolvedValueOnce({ task: { ...alpha, name: "Updated name" }, project_version: 2 });
    await user.click(screen.getByRole("button", { name: "Save task" }));
    await waitFor(() => expect(apiMocks.updateTask).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(apiMocks.getProjectSummary).toHaveBeenCalledTimes(2));
  });

  it("shows task dependencies and submits the selected successor", async () => {
    const user = userEvent.setup(); render(<WorkspacePage />);
    await user.click(await screen.findByRole("button", { name: /Beta/ }));
    expect(screen.getByText(/lag 0 min/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Add dependency" }));
    await waitFor(() => expect(apiMocks.createDependency).toHaveBeenCalledWith(100, { predecessor_task_id: 1, successor_task_id: 2, type: "FS", lag_work_minutes: 0 }));
  });

  it("updates the calendar with the current project version", async () => {
    const user = userEvent.setup(); render(<WorkspacePage />);
    await screen.findByRole("button", { name: /Alpha/ });
    apiMocks.updateProjectCalendar.mockResolvedValue({ calendar, project: { ...project, version: 2 } });
    await user.click(screen.getByRole("button", { name: "Settings" }));
    const timezone = screen.getByLabelText("Calendar timezone");
    await user.clear(timezone); await user.type(timezone, "Asia/Kolkata");
    await user.click(screen.getByRole("button", { name: "Save calendar" }));
    await waitFor(() => expect(apiMocks.updateProjectCalendar).toHaveBeenCalledWith(100, expect.objectContaining({ version: 1, timezone: "Asia/Kolkata" })));
  });

  it("keeps viewer planning controls read-only", async () => {
    apiMocks.listOrganizations.mockResolvedValue([viewer]);
    const user = userEvent.setup(); render(<WorkspacePage />);
    await user.click(await screen.findByRole("button", { name: /Alpha/ }));
    expect(screen.getByLabelText("Task name")).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Save task" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add dependency" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add task" })).not.toBeInTheDocument();
  });

  it("allows editing when summary loading fails", async () => {
    apiMocks.getProjectSummary.mockRejectedValue(new Error("Offline"));
    const user = userEvent.setup(); render(<WorkspacePage />);
    await user.click(await screen.findByRole("button", { name: /Alpha/ }));
    expect(screen.getByRole("button", { name: "Save task" })).toBeEnabled();
  });

  it("resets the view and selection when changing projects", async () => {
    apiMocks.listProjects.mockResolvedValue([project, secondProject]);
    apiMocks.getProject.mockImplementation((id) => Promise.resolve(id === 100 ? project : secondProject));
    const user = userEvent.setup(); render(<WorkspacePage />);
    await screen.findByRole("button", { name: /Alpha/ });
    await user.click(screen.getByRole("button", { name: "Timeline" }));
    await user.click(screen.getByRole("button", { name: "Second Project" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Tasks" })).toHaveAttribute("aria-current", "page"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await waitFor(() => expect(apiMocks.getProjectSummary).toHaveBeenLastCalledWith(101));
  });

  it("closes the detail dialog on Escape and restores focus", async () => {
    const user = userEvent.setup(); render(<WorkspacePage />);
    const trigger = await screen.findByRole("button", { name: /Alpha/ });
    await user.click(trigger);
    fireEvent(screen.getByRole("dialog"), new Event("cancel", { bubbles: true, cancelable: true }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("confirms the task name before deletion", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const user = userEvent.setup(); render(<WorkspacePage />);
    await user.click(await screen.findByRole("button", { name: /Alpha/ }));
    await user.click(screen.getByRole("button", { name: "Delete task" }));
    expect(confirm).toHaveBeenCalledWith('Delete "Alpha"?');
    expect(apiMocks.deleteTask).not.toHaveBeenCalled();
    confirm.mockReturnValue(true);
    await user.click(screen.getByRole("button", { name: "Delete task" }));
    await waitFor(() => expect(apiMocks.deleteTask).toHaveBeenCalledWith(100, 1));
    confirm.mockRestore();
  });

  it("shows API failures as an alert", async () => {
    apiMocks.listOrganizations.mockRejectedValue(new ApiError(503, "offline", "Unavailable"));
    render(<WorkspacePage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Unavailable");
  });
});
