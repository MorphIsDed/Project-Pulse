import { render, screen, waitFor } from "@testing-library/react";
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
  updateProjectCalendar: vi.fn(),
  listResources: vi.fn(),
  listAssignments: vi.fn(),
  getProjectWorkload: vi.fn(),
  getLevelingPreview: vi.fn(),
  createResource: vi.fn(),
  updateResource: vi.fn(),
  deleteResource: vi.fn(),
  createAssignment: vi.fn(),
  updateAssignment: vi.fn(),
  deleteAssignment: vi.fn(),
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
  apiMocks.listResources.mockResolvedValue([]);
  apiMocks.listAssignments.mockResolvedValue([]);
  apiMocks.getProjectWorkload.mockResolvedValue({
    resources: [],
    overloads: [],
    summary: {
      resource_count: 0,
      assignment_count: 0,
      load_day_count: 0,
      overload_count: 0,
      overloaded_resource_count: 0,
      excess_work_minutes: 0,
    },
  });
  apiMocks.getLevelingPreview.mockResolvedValue({
    project_id: 100,
    project_version: 1,
    before: {
      excess_work_minutes: 0,
      overload_count: 0,
      project_finish: "2026-01-10",
    },
    after: {
      excess_work_minutes: 0,
      overload_count: 0,
      project_finish: "2026-01-10",
    },
    proposals: [],
    remaining_overloads: [],
    notes: ["No overloads detected."],
  });
}

beforeEach(() => {
  Object.values(apiMocks).forEach((mock) => mock.mockReset());
  stubOwnerProject();
});

