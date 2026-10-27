import { useEffect, useState, type FormEvent } from "react";

import { CalendarEditor, TaskCard, WEEKDAYS, value, requiredNumber, type CalendarDraft } from "../components/PlanningForms";
import ProjectInsights from "../components/ProjectInsights";
import Dialog from "../components/Dialog";
import GanttChart from "../components/GanttChart";
import {
  ApiError,
  getProjectSummary,
  type ProjectSummary,
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
  type ProjectSchedule,
  type ProjectStatus,
  type ProjectUpdate,
  type Role,
  type Task,
  type TaskUpdate,
  type Workspace,
} from "../lib/api";

const PROJECT_STATUSES: ProjectStatus[] = [
  "active",
  "on_hold",
  "completed",
  "archived",
];
const ROLES: Role[] = ["owner", "admin", "editor", "viewer"];
const DEPENDENCY_TYPES: DependencyType[] = ["FS", "SS", "FF", "SF"];

function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "Something went wrong. Please try again.";
}

function formatScheduleTime(value: string): string {
  return value.replace("T", " ").slice(0, 16);
}

export default function WorkspacePage({ userName = "Your workspace", onLogout }: { userName?: string; onLogout?: () => Promise<void> }) {
  const [view, setView] = useState<"Tasks" | "Timeline" | "Settings">("Tasks");
  const [dialog, setDialog] = useState<"organization" | "workspace" | "members" | "project" | "task" | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);
  const [navigationOpen, setNavigationOpen] = useState(false);
  const [summary, setSummary] = useState<ProjectSummary | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [projectLoading, setProjectLoading] = useState(false);

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
    setView("Tasks"); setSelectedTaskId(null); setDialog(null);
    setTasks([]); setDependencies([]); setCalendar(null); setSchedule(null); setError(null);
  }, [projectId]);
  useEffect(() => {
    let active = true;
    setSummary(null); setSummaryError(null);
    if (projectId !== null) getProjectSummary(projectId)
      .then((result) => { if (active) setSummary(result); })
      .catch((reason) => { if (active) setSummaryError(errorMessage(reason)); });
    return () => { active = false; };
  }, [projectId, projectRefresh]);

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
        if (active) { setError(errorMessage(reason)); setProjectLoading(false); }
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
        if (active) { setError(errorMessage(reason)); setProjectLoading(false); }
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
        if (active) { setError(errorMessage(reason)); setProjectLoading(false); }
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
    setProjectLoading(true);
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
        setProjectLoading(false);
      })
      .catch((reason) => {
        if (active) { setError(errorMessage(reason)); setProjectLoading(false); }
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
    setSchedule(null);
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
    if (!window.confirm(`Delete "${organization.name}" and its contents?`)) return;
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
    if (!window.confirm(`Remove "${member.user.display_name}" from this organization?`)) return;
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
    if (!window.confirm(`Delete "${workspace.name}" and its contents?`)) return;
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
    if (!window.confirm(`Delete "${project.name}" and its contents?`)) return;
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
      setDialog(null);
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
    if (!window.confirm(`Delete "${tasks.find((task) => task.id === taskId)?.name}"?`)) return Promise.resolve();
    if (!project) return Promise.resolve();
    return perform(async () => {
      await deleteTask(project.id, taskId);
      setSelectedTaskId(null);
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
    const link = dependencies.find((item) => item.id === dependencyId);
    if (!window.confirm(`Delete dependency "${tasks.find((task) => task.id === link?.predecessor_task_id)?.name} to ${tasks.find((task) => task.id === link?.successor_task_id)?.name}"?`)) return;
    if (!project) return;
    void perform(async () => {
      await deleteDependency(project.id, dependencyId);
      setProjectRefresh((current) => current + 1);
    });
  }

  const taskNames = new Map(tasks.map((task) => [task.id, task.name]));
  const selectedTask = tasks.find((task) => task.id === selectedTaskId);
  const selectedDependencies = dependencies.filter((item) => item.predecessor_task_id === selectedTaskId || item.successor_task_id === selectedTaskId);
  const navigation = <>
    <div className="navigation-row">
      <div className="brand"><span className="mark">P</span> ProjectPulse</div>
      <label className="field navigation-select">Organization
        <select aria-label="Current organization" value={organizationId ?? ""} onChange={(e) => setOrganizationId(Number(e.target.value) || null)}>
          <option value="" disabled>Select organization</option>
          {organizations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
      </label>
      {organization && <label className="field navigation-select">Workspace
        <select aria-label="Current workspace" value={workspaceId ?? ""} onChange={(e) => setWorkspaceId(Number(e.target.value) || null)}>
          <option value="" disabled>Select workspace</option>
          {workspaces.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
      </label>}
      <div className="navigation-account"><span className="avatar">{userName[0]}</span><div><strong>{userName}</strong><small>{role}</small></div>
        {onLogout && <button className="quiet" disabled={busy} onClick={() => void perform(onLogout)}>Sign out</button>}
      </div>
    </div>
    <div className="navigation-row navigation-secondary">
      <div className="navigation-actions">
        <button className="quiet" onClick={() => { setNavigationOpen(false); setDialog("organization"); }}>Manage organizations</button>
        {organization && canManageTenant && <button className="quiet" onClick={() => { setNavigationOpen(false); setDialog("workspace"); }}>Manage workspaces</button>}
        {organization && <button className="quiet" onClick={() => { setNavigationOpen(false); setDialog("members"); }}>Members</button>}
      </div>
      <nav aria-label="Projects" className="project-nav">
        {projects.map((item) => <button key={item.id} aria-current={projectId === item.id ? "page" : undefined} onClick={() => { setProjectId(item.id); setNavigationOpen(false); }}><span className="project-icon" aria-hidden="true">▦</span>{item.name}</button>)}
        {!projects.length && <p className="muted">{loading ? "Loading…" : "No projects yet"}</p>}
      </nav>
      {workspace && canEditPlanning && <button className="quiet new-project" onClick={() => { setNavigationOpen(false); setDialog("project"); }}>+ New project</button>}
    </div>
  </>;
  const modalError = error && <p className="form-error" role="alert">{error}</p>;
  return <div className="workspace">
    <header className="top-navigation" aria-label="Workspace navigation">{navigation}</header>
    {navigationOpen && <Dialog title="Navigation" className="navigation-dialog" onClose={() => setNavigationOpen(false)}>{navigation}</Dialog>}
    <div className="workspace-main" role="main">
      <header className="workspace-toolbar"><button className="mobile-navigation quiet" onClick={() => setNavigationOpen(true)}>Navigation</button>
        <div className="project-title"><p className="eyebrow">{workspace?.name ?? "Your workspace"}</p><h1>{project?.name ?? "Welcome to ProjectPulse"}</h1></div>
        {project && <span className="role-chip">{project.status.replaceAll("_", " ")} · {role}</span>}
      </header>
      {project && <nav className="view-tabs" aria-label="Project views">{(["Tasks", "Timeline", "Settings"] as const).map((tab) => <button key={tab} aria-current={view === tab ? "page" : undefined} onClick={() => setView(tab)}>{tab}</button>)}</nav>}
      <div className="workspace-content">
        {!dialog && !selectedTask && modalError}
        {busy && !dialog && !selectedTask && <p className="muted" role="status">Saving changes…</p>}
        {!project ? <section className="empty-state"><span className="empty-icon">▦</span><h2>A little structure. A clearer day.</h2><p>Select a project, or create an organization and workspace to start planning.</p><button onClick={() => setDialog("organization")}>Get started</button></section> : <>
        {view === "Tasks" && <>
          <ProjectInsights summary={summary} error={summaryError} />
          <section className="task-list-panel"><div className="panel-heading"><div><h2>Tasks</h2><p className="muted">Small steps. Clear progress.</p></div>{canEditPlanning && <button disabled={busy || projectLoading} onClick={() => setDialog("task")}>Add task</button>}</div>
          {projectLoading ? <p role="status">Loading tasks…</p> : tasks.length ? <ul className="task-list">{tasks.map((task) => <li key={task.id}><button className="task-row" onClick={() => setSelectedTaskId(task.id)}><span className={`task-indicator ${task.status}`} aria-hidden="true"/><strong>{task.name}</strong><span className="task-status">{task.status.replaceAll("_", " ")}</span><span>{task.duration_work_minutes === 0 ? "Milestone" : `${task.duration_work_minutes} min`}</span><span>{task.progress}%</span><span aria-hidden="true">›</span></button></li>)}</ul> : <div className="empty-state"><h3>Your plan starts here</h3><p>No tasks yet. Add your first task to begin.</p></div>}
          </section>
        </>}
        {view === "Timeline" && <section className="panel">          <section className="schedule-panel">
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
                  Export calendar
                </a>
                <button
                  type="button"
                  onClick={() => setProjectRefresh((current) => current + 1)}
                  disabled={busy}
                >
                  Recalculate
                </button>
              </div>
            </div>
            {scheduleError ? (
              <p className="form-error" role="status">
                {scheduleError}
              </p>
            ) : null}
            {!schedule && !scheduleError && <p role="status">Calculating schedule…</p>}
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
                <GanttChart schedule={schedule} />
                {schedule.tasks.length === 0 ? (
                  <p className="muted">No scheduled tasks yet.</p>
                ) : (
                  <details><summary>Schedule details and float</summary><div className="schedule-table-wrap">
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
                  </div></details>
                )}

              </>
            ) : null}
          </section>

</section>}
        {view === "Settings" && <section className="panel settings-panel"><h2>Project settings</h2>          {canEditPlanning ? (
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


          {canDeleteProject && <div className="danger-zone"><h3>Delete project</h3><p>This also deletes its tasks and dependencies.</p><button className="danger" disabled={busy} onClick={handleDeleteProject}>Delete project</button></div>}
        </section>}
        </>}
      </div>
    </div>
    {dialog && <Dialog title={{ organization: "Organizations", workspace: "Workspaces", members: "Members", project: "New project", task: "New task" }[dialog]} onClose={() => { setDialog(null); setError(null); }}>
      {modalError}
      {busy && <p className="muted" role="status">Saving changes…</p>}
      {dialog === "organization" && <>            <form className="stack-form" onSubmit={handleCreateOrganization}>
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
</>}
      {dialog === "workspace" && <>              {canManageTenant ? (
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
</>}
      {dialog === "members" && <>              <ul className="item-list">
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
                        <select name="role" aria-label={`Role for ${member.user.display_name}`} defaultValue={member.role}>
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
</>}
      {dialog === "project" && <>                <form className="stack-form" onSubmit={handleCreateProject}>
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
</>}
      {dialog === "task" && <>                <form className="stack-form" onSubmit={handleCreateTask}>
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
</>}
    </Dialog>}
    {selectedTask && <Dialog title={selectedTask.name} className="task-detail-dialog" onClose={() => { setSelectedTaskId(null); setError(null); }}>
      {modalError}{busy && <p className="muted" role="status">Saving changes…</p>}<TaskCard key={selectedTask.id} task={selectedTask} tasks={tasks} canEdit={canEditPlanning} busy={busy} onUpdate={handleUpdateTask} onDelete={handleDeleteTask}/>
      <section className="dependency-panel">              <h3>Dependencies</h3>
              {selectedDependencies.length === 0 ? (
                <p className="muted">No dependencies yet.</p>
              ) : (
                <ul className="item-list compact">
                  {selectedDependencies.map((dependency) => (
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
                        defaultValue={tasks.find((task) => task.id !== selectedTaskId)?.id ?? ""}
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
                        defaultValue={selectedTask?.id ?? ""}
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
    </Dialog>}
  </div>;
}
