"""Small, on-demand project insights; no derived values are persisted."""

import numpy as np
import pandas as pd

from app.extensions import db
from app.models.planning import TASK_STATUSES, Task


def summarize_tasks(records, project_version: int) -> dict:
    frame = pd.DataFrame(records, columns=["status", "duration_work_minutes"])
    counts = frame.groupby("status").size().reindex(TASK_STATUSES, fill_value=0)
    total = len(frame)
    completed = int(counts["completed"])
    durations = frame.loc[
        frame["duration_work_minutes"] > 0, "duration_work_minutes"
    ].to_numpy(dtype=float)
    stats = None
    if durations.size:
        stats = {
            "mean": float(np.mean(durations)),
            "median": float(np.median(durations)),
            "p90": float(np.percentile(durations, 90)),
        }
    return {
        "project_version": project_version,
        "task_count": total,
        "completed_task_count": completed,
        "completion_percent": round(completed / total * 100, 2) if total else 0,
        "status_counts": {status: int(counts[status]) for status in TASK_STATUSES},
        "duration_stats": stats,
    }


def project_summary(project) -> dict:
    records = db.session.execute(
        db.select(Task.status, Task.duration_work_minutes)
        .where(Task.project_id == project.id)
    ).all()
    return summarize_tasks(records, project.version)
