import type { ProjectSummary } from "../lib/api";

export default function ProjectInsights({ summary, error }: {
  summary: ProjectSummary | null;
  error: string | null;
}) {
  if (!summary) {
    return <p className="muted" role="status">
      {error ? `Project insights unavailable: ${error}` : "Loading project insights…"}
    </p>;
  }
  return <>
    <div className="summary-grid">
      <div><span>Total tasks</span><strong>{summary.task_count}</strong></div>
      <div><span>Completed</span><strong>{summary.completed_task_count}</strong></div>
      <div><span>Completion</span><strong>{summary.completion_percent}%</strong></div>
    </div>
    <details className="insights">
      <summary>Project insights</summary>
      <div className="insight-grid">
        <div>
          <h3>Task status</h3>
          {Object.entries(summary.status_counts).map(([status, count]) => (
            <p key={status}>{status.replaceAll("_", " ")} <strong>{count}</strong></p>
          ))}
        </div>
        <div>
          <h3>Task duration · working minutes</h3>
          {summary.duration_stats ? <>
            <p>Mean <strong>{summary.duration_stats.mean.toFixed(1)}</strong></p>
            <p>Median <strong>{summary.duration_stats.median.toFixed(1)}</strong></p>
            <p>90th percentile <strong>{summary.duration_stats.p90.toFixed(1)}</strong></p>
          </> : <p>No positive-duration tasks yet.</p>}
          <small>Milestones are excluded from duration statistics.</small>
        </div>
      </div>
    </details>
  </>;
}
