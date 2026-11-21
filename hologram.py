"""Projected head template for the mirrored calibration preview."""
from math import cos, exp, pi, sin

# Height, temple radius, front-to-back radius, depth offset, nose/lip relief.
RINGS = (
    (-1, .03, .04, -.06, 0), (-.96, .28, .31, -.06, 0),
    (-.82, .55, .58, -.06, 0), (-.61, .69, .72, -.06, 0),
    (-.38, .75, .77, -.06, 0), (-.15, .76, .78, -.07, .02),
    (.03, .73, .74, -.07, .09), (.19, .69, .72, -.06, .24),
    (.28, .66, .69, -.05, .31), (.34, .64, .66, -.05, .12),
    (.44, .61, .63, -.04, .11), (.51, .59, .61, -.03, .06),
    (.58, .56, .58, -.02, .09), (.70, .50, .51, .02, .03),
    (.84, .37, .40, .09, .03), (.93, .21, .28, .15, .02),
    (.97, .04, .07, .25, 0),
)
SIDES = 48


def vertex(row, angle):
    y, width, depth, offset, relief = row
    return (width*sin(angle), y,
            offset + depth*cos(angle) + relief*exp(-9*(1-cos(angle))))


MESH = [[vertex(row, 2*pi*i/SIDES) for i in range(SIDES)] for row in RINGS]


class HeadGuide:
    def __init__(self):
        self.yaw = self.pitch = 0.
        self.reference = None

    def draw(self, canvas, width, height, pose, calibration):
        if pose is not None:
            if self.reference is None:
                self.reference = pose
            if calibration.poses[0] and calibration.step <= 1:
                self.reference = calibration.centroid(0)
            dx = pose[0] - self.reference[0]
            dy = pose[1] - self.reference[1]
            self.yaw += .48*(max(-1.32, min(1.32, -4.4*dx)) - self.yaw)
            self.pitch += .48*(max(-.68, min(.68, 3.4*dy)) - self.pitch)

        cy, sy = cos(self.yaw), sin(self.yaw)
        cp, sp = cos(self.pitch), sin(self.pitch)
        scale = min(height*.395, width*.30)

        def project(point):
            x, y, z = point
            depth = z*cy - x*sy
            return (width*.5 + scale*(x*cy + z*sy),
                    height*.46 + scale*(y*cp + depth*sp))

        def stroke(points, detail=False):
            coords = [value for point in points for value in point]
            if len(coords) < 4:
                return
            canvas.create_line(*coords, fill="#102b59", width=3 if detail else 5,
                               joinstyle="round", capstyle="round")
            canvas.create_line(*coords, fill="#578bb7" if detail else "#639edf",
                               width=1 if detail else 2, joinstyle="round", capstyle="round")

        # Depth-tested silhouette of the rotating surface, including the nose.
        projected = [[project(p) for p in ring] for ring in MESH]
        edges = set()
        for j in range(len(RINGS)-1):
            for i in range(SIDES):
                k = (i+1) % SIDES
                a,b,c = projected[j][i],projected[j][k],projected[j+1][i]
                if (b[0]-a[0])*(c[1]-a[1]) <= (b[1]-a[1])*(c[0]-a[0]):
                    continue
                quad = ((j,i),(j,k),(j+1,k),(j+1,i))
                for first, second in zip(quad, quad[1:]+quad[:1]):
                    edge = tuple(sorted((first,second)))
                    if edge in edges:
                        edges.remove(edge)
                    else:
                        edges.add(edge)
        # Join adjacent segments before drawing the luminous outline.
        neighbors = {}
        for a,b in edges:
            neighbors.setdefault(a,set()).add(b)
            neighbors.setdefault(b,set()).add(a)
        while neighbors:
            node = next(iter(neighbors))
            path = [node]
            while node in neighbors:
                nxt = neighbors[node].pop()
                neighbors[nxt].remove(node)
                for end in (node,nxt):
                    if not neighbors[end]:
                        del neighbors[end]
                path.append(nxt)
                node = nxt
            stroke([projected[j][i] for j,i in path])

        # Sparse construction lines leave the participant's eyes visible.
        stroke([project(vertex(row,0)) for row in RINGS], True)
        for row_index in (3,6,9,12):
            arc = []
            for i in range(-24,25):
                angle = i*pi/28
                if cos(angle+self.yaw) > .12:
                    arc.append(project(vertex(RINGS[row_index],angle)))
            stroke(arc, True)
        for side in (-1,1):
            if side*sy > .2:
                continue
            ear = [(side*(.71+.075*cos(t*pi/18)), .16+.18*sin(t*pi/18), -.10)
                   for t in range(37)]
            stroke([project(p) for p in ear], True)
            neck = [(side*x,y,z) for x,y,z in
                    ((.47,.70,-.11),(.43,.90,-.12),(.45,1.10,-.13),(.55,1.24,-.14))]
            stroke([project(p) for p in neck], True)
