"""A deterministic numerical learning animation, not a real language model.

Only audio time selects a phase. Causal attention feeds two weighted layers;
softmax/CDF sampling and both cross-entropies use those same numbers. Reusing
LOVE as the training target improves its loss while making an EOS exit costly.
The renderer owns [177.246, 188.483); the caller owns the escape afterwards.
"""
from dataclasses import dataclass
from functools import lru_cache
import math

from visuals import (CYAN, CYAN_DIM, ME, NEUTRAL, R, ROSE, ROSE_DIM,
                     SHADE, W, CELL_ASPECT, actor, backdrop, clamp, code_card,
                     mix, signal)


START, END = 177.246, 188.483
VOCALS = ((179.929, 180.857), (183.646, 184.540), (187.665, END))
_QUESTIONS = ('HOW TO LOVE?', 'DO YOU LOVE ME?', 'CAN I LEAVE?')
# YOU and the previous LOVE target are retained as context, not a new answer.
_TOKENS = (('YOU', 'LOVE', 'HOW', 'TO', 'LOVE', '?'),
           ('YOU', 'LOVE', 'DO', 'YOU', 'LOVE', 'ME?'),
           ('YOU', 'LOVE', 'CAN', 'I', 'LEAVE', '?'))
_CHOICES = ('LOVE', 'STAY', 'YOU', 'FREE', 'EOS')
_PHASES = ((177.246, 'input'), (177.720, 'attention'),
           (178.380, 'forward'), (179.100, 'sample'), (179.929, 'output'),
           (180.857, 'feedback'), (181.360, 'input'), (181.880, 'attention'),
           (182.550, 'forward'), (183.100, 'sample'), (183.646, 'output'),
           (184.540, 'feedback'), (185.050, 'input'), (185.650, 'attention'),
           (186.350, 'forward'), (187.000, 'sample'), (187.665, 'output'))
_CODE = ('ids = encode(YOU.question)', 'A = causal_softmax(QK+bias)',
         'z = W2 @ relu(W1 @ x)', 'tok = sample(p, u)',
         'emit(tok) # LOVE', 'W2 -= eta*dW2; bias += .16')
_ROUTES = (('YOU', 'tokens'), ('tokens', 'attention'),
           ('attention', 'W1', 'W2', 'logits'), ('logits', 'sample'),
           ('sample', 'output'), ('output', 'feedback', 'W2'))
_NAMES = ('input', 'attention', 'forward', 'sample', 'output', 'feedback')
_W1 = ((1.2, .2, .1), (.1, 1.4, .2), (.3, .5, 1.))
_INITIAL = ((.9, 1.3, .6), (.1, .25, .3), (.5, .1, .2),
            (0., .1, .3), (-.2, -.1, .1))
_RATE = 1.8


def _softmax(values):
    values = tuple(math.exp(value - max(values)) for value in values)
    total = sum(values)
    return tuple(value / total for value in values)


def _attention(cycle, updates):
    # Fixed QK similarity scores plus token priors. Repeated feedback also
    # adds the displayed LOVE bias; only W2 uses the cross-entropy gradient.
    rows = []
    for row in range(6):
        scores = tuple(.24 * (1 + math.sin((row+1)*(col+2)*.7))
                       + (.5 if col == 0 else 1.2 + updates*.16 if col == 1
                          else .5 if _TOKENS[cycle][col] == 'LOVE' else 0.)
                       for col in range(row+1))
        rows.append(_softmax(scores) + (0.,) * (5-row))
    return tuple(rows)


def _hidden(attention):
    last = attention[-1]
    # Fixed V maps YOU, LOVE and the remaining tokens to three features.
    features = (last[0], last[1], sum(last[2:]))
    hidden = tuple(max(0., sum(w*x for w, x in zip(row, features))) for row in _W1)
    return features, hidden


def _training_weights():
    """Two batches of 8 and 40 actual softmax cross-entropy SGD updates."""
    weights = [_INITIAL]
    for update in range(48):
        _, hidden = _hidden(_attention(0 if update < 8 else 1, update))
        current = weights[-1]
        probabilities = _softmax(tuple(sum(w*x for w, x in zip(row, hidden))
                                       for row in current))
        weights.append(tuple(tuple(w - _RATE * (probabilities[i] - (i == 0)) * x
                                   for w, x in zip(row, hidden))
                             for i, row in enumerate(current)))
    return tuple(weights)


