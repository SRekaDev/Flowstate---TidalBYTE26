"""Local webcam sampler and transparent, experimental session indicators."""
import threading
import time
from math import dist, sin, cos
from statistics import mean, median

from focus_engine import Engine, Frame, SessionModel

WINDOW = 30


class Camera:
    def __init__(self, start):
        self.start = start
        self.engine = Engine()
        self.engine_lock = threading.Lock()
        self.latest = None
        self.preview = True
        self.profile = None
        self.ready = threading.Event()
        self.stop = threading.Event()
        self.worker = threading.Thread(target=self.capture, daemon=True)
        self.status = "Starting camera"
        self.worker.start()

    def capture(self):
        cap = None
        session_model = None
        try:
            import cv2
            import mediapipe as mp
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                self.status = "Camera unavailable"
                return
            with mp.solutions.face_mesh.FaceMesh(max_num_faces=1) as mesh, mp.solutions.hands.Hands(max_num_hands=2,model_complexity=0) as hands:
                self.status = "Camera enabled"
                while not self.stop.is_set():
                    ok, frame = cap.read()
                    if not ok:
                        self.status = "Camera interrupted"
                        break
                    self.ready.set()
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    profile = self.profile
                    result = mesh.process(rgb) if profile is None else None
                    hand_result = hands.process(rgb)
                    now = time.monotonic()
                    pose = None
                    issue = "Bring your face into view and improve the lighting."
                    centered = False
                    if profile:
                        if session_model is None:
                            session_model = SessionModel(mp)
                        elapsed = now-self.start
                        features = session_model.measure(rgb,now,elapsed,profile,hand_result.multi_hand_landmarks)
                        with self.engine_lock:
                            if not self.stop.is_set():
                                self.engine.record(elapsed,features)
                    elif result.multi_face_landmarks:
                        pts = result.multi_face_landmarks[0].landmark
                        h, w = frame.shape[:2]
                        def point(i):
                            return (pts[i].x*w, pts[i].y*h)
                        def aspect(indices):
                            a,b,c,d,e,f = map(point, indices)
                            return (dist(b,f)+dist(c,e))/(2*max(1,dist(a,d)))
                        ear = mean([aspect((33,160,158,133,153,144)),
                                    aspect((362,385,387,263,373,380))])
                        left,right = sorted((point(33)[0],point(263)[0]))
                        x=(point(1)[0]-left)/max(1,right-left)
                        y=(point(1)[1]-point(10)[1])/max(1,point(152)[1]-point(10)[1])
                        fx=min(p.x for p in pts); rx=max(p.x for p in pts)
                        fy=min(p.y for p in pts); by=max(p.y for p in pts)
                        centered = abs((fx+rx)/2-.5)<.17 and abs((fy+by)/2-.5)<.20
                        covered=any(any(fx<q.x<rx and fy<q.y<by for q in hand.landmark)
                                    for hand in (hand_result.multi_hand_landmarks or []))
                        if covered:
                            issue="Move your hand away from your face."
                        elif min(fx,fy)<.01 or max(rx,by)>.99 or right-left < .075*w:
                            issue="Keep your whole face in view and move closer."
                        elif .04 < ear < .65:
                            pose=(x,y)
                            issue=""
                    preview=None
                    if self.preview:
                        height,width=frame.shape[:2]
                        thumb=cv2.resize(cv2.flip(frame,1),(400,round(400*height/width)))
                        ok,data=cv2.imencode(".ppm",thumb)
                        if ok:
                            preview=data.tobytes()
                    self.latest=(now,pose,issue,centered,preview)
                    self.stop.wait(.08)
        except Exception as error:
            self.status = "Camera unavailable (" + type(error).__name__ + ")"
        finally:
            if session_model is not None:
                session_model.detector.close()
            if cap is not None:
                cap.release()


def score(rows):
    if rows and rows[0].get("engine"):
        periods = []
        for row in rows:
            if (row.get("stress") or 0) < 70 or row["stress_seconds"] < 15:
                continue
            start, end = row["t"], row["t"]+row["duration"]
            if periods and periods[-1][1] == start:
                periods[-1] = (periods[-1][0],end)
            else:
                periods.append((start,end))
        return periods
    # Archived sessions retain their original interpretation.
    # First two minutes only. Insufficient personal reference leaves gaps.
    initial = [r for r in rows if r["t"] < 120 and r["duration"] >= 25]
    keys = [r for r in initial if r["keys"] >= 10]
    eyes = [r["closed"] for r in initial if r["closed"] is not None]
    base_edits = median(r["edits"]/r["keys"] for r in keys) if len(keys)>=2 else None
    base_eye = median(eyes) if len(eyes)>=2 else None
    periods = []
    streak = []
    high_seconds = 0
    previous_end = None
    for r in rows:
        typing = r["keys"] >= 10 and r["duration"] >= 20
        r["focus"] = r["orientation"]
        r["activity"] = ("Keyboard activity" if r["keys"] else
                         "Quiet · face visible" if r["orientation"] is not None else "Unobserved")
        r["fatigue"] = None
        r["gesture_points"] = 0
        if r["t"] >= 120 and base_eye is not None and r["closed"] is not None:
            eye_score = min(100,max(0,round(500*(r["closed"]-base_eye))))
            # A prolonged closure already contributes to eye_score; limit its extra weight.
            bonus = min(16, 8*(r.get("yawns") or 0) + 4*(r.get("long_closures") or 0))
            r["fatigue"] = min(100, eye_score + bonus)
            r["gesture_points"] = r["fatigue"] - eye_score
        if r["t"] != previous_end:
            high_seconds = 0
        previous_end = r["t"] + r["duration"]
        fatigue = r["fatigue"]
        r["focus_reduction"] = 0
        if fatigue is not None and fatigue >= 80 and r["orientation"] is not None:
            high_seconds += r["duration"]
            if high_seconds >= 60:
                # Experimental ceiling moves from 85 at fatigue 80 to 65 at 100.
                r["focus"] = min(r["orientation"], 165 - fatigue)
                r["focus_reduction"] = r["orientation"] - r["focus"]
        else:
            high_seconds = 0
        personal = r.get("typing_reference")
        if personal is None:
            personal = base_edits
        high = (typing and personal is not None and (r.get("typing_reference") is not None or r["t"]>=120) and
                r["edits"]/r["keys"] >= personal+.10)
        if high:
            streak.append(r)
        if not high or r is rows[-1]:
            if len(streak)>=2:
                periods.append((streak[0]["t"],streak[-1]["t"]+streak[-1]["duration"]))
            streak = []
    return periods


def example():
    engine = Engine()
    counts = {}
    for i in range(1800*8):
        t = i/8
        n = int(t//WINDOW)
        tense = 660<=t<810 or 1410<=t<1530
        tired = 1290<=t<1530
        yawn = tired and t%62<3
        closed = t%4<(.65 if tired else .16)
        yaw = 35 if t%90>68 else 3*sin(t/6)
        frame = Frame(t, closed, .75 if yawn else .07, yaw, 3*cos(t/8),
                      .16 if tense else .03, .17 if tense else .02, abs(yaw)<20)
        engine.record(t,None if 960<=t<1050 else frame)
        if n not in counts:
            counts[n] = dict(keys=0 if 900<=t<1050 else 55,edits=0 if 900<=t<1050 else 3)
    return engine.rows(1800,{str(k):v for k,v in counts.items()})
