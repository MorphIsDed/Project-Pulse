import type { FormEvent } from "react";
import type { Task, TaskUpdate, TaskStatus, ProjectCalendar, ProjectCalendarUpdate } from "../lib/api";
const TASK_STATUSES: TaskStatus[] = ["not_started", "in_progress", "blocked", "completed"];

export function value(data: FormData, name: string): string {
  return String(data.get(name) ?? "").trim();
}

export function requiredNumber(data: FormData, name: string): number {
  return Number(value(data, name));
}

type TaskCardProps = {
  task: Task;
  tasks: Task[];
  canEdit: boolean;
  busy: boolean;
  onUpdate: (taskId: number, payload: TaskUpdate) => Promise<void>;
  onDelete: (taskId: number) => Promise<void>;
};

export function TaskCard({
  task,
  tasks,
  canEdit,
  busy,
  onUpdate,
  onDelete,
}: TaskCardProps) {
  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const parent = value(data, "parent_task_id");
    await onUpdate(task.id, {
      name: value(data, "name"),
      status: value(data, "status") as TaskStatus,
      duration_work_minutes: requiredNumber(data, "duration_work_minutes"),
      progress: requiredNumber(data, "progress"),
      priority: requiredNumber(data, "priority"),
      parent_task_id: parent === "" ? null : Number(parent),
    });
  }

  return (
    <div className="task-editor">
      <form className="item-form" onSubmit={handleSubmit}>
        <label>
          Task name
          <input name="name" defaultValue={task.name} disabled={!canEdit} />
        </label>
        <label>
          Status
          <select name="status" defaultValue={task.status} disabled={!canEdit}>
            {TASK_STATUSES.map((status) => (
              <option key={status} value={status}>
                {status.replaceAll("_", " ")}
              </option>
            ))}
          </select>
        </label>
        <label>
          Progress
          <input
            name="progress"
            type="number"
            min="0"
            max="100"
            defaultValue={task.progress}
            disabled={!canEdit}
          />
        </label>
        <label>
          Duration (min)
          <input
            name="duration_work_minutes"
            type="number"
            min="0"
            defaultValue={task.duration_work_minutes}
            disabled={!canEdit}
          />
        </label>
        <label>
          Priority
          <input
            name="priority"
            type="number"
            min="1"
            max="5"
            defaultValue={task.priority}
            disabled={!canEdit}
          />
        </label>
        <label>
          Parent
          <select
            name="parent_task_id"
            defaultValue={task.parent_task_id ?? ""}
            disabled={!canEdit}
          >
            <option value="">No parent</option>
            {tasks
              .filter((candidate) => candidate.id !== task.id)
              .map((candidate) => (
                <option key={candidate.id} value={candidate.id}>
                  {candidate.name}
                </option>
              ))}
          </select>
        </label>
        {canEdit ? (
          <div className="item-actions">
            <button type="submit" disabled={busy}>
              Save task
            </button>
            <button
              type="button"
              className="danger"
              onClick={() => void onDelete(task.id)}
              disabled={busy}
            >
              Delete task
            </button>
          </div>
        ) : null}
      </form>
    </div>
  );
}

export const WEEKDAYS = [
  { key: "mon", label: "Monday" },
  { key: "tue", label: "Tuesday" },
  { key: "wed", label: "Wednesday" },
  { key: "thu", label: "Thursday" },
  { key: "fri", label: "Friday" },
  { key: "sat", label: "Saturday" },
  { key: "sun", label: "Sunday" },
];

export type CalendarDraft = Omit<ProjectCalendarUpdate, "version">;

type CalendarEditorProps = {
  calendar: ProjectCalendar;
  busy: boolean;
  onSave: (payload: CalendarDraft) => Promise<void>;
};

export function CalendarEditor({ calendar, busy, onSave }: CalendarEditorProps) {
  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const weekly_rules: Record<string, string[][]> = {};
    for (const day of WEEKDAYS) {
      const enabled = data.get(`${day.key}_enabled`) === "on";
      weekly_rules[day.key] = enabled
        ? [
            [
              value(data, `${day.key}_start`),
              value(data, `${day.key}_end`),
            ],
          ].filter(([start, end]) => start && end)
        : [];
    }
    await onSave({
      timezone: value(data, "timezone"),
      weekly_rules,
    });
  }

  return (
    <form
      className="stack-form calendar-form"
      onSubmit={handleSubmit}
      key={`${calendar.id}-${calendar.updated_at}`}
    >
      <label className="field">
        Calendar timezone
        <input name="timezone" defaultValue={calendar.timezone} required />
      </label>
      <div className="calendar-days">
        {WEEKDAYS.map((day) => {
          const intervals = calendar.weekly_rules[day.key] ?? [];
          const first = intervals[0] ?? ["09:00", "17:00"];
          return (
            <div className="calendar-day" key={day.key}>
              <label>
                <input
                  name={`${day.key}_enabled`}
                  type="checkbox"
                  defaultChecked={intervals.length > 0}
                />
                {day.label}
              </label>
              <input
                name={`${day.key}_start`}
                type="time"
                aria-label={`${day.label} start`}
                defaultValue={first[0] ?? "09:00"}
              />
              <input
                name={`${day.key}_end`}
                type="time"
                aria-label={`${day.label} end`}
                defaultValue={first[1] ?? "17:00"}
              />
            </div>
          );
        })}
      </div>
      <p className="muted">
        Weekly hours use one working window per day. Existing holiday
        exceptions are preserved.
      </p>
      <button type="submit" disabled={busy}>
        Save calendar
      </button>
    </form>
  );
}