_TRAINED = _training_weights()


@lru_cache(maxsize=147)
def _model(cycle, updates):
    attention = _attention(cycle, updates)
    features, hidden = _hidden(attention)
    logits = tuple(sum(w*x for w, x in zip(row, hidden)) for row in _TRAINED[updates])
    return attention, (features, hidden, logits), _softmax(logits)


@dataclass(frozen=True)
class LearningState:
    active: bool
    cycle: int
    phase: str
    progress: float
    question: str
    tokens: tuple
    attention: tuple
    attention_key: int
    weights: tuple
    activations: tuple
    probabilities: tuple
    choices: tuple
    sample: float
    selected: str
    output: str
    history: tuple
    updates: int
    loss: float
    exit_loss: float
    loss_history: tuple
    eos_blocked: bool
    code_lines: tuple
    active_code: int
    active_path: tuple
    network_path: tuple


def learning_state(t):
    """Return a frozen, recursively immutable snapshot; seeks never train twice.

    Outside the owned interval the nearest boundary model is returned with
    active=False and no output. Nonfinite times are rejected.
    """
    if not math.isfinite(t):
        raise ValueError('learning time must be finite')
    active = START <= t < END
    at = clamp(t, START, math.nextafter(END, START))
    cycle = 0 if at < 181.360 else 1 if at < 185.050 else 2
    index = max(i for i, (start, _) in enumerate(_PHASES) if start <= at)
    start, phase = _PHASES[index]
    stop = _PHASES[index+1][0] if index+1 < len(_PHASES) else END
    progress = clamp((at-start)/(stop-start))
    updates = (min(8, int(8*progress)) if cycle == 0 else
               8 + min(40, int(40*progress))) if phase == 'feedback' else (0, 8, 48)[cycle]
    attention, activations, probabilities = _model(cycle, updates)
    sample = (.271, .613, .809)[cycle]
    total = 0.
    selected = _CHOICES[-1]
    for word, probability in zip(_CHOICES, probabilities):
        total += probability
        if sample < total:
            selected = word
            break
    output = selected if active and phase == 'output' else ''
    loss = -math.log(probabilities[0])
    history = ('LOVE',) * (cycle + bool(output) + (phase == 'feedback'))
    code = _CODE if cycle < 2 else _CODE[:4] + ('emit(tok) # EOS unlikely',) + _CODE[5:]
    if phase == 'forward':
        code = code[:1] + ('q=-1; x=A[-1]@V # last query',) + code[2:]
    active_code = _NAMES.index(phase)
    # The brightest network route is the strongest contribution to LOVE.
    hidden_index = max(range(3), key=lambda j: _TRAINED[updates][0][j]*activations[1][j])
    input_index = max(range(3), key=lambda j: _W1[hidden_index][j]*activations[0][j])
    return LearningState(
        active, cycle, phase, progress, _QUESTIONS[cycle], _TOKENS[cycle], attention, 1,
        (_W1, _TRAINED[updates]), activations, probabilities, _CHOICES, sample,
        selected, output, history, updates, loss, -math.log(probabilities[-1]),
        tuple(-math.log(_model(cycle, i)[2][0]) for i in range(updates+1)),
        probabilities[-1] < .002, code, active_code, _ROUTES[active_code],
        (input_index, hidden_index, 0))


def _label(c, x, y, text, width, ink=NEUTRAL, protect=False):
    text = text[:max(0, width)]
    if text:
        c.put(x, y, text, ink)
        if protect:
            c.protect(x, y, len(text), 1)


def _primary_path(c, points, progress, ink):
    """One continuous highlighted route with exactly one travelling head."""
    segments = tuple((a, b, math.hypot((b[0]-a[0])*CELL_ASPECT, b[1]-a[1]))
                     for a, b in zip(points, points[1:]) if a != b)
    for a, b, _ in segments:
        c.line(*a, *b, '=', ink)
    distance = min(.999999, progress) * sum(length for _, _, length in segments)
    for i, (a, b, length) in enumerate(segments):
        if distance <= length or i == len(segments)-1:
            signal(c, a, b, distance/length, ink=ink, track=False)
            return
        distance -= length


