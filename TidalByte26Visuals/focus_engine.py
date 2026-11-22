"""Session-only adapter for the uploaded Focus Engine. Times are in seconds."""
from collections import deque
from dataclasses import dataclass
from math import asin, atan2, ceil, degrees, dist, floor
from pathlib import Path
from statistics import mean, median, pstdev


def unit(x):
    return max(0., min(1., x))


@dataclass
class Frame:
    t: float
    closed: bool
    mar: float
    yaw: float
    pitch: float
    lip: float
    brow: float
    facing: bool


class SessionModel:
    def __init__(self, mp):
        vision = mp.tasks.vision
        self.mp = mp
        model = Path(__file__).with_name("face_landmarker.task")
        self.detector = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_buffer=model.read_bytes()),
            running_mode=vision.RunningMode.VIDEO, num_faces=1,
            output_face_blendshapes=True, output_facial_transformation_matrixes=True))

    def measure(self, rgb, stamp, t, profile, hands):
        image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb)
        result = self.detector.detect_for_video(image, int(stamp*1000))
        if not (result.face_landmarks and result.face_blendshapes and result.facial_transformation_matrixes):
            return None
        pts = result.face_landmarks[0]
        xs, ys = [p.x for p in pts], [p.y for p in pts]
        bounds = min(xs), max(xs), min(ys), max(ys)
        if any(any(bounds[0]<p.x<bounds[1] and bounds[2]<p.y<bounds[3] for p in hand.landmark)
               for hand in hands or []):
            return None
        height, width = rgb.shape[:2]
        def distance(a,b):
            return dist((xs[a]*width,ys[a]*height),(xs[b]*width,ys[b]*height))
        if min(bounds[0],bounds[2])<.01 or max(bounds[1],bounds[3])>.99 or abs(xs[263]-xs[33])<.075:
            return None
        x = (xs[1]-min(xs[33],xs[263]))/abs(xs[263]-xs[33])
        y = (ys[1]-ys[10])/max(.001,ys[152]-ys[10])
        facing = profile['xlim'][0]<=x<=profile['xlim'][1] and profile['ylim'][0]<=y<=profile['ylim'][1]
        def ear(a,b,c,d,e,f):
            return (distance(b,f)+distance(c,e))/(2*max(1,distance(a,d)))
        eyes = (ear(33,160,158,133,153,144)+ear(362,385,387,263,373,380))/2
        scores = {c.category_name:c.score for c in result.face_blendshapes[0]}
        def pair(name):
            return (scores[name+'Left']+scores[name+'Right'])/2
        matrix = result.facial_transformation_matrixes[0]
        return Frame(t, eyes<.2 or pair('eyeBlink')>.5, distance(13,14)/max(1,distance(78,308)),
                     degrees(atan2(matrix[0,2],matrix[2,2])), degrees(asin(max(-1,min(1,-matrix[1,2])))),
                     pair('mouthPress'), pair('browDown'), facing)


