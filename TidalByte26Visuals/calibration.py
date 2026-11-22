"""Calibration timer driven by fresh camera observations."""
from statistics import median

STEPS = ("Type", "Left", "Right", "Up", "Down", "Center")


class Calibration:
    def __init__(self):
        self.step = 0
        self.elapsed = 0.0
        self.previous = None
        self.active = False
        self.clear = False
        self.last_key = None
        self.keys = self.edits = 0
        self.poses = [[] for _ in STEPS]
        self.prompt = "Center your face in the guide."

    def key(self, now, edit):
        if self.step == 0 and self.previous is not None and now-self.previous < .5 and self.clear:
            self.keys += 1
            self.edits += int(edit)
            self.last_key = now

    def observe(self, now, issue, pose):
        dt = now-self.previous if self.previous is not None else 0
        self.previous = now
        self.clear = not issue and pose is not None
        if self.step == len(STEPS):
            return
        if self.clear:
            x,y = pose
            if self.step == 0:
                if self.last_key is None or now-self.last_key > 2:
                    issue = "Type in the practice field to run the timer."
            else:
                reference = self.centroid(0)
                dx,dy = x-reference[0],y-reference[1]
                correct = (dx>.10, dx<-.10, dy<-.07, dy>.07,
                           abs(dx)<.08 and abs(dy)<.07)[self.step-1]
                if not correct:
                    issue = "Follow the direction shown, then hold still."
        if issue or pose is None:
            self.active = False
            if self.step:
                self.elapsed = 0
                self.poses[self.step].clear()
            self.prompt = issue or "Bring your face into view."
            return
        if self.active and 0 < dt <= .5:
            self.elapsed += dt
        elif self.step:
            self.elapsed = 0
            self.poses[self.step].clear()
        self.active = True
        self.prompt = "Keep typing naturally." if not self.step else "Hold this position."
        self.poses[self.step].append(pose)
        if self.elapsed >= (30 if not self.step else 1):
            self.step += 1
            self.elapsed = 0
            self.active = False

    def centroid(self, step):
        return tuple(map(median,zip(*self.poses[step])))

    def profile(self):
        center = self.centroid(5)
        return dict(center=center,
                    xlim=[(center[0]+self.centroid(i)[0])/2 for i in (2,1)],
                    ylim=[(center[1]+self.centroid(i)[1])/2 for i in (3,4)],
                    edit_rate=self.edits/max(1,self.keys), keys=self.keys)