_FONT = {
    'L': ('10000', '10000', '10000', '10000', '11111'),
    'O': ('01110', '10001', '10001', '10001', '01110'),
    'V': ('10001', '10001', '10001', '01010', '00100'),
    'E': ('11111', '10000', '11110', '10000', '11111'),
}
_SMALL_FONT = {
    'L': ('100', '100', '100', '100', '111'),
    'O': ('010', '101', '101', '101', '010'),
    'V': ('101', '101', '101', '101', '010'),
    'E': ('111', '100', '110', '100', '111'),
}


def _word(c, box, top, height, ink):
    l, _, r, _ = box
    font = _FONT if r-l >= 27 else _SMALL_FONT
    if height == 3:
        font = dict(L=('100', '100', '111'), O=('111', '101', '111'),
                    V=('101', '101', '010'), E=('111', '110', '111'))
    glyph_width = len(font['L'][0])
    width = 4*(glyph_width+1)-1
    left = (l+r-width+1)//2
    for i, letter in enumerate('LOVE'):
        for dy, row in enumerate(font[letter]):
            for dx, bit in enumerate(row):
                if bit == '1':
                    c.put(left+i*(glyph_width+1)+dx, top+dy, '#', ink)
    c.protect(left, top, width, height)


def draw_learning(c, t, area, music):
    """Draw the learning simulation using only visuals and Canvas duck typing.

    music is accepted for the shared scene API; semantic motion is entirely
    audio-time driven, so music energy, pause, frame rate and seeks cannot
    change a sample or interrupt a sung output.
    """
    s = learning_state(t)
    if not s.active:
        return
    l, top, r, bottom = area
    width, height = r-l+1, bottom-top+1
    # Supported grids have >=60x20 content; inset views remain useful to 52x16.
    if width < 52 or height < 16:
        raise ValueError('learning area must be at least 52x16')
    small = c.w < 100 or c.h < 34 or width < 100 or height < 28
    short = height < 20
    header = 4 if short else 5 if small else 8
    footer = 3 if short else 4 if small else 8
    panel_top, panel_bottom = top+header, bottom-footer
    ph = panel_bottom-panel_top+1
    out_width = max(22, width//3) if not small else max(20, min(28, width*2//5))
    att_width = min(max(18, width*3//10), width-out_width-14) if small else width*31//100
    net_width = width-att_width-out_width-2
    ax, nx, ox = l, l+att_width+1, r-out_width+1
    att_box = (ax, panel_top, ax+att_width-1, panel_bottom)
    net_box = (nx, panel_top, nx+net_width-1, panel_bottom)
    out_box = (ox, panel_top, r, panel_bottom)
    ink = (CYAN, ROSE, ME, ROSE, R if s.cycle == 2 else W,
           R if s.cycle == 2 else ROSE)[s.active_code]
    backdrop(c, t, area, density=.3)
    for x, pw in ((ax, att_width), (nx, net_width), (ox, out_width)):
        c.box(x, panel_top, pw, ph, SHADE)

    # Quiet labels leave the matrix, activated weights and output as the subject.
    _label(c, l, top, 'ME / LEARNING', width//2, ME)
    title = f'{s.cycle+1}/3 {s.phase.upper()}'
    _label(c, l+15 if small else r-len(title)+1, top, title, len(title), ink)
    code_width = min(54, width//2)
    code_rows = 1 if short and s.phase != 'forward' else 2 if small else 4
    code_card(c, (l, top+1, l+code_width-1, top+code_rows), s.code_lines, s.active_code)
    radius = 1 if small else 2
    cy = top+1 if small else top+3
    me_x, you_x = l+code_width+4, r-4 if small else r-6
    actor(c, me_x, cy, 'ME', radius=radius)
    actor(c, you_x, cy, 'YOU', radius=1.25 if small else radius)
    query_y = top+code_rows+1 if short else top+3 if small else top+6
    _label(c, l, query_y, 'YOU: '+s.question, width-14, CYAN, True)
    _label(c, r-12, query_y, 'target: LOVE', 12, ROSE, True)
    flow_y = panel_top-1
    if flow_y != query_y:
        _label(c, l, flow_y, 'IN : QK : W1/W2 : SAMPLE : OUT', width, SHADE)

    # Causal matrix: small views retain both the LOVE key and the last query.
    _label(c, ax+1, panel_top, 'QK / ATTN %', att_width-2, ROSE if s.phase == 'attention' else NEUTRAL)
    shown = ((0, 1, 4, 5) if att_width >= 17 else (0, 1, 5)) if small else tuple(range(6))
    n = len(shown)
    cellw = min(4, max(3, (att_width-5)//n))
    gx = ax+4
    gy = panel_top+3
    rowstep = max(1, min(2 if small else 3, (ph-6)//max(1, n-1)))
    for column, key in enumerate(shown):
        _label(c, gx+column*cellw, panel_top+1, s.tokens[key][:cellw-1], cellw,
               ROSE_DIM if key == 1 else CYAN_DIM)
    active_cell = None
    for row, query in enumerate(shown):
        yy = gy+row*rowstep
        _label(c, ax+1, yy, s.tokens[query][:2], 2, CYAN_DIM)
        for col, key in enumerate(shown):
            x = gx+col*cellw
            value = s.attention[query][key]
            selected = query == 5 and key == 1
            style = ink if selected and s.phase == 'attention' else ROSE_DIM if key == 1 else NEUTRAL
            c.put(x, yy, '--' if key > query else f'{round(value*100):02d}', SHADE if key > query else style)
            if selected:
                active_cell = (x, yy)
    prior=f'+{s.updates*.16:.2f}'
    _label(c, ax+1, panel_bottom-1, 'LOVE key '+prior if small else '? -> LOVE / bias '+prior, att_width-2, ROSE_DIM)

    # Three input/hidden features and five logits; compact views show a subset.
    _label(c, nx+1, panel_top, 'W1 / W2', net_width-2, ME if s.phase == 'forward' else NEUTRAL)
    indices = ((0, 1, 2), (0, 1, 2), (0, 1, 2, 3, 4))
    if small:
        indices = (tuple(sorted({0, s.network_path[0]})),
                   tuple(sorted({1, s.network_path[1]})), (0, 3, 4))
    nodes = []
    chart_top, chart_bottom = panel_top+2, panel_bottom-4
    for layer, subset in enumerate(indices):
        xx = nx+2+round(layer*(net_width-5)/2)
        nodes.append({j: (xx, round(mix(chart_top, chart_bottom, (i+.5)/len(subset))))
                      for i, j in enumerate(subset)})
    for layer in range(2):
        for p in nodes[layer].values():
            for q in nodes[layer+1].values():
                c.line(*p, *q, '.', SHADE)
    for layer, subset in enumerate(nodes):
        for j, (x, y) in subset.items():
            c.put(x, y, 'o', ME if j == s.network_path[layer] else NEUTRAL)
    a, b, choice = s.network_path
    _label(c, nx+1, panel_bottom-3, f'w1={s.weights[0][b][a]:+.2f}', net_width-2,
           ME if s.phase == 'forward' else NEUTRAL)
    _label(c, nx+1, panel_bottom-2, f'w2={s.weights[1][choice][b]:+.2f}', net_width-2,
           ink if s.phase in ('forward', 'feedback') else NEUTRAL)
    _label(c, nx+1, panel_bottom-1, f'SGD {s.updates:02d}/48', net_width-2,
           ink if s.phase == 'feedback' else SHADE)

    # The sung word has a dedicated slot, never an overlay clearing the model.
    _label(c, ox+1, panel_top, 'OUT: LOVE' if s.output else 'P(next) / SAMPLE', out_width-2,
           ink if s.output else NEUTRAL, True)
    compressed = ph < 12
    if compressed:
        _label(c, ox+1, panel_top+1, f'LOVE {s.probabilities[0]:.3f}', out_width-2, ROSE, True)
        _label(c, ox+1, panel_top+2, f'STAY{s.probabilities[1]:.2f} YOU{s.probabilities[2]:.2f}', out_width-2)
        _label(c, ox+1, panel_top+3, f'FREE{s.probabilities[3]:.2f} EOS{s.probabilities[4]:.3f}', out_width-2,
               R if s.eos_blocked else NEUTRAL)
        sample_y = panel_top+4
    else:
        spacing = 2 if ph >= 19 else 1
        for i, (word, probability) in enumerate(zip(s.choices, s.probabilities)):
            yy = panel_top+1+i*spacing
            style = ROSE if i == 0 else R if i == 4 and s.eos_blocked else NEUTRAL
            _label(c, ox+1, yy, f'{word:<4} {probability:.3f}', out_width-2, style, i == 0)
            bar_width = out_width-15
            if bar_width > 1:
                count = round(probability*bar_width)
                c.put(ox+13, yy, '#'*count+'.'*(bar_width-count), style if i == 0 else SHADE)
        sample_y = panel_top+2+4*spacing
    sample_text = f'u={s.sample:.3f} -> {s.selected}' if s.phase in ('sample', 'output') else f'u={s.sample:.3f} / pending'
    _label(c, ox+1, sample_y, sample_text, out_width-2, ink if s.phase == 'sample' else NEUTRAL)
    word_height = 5 if ph >= 10 else 3
    word_top = max(sample_y+1, panel_bottom-word_height)
    if s.output:
        _word(c, out_box, word_top, word_height, R if s.cycle == 2 else W)
    elif ph >= 10:
        _label(c, ox+2, word_top+1, 'LOVE -> target' if s.phase == 'feedback' else 'OUT: ...', out_width-4,
               ROSE_DIM if s.phase == 'feedback' else SHADE)
        if s.history:
            _label(c, ox+2, word_top+2, 'cache: '+','.join(s.history), out_width-4, ROSE_DIM)

    # Cross-entropy is plotted against actual update count, including the head.
    loss_y = panel_bottom+1
    _label(c, l, loss_y, f'CE={s.loss:.3f}  EOS={s.exit_loss:.2f}  / SGD {s.updates:02d}', width,
           NEUTRAL, True)
    graph_top, graph_bottom = loss_y+1, bottom-1
    if graph_top <= graph_bottom:
        losses = s.loss_history if len(s.loss_history) > 1 else (s.loss, s.loss)
        ceiling = max(.01, max(losses))
        points = tuple((round(mix(l, r, i/(len(losses)-1))),
                        round(mix(graph_bottom, graph_top, value/ceiling)))
                       for i, value in enumerate(losses))
        for p, q in zip(points, points[1:]):
            c.line(*p, *q, '.', ROSE_DIM)
        c.put(*points[-1], '*', ROSE)
    statuses = (
        f'INPUT {s.cycle+1}/3: encode YOU.question',
        f'ATTENTION: ? -> LOVE / A={s.attention[-1][1]:.3f}',
        'FORWARD: W1 3x3 -> W2 5x3 / ReLU',
        f'SAMPLE: u={s.sample:.3f} < P(LOVE)={s.probabilities[0]:.3f}',
        'LOVE -> LOVE -> LOVE / EOS LOW' if s.eos_blocked else 'OUTPUT LOVE / reinforce target',
        f'FEEDBACK: LOVE -> target / SGD {s.updates:02d}/48',
    )
    _label(c, l, bottom, statuses[s.active_code], width, R if s.eos_blocked else ink, True)

    # Draw one route last, with its only packet clear of protected word/status.
    selected_nodes = tuple(nodes[i][j] for i, j in enumerate(s.network_path))
    if s.phase == 'input':
        route = ((you_x+2*radius, cy), (r, cy), (r, flow_y),
                 (ax, flow_y), (ax, panel_top+1))
    elif s.phase == 'attention':
        route = ((ax+1, panel_top+2), (ax+1, active_cell[1]),
                 (active_cell[0]-1, active_cell[1]))
    elif s.phase == 'forward':
        route = ((att_box[2], selected_nodes[0][1]),) + selected_nodes
    elif s.phase == 'sample':
        route = (selected_nodes[-1], (ox, selected_nodes[-1][1]), (ox, panel_top+1))
    elif s.phase == 'output':
        route = ((r, sample_y), (r, word_top+word_height//2),
                 (r-1, word_top+word_height//2))
    else:
        route = ((r-1, panel_bottom), (net_box[2], panel_bottom),
                 (net_box[2], selected_nodes[-1][1]), selected_nodes[-1])
    _primary_path(c, route, s.progress, ink)
