import { type FormEvent, useEffect, useState } from "react";

import {
  ApiError,
  type Assignment,
  type LevelingPreview,
  type ProjectWorkload,
  type Resource,
  type Task,
  createAssignment,
  createResource,
  deleteAssignment,
  deleteResource,
  getLevelingPreview,
  getProjectWorkload,
  listAssignments,
  listResources,
  updateAssignment,
  updateResource,
} from "../lib/api";

type Props = {
  projectId: number;
  tasks: Task[];
  canEdit: boolean;
  refreshKey?: number;
};

function message(reason: unknown): string {
  if (reason instanceof ApiError) return reason.message;
  if (reason instanceof Error) return reason.message;
  return "The resource request could not be completed.";
}

function value(data: FormData, key: string): string {
  return String(data.get(key) ?? "").trim();
}

export default function ResourceWorkloadPanel({
  projectId,
  tasks,
  canEdit,
  refreshKey = 0,
}: Props) {
  const [resources, setResources] = useState<Resource[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [workload, setWorkload] = useState<ProjectWorkload | null>(null);
  const [preview, setPreview] = useState<LevelingPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [localRefresh, setLocalRefresh] = useState(0);

  useEffect(() => {
    let active = true;
    setError(null);
    Promise.all([
      listResources(projectId),
      listAssignments(projectId),
      getProjectWorkload(projectId),
      getLevelingPreview(projectId),
    ])
      .then(([resourceItems, assignmentItems, workloadItem, previewItem]) => {
        if (!active) return;
        setResources(resourceItems);
        setAssignments(assignmentItems);
        setWorkload(workloadItem);
        setPreview(previewItem);
      })
      .catch((reason) => {
        if (active) setError(message(reason));
      });
    return () => {
      active = false;
    };
  }, [projectId, refreshKey, localRefresh]);

  async function perform(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      setLocalRefresh((current) => current + 1);
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  function handleCreateResource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const name = value(data, "name");
    if (!name) return;
    void perform(async () => {
      await createResource(projectId, {
        name,
        role: value(data, "role"),
        capacity_work_minutes_per_day: Number(data.get("capacity")) || 480,
      });
      form.reset();
    });
  }

  function handleUpdateResource(
    event: FormEvent<HTMLFormElement>,
    resource: Resource,
  ) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    void perform(async () => {
      await updateResource(projectId, resource.id, {
        name: resource.name,
        role: value(data, "role"),
        capacity_work_minutes_per_day: Number(data.get("capacity")),
      });
    });
  }

  function handleCreateAssignment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const resourceId = Number(data.get("resource_id"));
    const taskId = Number(data.get("task_id"));
    if (!resourceId || !taskId) return;
    void perform(async () => {
      await createAssignment(projectId, {
        resource_id: resourceId,
        task_id: taskId,
        allocation_percent: Number(data.get("allocation")) || 100,
      });
      form.reset();
    });
  }

  function handleUpdateAssignment(
    event: FormEvent<HTMLFormElement>,
    assignment: Assignment,
  ) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    void perform(async () => {
      await updateAssignment(projectId, assignment.id, {
        allocation_percent: Number(data.get("allocation")),
      });
    });
  }

  function handleReload() {
    setPreview(null);
    setLocalRefresh((current) => current + 1);
  }

  const resourceNames = new Map(
    resources.map((resource) => [resource.id, resource.name]),
  );
  const taskNames = new Map(tasks.map((task) => [task.id, task.name]));

  return (
    <section className="resource-panel">
      <div className="panel-heading">
        <div>
          <h3>Resources &amp; workload</h3>
          <p className="muted">
            Assign people to tasks and preview leveling before changing the
            plan.
          </p>
        </div>
        <button type="button" onClick={handleReload} disabled={busy}>
          Refresh workload
        </button>
      </div>

      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}

      {workload ? (
        <p className="schedule-meta">
          {workload.summary.resource_count} resources A-{" "}
          {workload.summary.assignment_count} assignments A-{" "}
          {workload.summary.overload_count} overloads A-{" "}
          {workload.summary.excess_work_minutes} excess minutes
        </p>
      ) : null}

      {canEdit ? (
        <form className="stack-form" onSubmit={handleCreateResource}>
          <div className="form-row">
            <label className="field">
              Resource name
              <input name="name" placeholder="Alex" required />
            </label>
            <label className="field">
              Role
              <input name="role" placeholder="Developer" />
            </label>
            <label className="field">
              Capacity (min/day)
              <input
                name="capacity"
                type="number"
                min="1"
                max="1440"
                defaultValue="480"
              />
            </label>
          </div>
          <button type="submit" disabled={busy}>
            Add resource
          </button>
        </form>
      ) : null}

      {resources.length === 0 ? (
        <p className="muted">No resources yet.</p>
      ) : (
        <ul className="item-list compact">
          {resources.map((resource) => (
            <li className="member-row" key={resource.id}>
              <strong>{resource.name}</strong>
              {canEdit ? (
                <form
                  className="member-form"
                  onSubmit={(event) => handleUpdateResource(event, resource)}
                >
                  <input
                    name="role"
                    aria-label={`Role for ${resource.name}`}
                    defaultValue={resource.role}
                    placeholder="Role"
                  />
                  <input
                    name="capacity"
                    aria-label={`Capacity for ${resource.name}`}
                    type="number"
                    min="1"
                    max="1440"
                    defaultValue={resource.capacity_work_minutes_per_day}
                  />
                  <button type="submit" disabled={busy}>
                    Save
                  </button>
                  <button
                    type="button"
                    className="danger"
                    onClick={() =>
                      void perform(async () => {
                        await deleteResource(projectId, resource.id);
                      })
                    }
                    disabled={busy}
                  >
                    Delete
                  </button>
                </form>
              ) : (
                <span className="muted">
                  {resource.role || "Unassigned role"} A-{" "}
                  {resource.capacity_work_minutes_per_day} min/day
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      {assignments.length > 0 ? (
        <ul className="item-list compact">
          {assignments.map((assignment) => (
            <li className="member-row" key={assignment.id}>
              <span>
                <strong>{resourceNames.get(assignment.resource_id)}</strong>{" "}
                {taskNames.get(assignment.task_id) ?? assignment.task_id}
                <span className="role-chip small">
                  {assignment.allocation_percent}%
                </span>
              </span>
              {canEdit ? (
                <form
                  className="member-form"
                  onSubmit={(event) =>
                    handleUpdateAssignment(event, assignment)
                  }
                >
                  <input
                    name="allocation"
                    aria-label={`Allocation for assignment ${assignment.id}`}
                    type="number"
                    min="1"
                    max="100"
                    defaultValue={assignment.allocation_percent}
                  />
                  <button type="submit" disabled={busy}>
                    Update
                  </button>
                  <button
                    type="button"
                    className="danger"
                    onClick={() =>
                      void perform(async () => {
                        await deleteAssignment(projectId, assignment.id);
                      })
                    }
                    disabled={busy}
                  >
                    Remove
                  </button>
                </form>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">No assignments yet.</p>
      )}

      {canEdit && resources.length > 0 && tasks.length > 0 ? (
        <form className="stack-form" onSubmit={handleCreateAssignment}>
          <div className="form-row">
            <label className="field">
              Assign resource
              <select name="resource_id" defaultValue={resources[0]?.id ?? ""}>
                {resources.map((resource) => (
                  <option key={resource.id} value={resource.id}>
                    {resource.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              To task
              <select name="task_id" defaultValue={tasks[0]?.id ?? ""}>
                {tasks.map((task) => (
                  <option key={task.id} value={task.id}>
                    {task.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              Allocation (%)
              <input
                name="allocation"
                type="number"
                min="1"
                max="100"
                defaultValue="100"
              />
            </label>
          </div>
          <button type="submit" disabled={busy}>
            Add assignment
          </button>
        </form>
      ) : null}

      {workload && workload.resources.some((item) => item.load_days.length) ? (
        <div className="schedule-table-wrap">
          <table className="schedule-table">
            <thead>
              <tr>
                <th>Resource</th>
                <th>Date</th>
                <th>Load</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {workload.resources.flatMap((resource) =>
                resource.load_days.map((day) => (
                  <tr key={`${resource.resource_id}-${day.date}`}>
                    <td>{resource.resource_name}</td>
                    <td>{day.date}</td>
                    <td>
                      {day.assigned_work_minutes} /{" "}
                      {resource.capacity_work_minutes_per_day} min (
                      {day.load_percent}%)
                    </td>
                    <td>{day.overloaded ? "Overloaded" : "Within capacity"}</td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
      ) : null}

      {preview ? (
        <section className="leveling-preview">
          <h4>Leveling preview</h4>
          <p className="muted">
            Before: {preview.before.overload_count} overloads,{" "}
            {preview.before.excess_work_minutes} excess minutes, finish{" "}
            {preview.before.project_finish}. After: {preview.after.overload_count}{" "}
            overloads, {preview.after.excess_work_minutes} excess minutes,
            finish {preview.after.project_finish}.
          </p>
          {preview.proposals.length > 0 ? (
            <ul className="item-list compact">
              {preview.proposals.map((proposal) => (
                <li key={`${proposal.resource_id}-${proposal.task_id}`}>
                  Delay <strong>{proposal.task_name}</strong> for{" "}
                  {proposal.resource_name} until {proposal.proposed_start} (
                  {proposal.proposed_constraint_type.replaceAll("_", " ")}).
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No leveling proposals are available.</p>
          )}
          {preview.notes.map((note) => (
            <p className="muted" key={note}>
              {note}
            </p>
          ))}
        </section>
      ) : null}
    </section>
  );
}
