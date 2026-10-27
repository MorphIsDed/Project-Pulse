from collections import defaultdict
from datetime import datetime


def build_workload(
    calendar,
    resources: list[dict],
    assignments: list[dict],
    scheduled_tasks: list[dict],
) -> dict:
    task_by_id = {task["id"]: task for task in scheduled_tasks}
    load_by_resource = defaultdict(lambda: defaultdict(int))
    contributions = defaultdict(lambda: defaultdict(list))

    for assignment in assignments:
        task = task_by_id.get(assignment["task_id"])
        if task is None or task["duration_work_minutes"] == 0:
            continue
        start = datetime.fromisoformat(task["early_start_at"])
        finish = datetime.fromisoformat(task["early_finish_at"])
        minutes_by_date = calendar.working_minutes_by_date(start, finish)
        for day, task_minutes in minutes_by_date.items():
            allocated = int(
                round(
                    task_minutes
                    * assignment["allocation_percent"]
                    / 100
                )
            )
            if allocated <= 0:
                continue
            resource_id = assignment["resource_id"]
            load_by_resource[resource_id][day] += allocated
            contributions[resource_id][day].append(
                {
                    "task_id": task["id"],
                    "task_name": task["name"],
                    "task_priority": task["priority"],
                    "allocation_percent": assignment["allocation_percent"],
                    "allocated_work_minutes": allocated,
                }
            )

    resource_loads = []
    overloads = []
    total_excess = 0
    overloaded_resources = set()
    load_day_count = 0

    for resource in resources:
        resource_id = resource["id"]
        capacity = resource["capacity_work_minutes_per_day"]
        load_days = []
        overloaded_dates = []
        total_load = 0
        for day in sorted(load_by_resource[resource_id]):
            assigned = load_by_resource[resource_id][day]
            load_percent = round(assigned / capacity * 100, 1)
            overloaded = assigned > capacity
            excess = max(0, assigned - capacity)
            total_load += assigned
            load_day_count += 1
            load_days.append(
                {
                    "date": day.isoformat(),
                    "assigned_work_minutes": assigned,
                    "load_percent": load_percent,
                    "overloaded": overloaded,
                }
            )
            if overloaded:
                overloaded_dates.append(day.isoformat())
                overloaded_resources.add(resource_id)
                total_excess += excess
                overloads.append(
                    {
                        "resource_id": resource_id,
                        "resource_name": resource["name"],
                        "date": day.isoformat(),
                        "assigned_work_minutes": assigned,
                        "capacity_work_minutes": capacity,
                        "excess_work_minutes": excess,
                        "load_percent": load_percent,
                        "tasks": list(contributions[resource_id][day]),
                    }
                )

        resource_loads.append(
            {
                "resource_id": resource_id,
                "resource_name": resource["name"],
                "capacity_work_minutes_per_day": capacity,
                "total_assigned_work_minutes": total_load,
                "load_days": load_days,
                "overloaded_dates": overloaded_dates,
            }
        )

    overloads.sort(key=lambda item: (item["date"], item["resource_name"]))
    return {
        "resources": resource_loads,
        "overloads": overloads,
        "summary": {
            "resource_count": len(resources),
            "assignment_count": len(assignments),
            "load_day_count": load_day_count,
            "overload_count": len(overloads),
            "overloaded_resource_count": len(overloaded_resources),
            "excess_work_minutes": total_excess,
        },
    }
