"""Native, interactive post-session review."""
import csv
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from signals import score
from report import clock

BG = "#f1f6f9"
INK = "#183549"
PURPLE = "#6847ae"
MINT = "#c9f4e2"
PINK = "#ffe0eb"
LILAC = "#daedf6"
PEACH = "#ffe8c9"


def label(parent, text, size=11, bold=False, bg=BG, **options):
    return tk.Label(parent, text=text, bg=bg, fg=INK,
                    font=("Segoe UI", size, "bold" if bold else "normal"), **options)


def mascot(parent):
    c = tk.Canvas(parent, width=80, height=64, bg=LILAC, highlightthickness=0)
    c.create_polygon(12,20,40,6,68,20,40,35,fill="#b5edfc",outline="#76b9d7")
    c.create_polygon(12,20,40,35,40,58,12,43,fill="#57adc9",outline="#76b9d7")
    c.create_polygon(40,35,68,20,68,43,40,58,fill="#88d6e9",outline="#76b9d7")
    return c


class Dashboard(tk.Frame):
    def __init__(self, parent, rows, status, summary, demo, back):
        super().__init__(parent, bg=BG, padx=16, pady=10)
        self.rows = rows
        self.periods = score(rows)
        self.demo = demo
        self.index = 0
        self.detail = tk.StringVar()
        self.end = rows[-1]["t"] + rows[-1]["duration"]
        head = tk.Frame(self, bg=LILAC, padx=10, pady=4)
        head.pack(fill="x")
        mascot(head).pack(side="left")
        label(head, "Example session" if demo else "Your session", 21, True, LILAC).pack(side="left")
        ttk.Button(head, text="Done", command=back).pack(side="right", padx=5)
        grid = tk.Frame(self,bg=BG)
        grid.pack(fill="x", pady=7)
        for i,(name,value,tint) in enumerate([
                ("Session length", clock(self.end), LILAC),
                ("Frames processed", sum(r["frames"] for r in rows), MINT),
                ("Usable face samples", sum(r["samples"] for r in rows), PINK),
                ("Key presses", sum(r["keys"] for r in rows), PEACH)]):
            grid.columnconfigure(i,weight=1,uniform="card")
            tile = tk.Frame(grid,bg=tint,pady=5)
            tile.grid(row=0,column=i,sticky="nsew",padx=2)
            label(tile,str(value),17,True,tint).pack()
            label(tile,name,9,bg=tint).pack()
        tabs = ttk.Notebook(self)
        tabs.pack(fill="both",expand=True)
        timeline = tk.Frame(tabs,bg=BG,padx=10,pady=6)
        review = tk.Frame(tabs,bg=BG,padx=12,pady=8)
        tabs.add(timeline,text="  Timeline  ")
        tabs.add(review,text="  Session details  ")
        self.legend = label(timeline,"",10)
        self.legend.pack(anchor="w",pady=4)
        self.chart = tk.Canvas(timeline,bg="white",highlightthickness=0,height=170)
        self.chart.pack(fill="both",expand=True)
        self.chart.bind("<Configure>",lambda e:self.draw())
        self.chart.bind("<Motion>",self.inspect)
        self.chart.bind("<Button-1>",self.inspect)
        self.chart.bind("<Left>",lambda e:self.select(self.index-1))
        self.chart.bind("<Right>",lambda e:self.select(self.index+1))
        self.chart.configure(takefocus=True)
        label(timeline,"",10,textvariable=self.detail,anchor="w",justify="left",wraplength=650).pack(fill="x",pady=5)
        lines = self.explain(status,summary)
        box = tk.Text(review,wrap="word",font=("Segoe UI",11),bg="#fffafa",fg=INK,
                      relief="flat",padx=12,pady=10,height=7)
        bar = ttk.Scrollbar(review,command=box.yview)
        box.configure(yscrollcommand=bar.set)
        bar.pack(side="right",fill="y")
        box.pack(fill="both",expand=True)
        box.insert("end","\n\n".join(lines))
        box.configure(state="disabled")
        if not demo:
            ttk.Button(self,text="Export window data for training…",command=self.export).pack(anchor="e",pady=5)

    def explain(self,status,summary):
        rows = self.rows
        details = [summary, "Camera status at finish · "+status]
        if not sum(r["frames"] for r in rows):
            details.append("No processed frames reached the collector. Check webcam permissions and close other apps using the camera.")
        elif not sum(r["samples"] for r in rows):
            details.append("Frames arrived, but no usable face samples were found. Check lighting and keep your eyes in view.")
        if rows[0].get("engine"):
            details.append("Focus uses open eyes and head direction. Fatigue combines eye closure, blink duration and possible yawns. Estimated stress uses brow, lip and blink changes.")
            details.append("Elevated stress windows · "+(", ".join(clock(a)+"–"+clock(b) for a,b in self.periods) or "None flagged."))
            return details
        if all(r["focus"] is None for r in rows):
            details.append("Focus needs 60 usable samples spanning 20 seconds within one 30-second window.")
        if all(r["fatigue"] is None for r in rows):
            details.append("Fatigue needs two usable baseline windows in the first two minutes and a usable window after 2:00.")
        details.append("Possible stress periods · "+(", ".join(clock(a)+"–"+clock(b) for a,b in self.periods) or
                        "None flagged. The rule needs baseline typing and two consecutive windows with elevated correction rates."))
        details.append("The focus estimate starts with camera-facing posture. After 60 consecutive seconds of measured windows with fatigue at 80 or higher, its ceiling falls from 85 at fatigue 80 to 65 at fatigue 100. Missing data or a lower fatigue reading resets the timer. This is an experimental scoring rule. A quiet keyboard can mean thinking or reading. Fatigue measures a change in eye closure. Stress flags mark bursts of corrections. These are experimental rules.")
        return details

    def inspect(self,event):
        if event.type == tk.EventType.ButtonPress:
            self.chart.focus_set()
        frac = (event.x-40)/max(1,self.chart.winfo_width()-58)
        self.select(next((i for i,r in enumerate(self.rows) if r["t"]+r["duration"]>frac*self.end),len(self.rows)-1))

    def select(self,i):
        self.index = max(0,min(len(self.rows)-1,i))
        self.cursor()

    def cursor(self):
        c = self.chart
        c.delete("cursor")
        r = self.rows[self.index]
        w,h = c.winfo_width(),c.winfo_height()
        x = 40+(w-58)*(r["t"]+r["duration"]/2)/self.end
        c.create_line(x,12,x,max(13,h-26),fill="#aa94bd",dash=(3,4),tags="cursor")
        def val(k): return "insufficient data" if r[k] is None else str(r[k])
        self.detail.set(f'{clock(r["t"])}–{clock(r["t"]+r["duration"])}   ·   {r["frames"]} frames   ·   {r["samples"]} face samples   ·   {r["keys"]} presses\nFocus {val("focus")}   ·   Fatigue {val("fatigue")}   ·   {r["activity"]}')

    def draw(self):
        c = self.chart
        c.delete("all")
        w,h = c.winfo_width(),c.winfo_height()
        if min(w,h)<50: return
        series = [("focus","#117fac"),("fatigue","#bd4e27")]
        self.legend.configure(text="Blue · focus     Amber · fatigue     Pink bands · possible stress")
        if self.rows[0].get("engine"):
            series.append(("stress",PURPLE))
            self.legend.configure(text="Blue · focus     Amber · fatigue     Purple · estimated stress")
        limit = 100
        def x(t): return 40+(w-58)*t/self.end
        def y(v): return h-26-(h-40)*v/limit
        for a,b in self.periods:
            c.create_rectangle(x(a),12,x(b),h-26,fill=PINK,outline="")
        for i in range(3):
            v = limit*i/2
            c.create_line(40,y(v),w-18,y(v),fill="#e3dce9")
            c.create_text(36,y(v),text=f"{v:g}",anchor="e",fill=INK)
            c.create_text(x(self.end*i/2),h-12,text=clock(self.end*i/2),fill=INK)
        for k,color in series:
            prev = None
            for r in self.rows:
                if r[k] is None:
                    prev = None
                    continue
                a,b = x(r["t"]+r["duration"]/2), y(r[k])
                if prev: c.create_line(*prev,a,b,width=2,fill=color)
                c.create_oval(a-3,b-3,a+3,b+3,fill=color,outline="")
                prev=(a,b)
        if all(r["focus"] is None and r["fatigue"] is None for r in self.rows):
            c.create_text(w/2,h/2,text="More usable camera time needed. See Session details.",width=w-90,fill=INK)
        self.cursor()

    def export(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV spreadsheet","*.csv")])
        if not path: return
        features = ["t","duration","frames","samples","keys","edits","orientation","closed","focus","fatigue","stress","yawns","long_closures"]
        labels = ["participant_id","session_id","focus_rating","fatigue_rating","stress_rating"]
        try:
            with open(path,"w",encoding="utf-8",newline="") as f:
                writer = csv.DictWriter(f,fieldnames=features+labels,extrasaction="ignore")
                writer.writeheader()
                writer.writerows(self.rows)
        except OSError as e:
            messagebox.showerror("Export failed",str(e))
