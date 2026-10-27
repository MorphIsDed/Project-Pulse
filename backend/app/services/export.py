from datetime import date, datetime, timedelta, timezone

from app.services.scheduling import build_schedule


def project_ics(project) -> str:
    schedule = build_schedule(project)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ProjectPulse//Project Schedule//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(project.name)}",
        f"X-WR-TIMEZONE:{_escape(schedule['calendar']['timezone'])}",
    ]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    for task in schedule["tasks"]:
        start = _date(task["early_start"])
        finish = _date(task["early_finish"])
        if task["duration_work_minutes"] > 0:
            end = finish + timedelta(days=1)
        else:
            end = start
        description = [
            task.get("description") or "",
            f"Status: {task['status'].replace('_', ' ')}",
            f"Priority: {task['priority']}",
            f"Duration: {task['duration_work_minutes']} working minutes",
            f"Total float: {task['total_float_work_minutes']} minutes",
            "Critical path" if task["critical"] else "Noncritical",
        ]
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:task-{task['id']}@projectpulse.local",
                f"DTSTAMP:{stamp}",
                f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}",
                f"SUMMARY:{_escape(task['name'])}",
                f"DESCRIPTION:{_escape(chr(10).join(part for part in description if part))}",
                f"CATEGORIES:{_escape('Critical' if task['critical'] else 'Task')}",
                f"X-PROJECTPULSE-TASK-ID:{task['id']}",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def _date(value: str) -> date:
    return date.fromisoformat(value[:10])


def _escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )
