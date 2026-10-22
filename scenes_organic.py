"""Procedural program objects for 74.045 <= audio time < 85.078.

Only the supplied inclusive area is owned. No player/scenes imports, frame
counters, random state, cached frames, or assumptions about subtitle rows.
"""
from dataclasses import dataclass
import math

import visuals as v


@dataclass(frozen=True)
class OrganicState:
    subject: str
    resource: str
    phase: str
    progress: float


_CUES = (
    ('eggplant', 'NUTRIENTS', 74.045, 75.422, 76.959, 77.576),
    ('tomato', 'ANTIOXIDANTS', 77.576, 79.226, 80.620, 81.351),
    ('cat', 'ENJOYMENT', 81.351, 82.833, 84.268, 85.078),
)


def organic_state(t):
    """The single causal clock for code, extraction, transport, and receipt."""
    for subject, resource, start, extract, receive, end in _CUES:
        if start <= t < end:
            if t < extract:
                phase, a, b = 'cast', start, extract
            elif t < receive:
                phase, a, b = 'extract', extract, receive
            else:
                phase, a, b = 'receive', receive, end
            return OrganicState(subject, resource, phase, (t-a)/(b-a))
    return None


class _Area:
    """Clip ASCII primitives in both axes without changing the caller's clip."""
    def __init__(self, canvas, area):
        self.canvas = canvas
        l, top, r, bottom = area
        self.bounds = max(0, l), max(0, top), min(canvas.w-1, r), min(canvas.h-1, bottom)
        l, top, r, bottom = self.bounds
        self.w, self.h = r-l+1, bottom-top+1

    def put(self, x, y, text, style=v.N):
        x, y = int(x), int(y)
        l, top, r, bottom = self.bounds
        if not top <= y <= bottom:
            return
        text = str(text)
        first, last = max(0, l-x), min(len(text), r-x+1)
        if first < last:
            self.canvas.put(x+first, y, text[first:last], style)

    def line(self, x0, y0, x1, y1, ch='.', style=v.SHADE):
        steps = max(1, math.ceil(max(abs(x1-x0), abs(y1-y0))*1.5))
        for i in range(steps+1):
            u = i/steps
            self.put(round(v.mix(x0, x1, u)), round(v.mix(y0, y1, u)), ch, style)

    def protect(self, x, y, w, h):
        l, top, r, bottom = self.bounds
        right, end = min(r+1, x+w), min(bottom+1, y+h)
        x, y = max(l, x), max(top, y)
        if right > x and end > y:
            self.canvas.protect(x, y, right-x, end-y)


def _surface(c, box, inside, ink, dim, high):
    """A continuous silhouette, with sparse data hatching inside its surface."""
    l, top, r, bottom = box
    for y in range(math.floor(top), math.ceil(bottom)+1):
        for x in range(math.floor(l), math.ceil(r)+1):
            if not inside(x, y):
                continue
            edge = not all(inside(x+dx, y+dy) for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)))
            if edge:
                c.put(x, y, '#', ink)
            else:
                lit = x < v.mix(l, r, .38) and y < v.mix(top, bottom, .65)
                c.put(x, y, ':' if (x+y)%3 == 0 else '.', high if lit else dim)


def _ellipse(c, cx, cy, rx, ry, ink, dim, high):
    rx, ry = max(.5, rx), max(.5, ry)
    _surface(c, (cx-rx, cy-ry, cx+rx, cy+ry),
             lambda x, y: ((x-cx)/rx)**2+((y-cy)/ry)**2 <= 1,
             ink, dim, high)


def _polygon(c, points, ink, dim):
    l, top = min(x for x, _ in points), min(y for _, y in points)
    r, bottom = max(x for x, _ in points), max(y for _, y in points)
    for y in range(math.floor(top), math.ceil(bottom)+1):
        for x in range(math.floor(l), math.ceil(r)+1):
            inside = False
            for (ax, ay), (bx, by) in zip(points, points[1:]+points[:1]):
                if (ay > y) != (by > y) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
                    inside = not inside
            if inside:
                c.put(x, y, ':', dim)
    for a, b in zip(points, points[1:]+points[:1]):
        c.line(*a, *b, '#', ink)


