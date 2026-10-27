import { useEffect, useState, type FormEvent } from "react";

import AccountPanel from "../components/AccountPanel";
import GanttChart from "../components/GanttChart";
import InvitationPanel from "../components/InvitationPanel";
import NotificationPanel from "../components/NotificationPanel";
import ResourceWorkloadPanel from "../components/ResourceWorkloadPanel";
import RiskSimulationPanel from "../components/RiskSimulationPanel";
import {
  ApiError,
  addMember,
  createDependency,
  createOrganization,
  createProject,
  createTask,
  createWorkspace,
  deleteDependency,
  deleteOrganization,
  deleteProject,
  deleteTask,
  deleteWorkspace,
  getProject,
  getProjectCalendar,
  getProjectSchedule,
  listDependencies,
  listMembers,
  listOrganizations,
  listProjects,
  listTasks,
  listWorkspaces,
  removeMember,
  updateMemberRole,
  updateOrganization,
  updateProject,
  updateProjectCalendar,
  updateTask,
  updateWorkspace,
  type Dependency,
  type DependencyType,
  type Member,
  type Organization,
  type Project,
  type ProjectCalendar,
  type ProjectCalendarUpdate,
  type ProjectSchedule,
  type ProjectStatus,
  type ProjectUpdate,
  type Role,
  type Task,
  type TaskStatus,
  type TaskUpdate,
  type Workspace,
} from "../lib/api";

const PROJECT_STATUSES: ProjectStatus[] = [
  "active",
  "on_hold",
  "completed",
  "archived",
];
const TASK_STATUSES: TaskStatus[] = [
  "not_started",
  "in_progress",
  "blocked",
  "completed",
];
const ROLES: Role[] = ["owner", "admin", "editor", "viewer"];
const DEPENDENCY_TYPES: DependencyType[] = ["FS", "SS", "FF", "SF"];

function messageFor(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "Something went wrong. Please try again.";
}

function value(data: FormData, name: string): string {
  return String(data.get(name) ?? "").trim();
}

function optionalNumber(data: FormData, name: string): number | null {
  const raw = value(data, name);
  return raw === "" ? null : Number(raw);
}

function requiredNumber(data: FormData, name: string): number {
  return Number(value(data, name));
}

function errorMessage(error: unknown): string {
  return messageFor(error);
}

type TaskCardProps = {
  task: Task;
  tasks: Task[];
  canEdit: boolean;
  busy: boolean;
  onUpdate: (taskId: number, payload: TaskUpdate) => Promise<void>;
  onDelete: (taskId: number) => Promise<void>;
};

function TaskCard({
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
    <li className="item-card">
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
    </li>
  );
}

const WEEKDAYS = [
  { key: "mon", label: "Monday" },
  { key: "tue", label: "Tuesday" },
  { key: "wed", label: "Wednesday" },
  { key: "thu", label: "Thursday" },
  { key: "fri", label: "Friday" },
  { key: "sat", label: "Saturday" },
  { key: "sun", label: "Sunday" },
];

type CalendarDraft = Omit<ProjectCalendarUpdate, "version">;

type CalendarEditorProps = {
  calendar: ProjectCalendar;
  busy: boolean;
  onSave: (payload: CalendarDraft) => Promise<void>;
};