class Engine:
    def __init__(self):
        self.frames, self.blinks, self.yawns = deque(), deque(), deque()
        self.closed_at = self.open_at = self.prev = None
        self.counted_yawn = self.counted_long = False
        self.baseline_samples = []
        self.base = None
        self.baseline_start = None
        self.smooth = {}
        self.next_tick = 1
        self.buckets = {}

    def bucket(self,t):
        return self.buckets.setdefault(int(t//30),dict(frames=0,samples=0,facing=0,closed=0,
            yawns=0,long_closures=0,focus=[],stress=[],fatigue=[]))

    def record(self,t,f):
        while self.next_tick < t:
            self.tick(self.next_tick)
            self.next_tick += 1
        b = self.bucket(t)
        b['frames'] += 1
        if self.prev is None or t-self.prev>.5 or f is None:
            self.closed_at = self.open_at = None
            self.counted_yawn = self.counted_long = False
        self.prev = t
        self.frames.append((t,f))
        if f is None:
            return
        b['samples'] += 1
        b['facing'] += int(f.facing)
        b['closed'] += int(f.closed)
        if self.base is None and f.facing:
            if self.baseline_start is None:
                self.baseline_start = t
            self.baseline_samples.append(f)
        if f.closed:
            if self.closed_at is None:
                self.closed_at = t
            if t-self.closed_at >= .8 and not self.counted_long:
                b['long_closures'] += 1
                self.counted_long = True
        else:
            if self.closed_at is not None:
                self.blinks.append((t,t-self.closed_at,f))
            self.closed_at = None
            self.counted_long = False
        if f.mar>.6:
            if self.open_at is None:
                self.open_at = t
            if t-self.open_at>=1.5 and not self.counted_yawn:
                self.yawns.append(t)
                b['yawns'] += 1
                self.counted_yawn = True
        else:
            self.open_at = None
            self.counted_yawn = False

    def tick(self,t):
        for events in (self.frames,self.blinks):
            while events and events[0][0]<t-30:
                events.popleft()
        while self.yawns and self.yawns[0]<t-30:
            self.yawns.popleft()
        samples = self.baseline_samples
        if self.base is None and samples and t-self.baseline_start>=20 and len(samples)>=10:
            self.base = (median(f.yaw for f in samples),median(f.pitch for f in samples),
                         mean(f.lip for f in samples),pstdev(f.lip for f in samples),mean(f.brow for f in samples))
            samples.clear()
        if (not self.base and not samples) or not self.frames or self.prev is None or t-self.prev>.5:
            self.smooth.clear()
            return
        yaw,pitch,lip,sd,brow = self.base or (median(f.yaw for f in samples),median(f.pitch for f in samples),0,0,0)
        recent = [f for ts,f in self.frames if ts>=t-10]
        observed = [f for f in recent if f is not None]
        if not recent or len(observed)<len(recent)/2 or not any(f.t>t-1 for f in observed):
            self.smooth.clear()
            return
        def frontal(f,limit):
            return not f.closed and abs(f.yaw-yaw)<limit and abs(f.pitch-pitch)<20
        def stress_frame(f):
            return frontal(f,20) and f.mar<.3
        focus = 100*sum(frontal(f,25) for f in observed)/len(recent)
        closures = sum(bool(f and f.closed) for _,f in self.frames)/len(self.frames)
        duration = mean(e[1] for e in self.blinks) if self.blinks else 0
        fatigue = 100*(.6*unit((closures-.05)/.2)+.25*unit(len(self.yawns)/3)+.15*unit((duration-.15)/.35))
        valid = [f for f in observed if stress_frame(f)]
        values = dict(focus=focus,fatigue=fatigue)
        if len(valid)>=len(recent)/2:
            filtered = []
            ema = valid[0].brow
            for f in valid:
                ema += .3*(f.brow-ema)
                if f.t>=t-5:
                    filtered.append(ema)
            upper = sorted(filtered)[ceil(len(filtered)*.9)-1] if filtered else brow
            rate = 6*sum(ts>=t-10 and stress_frame(f) for ts,_,f in self.blinks)
            values['stress'] = 100*(.55*unit((upper-brow-.01)/.08)
                +.3*unit((mean(f.lip for f in valid)-lip)/(3*sd+.01))
                +.15*unit(abs(rate-15)/15-.5))
        elif 'stress' in self.smooth:
            self.smooth['stress'] *= 2**(-1/30)
        b = self.bucket(t-1)
        for key,value in values.items():
            prior = self.smooth.get(key,value)
            self.smooth[key] = prior+.4*(value-prior)
            if self.base or key == 'focus':
                b[key].append(floor(self.smooth[key]+.5))
            else:
                self.smooth[key] = 0

    def rows(self,elapsed,counts):
        while self.next_tick <= elapsed:
            self.tick(self.next_tick)
            self.next_tick += 1
        rows = []
        for t in range(0,max(1,ceil(elapsed)),30):
            b = self.bucket(t)
            n = b['samples']
            keys = counts.get(str(t//30),{})
            row = dict(t=t,duration=min(30,max(1,ceil(elapsed)-t)),engine='focus-engine-v1',
                frames=b['frames'],samples=n,keys=keys.get('keys',0),edits=keys.get('edits',0),
                orientation=round(100*b['facing']/n) if n else None,closed=b['closed']/n if n else None,
                yawns=b['yawns'] if n else None,long_closures=b['long_closures'] if n else None)
            for key in ('focus','stress','fatigue'):
                row[key] = round(mean(b[key])) if b[key] else None
                row[key+'_seconds'] = len(b[key])
            row['activity'] = ('Keyboard activity' if row['keys'] else
                               'Quiet · face visible' if n else 'Unobserved')
            rows.append(row)
        return rows
