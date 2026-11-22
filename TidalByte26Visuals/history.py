"""Summarize eligible local archives. Each measured session gets one vote."""
import json
import re
from pathlib import Path
from statistics import median
from datetime import datetime
from signals import score


def session_mean(rows):
    score(rows)
    total = seconds = 0
    for row in rows:
        value = row.get("focus", row.get("orientation"))
        span = row.get("focus_seconds", row["duration"])
        if value is not None and 0 <= value <= 100 and span > 0:
            total += value * span
            seconds += span
    return total / seconds if seconds else None


def calendar_entry(stamp,rows):
    def average(key):
        measured = [r for r in rows if r.get(key) is not None]
        seconds = sum(r.get(key+"_seconds",r["duration"]) for r in measured)
        return round(sum(r[key]*r.get(key+"_seconds",r["duration"]) for r in measured)/seconds) if seconds else None
    return dict(stamp=stamp.isoformat(timespec="seconds"),focus=average("focus"),
                fatigue=average("fatigue"),stress=average("stress"),minutes=round(sum(r["duration"] for r in rows)/60,1),
                keys=sum(r["keys"] for r in rows),edits=sum(r["edits"] for r in rows))


def focus_history(folder: Path, rows, reopening=False):
    means = []
    current = session_mean(rows)
    calendar=[]
    stamp=datetime.now()
    archives = sorted(folder.glob("Session-*.html"))
    for index, path in enumerate(archives):
        try:
            page = path.read_text(encoding="utf-8")
            match = re.search(r'<script type="application/json" id="session">(.*?)</script>', page, re.S)
            if match:
                previous = json.loads(match[1])["rows"]
                when=datetime.strptime(path.stem,"Session-%Y%m%d-%H%M%S-%f")
                value=session_mean(previous)
                if reopening and index == len(archives)-1 and previous == rows:
                    stamp=when
                    continue
                calendar.append(calendar_entry(when,previous))
            else:
                continue
            if value is not None and previous[0].get("engine") == rows[0].get("engine"):
                means.append(value)
        except (OSError, ValueError, KeyError, TypeError):
            continue
    prior = means[-5:]
    if current is not None:
        means.append(current)
    calendar.append(calendar_entry(stamp,rows))
    return {"calendar":calendar,"prior_count":len(prior), "usual":round(median(prior)) if prior else None, "sessions": len(means), "average": round(sum(means)/len(means)) if len(means)>=2 else None}
