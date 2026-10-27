import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ProjectSchedule, ScheduleTask } from "../lib/api";
import GanttChart from "./GanttChart";

const createdAt = "2026-01-01T00:00:00Z";

const calendar = {
  id: 5,
  project_id: 100,
  name: "Standard",
  timezone: "UTC",
  weekly_rules: { mon: [["09:00", "17:00"]] },
  exceptions: [],
  created_at: createdAt,
  updated_at: createdAt,
};

function makeTask(
  id: number,
  name: string,
  overrides: Partial<ScheduleTask> = {},
): ScheduleTask {
  return {
    id,
    project_id: 100,
    parent_task_id: null,
    name,
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
    ...overrides,
  };
}

const alpha = makeTask(1, "Alpha");
const beta = makeTask(2, "Beta", {
  early_start: "2026-01-06",
  early_finish: "2026-01-07",
  early_start_at: "2026-01-06T09:00+00:00",
  early_finish_at: "2026-01-07T17:00+00:00",
  late_start: "2026-01-08",
  late_finish: "2026-01-09",
  late_start_at: "2026-01-08T09:00+00:00",
  late_finish_at: "2026-01-09T17:00+00:00",
  total_float_work_minutes: 960,
  critical: false,
});
const milestone = makeTask(3, "Launch", {
  duration_work_minutes: 0,
  early_start: "2026-01-08",
  early_finish: "2026-01-08",
  early_start_at: "2026-01-08T09:00+00:00",
  early_finish_at: "2026-01-08T09:00+00:00",
  late_start: "2026-01-08",
  late_finish: "2026-01-08",
  late_start_at: "2026-01-08T09:00+00:00",
  late_finish_at: "2026-01-08T09:00+00:00",
  total_float_work_minutes: 0,
  critical: true,
});

const schedule: ProjectSchedule = {
  project_id: 100,
  project_version: 4,
  project_start: "2026-01-05",
  requested_start: "2026-01-05",
  start_source: "project",
  target_finish: null,
  project_finish: "2026-01-09",
  project_finish_at: "2026-01-09T17:00+00:00",
  calendar,
  tasks: [alpha, beta, milestone],
  dependencies: [
    {
      id: 20,
      project_id: 100,
      predecessor_task_id: 1,
      successor_task_id: 2,
      type: "FS",
      lag_work_minutes: 0,
      created_at: createdAt,
      updated_at: createdAt,
    },
  ],
  critical_path: [1, 3],
  warnings: [],
};

describe("GanttChart", () => {
  it("renders bars, float, milestones, and dependency links", () => {
    const { container } = render(<GanttChart schedule={schedule} />);

    expect(
      screen.getByRole("img", { name: "Gantt chart for 3 tasks" }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Alpha").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Beta").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Launch").length).toBeGreaterThan(0);

    const alphaBar = container.querySelector(
      '[data-testid="gantt-task-1"] .gantt-bar',
    );
    expect(alphaBar).toHaveClass("critical");
    expect(alphaBar).toHaveAttribute("width", "24");

    const betaBar = container.querySelector(
      '[data-testid="gantt-task-2"] .gantt-bar',
    );
    expect(betaBar).not.toHaveClass("critical");
    expect(betaBar).toHaveAttribute("width", "54");

    expect(
      container.querySelector('[data-testid="gantt-task-2"] .gantt-float-bar'),
    ).toHaveAttribute("width", "60");
    expect(
      screen.getByTestId("gantt-task-3").tagName.toLowerCase(),
    ).toBe("polygon");
    expect(screen.getByTestId("gantt-dependency-20")).toBeInTheDocument();
  });

  it("shows an empty state when the project has no tasks", () => {
    render(
      <GanttChart
        schedule={{
          ...schedule,
          tasks: [],
          dependencies: [],
          critical_path: [],
        }}
      />,
    );

    expect(
      screen.getByText("No tasks to display on the Gantt chart."),
    ).toBeInTheDocument();
  });
});