def _eggplant(c, box, t, music):
    l, top, r, bottom = box
    w, h = r-l, bottom-top
    cx = (l+r)/2+math.sin(t*1.6)*min(1, w*.025)
    neck = top+h*.13
    radius = min(w*.43, h*.68)

    def inside(x, y):
        u = (y-neck)/(bottom-neck)
        if not 0 <= u <= 1:
            return False
        center = cx+(u-.45)*w*.15
        half = radius*(.35+.65*u)*math.sqrt(max(0, 1-(2*u-1)**2))
        return abs(x-center) <= half

    _surface(c, (l, neck, r, bottom), inside, v.VIOLET_HIGH, v.VIOLET, v.VIOLET_HIGH)
    cap = [(cx, neck-.7), (cx-radius*.7, neck+.4), (cx-radius*.3, neck+.4),
           (cx-radius*.25, neck+1.2), (cx, neck+.5), (cx+radius*.37, neck+1.2),
           (cx+radius*.26, neck), (cx+radius*.65, neck+.2)]
    _polygon(c, cap, v.GREEN_HIGH, v.GREEN)
    c.line(cx, neck, cx+1, top+1, '#', v.GREEN_HIGH)
    c.line(cx+1, top+1, cx+3, top, '#', v.GREEN)
    # A highlight follows measured low-band energy, without changing phase.
    c.put(round(cx-radius*.2), round(neck+(bottom-neck)*.42), ':',
          v.W if music.low > .55 else v.VIOLET_HIGH)
    port_y = round((top+bottom)/2)
    row = [x for x in range(l, r+1) if inside(x, port_y)]
    return (row[0]-1, port_y), (row[-1]+1, port_y)


def _tomato(c, box, t, music):
    l, top, r, bottom = box
    w, h = r-l, bottom-top
    ry = min(h*.40, w*v.CELL_ASPECT*.46)
    rx = ry/v.CELL_ASPECT
    cx = (l+r)/2+math.sin(t*1.7)*min(.8, w*.02)
    cy = bottom-ry
    _ellipse(c, cx, cy, rx, ry, v.TOMATO, v.TOMATO_DIM, v.TOMATO_HIGH)
    leaf_y = cy-ry+ry*.12
    points = []
    for i in range(10):
        a = -math.pi/2+i*math.tau/10
        length = 1 if i%2 == 0 else .28
        points.append((cx+math.cos(a)*rx*.65*length,
                       leaf_y+math.sin(a)*max(1.2, ry*.34)*length))
    _polygon(c, points, v.GREEN_HIGH, v.GREEN)
    c.line(cx, leaf_y, cx+1, cy-ry-max(1, h*.08), '#', v.GREEN_HIGH)
    c.put(round(cx-rx*.47), round(cy-ry*.30), '(' if music.low < .6 else ':', v.W)
    port_y = round((top+bottom)/2)
    half = rx*math.sqrt(max(0, 1-((port_y-cy)/ry)**2))
    return (math.ceil(cx-half)-1, port_y), (math.floor(cx+half)+1, port_y)


def _cat(c, box, t, music):
    l, top, r, bottom = box
    w, h = r-l, bottom-top
    breath = math.sin((t-81.351)*3+music.beat_position*.18)*(.22+music.low*.25)

    def p(x, y):
        return l+x*w, top+y*h

    # Tail behind the torso: a broad rising hook, with its own tabby bands.
    for i in range(81):
        u = i/80
        x, y = p(.59+.34*math.sin(u*math.pi*.78)+.018*math.sin(t*2)*u,
                 .91-.48*u)
        c.put(round(x), round(y), '##', v.G if int(u*9)%3 == 1 else v.N)
    _ellipse(c, *p(.42, .70), w*.28, h*.28+breath, v.N, v.D, v.N)
    for side in (-1, 1):
        for row in (.55, .67, .79):
            c.line(*p(.42+side*.25, row), *p(.42+side*.10, row+.055), '=', v.G)
    for x in (.28, .55):
        _ellipse(c, *p(x, .94), w*.15, max(.55, h*.045), v.N, v.D, v.N)
        c.put(round(l+x*w)-1, round(top+h*.96), '//', v.G)
    _polygon(c, [p(.13, .28), p(.17, .01), p(.37, .18)], v.N, v.D)
    _polygon(c, [p(.48, .18), p(.68, .01), p(.72, .28)], v.N, v.D)
    c.line(*p(.19, .10), *p(.23, .20), '/', v.ROSE_DIM)
    c.line(*p(.65, .10), *p(.61, .20), '\\', v.ROSE_DIM)
    _ellipse(c, *p(.425, .30), w*.29, h*.23, v.N, v.D, v.N)
    # Forehead M, cheek stripes, separated green almond eyes, white whiskers.
    for x, dx in ((.33, .035), (.425, -.025), (.51, -.035)):
        c.line(*p(x, .09), *p(x+dx, .20), '|', v.G)
    blink = 1.10 <= (t-81.351)%2.7 < 1.23
    eye_y = round(top+h*.29)
    eye_width = max(1, round(w*.045))
    for x in (.30, .55):
        ex = round(l+x*w)
        if blink:
            c.put(ex-eye_width, eye_y, '-'*(eye_width*2+1), v.NEUTRAL)
        else:
            c.put(ex-eye_width, eye_y, '('+'o'*(eye_width*2-1)+')', v.GREEN_HIGH)
            c.put(ex, eye_y, '|', v.W)
    nose_x, nose_y = round(l+w*.425), max(eye_y+1, round(top+h*.39))
    c.put(nose_x, nose_y, 'v', v.ROSE)
    c.put(nose_x-1, nose_y+1, 'w', v.W)
    for side in (-1, 1):
        for offset in (-1, 1):
            c.line(nose_x+side*w*.12, nose_y,
                   nose_x+side*w*.38, nose_y+offset, '-', v.W)
    c.protect(round(l+w*.12), eye_y, round(w*.63), max(2, nose_y-eye_y+2))
    return ((round(nose_x-w*.38)-1, nose_y),
            (round(nose_x+w*.38)+1, nose_y))


