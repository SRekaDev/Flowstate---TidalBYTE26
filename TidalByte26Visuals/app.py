"""Windows study capture and in-app session review."""
import ctypes
from tkinter import font as tkfont
import os
import sys
import threading
import time
import json
import subprocess
import html
import re
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from calibration import Calibration, STEPS
from hologram import HeadGuide
from signals import Camera, WINDOW, example
from history import focus_history
from report import report, summarize
from dashboard import Dashboard
from launcher import build

BG = "#14171c"
PANEL = "#2d3035"
INK = "#eff7fa"
CYAN = "#62eee2"

def collect(state, counts, end):
    camera = state["camera"]
    camera.stop.set()
    camera.worker.join(timeout=2)
    with camera.engine_lock:
        rows = camera.engine.rows(max(0, end-state["start"]), counts)
    for row in rows:
        row["typing_reference"] = state["profile"]["edit_rate"]
    return rows


class SessionApp:
    def __init__(self, root):
        self.root = root
        self.state = None
        self.listener = None
        self.root.title("Flowstate · Study sessions")
        scale = self.root.winfo_fpixels("1i") / 96
        self.root.geometry(f"{round(760*scale)}x{round(560*scale)}")
        self.root.minsize(round(620*scale),round(460*scale))
        self.root.configure(bg=BG)
        self.folder = Path(os.environ["LOCALAPPDATA"])/"TidalByte"/"Reports"
        self.dashboard = None
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        frame = tk.Frame(root, bg=BG)
        self.home = frame
        frame.pack(fill="both",expand=True)
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TButton",background=PANEL,foreground=INK,borderwidth=0,padding=(15,9))
        style.map("TButton",background=[("active","#38545b")],foreground=[("disabled","#889699")])
        style.configure("Primary.TButton",background=CYAN,foreground="#102d32")
        style.map("Primary.TButton",background=[("active","#a8fff4")])
        style.configure("TCheckbutton",background=BG,foreground=INK)
        style.configure("Horizontal.TProgressbar",background=CYAN,troughcolor=PANEL)
        self.brand = tk.PhotoImage(file=str(Path(__file__).with_name("flowstate-icon.png"))).subsample(3)
        root.iconphoto(True,self.brand)
        self.heading=tk.StringVar(value="Ready to focus?")
        self.message=tk.StringVar()
        self.popup=self.cal=None
        self.ai=tk.BooleanVar(value=True)
        build(self,frame)
        self.reset()

    def reset(self):
        self.state = None
        self.listener = None
        self.cal = None
        self.camera_button.configure(state="disabled")
        self.root.title("Flowstate · Study sessions")
        self.message.set("Start with 30 seconds of practice typing and five head positions. Flowstate then runs quietly until you finish.")
        self.heading.set("Ready to focus?")
        self.action.configure(text="Begin session",command=self.start,state="normal")
        self.sample.configure(state="normal")
        self.ai_box.configure(state="normal")
        self.latest.configure(state="normal" if (self.folder/"latest.json").is_file() else "disabled")
        self.past_sessions.configure(state="normal" if any(self.folder.glob("Session-*.html")) else "disabled")

    def start(self):
        start = time.monotonic()
        self.state = dict(start=start,camera=Camera(start))
        self.counts = {}
        self.lock = threading.Lock()
        self.heading.set("Getting ready")
        self.message.set("Opening webcam…")
        self.action.configure(text="Cancel setup",command=self.cancel)
        self.sample.configure(state="disabled")
        self.latest.configure(state="disabled")
        self.past_sessions.configure(state="disabled")
        self.ai_box.configure(state="disabled")
        self.check_camera()

    def cancel(self):
        self.hide_camera()
        if self.state:
            self.state["camera"].stop.set()
        self.reset()

    def check_camera(self):
        state=self.state
        if not state:
            return
        cam=state["camera"]
        if not cam.worker.is_alive() or time.monotonic()-state["start"]>60:
            self.cancel()
            messagebox.showerror("Camera setup","Could not open the camera. Check Windows camera access and close other camera apps.")
        elif cam.latest:
            self.cal=Calibration()
            self.head_guide=HeadGuide()
            self.show_camera()
        else:
            self.root.after(100,lambda: self.check_camera() if self.state is state else None)

    def hide_camera(self):
        if self.popup:
            self.popup.destroy()
            self.popup=None
            self.photo=None
        if self.state:
            self.state["camera"].preview=False

    def show_camera(self):
        if not self.state:
            return
        if self.popup:
            self.popup.lift()
            return
        self.state["camera"].preview=True
        win=self.popup=tk.Toplevel(self.root)
        win.configure(bg=BG)
        win.title("Flowstate · Calibration" if self.cal else "Flowstate · Webcam")
        win.protocol("WM_DELETE_WINDOW",self.cancel if self.cal else self.hide_camera)
        self.stage_label=tk.Label(win,bg=BG,fg=CYAN,font=("Lexend",15,"bold"))
        self.stage_label.pack(pady=6)
        self.screen=tk.Canvas(win,width=400,height=300,bg="#080b0e",highlightthickness=0)
        self.screen.pack(padx=16)
        self.cue=tk.Label(win,fg=INK,bg=BG,wraplength=390)
        self.cue.pack(pady=6)
        if self.cal:
            self.bar=ttk.Progressbar(win,length=365,maximum=35)
            self.bar.pack()
            tk.Label(win,text="Type naturally about what you plan to study.",bg=BG,fg=INK).pack(pady=5)
            self.practice=tk.Entry(win,width=46,bg=PANEL,fg=INK,insertbackground=CYAN)
            self.practice.pack(padx=16,pady=8)
            self.practice.focus_set()
            self.practice.bind("<KeyPress>",self.practice_key)
        ttk.Button(win,text="Cancel calibration" if self.cal else "Close preview",
                   command=self.cancel if self.cal else self.hide_camera).pack(pady=8)
        self.last_frame=None
        self.refresh_camera(win)

    def practice_key(self,event):
        now=time.monotonic()
        if self.cal and (event.char and event.char.isprintable() or event.keysym in ("BackSpace","Delete")):
            self.cal.key(now,event.keysym in ("BackSpace","Delete"))

    def refresh_camera(self,win):
        if self.popup is not win or not self.state:
            return
        cam=self.state["camera"]
        if not cam.worker.is_alive():
            if self.cal:
                self.cancel()
            else:
                self.hide_camera()
            messagebox.showwarning("Camera interrupted","Webcam capture stopped. Check the camera connection.")
            return
        packet=cam.latest
        if packet:
            stamp,pose,issue,centered,image=packet
            fresh=time.monotonic()-stamp<.5
            if stamp!=self.last_frame and fresh:
                self.last_frame=stamp
                if self.cal:
                    if not centered and not issue:
                        issue="Move your face inside the guide."
                    self.cal.observe(stamp,issue,pose)
                    if self.cal.step==len(STEPS):
                        self.begin_session()
                        return
                if image:
                    self.photo=tk.PhotoImage(data=image,format="PPM")
                    h=self.photo.height()
                    self.screen.configure(height=h)
                    self.screen.delete("all")
                    self.screen.create_image(0,0,anchor="nw",image=self.photo)
                    if self.cal:
                        self.head_guide.draw(self.screen, self.photo.width(), h,
                                             pose if self.cal.clear else None, self.cal)
            if self.cal:
                c=self.cal
                title="Practice typing" if c.step==0 else ("Face center" if c.step==5 else "Turn "+STEPS[c.step].lower())
                remaining=(30 if c.step==0 else 1)-c.elapsed
                self.stage_label.configure(text=f"{title}  ·  {remaining:.1f}s")
                self.bar.configure(value=(30+c.step-1 if c.step else 0)+c.elapsed)
                self.cue.configure(text=c.prompt if fresh else "Paused · waiting for a clear camera image.")
                if c.step:
                    self.practice.configure(state="disabled")
            else:
                self.stage_label.configure(text="Webcam preview")
                self.cue.configure(text="Session active")
        self.root.after(65,lambda:self.refresh_camera(win))

    def begin_session(self):
        profile=self.cal.profile()
        self.cal=None
        self.hide_camera()
        state=self.state
        cam=state["camera"]
        state["profile"]=profile
        cam.start=state["start"]=time.monotonic()
        cam.profile=profile
        try:
            from pynput import keyboard
            self.listener=keyboard.Listener(on_press=self.press)
            self.listener.start()
            self.listener.wait()
        except Exception as exc:
            if self.listener:
                self.listener.stop()
            self.cancel()
            messagebox.showerror("Keyboard setup",str(exc))
            return
        self.heading.set("Session active")
        self.action.configure(text="Finish session and open report",command=self.finish)
        self.camera_button.configure(state="normal")
        self.root.title("Flowstate · Session active")
        self.message.set("Session active. Restore this window to preview your webcam or finish.")
        self.root.iconify()

    def press(self,key):
        from pynput.keyboard import Key
        edit = key in (Key.backspace,Key.delete)
        if not edit and getattr(key,"char",None) is None and key not in (Key.space,Key.enter):
            return
        with self.lock:
            if self.state is None:
                return
            n = str(int((time.monotonic()-self.state["start"])//WINDOW))
            row = self.counts.setdefault(n,dict(keys=0,edits=0))
            row["keys"] += 1
            row["edits"] += int(edit)

    def view(self, rows,status,summary,demo=False, path=None, history=None, local_review=False):
        try:
            if path is None:
                self.folder.mkdir(parents=True,exist_ok=True)
                path = self.folder/("Example.html" if demo else "Latest-review.html")
                path.write_text(report(rows,demo,status,summary=summary,history=history),encoding="utf-8")
            viewer = Path(__file__).with_name("report_window.py")
            command = [sys.executable, str(viewer), str(path.resolve())]
            if local_review:
                command.append("--review")
            process = subprocess.Popen(command)
        except OSError:
            self.native_view(rows,status,summary,demo)
            return

        self.root.withdraw()
        def on_viewer_close():
            result = process.poll()
            if result is None:
                self.root.after(150,on_viewer_close)
                return
            self.root.deiconify()
            if result:
                self.native_view(rows,status,summary,demo)
            else:
                self.message.set("Report closed. You can start another study session.")
        on_viewer_close()

    def native_view(self, rows,status,summary,demo=False):
        self.home.pack_forget()
        self.dashboard = Dashboard(self.root,rows,status,summary,demo,self.go_home)
        self.dashboard.pack(fill="both",expand=True)
        self.root.title("Flowstate · Session review")

    def go_home(self):
        self.dashboard.destroy()
        self.dashboard = None
        self.home.pack(fill="both",expand=True)
        self.reset()

    def open_latest(self):
        try:
            data = json.loads((self.folder/"latest.json").read_text(encoding="utf-8"))
            report_file = data.pop("report_file", None)
            path = None
            if (isinstance(report_file, str) and Path(report_file).name == report_file
                    and report_file.startswith("Session-") and report_file.endswith(".html")):
                candidate = self.folder / report_file
                if candidate.is_file():
                    path = candidate
            if "calendar" not in (data.get("history") or {}) or ("engine" not in data["rows"][0] and "focus_reduction" not in data["rows"][0]):
                data["summary"] = summarize(data["rows"])
                data["history"] = focus_history(self.folder,data["rows"],reopening=True)
                path = None
            self.view(**data, path=path)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            messagebox.showerror("Report unavailable",str(exc))

    def open_past_session(self):
        selection = filedialog.askopenfilename(
            parent=self.root, title="Open a saved Flowstate session", initialdir=self.folder,
            filetypes=[("Flowstate session reports", "Session-*.html")],
        )
        if not selection:
            return
        try:
            path = Path(selection).resolve(strict=True)
            if path.parent != self.folder.resolve() or not path.name.startswith("Session-") or path.suffix != ".html":
                raise ValueError("Choose a saved session from the Flowstate Reports folder.")
            page = path.read_text(encoding="utf-8")
            embedded = re.search(r'<script type="application/json" id="session">(.*?)</script>', page, re.S)
            if not embedded:
                raise ValueError("This file does not contain a Flowstate session.")
            payload = json.loads(embedded[1])
            rows = payload["rows"]
            if not isinstance(rows, list) or not rows:
                raise ValueError("This report has no session data.")
            summary = summarize(rows)
            review = re.search(r'<h3 id="nemotron-heading">Nemotron review</h3><p>(.*?)</p>', page, re.S)
            if review:
                summary += " Nemotron review · " + html.unescape(review[1])
            self.view(rows, payload.get("status", "Saved session"), summary, path=path)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            messagebox.showerror("Report unavailable", str(exc), parent=self.root)

    def preview(self):
        rows = example()
        self.view(rows,"Simulated capture",summarize(rows),True,local_review=self.ai.get())

    def finish(self):
        end = time.monotonic()
        self.hide_camera()
        self.listener.stop()
        state = self.state
        with self.lock:
            self.state = None
            counts = self.counts
        self.action.configure(state="disabled")
        self.message.set("Preparing your session report…")
        self.root.update_idletasks()
        rows = collect(state,counts,end)
        status = state["camera"].status
        summary = summarize(rows)
        self.reset()
        try:
            self.folder.mkdir(parents=True,exist_ok=True)
            name = datetime.now().strftime("Session-%Y%m%d-%H%M%S-%f")
            html_path = self.folder/(name+".html")
            history = focus_history(self.folder,rows)
            html_path.write_text(report(rows,False,status,summary=summary,history=history),encoding="utf-8")
            temp = self.folder/(name+".tmp")
            temp.write_text(json.dumps(dict(rows=rows,status=status,summary=summary,history=history,
                                            report_file=html_path.name)),encoding="utf-8")
            temp.replace(self.folder/"latest.json")
            self.latest.configure(state="normal")
            self.past_sessions.configure(state="normal")
            self.view(rows,status,summary,path=html_path,local_review=self.ai.get())
        except OSError as exc:
            self.native_view(rows,status,summary)
            messagebox.showwarning("Report is available in this window",f"Could not save your local copy. {exc}")

    def close(self):
        if self.listener and self.state:
            self.finish()
            return
        elif self.state:
            self.cancel()
        self.root.destroy()

if __name__ == "__main__":
    if sys.platform != "win32":
        sys.exit("Flowstate capture requires Windows.")
    # Opt in before Tk creates any HWND so Windows draws text at display resolution.
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except AttributeError:
        ctypes.windll.user32.SetProcessDPIAware()
    if sys.platform == 'win32':
        font_path = Path(__file__).with_name('fonts') / 'Lexend.ttf'
        ctypes.windll.gdi32.AddFontResourceExW(str(font_path), 0x10, None)
    root = tk.Tk()
    for name in tkfont.names(root):
        tkfont.nametofont(name, root=root).configure(family="Lexend")
    root.option_add("*Font", "TkDefaultFont")
    SessionApp(root)
    root.mainloop()
