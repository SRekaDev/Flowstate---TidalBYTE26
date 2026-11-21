import base64, html, json
from pathlib import Path
from functools import lru_cache
from signals import score
def clock(seconds):
    return f'{int(seconds)//60}:{int(seconds)%60:02}'

def summarize(rows):
    periods = score(rows)
    focus = [r for r in rows if r["focus"] is not None]
    fatigue = [r["fatigue"] for r in rows if r["fatigue"] is not None]
    avg = round(sum(r["focus"]*r.get("focus_seconds",r["duration"]) for r in focus)/sum(r.get("focus_seconds",r["duration"]) for r in focus)) if focus else None
    duration = rows[-1]["t"]+rows[-1]["duration"]
    if focus:
        summary = f'Your average focus was {avg}/100 over {clock(sum(r.get("focus_seconds",r["duration"]) for r in focus))} of measured time.'
    else:
        summary = 'There was too little camera data to estimate focus.'
    if fatigue:
        peak = max(fatigue)
        first_peak = next(r for r in rows if r["fatigue"] == peak)
        summary += f' Fatigue first reached its peak of {peak}/100 at {clock(first_peak["t"])}.'
    else:
        summary += ' A longer session with your eyes in view can help estimate fatigue.'
    if periods:
        if rows[0].get("engine"):
            summary += f' The first window with elevated estimated stress began at {clock(periods[0][0])}.'
        else:
            summary += f' Typing corrections rose above your usual rate at {clock(periods[0][0])}.'
    return summary


@lru_cache(maxsize=1)
def template():
    folder = Path(__file__).resolve().parent
    mark = base64.b64encode((folder/"flowstate-icon.png").read_bytes()).decode("ascii")
    return (folder/"ice.html").read_text(encoding="utf-8").replace("@@MARK@@",mark)


def review_markup(review):
    message = html.escape(review.removeprefix("Nemotron review · "))
    return (
        '<section class="nemotron-review" aria-labelledby="nemotron-heading">'
        '<span class="nemotron-mascot" aria-hidden="true"><span class="nemotron-penguin"></span></span>'
        '<div class="nemotron-speech"><h3 id="nemotron-heading">Nemotron review</h3>'
        f'<p>{message}</p></div></section>'
    )


def report(rows, demo, status, summary=None, history=None):
    periods = score(rows)
    if demo and history is None:
        # Five illustrative prior scores, for the sample report only.
        from statistics import median
        from history import session_mean, calendar_entry
        from datetime import datetime, timedelta
        prior = [69, 75, 78, 71, 74]
        current = session_mean(rows)
        all_scores = prior + ([current] if current is not None else [])
        now=datetime.now().replace(hour=15,minute=0,second=0,microsecond=0)
        calendar=[dict(stamp=(now-timedelta(days=days,hours=2)).isoformat(),focus=f,
                       fatigue=heat,minutes=25,keys=key_count,edits=edits)
                  for days,f,heat,key_count,edits in zip([150,25,5,2,0],prior,[38,44,27,40,33],
                                                        [800,750,620,710,530],[40,45,32,38,30])]
        calendar.append(calendar_entry(now,rows))
        history = dict(calendar=calendar,prior_count=len(prior), usual=median(prior),
                       sessions=len(all_scores), average=round(sum(all_scores)/len(all_scores)))
    payload = json.dumps(dict(rows=rows,periods=periods,status=status,history=history or {"sessions":0,"average":None},demo=demo),allow_nan=False).replace("<",r"\u003c")
    export = "" if demo else '<button class="export" id="export">Export training CSV</button>'
    return (template().replace("@@TYPE@@","Sample session" if demo else "Completed session")
            .replace("@@EXPORT@@",export).replace("@@DATA@@",payload)
            .replace("@@SUMMARY@@",html.escape(summary or summarize(rows))))