function CalendarEditor({ calendar, busy, onSave }: CalendarEditorProps) {
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

function formatScheduleTime(value: string): string {
  return value.replace("T", " ").slice(0, 16);
}

export default function WorkspacePage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState<number | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [workspaceId, setWorkspaceId] = useState<number | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [dependencies, setDependencies] = useState<Dependency[]>([]);
  const [calendar, setCalendar] = useState<ProjectCalendar | null>(null);
  const [schedule, setSchedule] = useState<ProjectSchedule | null>(null);
  const [scheduleError, setScheduleError] = useState<string | null>(null);
  const [projectRefresh, setProjectRefresh] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const organization =
    organizations.find((item) => item.id === organizationId) ?? null;
  const workspace =
    workspaces.find((item) => item.id === workspaceId) ?? null;
  const project = projects.find((item) => item.id === projectId) ?? null;
  const role = organization?.role ?? "viewer";
  const canManageTenant = role === "owner" || role === "admin";
  const canDeleteOrganization = role === "owner";
  const canEditPlanning =
    role === "owner" || role === "admin" || role === "editor";
  const canDeleteProject = role === "owner" || role === "admin";

  useEffect(() => {
    let active = true;
    setLoading(true);
    listOrganizations()
      .then((items) => {
        if (!active) return;
        setOrganizations(items);
        setOrganizationId((current) =>
          current !== null && items.some((item) => item.id === current)
            ? current
            : items[0]?.id ?? null,
        );
      })
      .catch((reason) => {
        if (active) setError(errorMessage(reason));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (organizationId === null) {
      setMembers([]);
      setWorkspaces([]);
      setWorkspaceId(null);
      return;
    }
    let active = true;
    setProjects([]);
    setProjectId(null);
    setTasks([]);
    setDependencies([]);
    setCalendar(null);
    setSchedule(null);
    setScheduleError(null);
    Promise.all([
      listWorkspaces(organizationId),
      listMembers(organizationId),
    ])
      .then(([workspaceItems, memberItems]) => {
        if (!active) return;
        setWorkspaces(workspaceItems);
        setMembers(memberItems);
        setWorkspaceId((current) =>
          current !== null &&
          workspaceItems.some((item) => item.id === current)
            ? current
            : workspaceItems[0]?.id ?? null,
        );
      })
      .catch((reason) => {
        if (active) setError(errorMessage(reason));
      });
    return () => {
      active = false;
    };
  }, [organizationId]);

  useEffect(() => {
    if (workspaceId === null) {
      setProjects([]);
      setProjectId(null);
      return;
    }
    let active = true;
    setProjects([]);
    setProjectId(null);
    setTasks([]);
    setDependencies([]);
    setCalendar(null);
    setSchedule(null);
    setScheduleError(null);
    listProjects(workspaceId)
      .then((items) => {
        if (!active) return;
        setProjects(items);
        setProjectId((current) =>
          current !== null && items.some((item) => item.id === current)
            ? current
            : items[0]?.id ?? null,
        );
      })
      .catch((reason) => {
        if (active) setError(errorMessage(reason));
      });
    return () => {
      active = false;
    };
  }, [workspaceId]);

  useEffect(() => {
    if (projectId === null) {
      setTasks([]);
      setDependencies([]);
      setCalendar(null);
      setSchedule(null);
      setScheduleError(null);
      return;
    }
    let active = true;
    Promise.all([
      getProject(projectId),
      listTasks(projectId),
      listDependencies(projectId),
      getProjectCalendar(projectId),
    ])
      .then(([projectItem, taskItems, dependencyItems, calendarItem]) => {
        if (!active) return;
        setProjects((current) =>
          current.map((item) =>
            item.id === projectItem.id ? projectItem : item,
          ),
        );
        setTasks(taskItems);
        setDependencies(dependencyItems);
        setCalendar(calendarItem);
      })
      .catch((reason) => {
        if (active) setError(errorMessage(reason));
      });
    return () => {
      active = false;
    };
  }, [projectId, projectRefresh]);

  useEffect(() => {
    if (projectId === null) {
      setSchedule(null);
      setScheduleError(null);
      return;
    }
    let active = true;
    setScheduleError(null);
    getProjectSchedule(projectId)
      .then((item) => {
        if (active) setSchedule(item);
      })
      .catch((reason) => {
        if (!active) return;
        setSchedule(null);
        setScheduleError(errorMessage(reason));
      });
    return () => {
      active = false;
    };
  }, [projectId, projectRefresh]);

  async function perform(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  function handleCreateOrganization(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const name = value(data, "name");
    if (!name) return;
    void perform(async () => {
      const created = await createOrganization(name);
      setOrganizations((current) =>
        [...current, created].sort((a, b) => a.name.localeCompare(b.name)),
      );
      setOrganizationId(created.id);
      form.reset();
    });
  }

  function handleRenameOrganization(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organization) return;
    const data = new FormData(event.currentTarget);
    const name = value(data, "name");
    if (!name) return;
    void perform(async () => {
      const updated = await updateOrganization(organization.id, name);
      setOrganizations((current) =>
        current
          .map((item) => (item.id === updated.id ? updated : item))
          .sort((a, b) => a.name.localeCompare(b.name)),
      );
    });
  }

  function handleDeleteOrganization() {
    if (!organization) return;
    void perform(async () => {
      await deleteOrganization(organization.id);
      const remaining = organizations.filter(
        (item) => item.id !== organization.id,
      );
      setOrganizations(remaining);
      setOrganizationId(remaining[0]?.id ?? null);
    });
  }

  function handleAddMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organization) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    void perform(async () => {
      await addMember(
        organization.id,
        value(data, "email"),
        value(data, "role") as Role,
      );
      setMembers(await listMembers(organization.id));
      form.reset();
    });
  }

  function handleUpdateMemberRole(
    event: FormEvent<HTMLFormElement>,
    member: Member,
  ) {
    event.preventDefault();
    if (!organization) return;
    const data = new FormData(event.currentTarget);
    void perform(async () => {
      await updateMemberRole(
        organization.id,
        member.user_id,
        value(data, "role") as Role,
      );
      setMembers(await listMembers(organization.id));
    });
  }

  function handleRemoveMember(member: Member) {
    if (!organization) return;
    void perform(async () => {
      await removeMember(organization.id, member.user_id);
      setMembers(await listMembers(organization.id));
    });
  }

  function handleCreateWorkspace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organization) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const name = value(data, "name");
    if (!name) return;
    void perform(async () => {
      const created = await createWorkspace(organization.id, name);
      setWorkspaces((current) =>
        [...current, created].sort((a, b) => a.name.localeCompare(b.name)),
      );
      setWorkspaceId(created.id);
      form.reset();
    });
  }

  function handleRenameWorkspace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspace) return;
    const data = new FormData(event.currentTarget);
    const name = value(data, "name");
    if (!name) return;
    void perform(async () => {
      const updated = await updateWorkspace(workspace.id, name);
      setWorkspaces((current) =>
        current
          .map((item) => (item.id === updated.id ? updated : item))
          .sort((a, b) => a.name.localeCompare(b.name)),
      );
    });
  }

  function handleDeleteWorkspace() {
    if (!workspace) return;
    void perform(async () => {
      await deleteWorkspace(workspace.id);
      const remaining = workspaces.filter((item) => item.id !== workspace.id);
      setWorkspaces(remaining);
      setWorkspaceId(remaining[0]?.id ?? null);
    });
  }

  function handleCreateProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspace) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const name = value(data, "name");
    if (!name) return;
    void perform(async () => {
      const created = await createProject(workspace.id, {
        name,
        start_date: value(data, "start_date") || null,
        target_finish: value(data, "target_finish") || null,
      });
      setProjects((current) =>
        [...current, created].sort((a, b) => a.name.localeCompare(b.name)),
      );
      setProjectId(created.id);
      form.reset();
    });
  }

  function handleUpdateProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!project) return;
    const data = new FormData(event.currentTarget);
    const payload: ProjectUpdate = {
      version: project.version,
      name: value(data, "name"),
      status: value(data, "status") as ProjectStatus,
      start_date: value(data, "start_date") || null,
      target_finish: value(data, "target_finish") || null,
    };
    void perform(async () => {
      const updated = await updateProject(project.id, payload);
      setProjects((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
      setProjectRefresh((current) => current + 1);
    });
  }

  function handleUpdateCalendar(payload: CalendarDraft) {
    if (!project) return Promise.resolve();
    return perform(async () => {
      const updated = await updateProjectCalendar(project.id, {
        version: project.version,
        ...payload,
      });
      setCalendar(updated.calendar);
      setProjects((current) =>
        current.map((item) =>
          item.id === updated.project.id ? updated.project : item,
        ),
      );
      setProjectRefresh((current) => current + 1);
    });
  }

  function handleDeleteProject() {
    if (!project) return;
    void perform(async () => {
      await deleteProject(project.id);
      const remaining = projects.filter((item) => item.id !== project.id);
      setProjects(remaining);
      setProjectId(remaining[0]?.id ?? null);
    });
  }

  function handleCreateTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!project) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const name = value(data, "name");
    if (!name) return;
    const parent = value(data, "parent_task_id");
    void perform(async () => {
      await createTask(project.id, {
        name,
        parent_task_id: parent === "" ? null : Number(parent),
        duration_work_minutes: requiredNumber(data, "duration_work_minutes"),
        priority: requiredNumber(data, "priority"),
      });
      setProjectRefresh((current) => current + 1);
      form.reset();
    });
  }

  function handleUpdateTask(taskId: number, payload: TaskUpdate) {
    if (!project) return Promise.resolve();
    return perform(async () => {
      await updateTask(project.id, taskId, payload);
      setProjectRefresh((current) => current + 1);
    });
  }

  function handleDeleteTask(taskId: number) {
    if (!project) return Promise.resolve();
    return perform(async () => {
      await deleteTask(project.id, taskId);
      setProjectRefresh((current) => current + 1);
    });
  }

  function handleCreateDependency(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!project) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const predecessor = value(data, "predecessor_task_id");
    const successor = value(data, "successor_task_id");
    if (!predecessor || !successor) return;
    void perform(async () => {
      await createDependency(project.id, {
        predecessor_task_id: Number(predecessor),
        successor_task_id: Number(successor),
        type: value(data, "type") as DependencyType,
        lag_work_minutes: requiredNumber(data, "lag_work_minutes"),
      });
      setProjectRefresh((current) => current + 1);
    });
  }

  function handleDeleteDependency(dependencyId: number) {
    if (!project) return;
    void perform(async () => {
      await deleteDependency(project.id, dependencyId);
      setProjectRefresh((current) => current + 1);
    });
  }

  const taskNames = new Map(tasks.map((task) => [task.id, task.name]));

  return (
    <section className="workspace">
      <div className="workspace-heading">
        <div>
          <p className="eyebrow">PLANNING WORKSPACE</p>
          <h1 className="page-title">
            Build the plan,
            <br />
            <em>then see what moves.</em>
          </h1>
        </div>
        {organization ? (
          <div className="role-chip">
            Signed in as <strong>{role}</strong> in {organization.name}
          </div>
        ) : null}
      </div>

      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="workspace-grid">
        <div className="workspace-column">
          <section className="panel">
            <h2>Organizations</h2>
            {loading ? <p className="muted">Loading organizations…</p> : null}
            {!loading && organizations.length === 0 ? (
              <p className="muted">No organizations yet. Create one to begin.</p>
            ) : null}
            {organizations.length > 0 ? (
              <label className="field">
                Current organization
                <select
                  value={organizationId ?? ""}
                  onChange={(event) =>
                    setOrganizationId(Number(event.target.value) || null)
                  }
                >
                  {organizations.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name} ({item.role})
                    </option>
                  ))}
                </select>
              </label>
            ) : null}

            <form className="stack-form" onSubmit={handleCreateOrganization}>
              <label className="field">
                New organization
                <input name="name" placeholder="Studio North" required />
              </label>
              <button type="submit" disabled={busy}>
                Create organization
              </button>
            </form>

            {organization && canManageTenant ? (
              <form className="stack-form" onSubmit={handleRenameOrganization}>
                <label className="field">
                  Rename organization
                  <input
                    key={organization.id}
                    name="name"
                    defaultValue={organization.name}
                    required
                  />
                </label>
                <button type="submit" disabled={busy}>
                  Rename organization
                </button>
              </form>
            ) : null}
            {organization && canDeleteOrganization ? (
              <button
                type="button"
                className="danger"
                onClick={handleDeleteOrganization}
                disabled={busy}
              >
                Delete organization
              </button>
            ) : null}
          </section>

          {organization ? (
            <section className="panel">
              <h2>Members</h2>
              <ul className="item-list">
                {members.map((member) => (
                  <li className="member-row" key={member.user_id}>
                    <div>
                      <strong>{member.user.display_name}</strong>
                      <span className="muted"> {member.user.email}</span>
                    </div>
                    <span className="role-chip small">{member.role}</span>
                    {canManageTenant &&
                    (member.role !== "owner" || role === "owner") ? (
                      <form
                        className="member-form"
                        onSubmit={(event) =>
                          handleUpdateMemberRole(event, member)
                        }
                      >
                        <select name="role" defaultValue={member.role}>
                          {ROLES.map((item) => (
                            <option key={item} value={item}>
                              {item}
                            </option>
                          ))}
                        </select>
                        <button type="submit" disabled={busy}>
                          Update role
                        </button>
                        <button
                          type="button"
                          className="danger"
                          onClick={() => handleRemoveMember(member)}
                          disabled={busy}
                        >
                          Remove
                        </button>
                      </form>
                    ) : null}
                  </li>
                ))}
              </ul>
              {canManageTenant ? (
                <form className="stack-form" onSubmit={handleAddMember}>
                  <label className="field">
                    Member email
                    <input
                      name="email"
                      type="email"
                      placeholder="person@example.com"
                      required
                    />
                  </label>
                  <label className="field">
                    Role
                    <select name="role" defaultValue="viewer">
                      {ROLES.map((item) => (
                        <option key={item} value={item}>
                          {item}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button type="submit" disabled={busy}>
                    Add member
                  </button>
                </form>
              ) : null}
              <InvitationPanel
                organizationId={organization.id}
                canManage={canManageTenant}
                onAccepted={(organizationId) =>
                  setOrganizationId(organizationId)
                }
              />
            </section>
          ) : null}

          <NotificationPanel refreshKey={projectRefresh} />
          <AccountPanel />
        </div>

        <div className="workspace-column">
          {organization ? (
            <section className="panel">
              <h2>Workspaces</h2>
              {workspaces.length > 0 ? (
                <label className="field">
                  Current workspace
                  <select
                    value={workspaceId ?? ""}
                    onChange={(event) =>
                      setWorkspaceId(Number(event.target.value) || null)
                    }
                  >
                    {workspaces.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <p className="muted">No workspaces in this organization.</p>
              )}

              {canManageTenant ? (
                <>
                  <form className="stack-form" onSubmit={handleCreateWorkspace}>
                    <label className="field">
                      New workspace
                      <input name="name" placeholder="Delivery" required />
                    </label>
                    <button type="submit" disabled={busy}>
                      Create workspace
                    </button>
                  </form>
                  {workspace ? (
                    <form className="stack-form" onSubmit={handleRenameWorkspace}>
                      <label className="field">
                        Rename workspace
                        <input
                          key={workspace.id}
                          name="name"
                          defaultValue={workspace.name}
                          required
                        />
                      </label>
                      <button type="submit" disabled={busy}>
                        Rename workspace
                      </button>
                    </form>
                  ) : null}
                  {workspace ? (
                    <button
                      type="button"
                      className="danger"
                      onClick={handleDeleteWorkspace}
                      disabled={busy}
                    >
                      Delete workspace
                    </button>
                  ) : null}
                </>
              ) : null}
            </section>
          ) : null}

          {workspace ? (
            <section className="panel">
              <h2>Projects</h2>
              {projects.length > 0 ? (
                <label className="field">
                  Current project
                  <select
                    value={projectId ?? ""}
                    onChange={(event) =>
                      setProjectId(Number(event.target.value) || null)
                    }
                  >
                    {projects.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name} ({item.status})
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <p className="muted">No projects in this workspace.</p>
              )}

              {canEditPlanning ? (
                <form className="stack-form" onSubmit={handleCreateProject}>
                  <label className="field">
                    New project
                    <input name="name" placeholder="Website launch" required />
                  </label>
                  <div className="form-row">
                    <label className="field">
                      Start date
                      <input name="start_date" type="date" />
                    </label>
                    <label className="field">
                      Target finish
                      <input name="target_finish" type="date" />
                    </label>
                  </div>
                  <button type="submit" disabled={busy}>
                    Create project
                  </button>
                </form>
              ) : null}
            </section>
          ) : null}
        </div>
      </div>

      {project ? (
        <section className="panel project-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">PROJECT</p>
              <h2>{project.name}</h2>
              <p className="muted">
                Version {project.version}
                {calendar
                  ? ` · ${calendar.timezone} working calendar`
                  : ""}
              </p>
            </div>
            {canDeleteProject ? (
              <button
                type="button"
                className="danger"
                onClick={handleDeleteProject}
                disabled={busy}
              >
                Delete project
              </button>
            ) : null}
          </div>

          {canEditPlanning ? (
            <form className="stack-form" onSubmit={handleUpdateProject}>
              <div className="form-row">
                <label className="field">
                  Project name
                  <input
                    key={`${project.id}-${project.version}`}
                    name="name"
                    defaultValue={project.name}
                    required
                  />
                </label>
                <label className="field">
                  Status
                  <select name="status" defaultValue={project.status}>
                    {PROJECT_STATUSES.map((status) => (
                      <option key={status} value={status}>
                        {status.replaceAll("_", " ")}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="form-row">
                <label className="field">
                  Start date
                  <input
                    name="start_date"
                    type="date"
                    defaultValue={project.start_date ?? ""}
                  />
                </label>
                <label className="field">
                  Target finish
                  <input
                    name="target_finish"
                    type="date"
                    defaultValue={project.target_finish ?? ""}
                  />
                </label>
              </div>
              <button type="submit" disabled={busy}>
                Save project
              </button>
            </form>
          ) : null}

          <section className="schedule-panel">
            <div className="panel-heading">
              <div>
                <h3>Schedule</h3>
                <p className="muted">
                  Dates are calculated on demand from dependencies, constraints,
                  and the working calendar.
                </p>
              </div>
              <div className="panel-actions">
                <a
                  className="button-link"
                  href={`/api/v1/projects/${project.id}/export.ics`}
                >
                  Export ICS
                </a>
                <button
                  type="button"
                  onClick={() => setProjectRefresh((current) => current + 1)}
                  disabled={busy}
                >
                  Refresh schedule
                </button>
              </div>
            </div>
            {scheduleError ? (
              <p className="form-error" role="status">
                {scheduleError}
              </p>
            ) : null}
            {schedule ? (
              <>
                <p className="schedule-meta">
                  {schedule.project_start} → {schedule.project_finish}
                  <span className="muted">
                    {" "}
                    · version {schedule.project_version} ·{" "}
                    {schedule.start_source === "today_default"
                      ? "start defaulted to today"
                      : "project start"}
                  </span>
                </p>
                {schedule.warnings.length > 0 ? (
                  <ul className="schedule-warnings">
                    {schedule.warnings.map((warning) => (
                      <li key={`${warning.code}-${warning.message}`}>
                        {warning.message}
                      </li>
                    ))}
                  </ul>
                ) : null}
                {schedule.tasks.length === 0 ? (
                  <p className="muted">No scheduled tasks yet.</p>
                ) : (
                  <div className="schedule-table-wrap">
                    <table className="schedule-table">
                      <thead>
                        <tr>
                          <th>Task</th>
                          <th>Start</th>
                          <th>Finish</th>
                          <th>Float</th>
                          <th>Critical</th>
                        </tr>
                      </thead>
                      <tbody>
                        {schedule.tasks.map((task) => (
                          <tr key={task.id}>
                            <td>{task.name}</td>
                            <td>{formatScheduleTime(task.early_start_at)}</td>
                            <td>{formatScheduleTime(task.early_finish_at)}</td>
                            <td>{task.total_float_work_minutes} min</td>
                            <td>{task.critical ? "Yes" : "No"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                <GanttChart schedule={schedule} />
              </>
            ) : null}
          </section>

          {calendar ? (
            <section className="calendar-panel">
              <h3>Working calendar</h3>
              {canEditPlanning ? (
                <CalendarEditor
                  calendar={calendar}
                  busy={busy}
                  onSave={handleUpdateCalendar}
                />
              ) : (
                <p className="muted">
                  {calendar.timezone} ·{" "}
                  {
                    WEEKDAYS.filter(
                      (day) => (calendar.weekly_rules[day.key] ?? []).length > 0,
                    ).length
                  }{" "}
                  working days per week
                </p>
              )}
            </section>
          ) : null}

          <ResourceWorkloadPanel
            projectId={project.id}
            tasks={tasks}
            canEdit={canEditPlanning}
            refreshKey={projectRefresh}
          />

          <RiskSimulationPanel
            projectId={project.id}
            canRun={canEditPlanning}
          />

          <div className="project-sections">
            <section>
              <h3>Tasks</h3>
              {tasks.length === 0 ? (
                <p className="muted">No tasks yet.</p>
              ) : (
                <ul className="item-list">
                  {tasks.map((task) => (
                    <TaskCard
                      key={task.id}
                      task={task}
                      tasks={tasks}
                      canEdit={canEditPlanning}
                      busy={busy}
                      onUpdate={handleUpdateTask}
                      onDelete={handleDeleteTask}
                    />
                  ))}
                </ul>
              )}

              {canEditPlanning ? (
                <form className="stack-form" onSubmit={handleCreateTask}>
                  <label className="field">
                    New task name
                    <input name="name" placeholder="Draft the plan" required />
                  </label>
                  <label className="field">
                    Parent task
                    <select name="parent_task_id" defaultValue="">
                      <option value="">No parent</option>
                      {tasks.map((task) => (
                        <option key={task.id} value={task.id}>
                          {task.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="form-row">
                    <label className="field">
                      Duration (min)
                      <input
                        name="duration_work_minutes"
                        type="number"
                        min="0"
                        defaultValue="0"
                      />
                    </label>
                    <label className="field">
                      Priority
                      <input
                        name="priority"
                        type="number"
                        min="1"
                        max="5"
                        defaultValue="3"
                      />
                    </label>
                  </div>
                  <button type="submit" disabled={busy}>
                    Add task
                  </button>
                </form>
              ) : null}
            </section>

            <section>
              <h3>Dependencies</h3>
              {dependencies.length === 0 ? (
                <p className="muted">No dependencies yet.</p>
              ) : (
                <ul className="item-list compact">
                  {dependencies.map((dependency) => (
                    <li className="dependency-row" key={dependency.id}>
                      <span>
                        {taskNames.get(dependency.predecessor_task_id) ??
                          dependency.predecessor_task_id}{" "}
                        →{" "}
                        {taskNames.get(dependency.successor_task_id) ??
                          dependency.successor_task_id}{" "}
                        <span className="role-chip small">
                          {dependency.type}
                        </span>{" "}
                        <span className="muted">
                          lag {dependency.lag_work_minutes} min
                        </span>
                      </span>
                      {canEditPlanning ? (
                        <button
                          type="button"
                          className="danger"
                          onClick={() =>
                            handleDeleteDependency(dependency.id)
                          }
                          disabled={busy}
                        >
                          Delete dependency
                        </button>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}

              {canEditPlanning && tasks.length >= 2 ? (
                <form className="stack-form" onSubmit={handleCreateDependency}>
                  <div className="form-row">
                    <label className="field">
                      Predecessor
                      <select
                        name="predecessor_task_id"
                        defaultValue={tasks[0]?.id ?? ""}
                      >
                        {tasks.map((task) => (
                          <option key={task.id} value={task.id}>
                            {task.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      Successor
                      <select
                        name="successor_task_id"
                        defaultValue={tasks[1]?.id ?? ""}
                      >
                        {tasks.map((task) => (
                          <option key={task.id} value={task.id}>
                            {task.name}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <div className="form-row">
                    <label className="field">
                      Dependency type
                      <select name="type" defaultValue="FS">
                        {DEPENDENCY_TYPES.map((type) => (
                          <option key={type} value={type}>
                            {type}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      Lag minutes
                      <input
                        name="lag_work_minutes"
                        type="number"
                        defaultValue="0"
                      />
                    </label>
                  </div>
                  <button type="submit" disabled={busy}>
                    Add dependency
                  </button>
                </form>
              ) : null}
            </section>
          </div>
        </section>
      ) : null}
    </section>
  );
}
