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


def review_evidence(rows):
    """Keep the first and last windows, representative samples, and key changes."""
    if not rows:
        return {}
    last = len(rows) - 1
    indices = {step * last // 15 for step in range(16)}
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
    missing = next((i for i, row in enumerate(rows) if row["focus"] is None), None)
    if missing is not None:
        indices.add(missing)
    return {
        str(i + 1): {field: rows[i][field] for field in ("t", "duration", "focus", "fatigue", "samples", "keys")}
        for i in sorted(indices)
    }


def review_findings(rows):
    """Write factual observations using only values calculated by TidalByte."""
    evidence = review_evidence(rows)
    focus = [row for row in evidence.values() if row["focus"] is not None]
    fatigue = [row for row in evidence.values() if row["fatigue"] is not None]
    findings = {}
    if focus:
        lowest = min(focus, key=lambda row: row["focus"])
        findings["low_focus"] = f'Focus looked less steady around {timestamp(lowest["t"])}.'
    if len(focus) > 1 and focus[0]["focus"] != focus[-1]["focus"]:
        direction = "at the start" if focus[0]["focus"] > focus[-1]["focus"] else "near the end"
        findings["focus_change"] = f"Focus looked stronger {direction}."
    if fatigue:
        peak = max(fatigue, key=lambda row: row["fatigue"])
        if peak["fatigue"] > 0:
            findings["peak_fatigue"] = f'Signs of tiredness stood out around {timestamp(peak["t"])}.'
        else:
            findings["steady_fatigue"] = "The camera didn’t pick up an increase in signs of tiredness."
    missing = next((row for row in rows if row["focus"] is None), None)
    if missing:
        findings["coverage_gap"] = "There was a stretch where the camera couldn’t pick up enough to judge focus."
    return evidence, findings


def format_review(findings, ranked):
    encouragement = (
        "If you felt tired too, try a short reset before your next session. Small breaks count."
        if "peak_fatigue" in ranked else
        "Take a moment to notice what worked for you. One small change is plenty for next time."
    )
    observations = " ".join(findings[item] for item in ranked)
    return f"Nemotron review · {observations} {encouragement}"


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
            "Prefer a meaningful change or peak, and include a coverage gap when present. "
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
