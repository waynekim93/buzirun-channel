"""진행 보고 자리 (투게독의 AI 일터 보고는 부지런엔 없음) — 콘솔 출력만."""
from datetime import timedelta, timezone

KST = timezone(timedelta(hours=9))


def report(dept: str, msg: str, who: str = "", stage: str | None = None, kind: str = "work", **current):
    if kind in ("error", "report"):
        print(f"  [{dept}] {msg}")


def current_dept() -> str:
    return "pd"


def board():
    pass
