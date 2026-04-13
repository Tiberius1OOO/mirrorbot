"""
UTC slot helpers for scheduled /ranking autoposts.
"""

from datetime import datetime, timezone


def ranking_time_slots_utc(interval_h: int, hour: int, minute: int) -> set[tuple[int, int]]:
    h, m = hour % 24, minute % 60
    if interval_h == 24:
        return {(h, m)}
    return {(h, m), ((h + 12) % 24, m)}


def ranking_slot_key_utc(now: datetime) -> str:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)
    return f"{now.year}-{now.month:02d}-{now.day:02d}T{now.hour:02d}:{now.minute:02d}"


def ranking_should_fire(
    interval_h: int,
    hour: int,
    minute: int,
    last_fired_slot: str,
    now: datetime,
) -> bool:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)
    if (now.hour, now.minute) not in ranking_time_slots_utc(interval_h, hour, minute):
        return False
    return ranking_slot_key_utc(now) != (last_fired_slot or "")
