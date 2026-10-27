from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.scheduling.errors import ScheduleError


DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
MAX_CALENDAR_DAYS = 36600


def _invalid(message: str, code: str = "invalid_calendar") -> ScheduleError:
    return ScheduleError(code, message, 400)


def _parse_clock(value, field: str) -> time:
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        raise _invalid(f"{field} must use HH:MM.")
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError:
        raise _invalid(f"{field} must use HH:MM.") from None


def _parse_intervals(value, field: str) -> list[list[str]]:
    if not isinstance(value, list):
        raise _invalid(f"{field} must be a list of intervals.")
    parsed = []
    for interval in value:
        if not isinstance(interval, (list, tuple)) or len(interval) != 2:
            raise _invalid(f"{field} intervals must contain a start and end.")
        start = _parse_clock(interval[0], field)
        end = _parse_clock(interval[1], field)
        if start >= end:
            raise _invalid(f"{field} interval start must precede its end.")
        parsed.append((start, end))

    parsed.sort(key=lambda item: item[0])
    for previous, current in zip(parsed, parsed[1:]):
        if current[0] < previous[1]:
            raise _invalid(f"{field} intervals must not overlap.")
    return [
        [start.strftime("%H:%M"), end.strftime("%H:%M")]
        for start, end in parsed
    ]


def parse_timezone(value) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _invalid("Timezone is required.", "invalid_timezone")
    name = value.strip()
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise _invalid("Choose a valid IANA timezone.", "invalid_timezone") from None
    return name


def parse_weekly_rules(value) -> dict[str, list[list[str]]]:
    if not isinstance(value, dict):
        raise _invalid("Weekly rules must be an object.")
    if set(value) != set(DAY_KEYS):
        raise _invalid(
            "Weekly rules must contain mon, tue, wed, thu, fri, sat, and sun.",
            "invalid_weekly_rules",
        )
    rules = {}
    for day in DAY_KEYS:
        rules[day] = _parse_intervals(value[day], f"weekly_rules.{day}")
    if not any(rules.values()):
        raise _invalid(
            "The calendar must contain at least one working interval.",
            "invalid_weekly_rules",
        )
    return rules


def parse_exceptions(value) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise _invalid("Exceptions must be a list.", "invalid_exception")
    parsed = []
    seen = set()
    for raw in value:
        if not isinstance(raw, dict):
            raise _invalid("Each exception must be an object.", "invalid_exception")
        extra = set(raw) - {"date", "name", "working", "intervals"}
        if extra:
            raise _invalid(
                "Exceptions contain unsupported fields.",
                "invalid_exception",
                )
        raw_date = raw.get("date")
        if not isinstance(raw_date, str):
            raise _invalid("Exception dates must use YYYY-MM-DD.", "invalid_exception")
        try:
            exception_date = date.fromisoformat(raw_date)
        except ValueError:
            raise _invalid(
                "Exception dates must use YYYY-MM-DD.", "invalid_exception"
            ) from None
        if exception_date in seen:
            raise _invalid(
                "Each date can have only one exception.", "invalid_exception"
            )
        seen.add(exception_date)
        working = raw.get("working")
        if type(working) is not bool:
            raise _invalid(
                "Exception working must be true or false.", "invalid_exception"
            )
        intervals = raw.get("intervals")
        if working:
            if not intervals:
                raise _invalid(
                    "Working exceptions need at least one interval.",
                    "invalid_exception",
                )
            intervals = _parse_intervals(
                intervals, f"exception {raw_date} intervals"
            )
        else:
            if intervals:
                raise _invalid(
                    "Nonworking exceptions cannot have intervals.",
                    "invalid_exception",
                )
            intervals = []
        name = raw.get("name")
        if name is not None:
            if not isinstance(name, str) or len(name.strip()) > 120:
                raise _invalid(
                    "Exception names must be 120 characters or fewer.",
                    "invalid_exception",
                )
            name = name.strip()
        item = {
            "date": exception_date.isoformat(),
            "working": working,
            "intervals": intervals,
        }
        if name:
            item["name"] = name
        parsed.append(item)
    parsed.sort(key=lambda item: item["date"])
    return parsed


