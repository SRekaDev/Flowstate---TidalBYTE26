"""Send a bounded, aggregate-only session review to the local NemoClaw sandbox."""

import json
import subprocess
from uuid import uuid4


MODEL = "nemotron-3-nano:4b"
SANDBOX = "tidalbyte26-retry"
WSL = [
    "wsl.exe", "-d", "Ubuntu-24.04", "--exec", "/usr/bin/env", "NEMOCLAW_DISABLE_TELEMETRY=1",
    "NEMOCLAW_GATEWAY_PORT=8990",
]


def timestamp(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"


def clear_face_window(row):
    return (row["samples"] >= 30 and row["samples"] * 2 >= row.get("frames", row["samples"])
            and row.get("focus_seconds", row["duration"]) * 2 >= row["duration"])


def head_turn_drop(rows):
    """Find adjacent windows where lower focus coincides with less forward-facing posture."""
    matches = []
    for i, (before, after) in enumerate(zip(rows, rows[1:]), start=1):
        if before["t"] + before["duration"] != after["t"]:
            continue
        if not all(clear_face_window(row) and row["focus"] is not None
                   and row.get("orientation") is not None for row in (before, after)):
            continue
        focus_drop = before["focus"] - after["focus"]
        if focus_drop >= 8 and before["orientation"] - after["orientation"] >= 15:
            matches.append((focus_drop, i))
    return max(matches, default=(0, None), key=lambda match: match[0])[1]


def review_evidence(rows, turn):
    """Keep the first and last windows, representative samples, and key changes."""
    if not rows:
        return {}
    last = len(rows) - 1
    indices = {step * last // 13 for step in range(14)}
    for field, select in (("focus", min), ("fatigue", max)):
        measured = [i for i, row in enumerate(rows) if row[field] is not None]
        if measured:
            indices.add(select(measured, key=lambda i: rows[i][field]))
    drops = [
        i for i in range(1, len(rows))
        if rows[i - 1]["focus"] is not None and rows[i]["focus"] is not None
        and rows[i - 1]["t"] + rows[i - 1]["duration"] == rows[i]["t"]
        and rows[i - 1]["focus"] > rows[i]["focus"]
    ]
    if drops:
        steepest = max(drops, key=lambda i: rows[i - 1]["focus"] - rows[i]["focus"])
        indices.update((steepest - 1, steepest))
    if turn is not None:
        indices.update((turn - 1, turn))
    missing = next((i for i, row in enumerate(rows) if row["focus"] is None), None)
    if missing is not None:
        indices.add(missing)
    return {
        str(i + 1): {field: rows[i].get(field) for field in (
            "t", "duration", "focus", "fatigue", "samples", "keys", "orientation", "closed", "yawns", "long_closures",
        )}
        for i in sorted(indices)
    }


def review_findings(rows):
    """Write factual observations using only values calculated by TidalByte."""
    turn = head_turn_drop(rows)
    evidence = review_evidence(rows, turn)
    focus = [row for row in evidence.values() if row["focus"] is not None]
    fatigue = [row for row in evidence.values() if row["fatigue"] is not None]
    findings = {}
    if focus:
        lowest = min(focus, key=lambda row: row["focus"])
        findings["low_focus"] = f'Focus looked less steady around {timestamp(lowest["t"])}.'
    if len(focus) > 1 and focus[0]["focus"] != focus[-1]["focus"]:
        direction = "at the start" if focus[0]["focus"] > focus[-1]["focus"] else "near the end"
        findings["focus_change"] = f"Focus looked stronger {direction}."
    if turn is not None:
        findings["head_turns"] = (
            f'Around {timestamp(rows[turn]["t"])}, focus dipped while you spent more time facing away '
            "from your usual forward position."
        )
    if fatigue:
        peak = max(fatigue, key=lambda row: row["fatigue"])
        if peak["fatigue"] > 0:
            signs = []
            if peak["long_closures"]:
                signs.append("longer eye closures")
            elif peak["samples"] >= 30 and peak["closed"] is not None and peak["closed"] >= .15:
                signs.append("more time with your eyes closed")
            if peak["yawns"]:
                signs.append("yawn-like movements")
            observation = f' The camera picked up {" and ".join(signs)} around then.' if signs else ""
            findings["peak_fatigue"] = f'Signs of tiredness stood out around {timestamp(peak["t"])}.{observation}'
        else:
            findings["steady_fatigue"] = "The camera didn’t pick up an increase in signs of tiredness."
    missing = next((row for row in rows if row["focus"] is None), None)
    if missing:
        findings["coverage_gap"] = "There was a stretch where the camera couldn’t pick up enough to judge focus."
    return evidence, findings


def format_review(findings, ranked):
    if "peak_fatigue" in ranked:
        encouragement = "If you felt tired too, try a short reset before your next session. Small breaks count."
    elif "head_turns" in ranked:
        encouragement = "If you want a steadier next stretch, try keeping what you need in front of you."
    else:
        encouragement = "Take a moment to notice what worked for you. One small change is plenty for next time."
    observations = " ".join(findings[item] for item in ranked)
    return f"Nemotron review · {observations} {encouragement}"


def has_review_data(rows):
    return any(row.get("samples", 0) > 0
               and (row.get("focus") is not None or row.get("fatigue") is not None)
               for row in rows)


def run_nemoclaw(*args, message=None, timeout=45):
    launch = 'export PATH="$HOME/.local/bin:$PATH"; exec "$HOME/.local/bin/nemoclaw" "$@"'
    if message is not None:
        launch = 'IFS= read -r -d "" prompt || true; ' + launch + ' -m "$prompt"'
    result = subprocess.run(
        [*WSL, "/bin/bash", "-c", launch, "nemoclaw", *args],
        input=message or "", capture_output=True, encoding="utf-8",
        errors="replace", timeout=timeout, check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise ValueError("The local NemoClaw command did not complete.")
    return result.stdout.strip()


def review_session(rows):
    if not has_review_data(rows):
        return None
    evidence, findings = review_findings(rows)
    if not findings or set(findings) == {"coverage_gap"}:
        return None
    try:
        route = dict(line.split(": ", 1) for line in run_nemoclaw("inference", "get").splitlines() if ": " in line)
        if (route.get("Provider") != "ollama-local" or route.get("Model", "").strip() != MODEL
                or route.get("Endpoint") != "http://host.openshell.internal:11435/v1"):
            return None
        tool_policy = json.loads(run_nemoclaw(
            SANDBOX, "exec", "--", "openclaw", "config", "get", "tools.deny", "--json",
        ))
        if not isinstance(tool_policy, list) or "*" not in tool_policy:
            return None
        prompt = (
            "Prioritize the most informative findings in this productivity session. Focus and fatigue are "
            "experimental scores. Timestamps in the evidence are seconds. Null is unavailable, never zero. "
            "Prefer a head-turn finding or a tiredness finding with a concrete camera observation over "
            "a generic score change, and include a coverage gap when present. "
            'Return only JSON like {"findings":["peak_fatigue","coverage_gap"]} with one to three distinct '
            "IDs chosen from the supplied findings. Do not write prose or call tools. "
            + json.dumps({"findings": findings, "evidence": evidence}, separators=(",", ":"))
        )
        output = run_nemoclaw(
            SANDBOX, "agent", "--agent", "main", "--session-id", str(uuid4()), "--thinking", "off",
            timeout=360, message=prompt,
        )
        if output.startswith("```") and output.endswith("```"):
            output = output.partition("\n")[2].rsplit("```", 1)[0]
        selected = json.loads(output)["findings"]
        if not isinstance(selected, list) or not 1 <= len(selected) <= 3:
            return None
        if any(not isinstance(item, str) or item not in findings for item in selected):
            return None
        ranked = list(dict.fromkeys(selected))
        if "coverage_gap" in findings and "coverage_gap" not in ranked:
            ranked = ranked[:2] + ["coverage_gap"]
        return format_review(findings, ranked)
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError):
        return None
