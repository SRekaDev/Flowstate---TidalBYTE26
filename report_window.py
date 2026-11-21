"""Display a self-contained local report in Flowstate's Windows viewer."""
import json
import re
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Event, Thread

from report import review_markup
from session_review import review_session


REVIEW_SLOT = '<div id="nemotron-slot" aria-live="polite">'
REVIEW_UNAVAILABLE = "I couldn’t finish this review. Your session report is ready to explore."


def add_review(path, display):
    """Update the open report and keep the completed review in its saved HTML."""
    try:
        page = path.read_text(encoding="utf-8")
        if REVIEW_SLOT + "</div>" not in page:
            return
        payload = re.search(r'<script type="application/json" id="session">(.*?)</script>', page, re.S)
        if not payload:
            return
        rows = json.loads(payload[1])["rows"]
        display("pending", review_markup("Looking over your session. You can explore the report while I work."))
        review = review_session(rows)
        if review is None:
            display("failed", review_markup(REVIEW_UNAVAILABLE))
            return
        block = review_markup(review)
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as pending:
            pending_path = Path(pending.name)
            pending.write(page.replace(REVIEW_SLOT, REVIEW_SLOT + block, 1))
        try:
            pending_path.replace(path)
        finally:
            pending_path.unlink(missing_ok=True)
        display("ready", block)
    except (OSError, ValueError, KeyError, TypeError):
        display("failed", review_markup(REVIEW_UNAVAILABLE))


def show(path, local_review=False):
    import webview

    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.settings["ALLOW_FILE_URLS"] = True
    window = webview.create_window(
        "Flowstate · Session report", url=path.resolve(strict=True).as_uri(),
        width=1150, height=800, min_size=(520, 400), maximized=True,
        background_color="#14171c",
    )
    loaded = Event()

    def display_review(state, markup):
        window.evaluate_js(f"""
            ((state, markup) => {{
                const slot = document.getElementById('nemotron-slot');
                if (!slot) return;
                if (state === 'ready') {{
                    const button = slot.querySelector('button');
                    if (!button) {{
                        slot.innerHTML = markup;
                        return;
                    }}
                    slot.reviewMarkup = markup;
                    slot.querySelector('p').textContent = 'Your Nemotron review is ready.';
                    button.textContent = 'Show Nemotron review';
                    return;
                }}
                slot.innerHTML = markup;
                if (state !== 'pending') return;
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'nemotron-refresh';
                button.textContent = 'Refresh Nemotron review';
                button.addEventListener('click', () => {{
                    if (slot.reviewMarkup) {{
                        slot.innerHTML = slot.reviewMarkup;
                        slot.querySelector('h3').tabIndex = -1;
                        slot.querySelector('h3').focus();
                    }} else {{
                        slot.querySelector('p').textContent = 'Still reviewing your session. Check again in a moment.';
                    }}
                }});
                slot.querySelector('.nemotron-speech').append(button);
            }})({json.dumps(state)}, {json.dumps(markup)});
        """)

    def check_report():
        try:
            if window.evaluate_js("Boolean(document.querySelector('#plot #markers'))"):
                if local_review and not loaded.is_set():
                    Thread(target=add_review, args=(path, display_review), daemon=True).start()
                loaded.set()
                return
        except Exception:
            pass
        window.destroy()

    window.events.loaded += check_report
    webview.start(gui="edgechromium")
    return 0 if loaded.is_set() else 1


if __name__ == "__main__":
    sys.exit(show(Path(sys.argv[1]), local_review="--review" in sys.argv[2:]))
