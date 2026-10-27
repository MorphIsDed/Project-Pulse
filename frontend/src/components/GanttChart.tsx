import type { DependencyType, ProjectSchedule, ScheduleTask } from "../lib/api";

const DAY_WIDTH = 30;
const ROW_HEIGHT = 30;
const HEADER_HEIGHT = 46;
const LABEL_WIDTH = 230;
const BAR_HEIGHT = 16;
const BAR_OFFSET = 7;
const RIGHT_PADDING = 24;

type TaskGeometry = {
  left: number;
  right: number;
  centerY: number;
};

function dayValue(value: string): number {
  const [year, month, day] = value.slice(0, 10).split("-").map(Number);
  return Date.UTC(year, month - 1, day);
}

function diffDays(start: number, end: number): number {
  return Math.round((end - start) / 86_400_000);
}

function dayAt(start: number, index: number): number {
  return start + index * 86_400_000;
}

function dayLabel(value: number): string {
  return new Date(value).toLocaleDateString("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

function shortDay(value: number): string {
  return String(new Date(value).getUTCDate());
}

function taskTitle(task: ScheduleTask): string {
  return [
    task.name,
    `Early: ${task.early_start_at} to ${task.early_finish_at}`,
    `Total float: ${task.total_float_work_minutes} min`,
    task.critical ? "Critical" : "Noncritical",
  ].join("\n");
}

function dependencyLabel(type: DependencyType): string {
  return type;
}

export default function GanttChart({ schedule }: { schedule: ProjectSchedule }) {
  if (schedule.tasks.length === 0) {
    return <p className="muted">No tasks to display on the Gantt chart.</p>;
  }

  const projectStart = dayValue(schedule.project_start);
  const latest = Math.max(
    dayValue(schedule.project_finish),
    schedule.target_finish ? dayValue(schedule.target_finish) : 0,
    ...schedule.tasks.map((task) => dayValue(task.late_finish)),
  );
  const totalDays = Math.max(1, diffDays(projectStart, latest) + 1);
  const chartWidth = LABEL_WIDTH + totalDays * DAY_WIDTH + RIGHT_PADDING;
  const chartHeight = HEADER_HEIGHT + schedule.tasks.length * ROW_HEIGHT + 12;

  const geometry = new Map<number, TaskGeometry>();
  schedule.tasks.forEach((task, index) => {
    const start = Math.max(
      projectStart,
      dayValue(task.early_start),
    );
    const finish = Math.max(start, dayValue(task.early_finish));
    const left = LABEL_WIDTH + diffDays(projectStart, start) * DAY_WIDTH;
    const right = LABEL_WIDTH + (diffDays(projectStart, finish) + 1) * DAY_WIDTH;
    geometry.set(task.id, {
      left,
      right,
      centerY: HEADER_HEIGHT + index * ROW_HEIGHT + ROW_HEIGHT / 2,
    });
  });

  const months: { key: string; label: string; start: number; days: number }[] =
    [];
  for (let index = 0; index < totalDays; index += 1) {
    const value = dayAt(projectStart, index);
    const date = new Date(value);
    const key = `${date.getUTCFullYear()}-${date.getUTCMonth()}`;
    const current = months[months.length - 1];
    if (current?.key === key) {
      current.days += 1;
    } else {
      months.push({
        key,
        label: date.toLocaleDateString("en", {
          month: "short",
          year: "numeric",
          timeZone: "UTC",
        }),
        start: index,
        days: 1,
      });
    }
  }

  return (
    <div className="gantt">
      <div className="gantt-legend">
        <span>
          <i className="gantt-key normal" /> Task
        </span>
        <span>
          <i className="gantt-key critical" /> Critical
        </span>
        <span>
          <i className="gantt-key float" /> Float
        </span>
        <span>
          <i className="gantt-key milestone" /> Milestone
        </span>
      </div>
      <div className="gantt-scroll">
        <svg
          className="gantt-svg"
          width={chartWidth}
          height={chartHeight}
          role="img"
          aria-label={`Gantt chart for ${schedule.tasks.length} tasks`}
        >
          <title>Project Gantt chart</title>
          <defs>
            <marker
              id="gantt-arrow"
              markerWidth="6"
              markerHeight="6"
              refX="5"
              refY="3"
              orient="auto"
            >
              <path d="M0,0 L6,3 L0,6 Z" />
            </marker>
          </defs>

          {months.map((month) => (
            <g key={month.key}>
              <text
                className="gantt-month"
                x={LABEL_WIDTH + month.start * DAY_WIDTH + 6}
                y={16}
              >
                {month.label}
              </text>
              <line
                className="gantt-month-line"
                x1={LABEL_WIDTH + month.start * DAY_WIDTH}
                x2={LABEL_WIDTH + month.start * DAY_WIDTH}
                y1={0}
                y2={chartHeight}
              />
            </g>
          ))}

          {Array.from({ length: totalDays }, (_, index) => {
            const value = dayAt(projectStart, index);
            const weekday = new Date(value).getUTCDay();
            const x = LABEL_WIDTH + index * DAY_WIDTH;
            return (
              <g key={value}>
                {weekday === 0 || weekday === 6 ? (
                  <rect
                    className="gantt-weekend"
                    x={x}
                    y={HEADER_HEIGHT}
                    width={DAY_WIDTH}
                    height={chartHeight - HEADER_HEIGHT}
                  />
                ) : null}
                <line
                  className="gantt-day-line"
                  x1={x}
                  x2={x}
                  y1={HEADER_HEIGHT}
                  y2={chartHeight}
                />
                <text
                  className="gantt-day"
                  x={x + DAY_WIDTH / 2}
                  y={38}
                  textAnchor="middle"
                >
                  {shortDay(value)}
                </text>
              </g>
            );
          })}

          <line
            className="gantt-header-line"
            x1={LABEL_WIDTH}
            x2={chartWidth - RIGHT_PADDING}
            y1={HEADER_HEIGHT}
            y2={HEADER_HEIGHT}
          />

          {schedule.tasks.map((task, index) => {
            const taskGeometry = geometry.get(task.id);
            if (!taskGeometry) return null;
            const y = HEADER_HEIGHT + index * ROW_HEIGHT;
            return (
              <g key={task.id}>
                <rect
                  className="gantt-row"
                  x={0}
                  y={y}
                  width={chartWidth}
                  height={ROW_HEIGHT}
                />
                <text className="gantt-task-name" x={12} y={y + 20}>
                  <title>{task.name}</title>
                  {task.name.length > 28
                    ? `${task.name.slice(0, 27)}…`
                    : task.name}
                </text>
              </g>
            );
          })}

          {schedule.tasks.map((task) => {
            const taskGeometry = geometry.get(task.id);
            if (!taskGeometry) return null;
            const { left, right, centerY } = taskGeometry;
            const barX = left + 3;
            const barWidth = Math.max(6, right - left - 6);
            const floatDays = diffDays(
              dayValue(task.early_finish),
              dayValue(task.late_finish),
            );
            if (task.duration_work_minutes === 0) {
              const center = left + DAY_WIDTH / 2;
              const points = [
                `${center},${centerY - 7}`,
                `${center + 7},${centerY}`,
                `${center},${centerY + 7}`,
                `${center - 7},${centerY}`,
              ].join(" ");
              return (
                <polygon
                  key={task.id}
                  className={`gantt-milestone${task.critical ? " critical" : ""}`}
                  points={points}
                  data-testid={`gantt-task-${task.id}`}
                >
                  <title>{taskTitle(task)}</title>
                </polygon>
              );
            }
            return (
              <g key={task.id} data-testid={`gantt-task-${task.id}`}>
                {floatDays > 0 ? (
                  <rect
                    className="gantt-float-bar"
                    x={right}
                    y={centerY - 4}
                    width={floatDays * DAY_WIDTH}
                    height={8}
                  >
                    <title>{`${task.total_float_work_minutes} min float`}</title>
                  </rect>
                ) : null}
                <rect
                  className={`gantt-bar${task.critical ? " critical" : ""}`}
                  x={barX}
                  y={centerY - BAR_HEIGHT / 2}
                  width={barWidth}
                  height={BAR_HEIGHT}
                  rx={4}
                >
                  <title>{taskTitle(task)}</title>
                </rect>
              </g>
            );
          })}

          {schedule.dependencies.map((dependency) => {
            const predecessor = geometry.get(dependency.predecessor_task_id);
            const successor = geometry.get(dependency.successor_task_id);
            if (!predecessor || !successor) return null;
            const startsRight =
              dependency.type === "FS" || dependency.type === "FF";
            const endsRight =
              dependency.type === "FF" || dependency.type === "SF";
            const startX = startsRight ? predecessor.right : predecessor.left;
            const endX = endsRight ? successor.right : successor.left;
            const midX = endsRight
              ? Math.max(startX, endX) + 12
              : Math.min(startX, endX) - 12;
            return (
              <path
                key={dependency.id}
                className="gantt-dependency"
                d={`M ${startX} ${predecessor.centerY} H ${midX} V ${successor.centerY} H ${endX}`}
                markerEnd="url(#gantt-arrow)"
                data-testid={`gantt-dependency-${dependency.id}`}
              >
                <title>{dependencyLabel(dependency.type)} dependency</title>
              </path>
            );
          })}

          <line
            className="gantt-label-line"
            x1={LABEL_WIDTH}
            x2={LABEL_WIDTH}
            y1={0}
            y2={chartHeight}
          />
        </svg>
      </div>
      <p className="muted">
        Timeline ends {dayLabel(latest)}. Float bars extend to the latest finish
        allowed by the target and dependency network.
      </p>
    </div>
  );
}
