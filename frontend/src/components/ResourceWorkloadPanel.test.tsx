import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ResourceWorkloadPanel from "./ResourceWorkloadPanel";
import type {
  Assignment,
  LevelingPreview,
  ProjectWorkload,
  Resource,
  Task,
} from "../lib/api";

const apiMocks = vi.hoisted(() => ({
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
}));

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, ...apiMocks };
});

const createdAt = "2026-01-01T00:00:00Z";

const task: Task = {
  id: 1,
  project_id: 100,
  parent_task_id: null,
  name: "Draft the plan",
  description: "",
  status: "not_started",
  duration_work_minutes: 480,
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

const resource: Resource = {
  id: 5,
  project_id: 100,
  name: "Alex",
  role: "Developer",
  capacity_work_minutes_per_day: 480,
  created_at: createdAt,
  updated_at: createdAt,
};

const assignment: Assignment = {
  id: 9,
  project_id: 100,
  resource_id: 5,
  task_id: 1,
  allocation_percent: 100,
  created_at: createdAt,
  updated_at: createdAt,
};

const workload: ProjectWorkload = {
  resources: [
    {
      resource_id: 5,
      resource_name: "Alex",
      capacity_work_minutes_per_day: 480,
      total_assigned_work_minutes: 960,
      load_days: [
        {
          date: "2026-01-05",
          assigned_work_minutes: 960,
          load_percent: 200,
          overloaded: true,
        },
      ],
      overloaded_dates: ["2026-01-05"],
    },
  ],
  overloads: [
    {
      resource_id: 5,
      resource_name: "Alex",
      date: "2026-01-05",
      assigned_work_minutes: 960,
      capacity_work_minutes: 480,
      excess_work_minutes: 480,
      load_percent: 200,
      tasks: [],
    },
  ],
  summary: {
    resource_count: 1,
    assignment_count: 1,
    load_day_count: 1,
    overload_count: 1,
    overloaded_resource_count: 1,
    excess_work_minutes: 480,
  },
};

const preview: LevelingPreview = {
  project_id: 100,
  project_version: 4,
  before: {
    excess_work_minutes: 480,
    overload_count: 1,
    project_finish: "2026-01-05",
  },
  after: {
    excess_work_minutes: 0,
    overload_count: 0,
    project_finish: "2026-01-06",
  },
  proposals: [
    {
      resource_id: 5,
      resource_name: "Alex",
      task_id: 1,
      task_name: "Draft the plan",
      proposed_start: "2026-01-06",
      proposed_constraint_type: "start_no_earlier_than",
    },
  ],
  remaining_overloads: [],
  notes: ["This is an explainable preview, not an automatic schedule change."],
};

beforeEach(() => {
  Object.values(apiMocks).forEach((mock) => mock.mockReset());
  apiMocks.listResources.mockResolvedValue([resource]);
  apiMocks.listAssignments.mockResolvedValue([assignment]);
  apiMocks.getProjectWorkload.mockResolvedValue(workload);
  apiMocks.getLevelingPreview.mockResolvedValue(preview);
  apiMocks.createResource.mockResolvedValue({
    resource: { ...resource, id: 6, name: "Sam" },
    project_version: 5,
  });
});

describe("ResourceWorkloadPanel", () => {
  it("shows workload overloads and leveling proposals", async () => {
    render(
      <ResourceWorkloadPanel
        projectId={100}
        tasks={[task]}
        canEdit={false}
      />,
    );

    await screen.findByRole("heading", { name: "Resources & workload" });
    expect(screen.getByText("Overloaded")).toBeInTheDocument();
    expect(
      screen.getByText(
        (_content, element) =>
          element?.tagName === "LI" &&
          element.textContent?.includes(
            "Delay Draft the plan for Alex until 2026-01-06",
          ) === true,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/excess minutes, finish 2026-01-06/),
    ).toBeInTheDocument();
  });

  it("creates a resource and refreshes the panel", async () => {
    const browser = userEvent.setup();
    render(
      <ResourceWorkloadPanel projectId={100} tasks={[task]} canEdit />,
    );

    await screen.findByLabelText("Resource name");
    await browser.type(screen.getByLabelText("Resource name"), "Sam");
    await browser.type(screen.getByLabelText("Role"), "Designer");
    await browser.clear(screen.getByLabelText("Capacity (min/day)"));
    await browser.type(screen.getByLabelText("Capacity (min/day)"), "360");
    await browser.click(screen.getByRole("button", { name: "Add resource" }));

    await waitFor(() =>
      expect(apiMocks.createResource).toHaveBeenCalledWith(100, {
        name: "Sam",
        role: "Designer",
        capacity_work_minutes_per_day: 360,
      }),
    );
  });
});