class WorkingCalendar:
    def __init__(
        self,
        timezone_name: str,
        weekly_rules: dict[str, list[list[str]]],
        exceptions: list[dict] | None = None,
    ) -> None:
        self.timezone_name = timezone_name
        self.timezone = ZoneInfo(timezone_name)
        self.weekly_rules = weekly_rules
        self.exceptions = exceptions or []
        self._exceptions = {
            date.fromisoformat(item["date"]): item for item in self.exceptions
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkingCalendar":
        return cls(
            parse_timezone(data.get("timezone")),
            parse_weekly_rules(data.get("weekly_rules")),
            parse_exceptions(data.get("exceptions")),
        )

    def today(self) -> date:
        return datetime.now(self.timezone).date()

    def local_datetime(self, instant: datetime) -> datetime:
        return self._aware(instant).astimezone(self.timezone)

    def local_date(self, instant: datetime) -> date:
        return self.local_datetime(instant).date()

    def has_work_on(self, day: date) -> bool:
        return bool(self._intervals_for(day))

    def first_start_on_or_after(self, day: date) -> datetime:
        cursor = day
        for _ in range(MAX_CALENDAR_DAYS):
            windows = self._windows_for(cursor)
            if windows:
                return windows[0][0]
            cursor += timedelta(days=1)
        raise ScheduleError(
            "schedule_horizon_exceeded",
            "The calendar has no working day within the supported range.",
        )

    def first_end_on_or_after(self, day: date) -> datetime:
        cursor = day
        for _ in range(MAX_CALENDAR_DAYS):
            windows = self._windows_for(cursor)
            if windows:
                return windows[-1][1]
            cursor += timedelta(days=1)
        raise ScheduleError(
            "schedule_horizon_exceeded",
            "The calendar has no working day within the supported range.",
        )

    def last_start_on_or_before(self, day: date) -> datetime:
        cursor = day
        for _ in range(MAX_CALENDAR_DAYS):
            windows = self._windows_for(cursor)
            if windows:
                return windows[-1][0]
            cursor -= timedelta(days=1)
        raise ScheduleError(
            "schedule_horizon_exceeded",
            "The calendar has no working day within the supported range.",
        )

    def last_end_on_or_before(self, day: date) -> datetime:
        cursor = day
        for _ in range(MAX_CALENDAR_DAYS):
            windows = self._windows_for(cursor)
            if windows:
                return windows[-1][1]
            cursor -= timedelta(days=1)
        raise ScheduleError(
            "schedule_horizon_exceeded",
            "The calendar has no working day within the supported range.",
        )

    def add_working_minutes(self, start: datetime, minutes: int) -> datetime:
        if type(minutes) is not int:
            raise ScheduleError(
                "invalid_duration", "Working minutes must be an integer.", 400
            )
        if minutes == 0:
            return self.next_working_instant(start)

        if minutes > 0:
            cursor = self.next_working_instant(start)
            remaining = minutes
            for _ in range(MAX_CALENDAR_DAYS * 4):
                window_start, window_end = self._window_on_or_after(cursor)
                if cursor < window_start:
                    cursor = window_start
                available = int(
                    (window_end - cursor).total_seconds() // 60
                )
                if remaining <= available:
                    return cursor + timedelta(minutes=remaining)
                remaining -= available
                cursor = window_end
            raise ScheduleError(
                "schedule_horizon_exceeded",
                "The calendar calculation exceeded the supported range.",
            )

        cursor = self.previous_working_instant(start)
        remaining = abs(minutes)
        for _ in range(MAX_CALENDAR_DAYS * 4):
            window_start, window_end = self._window_on_or_before(cursor)
            if cursor > window_end:
                cursor = window_end
            available = int((cursor - window_start).total_seconds() // 60)
            if remaining <= available:
                return cursor - timedelta(minutes=remaining)
            remaining -= available
            cursor = window_start
        raise ScheduleError(
            "schedule_horizon_exceeded",
            "The calendar calculation exceeded the supported range.",
        )

    def working_minutes_between(
        self, start: datetime, end: datetime
    ) -> int:
        start = self._aware(start)
        end = self._aware(end)
        if end < start:
            return -self.working_minutes_between(end, start)
        if end == start:
            return 0

        cursor = self.local_date(start)
        last = self.local_date(end)
        total = 0
        for _ in range(MAX_CALENDAR_DAYS):
            for window_start, window_end in self._windows_for(cursor):
                overlap_start = max(window_start, start)
                overlap_end = min(window_end, end)
                if overlap_end > overlap_start:
                    total += int(
                        (overlap_end - overlap_start).total_seconds() // 60
                    )
            if cursor >= last:
                break
            cursor += timedelta(days=1)
        return total

    def working_minutes_by_date(
        self, start: datetime, end: datetime
    ) -> dict[date, int]:
        start = self._aware(start)
        end = self._aware(end)
        if end <= start:
            return {}

        cursor = self.local_date(start)
        last = self.local_date(end)
        minutes_by_date = {}
        for _ in range(MAX_CALENDAR_DAYS):
            total = 0
            for window_start, window_end in self._windows_for(cursor):
                overlap_start = max(window_start, start)
                overlap_end = min(window_end, end)
                if overlap_end > overlap_start:
                    total += int(
                        (overlap_end - overlap_start).total_seconds() // 60
                    )
            if total:
                minutes_by_date[cursor] = total
            if cursor >= last:
                break
            cursor += timedelta(days=1)
        return minutes_by_date

    def next_working_instant(self, start: datetime) -> datetime:
        start = self._aware(start)
        cursor = start
        for _ in range(MAX_CALENDAR_DAYS):
            for window_start, window_end in self._windows_for(
                self.local_date(cursor)
            ):
                if window_start <= cursor < window_end:
                    return cursor
                if cursor < window_start:
                    return window_start
            cursor = datetime.combine(
                self.local_date(cursor) + timedelta(days=1),
                time.min,
                tzinfo=self.timezone,
            ).astimezone(dt_timezone.utc)
        raise ScheduleError(
            "schedule_horizon_exceeded",
            "The calendar has no working instant within the supported range.",
        )

    def previous_working_instant(self, start: datetime) -> datetime:
        start = self._aware(start)
        cursor = start
        for _ in range(MAX_CALENDAR_DAYS):
            windows = self._windows_for(self.local_date(cursor))
            for window_start, window_end in reversed(windows):
                if window_start < cursor <= window_end:
                    return cursor
                if cursor > window_end:
                    return window_end
            cursor = datetime.combine(
                self.local_date(cursor) - timedelta(days=1),
                time.max,
                tzinfo=self.timezone,
            ).astimezone(dt_timezone.utc)
        raise ScheduleError(
            "schedule_horizon_exceeded",
            "The calendar has no working instant within the supported range.",
        )

    def serialize(self) -> dict:
        return {
            "timezone": self.timezone_name,
            "weekly_rules": self.weekly_rules,
            "exceptions": self.exceptions,
        }

    def _window_on_or_after(self, instant: datetime):
        cursor = instant
        for _ in range(MAX_CALENDAR_DAYS):
            for window_start, window_end in self._windows_for(
                self.local_date(cursor)
            ):
                if window_end <= cursor:
                    continue
                return window_start, window_end
            cursor = datetime.combine(
                self.local_date(cursor) + timedelta(days=1),
                time.min,
                tzinfo=self.timezone,
            ).astimezone(dt_timezone.utc)
        raise ScheduleError(
            "schedule_horizon_exceeded",
            "The calendar has no working window within the supported range.",
        )

    def _window_on_or_before(self, instant: datetime):
        cursor = instant
        for _ in range(MAX_CALENDAR_DAYS):
            for window_start, window_end in reversed(
                self._windows_for(self.local_date(cursor))
            ):
                if window_start >= cursor:
                    continue
                return window_start, window_end
            cursor = datetime.combine(
                self.local_date(cursor) - timedelta(days=1),
                time.max,
                tzinfo=self.timezone,
            ).astimezone(dt_timezone.utc)
        raise ScheduleError(
            "schedule_horizon_exceeded",
            "The calendar has no working window within the supported range.",
        )

    def _intervals_for(self, day: date) -> list[list[str]]:
        exception = self._exceptions.get(day)
        if exception is not None:
            return exception["intervals"] if exception["working"] else []
        return self.weekly_rules[DAY_KEYS[day.weekday()]]

    def _windows_for(self, day: date) -> list[tuple[datetime, datetime]]:
        windows = []
        for start_text, end_text in self._intervals_for(day):
            local_start = datetime.combine(
                day, _parse_clock(start_text, "interval start")
            ).replace(tzinfo=self.timezone)
            local_end = datetime.combine(
                day, _parse_clock(end_text, "interval end")
            ).replace(tzinfo=self.timezone)
            start = local_start.astimezone(dt_timezone.utc)
            end = local_end.astimezone(dt_timezone.utc)
            if end <= start:
                raise _invalid(
                    "Each working interval must have a positive duration."
                )
            windows.append((start, end))
        return windows

    @staticmethod
    def _aware(value: datetime) -> datetime:
        if not isinstance(value, datetime):
            raise ScheduleError(
                "invalid_schedule",
                "Schedule instants must be datetimes.",
                400,
            )
        if value.tzinfo is None:
            return value.replace(tzinfo=dt_timezone.utc)
        return value.astimezone(dt_timezone.utc)