describe("WorkspacePage", () => {
  it("loads the organization, workspace, project, tasks, and dependencies", async () => {
    render(<WorkspacePage />);

    expect(
      await screen.findByRole("heading", { name: "Demo Project" }),
    ).toBeInTheDocument();
    expect(await screen.findByText(/lag 0 min/)).toBeInTheDocument();
    expect(screen.getAllByDisplayValue("Alpha").length).toBeGreaterThan(0);
    expect(screen.getAllByDisplayValue("Beta").length).toBeGreaterThan(0);
    expect(await screen.findByText("2026-01-06 09:00")).toBeInTheDocument();
    expect(apiMocks.listWorkspaces).toHaveBeenCalledWith(1);
    expect(apiMocks.listMembers).toHaveBeenCalledWith(1);
    expect(apiMocks.listProjects).toHaveBeenCalledWith(10);
    expect(apiMocks.listTasks).toHaveBeenCalledWith(100);
    expect(apiMocks.getProjectSchedule).toHaveBeenCalledWith(100);
  });

  it("creates an organization and selects it", async () => {
    const browser = userEvent.setup();
    const secondOrg = { ...owner, id: 2, name: "Second Org" };
    apiMocks.listOrganizations.mockResolvedValue([]);
    apiMocks.createOrganization.mockResolvedValue(secondOrg);
    apiMocks.listWorkspaces.mockResolvedValue([]);
    apiMocks.listMembers.mockResolvedValue([]);

    render(<WorkspacePage />);
    expect(
      await screen.findByText("No organizations yet. Create one to begin."),
    ).toBeInTheDocument();

    await browser.type(
      screen.getByLabelText("New organization"),
      "Second Org",
    );
    await browser.click(
      screen.getByRole("button", { name: "Create organization" }),
    );

    expect(
      await screen.findByRole("option", { name: "Second Org (owner)" }),
    ).toBeInTheDocument();
    expect(apiMocks.createOrganization).toHaveBeenCalledWith("Second Org");
    expect(apiMocks.listWorkspaces).toHaveBeenCalledWith(2);
  });

  it("creates a project in the current workspace", async () => {
    const browser = userEvent.setup();
    apiMocks.listProjects.mockResolvedValue([]);
    apiMocks.createProject.mockResolvedValue(secondProject);
    apiMocks.getProject.mockResolvedValue(secondProject);
    apiMocks.listTasks.mockResolvedValue([]);
    apiMocks.listDependencies.mockResolvedValue([]);
    apiMocks.getProjectCalendar.mockResolvedValue({
      ...calendar,
      id: 6,
      project_id: 101,
    });

    render(<WorkspacePage />);
    expect(
      await screen.findByText("No projects in this workspace."),
    ).toBeInTheDocument();

    await browser.type(screen.getByLabelText("New project"), "Second Project");
    await browser.click(screen.getByRole("button", { name: "Create project" }));

    expect(
      await screen.findByRole("heading", { name: "Second Project" }),
    ).toBeInTheDocument();
    expect(apiMocks.createProject).toHaveBeenCalledWith(10, {
      name: "Second Project",
      start_date: null,
      target_finish: null,
    });
  });

  it("creates a task and refreshes the project", async () => {
    const browser = userEvent.setup();
    apiMocks.createTask.mockResolvedValue({
      task: makeTask(3, "Gamma"),
      project_version: 2,
    });
    apiMocks.listTasks
      .mockResolvedValueOnce([alpha, beta])
      .mockResolvedValue([alpha, beta, makeTask(3, "Gamma")]);

    render(<WorkspacePage />);
    await screen.findByRole("heading", { name: "Demo Project" });
    await screen.findByRole("button", { name: "Add dependency" });

    await browser.type(screen.getByLabelText("New task name"), "Gamma");
    await browser.click(screen.getByRole("button", { name: "Add task" }));

    await waitFor(() =>
      expect(apiMocks.createTask).toHaveBeenCalledWith(100, {
        name: "Gamma",
        parent_task_id: null,
        duration_work_minutes: 0,
        priority: 3,
      }),
    );
    expect(await screen.findByDisplayValue("Gamma")).toBeInTheDocument();
  });

  it("creates a dependency between the first two tasks", async () => {
    const browser = userEvent.setup();
    apiMocks.listDependencies.mockResolvedValue([]);
    apiMocks.createDependency.mockResolvedValue({
      dependency,
      project_version: 2,
    });

    render(<WorkspacePage />);
    await screen.findByRole("heading", { name: "Demo Project" });
    await screen.findByRole("button", { name: "Add dependency" });

    await browser.click(
      screen.getByRole("button", { name: "Add dependency" }),
    );

    await waitFor(() =>
      expect(apiMocks.createDependency).toHaveBeenCalledWith(100, {
        predecessor_task_id: 1,
        successor_task_id: 2,
        type: "FS",
        lag_work_minutes: 0,
      }),
    );
  });

  it("updates the working calendar with the current project version", async () => {
    const browser = userEvent.setup();
    const updatedCalendar = { ...calendar, timezone: "Europe/London" };
    apiMocks.updateProjectCalendar.mockResolvedValue({
      calendar: updatedCalendar,
      project: { ...project, version: 2 },
    });

    render(<WorkspacePage />);
    await screen.findByRole("heading", { name: "Demo Project" });

    const timezone = await screen.findByLabelText("Calendar timezone");
    await browser.clear(timezone);
    await browser.type(timezone, "Europe/London");
    await browser.click(
      screen.getByRole("button", { name: "Save calendar" }),
    );

    await waitFor(() =>
      expect(apiMocks.updateProjectCalendar).toHaveBeenCalledWith(100, {
        version: 1,
        timezone: "Europe/London",
        weekly_rules: {
          mon: [["09:00", "17:00"]],
          tue: [],
          wed: [],
          thu: [],
          fri: [],
          sat: [],
          sun: [],
        },
      }),
    );
    expect(await screen.findByDisplayValue("Europe/London")).toBeInTheDocument();
  });

  it("gives viewers read-only planning controls", async () => {
    apiMocks.listOrganizations.mockResolvedValue([viewer]);

    render(<WorkspacePage />);
    await screen.findByRole("heading", { name: "Demo Project" });

    expect(await screen.findByDisplayValue("Alpha")).toBeDisabled();
    expect(
      screen.queryByRole("button", { name: "Create project" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Create workspace" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Add member" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Add task" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Delete project" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Save calendar" }),
    ).not.toBeInTheDocument();
  });

  it("shows API failures as an alert", async () => {
    apiMocks.listOrganizations.mockRejectedValue(
      new ApiError(500, "internal_error", "Could not load organizations."),
    );

    render(<WorkspacePage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Could not load organizations.",
    );
  });
});