def _purr(c, start, end, t, music, amount):
    x0, y = start
    x1, _ = end
    phase = (t-82.833)*2+music.beat_position*.22
    amplitude = .6+music.low+music.beat*.6
    for x in range(round(x0), round(x1)+1):
        yy = y+2+math.sin((x-x0)*.65-phase*math.tau)*amplitude*amount
        c.put(x, round(yy), '~', v.ROSE)


def _resource_transfer(c, source, buffer, target, state, music, you_x, radius):
    """Six visible payload groups are extracted, stored, then absorbed by YOU."""
    l, top, r, bottom = c.bounds
    cy = source[1]
    receiving = state.phase == 'receive'
    progress = v.clamp(state.progress/.72) if receiving else state.progress
    # Every group has an explicit departure and arrival; seeking cannot credit it early.
    flight = .28
    departures = tuple(i*(1-flight)/5 for i in range(6))
    arrived = sum(progress >= departure+flight for departure in departures)
    received = arrived if receiving else 0
    stored = 6-received if receiving else arrived
    unit = 'N' if state.subject == 'eggplant' else 'A'
    token = '[N]' if unit == 'N' else '{A}'
    lane_gap = 1 if c.w < 100 or c.h < 34 else 2
    x0, x1 = (buffer[0]+4, target[0]) if receiving else (source[0], buffer[0])
    for offset in (-lane_gap-1, lane_gap+1):
        c.line(source[0], cy+offset, target[0], cy+offset, '=', v.GREEN)
    for lane in (-1, 0, 1):
        yy = cy+lane*lane_gap
        c.line(x0, yy, x1, yy, '.', v.GREEN)
        for departure in departures:
            u = (progress-departure)/flight
            if not 0 <= u < 1:
                continue
            xx = round(v.mix(x0, x1-2, u))
            c.put(xx, yy, token, v.GREEN_HIGH)
            if xx > x0:
                c.put(xx-1, yy, ':', v.W if music.beat > .65 else v.GREEN)
    # The label sits above the channel, and the store remains below the moving groups.
    label_x = max(l, min(r-len(state.resource)+1, source[0]+1))
    label_y = max(top+3, round(cy-radius-3))
    c.put(label_x, label_y, state.resource, v.GREEN_HIGH)
    c.protect(label_x, label_y, len(state.resource), 1)
    meter = ('SEND ' if receiving else 'STORE ')+f'{round(progress*100):03d}%'
    c.put(label_x, label_y+1, meter, v.W)
    c.protect(label_x, label_y+1, len(meter), 1)
    store_x = max(source[0], min(buffer[0]-2, target[0]-8))
    c.put(store_x, cy+lane_gap+2, '['+unit*stored+'.'*(6-stored)+']', v.GREEN_HIGH)
    if receiving:
        c.put(round(you_x)-3, round(cy+radius+2), f'RX +{received:02d}', v.GREEN_HIGH)
        if received:
            halo = min(radius+1.1+music.beat*.25, (r-you_x)*v.CELL_ASPECT)
            for i in range(48):
                angle=i*math.tau/48
                c.put(round(you_x+math.cos(angle)*halo/v.CELL_ASPECT),
                      round(cy+math.sin(angle)*halo), ':', v.GREEN_HIGH)
    return received


def draw_organic(c, t, area, music):
    """Render one audio sample; Canvas needs only w/h, put, line, protect."""
    state = organic_state(t)
    if state is None:
        return
    c = _Area(c, area)
    if c.w < 12 or c.h < 8:
        return
    l, top, r, bottom = c.bounds
    small = c.w < 100 or c.h < 34
    code_rows = 2 if small else 4
    object_top, object_bottom = top+code_rows+2, bottom-3
    if object_bottom-object_top < 4:
        return
    box = (l+round(c.w*.19), object_top, l+round(c.w*.63), object_bottom)
    radius = min(3, max(1, (object_bottom-object_top)/10))
    radius = max(2, radius) if c.w >= 48 else radius
    me_x, you_x = l+round(c.w*.085), l+round(c.w*.90)
    buffer_x = l+round(c.w*.75)
    resource_ink = v.ROSE if state.subject == 'cat' else v.GREEN_HIGH
    v.backdrop(c, t, (l, object_top, r, object_bottom), density=.3)
    if state.subject == 'eggplant':
        call_port, source = _eggplant(c, box, t, music)
        constructor, method = 'Eggplant', 'nutrients'
    elif state.subject == 'tomato':
        call_port, source = _tomato(c, box, t, music)
        constructor, method = 'Tomato', 'antioxidants'
    else:
        call_port, source = _cat(c, box, t, music)
        constructor, method = 'TabbyCat', 'purr'

    cy = source[1]
    buffer = (buffer_x-2, cy)
    target = (round(you_x-radius/v.CELL_ASPECT)-1, cy)

    phase = ('cast', 'extract', 'receive').index(state.phase)
    received = 0
    if phase == 0:
        v.signal(c, (round(me_x+radius/v.CELL_ASPECT)+1, cy),
                 call_port, min(.999, state.progress), ink=v.ME, trail=2)
        status = 'CAST / me : '+constructor
    else:
        if state.subject == 'cat':
            _purr(c, source, buffer, t, music, .5+.5*state.progress if phase == 1 else 1)
        else:
            received = _resource_transfer(c, source, buffer, target, state, music, you_x, radius)
        v.signal(c, source, buffer, min(.999, state.progress), ink=resource_ink,
                 trail=2, amount=1 if phase == 1 else 0, track=state.subject == 'cat')
        if state.subject == 'cat':
            c.put(buffer_x-1, cy-1, '[r]', resource_ink)
            c.put(buffer_x-1, cy+1, 'OUT', v.NEUTRAL)
        if phase == 1:
            status = ('PURR' if state.subject == 'cat' else 'EXTRACT')+' / '+state.resource
        else:
            travel = min(.999, state.progress/.72)
            v.signal(c, (buffer_x+2, cy), target, travel, ink=resource_ink,
                     trail=2, track=state.subject == 'cat')
            status = state.resource+' -> YOU / '+('RX OK' if state.progress >= .72 else 'RECEIVING')

    # Packets precede protected actor labels, so transport cannot erase identity.
    v.actor(c, me_x, cy, 'ME', radius=radius)
    v.actor(c, you_x, cy, 'YOU', radius=radius)
    if received:
        for yy in range(math.ceil(cy-radius), math.floor(cy+radius)+1):
            if yy == round(cy):
                continue
            dy = (yy-cy)/radius
            for xx in range(math.ceil(you_x-radius/v.CELL_ASPECT), math.floor(you_x+radius/v.CELL_ASPECT)+1):
                dx = (xx-you_x)*v.CELL_ASPECT/radius
                if dx*dx+dy*dy < .55 and dy >= 1-2*received/6:
                    c.put(xx, yy, '+', v.GREEN_HIGH)
    lines = ('me.cast('+constructor+');', 'r = me.'+method+'();', 'you.receive(r);')
    v.code_card(c, (l+1, top, r-1, top+code_rows-1), lines, active=phase)
    c.put(l+1, bottom, status, resource_ink if phase else v.ME)
    c.protect(l+1, bottom, min(len(status), c.w-2), 1)
