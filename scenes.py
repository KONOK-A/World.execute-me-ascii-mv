"""Lyric-driven choreography with escalating glitch effects. No sidebars."""
import math
import visuals as v

TAU=math.tau
CELL_ASPECT=v.CELL_ASPECT  # Terminal cell width / height.
D,N,B,W,R,G,K,Y=0,1,2,3,4,5,6,3  # Y=Yellow (use white=3 as bright yellow)
RD=7

def mix(a,b,u):return a+(b-a)*u
def clamp(x,a=0,b=1):return min(b,max(a,x))
def hash16(i):
    v=(i+0x9E3779B9)&0xFFFFFFFF
    v=((v^(v>>16))*0x7FEB352D)&0xFFFFFFFF
    v=((v^(v>>15))*0x846CA68B)&0xFFFFFFFF
    return (v^(v>>16))&65535

def clear(c,x,y,w,h):
    for yy in range(int(y),int(y+h)):c.put(x,yy,' '*max(0,int(w)),K)

def glitch_intensity(t):
    """Each departure accumulates damage; later execution never resets it."""
    if t<60:return 0.05
    if t<110:return mix(0.05,0.25,(t-60)/50)
    if t<110.9:return mix(0.25,0.6,(t-110)/37)
    anchors=((110.9,.259),(112.22,.34),(113.1,.43),(114.18,.51),
             (114.92,.59),(115.78,.66),(117.274,.73),(125.708,.81),
             (147.66,.92),(177.246,1.0))
    for (a,low),(b,high) in zip(anchors,anchors[1:]):
        if t<b:return mix(low,high,clamp((t-a)/(b-a)))
    return 1.0

def apply_glitch(c,t,top,bt,music,intensity=None):
    """Persistent scars carry the story; short audio transients carry the noise."""
    damage=glitch_intensity(t) if intensity is None else intensity
    burst=max(music.accent,music.onset*.65,music.beat*.18)
    tick=int(t*12)
    if t>=110.9:
        for band in range(1+int(damage*3)):
            row=top+hash16(band*71+int(damage*8))%max(1,bt-top+1)
            x=2+hash16(band*131)%max(1,c.w-12)
            c.put(x,row,'_..' if damage<.75 else '..//_',G)
    if burst<.12:return
    # Short, local row echoes. Repaint through Canvas.put to preserve wide cells.
    for i in range(int(damage*burst*3)):
        row=top+hash16(tick+i*37)%max(1,bt-top+1)
        shift=round(math.sin(tick+i)*3*burst)
        if shift:
            source=c.cells[row][:]
            c.put(0,row,' '*c.w,D)
            for x,(ch,style) in enumerate(source):
                if ch and ch!=' ':c.put(x+shift,row,ch,style)
    for i in range(int((2+damage*18)*burst*music.high)):
        x=2+hash16(tick+i*31)%max(1,c.w-4)
        y=top+hash16(tick+i*53)%max(1,bt-top+1)
        c.put(x,y,'+' if burst>.55 else '.',R if damage>.85 and music.accent>.65 else B)
    if burst>.55 and damage>.3:
        row=top+hash16(tick*17)%max(1,bt-top+1)
        start=2+hash16(tick)%max(1,c.w-18)
        c.put(start,row,'=:/:'[:2+int(burst*2)],N)


def simple_area(c,top,bt):
    """Return full-width area without sidebars"""
    return (2,top,c.w-3,bt)

# ============ ROTATION & 3D ============
def fit_scale(area,width=2,height=2):
    """Columns per model unit, fitted on both axes with one physical scale."""
    l,top,r,bt=area
    return min((r-l)/width,(bt-top)/(height*CELL_ASPECT))

# An authored heart is slightly wider than it is tall; it is not a circle.
HEART_WIDTH,HEART_HEIGHT=2.44,2.

def _heart_profile():
    """Scan-convert the classic parametric contour once, using only math."""
    right=[]
    for i in range(257):
        a=i*math.pi/256
        right.append((16*math.sin(a)**3,
                      -(13*math.cos(a)-5*math.cos(2*a)-2*math.cos(3*a)-math.cos(4*a))))
    low=min(y for _,y in right);high=max(y for _,y in right)
    right=[(x/16*HEART_WIDTH/2,(y-low)/(high-low)) for x,y in right]
    points=right+[(-x,y) for x,y in reversed(right[1:-1])]
    rows=[[] for _ in range(1024)]
    for (x0,y0),(x1,y1) in zip(points,points[1:]+points[:1]):
        if y0==y1:continue
        first=max(0,math.ceil(min(y0,y1)*len(rows)-.5))
        last=min(len(rows),math.ceil(max(y0,y1)*len(rows)-.5))
        for row in range(first,last):
            y=(row+.5)/len(rows)
            rows[row].append(x0+(x1-x0)*(y-y0)/(y1-y0))
    return tuple(tuple(sorted(row)) for row in rows)

_HEART_PROFILE=_heart_profile()

def heart_contains(x,y):
    """Test the shared silhouette in model coordinates (up is positive y)."""
    if not -1<y<=1:return False
    row=min(len(_HEART_PROFILE)-1,int((1-y)*.5*len(_HEART_PROFILE)))
    spans=_HEART_PROFILE[row]
    return bool(spans) and (spans[0]<=x<=spans[1] or
                           len(spans)==4 and spans[2]<=x<=spans[3])

def heart_edge(x,y,dx,dy):
    return not (heart_contains(x-dx,y) and heart_contains(x+dx,y) and
                heart_contains(x,y-dy) and heart_contains(x,y+dy))

def rot(x,y,z,t):
    a,b=t*.37,t*.23
    x,z=x*math.cos(a)+z*math.sin(a),z*math.cos(a)-x*math.sin(a)
    y,z=y*math.cos(b)-z*math.sin(b),y*math.sin(b)+z*math.cos(b)
    return x,y,z

def point(x,y,z,area,t=0,rotate=True):
    if rotate:x,y,z=rot(x,y,z,t)
    l,top,r,bt=area
    p=3.7/(3.7+z)
    scale=fit_scale(area)*.68
    return (l+r)/2+x*scale*p,(top+bt)/2+y*scale*CELL_ASPECT*p,z

def projected(c,vertices,edges,area,t,style=N,reveal=1):
    ps=[point(*v,area,t) for v in vertices]
    count=int(len(edges)*clamp(reveal))
    for i,(a,b) in enumerate(edges[:count]):
        x,y,z=ps[a];xx,yy,zz=ps[b]
        c.line(x,y,xx,yy,':' if (z+zz)<0 else '.',style if (z+zz)<0 else G)
    for i,(x,y,z) in enumerate(ps):
        if i<len(vertices)*reveal:c.put(x,y,'+' if z>0 else '@',N if z>0 else B)

# ============ LYRIC-DRIVEN SCENES ============

def lyric_power_line(c,t,area,music):
    """A small, ordered boot ritual advances on the reviewed opening transients."""
    l,top,r,bt=area;cx,cy=(l+r)//2,(top+bt)//2
    events=music.events('boot')
    if len(events)!=5:raise ValueError('The score requires five boot events')
    done=sum(e.time<=t for e in events)
    c.center(top,'POWER ON / SELF INITIALIZATION',B)
    panel_w=min(72,r-l-4);x=cx-panel_w//2;y=top+3
    c.box(x,y,panel_w,min(10,bt-y),G)
    for i,event in enumerate(events):
        age=t-event.time
        ink=W if 0<=age<.16 else B if age>=0 else G
        label=f'{i+1:02d} {event.label:<15} '+('[ OK ]' if age>=0 else '[ .. ]')
        c.put(x+3,y+1+i,label[:panel_w-5],ink)
        if 0<=age<.22:c.put(x+panel_w-4,y+1+i,'<',W)
    line_y=min(bt-2,y+8)
    span=max(1,panel_w-6)
    c.put(x+3,line_y,('>'*int(span*done/5)).ljust(span,'.'),B)
    if done==5:
        c.center(bt,'SYSTEM READY / ENTITY LOADING',W)
    else:
        c.center(bt,f'CHECK {done:02d}/05 / SIGNAL {int(music.mid*100):03d}%',N)
    c.protect(x,y,panel_w,min(10,bt-y))

def lyric_protection(c,t,area,elapsed):
    """Protection - shield forming"""
    l,top,r,bt=area;cx,cy=(l+r)//2,(top+bt)//2
    progress=clamp(elapsed/0.95)
    # Expanding shield circles
    for ring in range(5):
        radius=(20+ring*8)*progress
        for i in range(int(radius*2)):
            angle=i*TAU/(radius*2)
            x=cx+math.cos(angle)*radius
            y=cy+math.sin(angle)*radius*0.5
            if l<x<r and top<y<bt:
                c.put(x,y,'#' if ring==0 else '+' if ring<3 else '.',
                      W if ring==0 else B if ring<3 else N)
    c.center(cy,'PROTECTION',W if progress>0.7 else B)
    if progress>0.5:
        c.center(cy+2,'[ ACTIVE ]',B)

def lyric_lay_pieces(c,t,area,elapsed):
    """Lay down your pieces - components assembling"""
    l,top,r,bt=area;cx,cy=(l+r)//2,(top+bt)//2
    # Pieces flying in from edges and assembling
    pieces=8
    for i in range(pieces):
        phase=(elapsed-i*0.15)/1.2
        if phase<0:continue
        u=clamp(phase);ease=1-(1-u)**3  # ease out cubic
        angle=i*TAU/pieces
        # Start from edge
        start_r=max(r-l,bt-top)*0.8
        end_r=15
        radius=mix(start_r,end_r,ease)
        x=cx+math.cos(angle)*radius
        y=cy+math.sin(angle)*radius*0.5
        # Draw piece
        chars=['[]','{}','<>','//','\\\\','||','==','##']
        c.put(x,y,chars[i%len(chars)],W if ease>0.9 else B if ease>0.6 else N)
        # Trail
        if ease<0.8:
            for trail in range(3):
                tr=mix(start_r,end_r,max(0,ease-trail*0.1))
                tx=cx+math.cos(angle)*tr
                ty=cy+math.sin(angle)*tr*0.5
                c.put(tx,ty,'.',G)

def lyric_object_creation(c,t,area,elapsed):
    """Object creation - cube materializing"""
    l,top,r,bt=area
    vs=[(x,y,z) for z in (-.75,.75) for y in (-.8,.8) for x in (-.8,.8)]
    edges=[(i,j) for i in range(8) for j in range(i+1,8) if bin(i^j).count('1')==1]
    reveal=clamp(elapsed/1.0)
    projected(c,vs,edges,area,t,N,reveal)
    cx,cy=(l+r)//2,(top+bt)//2
    if reveal>0.5:
        c.center(cy,'ENTITY: ME',W)

def lyric_data_parameters(c,t,area,elapsed):
    """Fill in my data parameters - hex data filling"""
    l,top,r,bt=area
    progress=clamp(elapsed/2.6)
    cols=max(1,(r-l-10)//5);rows=max(1,bt-top-2);n=int(progress*cols*rows)
    for row in range(rows):
        c.put(l+2,top+1+row,f'{row*cols*2:04X}:',D)
        for col in range(cols):
            i=row*cols+col
            xx=l+9+col*5;yy=top+1+row
            if i<n:
                scan=(int(elapsed*17)%cols)==col
                c.put(xx,yy,f'{hash16(i):04X}',W if scan else B if abs(i-n)<cols else N)
            else:
                c.put(xx,yy,'....',G)

LIFE_CACHE={}

def life_state(cols,rows,generation):
    """Conway's Game of Life state computation"""
    key=(cols,rows)
    if key not in LIFE_CACHE:
        # Initial random state
        LIFE_CACHE[key]=[{(x,y) for y in range(rows) for x in range(cols) if hash16(x*71+y*199)%100<29}]
    states=LIFE_CACHE[key]
    while len(states)<=generation:
        counts={}
        for x,y in states[-1]:
            for dx,dy in [(-1,-1),(0,-1),(1,-1),(-1,0),(1,0),(-1,1),(0,1),(1,1)]:
                p=((x+dx)%cols,(y+dy)%rows)
                counts[p]=counts.get(p,0)+1
        states.append({p for p,n in counts.items() if n==3 or (n==2 and p in states[-1])})
    return states[generation]

def lyric_simulation(c,t,area,elapsed):
    """SIMULATION - code block with condition, then yielding binary data streams"""
    l,top,r,bt=area;cx,cy=(l+r)//2,(top+bt)//2  # Use // for integer division
    progress=clamp(elapsed/4.9)  # ~5 seconds total

    # Phase 1: Show code block with condition (0-2s)
    if elapsed<2:
        phase1=elapsed/2.0

        # Code box frame
        box_width=min(r-l-10, 70)
        box_height=min(bt-top-8, 12)
        box_left=cx-box_width//2
        box_top=cy-box_height//2

        # Draw box border
        if phase1>0.1:
            # Top border
            c.put(box_left, box_top, '┌', Y)
            for i in range(1, box_width-1):
                c.put(box_left+i, box_top, '─', Y)
            c.put(box_left+box_width-1, box_top, '┐', Y)

            # Bottom border
            c.put(box_left, box_top+box_height-1, '└', Y)
            for i in range(1, box_width-1):
                c.put(box_left+i, box_top+box_height-1, '─', Y)
            c.put(box_left+box_width-1, box_top+box_height-1, '┘', Y)

            # Side borders
            for i in range(1, box_height-1):
                c.put(box_left, box_top+i, '│', Y)
                c.put(box_left+box_width-1, box_top+i, '│', Y)

        # Code content - typing effect
        code_lines=[
            'if ( if I can ) {',
            '',
            '    yield(world.simulations);',
            '',
            '}',
        ]

        if phase1>0.3:
            chars_to_show=int((phase1-0.3)*len(''.join(code_lines))*2)
            char_count=0

            for line_i, line in enumerate(code_lines):
                y_pos=box_top+2+line_i*2
                if y_pos<box_top+box_height-1:
                    # Calculate how many chars to show on this line
                    if char_count<chars_to_show:
                        shown_chars=min(len(line), chars_to_show-char_count)
                        shown_text=line[:shown_chars]
                        c.put(box_left+4, y_pos, shown_text, Y if 'yield' in line else B)
                        char_count+=len(line)

        # Condition label
        if phase1>0.7:
            label_text='CONDITION: TRUE'
            label_x=box_left+2
            label_y=box_top+box_height
            # Yellow highlight box
            c.put(label_x-1, label_y, '▐', Y)
            c.put(label_x, label_y, label_text, Y)
            c.put(label_x+len(label_text), label_y, '▌', Y)

        # Top label
        c.center(top+1, 'CONTROL FLOW', Y if phase1>0.5 else B)

        # Frame number
        c.put(box_left-2, box_top-2, '2', N)

    # Phase 2: Execute yield - binary data streams (2-5s)
    else:
        phase2=(elapsed-2)/2.9

        # Top status
        num_simulations=int(phase2*784)+100
        c.put(l+3, top+1, f'YIELD:', Y)
        c.put(l+15, top+1, f'{num_simulations} SIMULATIONS', B)

        # Binary data streams falling/floating
        num_streams=int(phase2*50)+20

        for stream_i in range(num_streams):
            # Stream properties
            stream_seed=hash16(stream_i*19)
            stream_x=l+5+(stream_seed%(r-l-10))
            stream_speed=1+((stream_seed>>8)%3)*0.5
            stream_length=8+((stream_seed>>4)%12)

            # Stream position (vertical)
            stream_y_base=top+int(elapsed*stream_speed*5)%(bt-top+stream_length)

            # Draw stream
            for seg_i in range(stream_length):
                y_pos=stream_y_base-seg_i

                if top+3<y_pos<bt-2:
                    # Binary content: mix of 0, O, o
                    char_seed=hash16(stream_i*23+seg_i*17+int(elapsed*10))
                    if char_seed%3==0:
                        char='0'
                    elif char_seed%3==1:
                        char='O'
                    else:
                        char='o'

                    # Brightness based on position in stream
                    brightness=1-(seg_i/stream_length)

                    if brightness>0.7:
                        c.put(stream_x, y_pos, char, Y)
                    elif brightness>0.4:
                        c.put(stream_x, y_pos, char, B)
                    else:
                        c.put(stream_x, y_pos, char, N)

        # Scattered letters from video (occasional)
        if phase2>0.3:
            scatter_chars=['C','YOU','B','A','E8A','D','&','=>','8','6','!','I']
            for i,ch in enumerate(scatter_chars):
                if hash16(i*31+int(elapsed*7))%4==0:
                    scatter_x=l+10+hash16(i*37)%(r-l-20)
                    scatter_y=top+5+hash16(i*41)%(bt-top-10)
                    c.put(scatter_x, scatter_y, ch, Y if hash16(i)%3==0 else B)

        # Bottom status
        if phase2>0.5:
            c.center(bt-3, 'Give you all the simulations', Y if int(elapsed*4)%2 else B)

def lyric_points_dimension(c,t,area,elapsed,music):
    """If I'm a set of points - dimensional progression: 0D→1D→2D→3D"""
    l,top,r,bt=area;cx,cy=(l+r)//2,(top+bt)//2
    progress=clamp(elapsed/3.5)

    # Phase 0: Points (0D) - 0-25%
    if progress<0.25:
        phase=progress/0.25
        # Random points appearing
        count=24+int(phase*96)
        for i in range(count):
            x=l+hash16(i*7)%(r-l)
            y=top+hash16(i*13)%(bt-top)
            brightness=1-(i/count)*0.5
            c.put(x,y,'·' if brightness<0.7 else '+' if brightness<0.85 else '*',
                  W if brightness>0.9 else B if brightness>0.7 else N)
        c.center(cy+int((bt-top)*0.3),'0D: POINTS',W if phase>0.7 else B)

    # Phase 1: Lines (1D) - 25-50%
    elif progress<0.5:
        phase=(progress-0.25)/0.25
        # Points connecting into lines
        num_lines=int(phase*15)+5
        for line_i in range(num_lines):
            # Random line endpoints
            x1=l+hash16(line_i*7)%(r-l)
            y1=top+hash16(line_i*13)%(bt-top)
            x2=l+hash16((line_i+1)*7)%(r-l)
            y2=top+hash16((line_i+1)*13)%(bt-top)

            # Draw line with trail
            steps=int(math.hypot(x2-x1,(y2-y1)*2))
            reveal=clamp((phase*3-line_i*0.08))
            for s in range(int(steps*reveal)):
                u=s/steps if steps>0 else 0
                x=int(x1+(x2-x1)*u)
                y=int(y1+(y2-y1)*u)
                age=1-abs(u-reveal)*2
                if age>0:
                    c.put(x,y,'─' if abs(x2-x1)>abs(y2-y1)*2 else '|' if abs(y2-y1)>abs(x2-x1) else '/',
                          W if age>0.8 else B if age>0.5 else N)

            # Endpoints
            c.put(x1,y1,'●',W)
            if reveal>0.8:c.put(x2,y2,'●',W)

        c.center(cy+int((bt-top)*0.3),'1D: LINES',W if phase>0.7 else B)

    # Phase 2: Surface (2D) - 50-75%
    elif progress<0.75:
        phase=(progress-0.5)/0.25
        # Grid/mesh forming a surface
        grid_density=int(phase*12)+4

        # Wave surface
        for gy in range(grid_density):
            for gx in range(grid_density):
                u=gx/(grid_density-1) if grid_density>1 else 0.5
                v=gy/(grid_density-1) if grid_density>1 else 0.5

                # Position on screen
                x=l+(r-l)*u
                y=top+(bt-top)*v

                # Wave displacement
                wave=math.sin(u*TAU*2+t)*math.cos(v*TAU*2-t*0.7)*phase
                y_displaced=y+wave*(bt-top)*0.1

                # Draw grid point
                brightness=phase+wave*0.3
                c.put(x,y_displaced,'█' if brightness>0.8 else '▓' if brightness>0.6 else '▒' if brightness>0.4 else '░',
                      W if brightness>0.85 else B if brightness>0.6 else N)

                # Connect horizontally
                if gx<grid_density-1:
                    next_u=(gx+1)/(grid_density-1)
                    next_x=l+(r-l)*next_u
                    next_wave=math.sin(next_u*TAU*2+t)*math.cos(v*TAU*2-t*0.7)*phase
                    next_y_displaced=y+next_wave*(bt-top)*0.1
                    c.line(x,y_displaced,next_x,next_y_displaced,'─',G)

                # Connect vertically
                if gy<grid_density-1:
                    next_v=(gy+1)/(grid_density-1)
                    next_y=top+(bt-top)*next_v
                    next_wave=math.sin(u*TAU*2+t)*math.cos(next_v*TAU*2-t*0.7)*phase
                    next_y_displaced=next_y+next_wave*(bt-top)*0.1
                    c.line(x,y_displaced,x,next_y_displaced,'|',G)

        c.center(cy+int((bt-top)*0.35),'2D: SURFACE',W if phase>0.7 else B)

    # Phase 3: Volume (3D) - 75-100%
    else:
        phase=(progress-0.75)/0.25
        # Rotating 3D cube with perspective

        # Cube vertices
        size=0.8
        vertices=[
            (x*size,y*size,z*size)
            for z in (-1,1) for y in (-1,1) for x in (-1,1)
        ]

        # Rotate
        angle_x=t*0.5
        angle_y=t*0.7
        angle_z=t*0.3

        rotated=[]
        for x,y,z in vertices:
            # Rotate around Y
            x,z=x*math.cos(angle_y)-z*math.sin(angle_y),x*math.sin(angle_y)+z*math.cos(angle_y)
            # Rotate around X
            y,z=y*math.cos(angle_x)-z*math.sin(angle_x),y*math.sin(angle_x)+z*math.cos(angle_x)
            # Rotate around Z
            x,y=x*math.cos(angle_z)-y*math.sin(angle_z),x*math.sin(angle_z)+y*math.cos(angle_z)
            rotated.append((x,y,z))

        # Project to 2D with perspective
        projected=[]
        # Fit a physically square terminal-space projection to the available area.
        raw=[(x/(3.5+z),y/(3.5+z)*.5,z) for x,y,z in rotated]
        x0=min(p[0] for p in raw);x1=max(p[0] for p in raw)
        y0=min(p[1] for p in raw);y1=max(p[1] for p in raw)
        scale=min((r-l)*.7/(x1-x0),(bt-top)*.7/(y1-y0))*(1+.025*music.low*music.beat)
        for x,y,z in raw:
            px=cx+(x-(x0+x1)/2)*scale
            py=cy+(y-(y0+y1)/2)*scale
            projected.append((px,py,z))

        # Draw edges
        edges=[
            (0,1),(1,3),(3,2),(2,0),  # Back face
            (4,5),(5,7),(7,6),(6,4),  # Front face
            (0,4),(1,5),(2,6),(3,7)   # Connecting edges
        ]

        for i,(a,b) in enumerate(edges):
            xa,ya,za=projected[a]
            xb,yb,zb=projected[b]
            avg_z=(za+zb)/2
            # Hidden line removal
            style=N if avg_z<0 else B if avg_z<0.5 else W
            char=':' if avg_z<0 else '.' if avg_z<0.5 else '='
            c.line(xa,ya,xb,yb,char,style)

        # Draw vertices
        for i,(x,y,z) in enumerate(projected):
            label=f'{i}' if phase>0.7 else '●'
            c.put(x,y,label,W if z>0.5 else B if z>0 else N)

        # Internal structure lines (showing volume)
        if phase>0.5:
            # Diagonals
            diagonals=[(0,7),(1,6),(2,5),(3,4)]
            for a,b in diagonals:
                xa,ya,za=projected[a]
                xb,yb,zb=projected[b]
                if (a+b+int(t*10))%3==0:
                    c.line(xa,ya,xb,yb,'·',G)

        c.center(cy+int((bt-top)*0.35),'3D: VOLUME',W if phase>0.7 else B)

    # Top label
    dim_label=['0D','1D','2D','3D'][min(3,int(progress*4))]
    c.center(top,f'DIMENSIONAL PROGRESSION: {dim_label}',W)

def lyric_circle_circumference(c,t,area,elapsed,music):
    """If I'm a circle - explosive full-screen circle with trailing particles and dynamic formula"""
    l,top,r,bt=area;cx,cy=(l+r)//2,(top+bt)//2
    progress=clamp(elapsed/3.5)

    # Radius grows explosively
    # A character cell is about twice as tall as it is wide. Fit physical radius,
    # then establish the silhouette early so the spoken phrase has a clear subject.
    max_radius=min((r-l)*.42,(bt-top+1)*.34/.5)
    growth=1-(1-clamp(elapsed/.75))**3
    radius=max_radius*(.15+.85*growth)*(1+.025*music.low*music.beat)

    # Phase 1: Circle explosion with particle trails (0-1.5s)
    if elapsed<1.5:
        phase1=elapsed/1.5

        # Draw main circle with varying density
        circle_points=int(120+phase1*180)
        for i in range(circle_points):
            angle=i*TAU/circle_points
            x=cx+math.cos(angle)*radius
            y=cy+math.sin(angle)*radius*0.5

            # Pulsing brightness
            brightness=.4*music.beat+.6*abs(math.sin(music.beat_phase*TAU+angle*2))

            if brightness>0.7:
                c.put(x,y,'●',W)
            elif brightness>0.4:
                c.put(x,y,'○',B)
            else:
                c.put(x,y,'·',N)

            # Trailing particles expanding outward
            if phase1>0.3 and i%8==0:
                for trail in range(4):
                    trail_progress=(phase1-0.3)/0.7-trail*0.08
                    if trail_progress>0:
                        trail_radius=radius*(1+trail_progress*0.5)
                        tx=cx+math.cos(angle)*trail_radius
                        ty=cy+math.sin(angle)*trail_radius*0.5
                        if l<tx<r and top<ty<bt:
                            c.put(tx,ty,'*' if trail==0 else '+' if trail==1 else '·',
                                  W if trail==0 else B if trail==1 else N)

        # Center point
        c.put(cx,cy,'◉',R)

        # Growing label
        if phase1>0.5:
            c.center(top+2,'CIRCLE EXPANDING',W if phase1>0.8 else B)

    # Phase 2: Rotating radii explosion (1.5-2.5s)
    elif elapsed<2.5:
        phase2=(elapsed-1.5)/1.0

        # Main circle fully formed
        for i in range(180):
            angle=i*TAU/180
            x=cx+math.cos(angle)*radius
            y=cy+math.sin(angle)*radius*0.5
            brightness=(i%10==0)
            c.put(x,y,'◉' if brightness else 'o',W if brightness else B)

        # Multiple rotating radii
        num_radii=int(phase2*24)+4
        for i in range(num_radii):
            angle=i*TAU/num_radii+elapsed*1.5

            # Draw radius line with segments
            segments=int(radius)+1
            for seg in range(segments):
                r_progress=seg/segments
                rx=cx+math.cos(angle)*seg
                ry=cy+math.sin(angle)*seg*0.5

                # Gradient along radius
                if r_progress>0.8:
                    c.put(rx,ry,'═',W)
                elif r_progress>0.5:
                    c.put(rx,ry,'─',B)
                else:
                    c.put(rx,ry,'·',N)

            # Endpoint markers
            ex=cx+math.cos(angle)*radius
            ey=cy+math.sin(angle)*radius*0.5
            c.put(ex,ey,'●',Y)

        # Center
        c.put(cx,cy,'◉',R)

        # Radii count
        c.center(top+2,f'RADII: {num_radii}',W if phase2>0.7 else B)

        # Formula hint
        if phase2>0.5:
            c.center(cy-int((bt-top)*0.35),'r',Y)

    # Phase 3: Formula revelation with particle burst (2.5-3.5s)
    else:
        phase3=(elapsed-2.5)/1.0

        # Full circle
        for i in range(200):
            angle=i*TAU/200
            x=cx+math.cos(angle)*radius
            y=cy+math.sin(angle)*radius*0.5
            pulse=abs(math.sin(elapsed*3+angle*3))
            c.put(x,y,'◉' if pulse>0.7 else 'o',W if pulse>0.8 else B)

        # Selected radii
        for i in range(0,12):
            angle=i*TAU/12
            for seg in range(int(radius)):
                rx=cx+math.cos(angle)*seg
                ry=cy+math.sin(angle)*seg*0.5
                if seg%3==0:
                    c.put(rx,ry,'─',G)

        # Center
        c.put(cx,cy,'◉',R)

        # Formula builds up character by character
        formulas=[
            ('C = ?',         0.0, cy-int((bt-top)*0.2)),
            ('C = 2πr',       0.3, cy-int((bt-top)*0.2)),
            (f'C ≈ {2*3.14159*radius:.1f}', 0.6, cy),
        ]

        for formula,threshold,y_pos in formulas:
            if phase3>=threshold:
                reveal_progress=(phase3-threshold)*5
                chars_shown=min(len(formula),int(reveal_progress*len(formula)))
                shown=formula[:chars_shown]
                c.center(y_pos,shown,W if phase3>threshold+0.2 else B)

        # Arc length markers radiating out
        if phase3>0.7:
            for i in range(0,180,15):
                angle=i*TAU/180
                for pulse_dist in range(3):
                    px=cx+math.cos(angle)*(radius+5+pulse_dist*3+phase3*10)
                    py=cy+math.sin(angle)*(radius+5+pulse_dist*3+phase3*10)*0.5
                    if l<px<r and top<py<bt:
                        c.put(px,py,'*' if pulse_dist==0 else '·',
                              W if pulse_dist==0 else B if pulse_dist==1 else N)

        # Circumference label
        if phase3>0.8:
            c.center(bt-3,'CIRCUMFERENCE = 2πr',W if int(elapsed*4)%2 else B)

def lyric_sine_tangent(c,t,area,elapsed,music):
    """If I'm a sine wave - sine with tangent lines demonstration"""
    l,top,r,bt=area;cx,cy=(l+r)//2,(top+bt)//2
    progress=clamp(elapsed/3.0)
    amplitude=(bt-top)*(.28+.05*music.mid)

    # Draw sine wave
    for x in range(l+1,r):
        angle=(x-l)/(r-l)*TAU*2.5-t*0.5
        y=cy+math.sin(angle)*amplitude
        c.put(x,y,'~' if (x-l)%2 else '≈',B if (x-l)%3 else N)

    # Draw tangent lines at specific points
    num_tangents=int(progress*5)+1
    for i in range(min(num_tangents,5)):
        # Position along the wave
        t_point=i/4
        wave_x=l+(r-l)*t_point
        angle=(wave_x-l)/(r-l)*TAU*2.5-t*0.5
        wave_y=cy+math.sin(angle)*amplitude

        # Draw point
        c.put(wave_x,wave_y,'●',W if i==num_tangents-1 else Y)

        # Calculate tangent slope: derivative of sin is cos
        slope=math.cos(angle)*amplitude/(r-l)*TAU*2.5

        # Draw tangent line
        tangent_len=min(r-l,bt-top)*0.15
        for tx in range(-int(tangent_len),int(tangent_len)):
            tangent_x=wave_x+tx
            tangent_y=wave_y+slope*tx
            if l<tangent_x<r and top<tangent_y<bt:
                c.put(tangent_x,tangent_y,'─' if abs(slope)<0.3 else '\\' if slope>0 else '/',
                      Y if i==num_tangents-1 else G)

    # Show derivative formula
    if progress>0.3:
        c.center(top+2,'y = sin(x)',B)
    if progress>0.6:
        c.center(top+4,"y' = cos(x)",W)
    if progress>0.8:
        c.center(bt-2,'TANGENT LINES',G)

def lyric_infinity_limit(c,t,area,elapsed,music):
    """A luminous, data-bearing infinity ribbon is bounded by YOU."""
    l,top,r,bt=area;cx,cy=(l+r)/2,(top+bt)/2
    rail=max(9,min(16,c.w//8))
    ml=l+rail+2;mr=r-rail-2
    mw=mr-ml+1
    growth=clamp(elapsed/1.64)
    closing=clamp((t-42.346)/(43.507-42.346))
    locked=t>=43.507
    bound_l=ml+int(mw*.075*closing);bound_r=mr-int(mw*.075*closing)
    radius_x=mw*.47*(.76+.24*growth)*(1+.025*music.low*music.beat)
    radius_y=max(2,(bt-top-7)*.43)
    counter=int(8+elapsed*elapsed*39)
    c.center(top,'INFINITE LOOP / n -> INF',W)
    c.center(top+1,'[ LIMITATIONS / BOUND BY YOU ]' if locked else 'YOU.LIMIT / BOUNDARY ACQUIRED' if closing else 'GROWTH RATE: EXPONENTIAL',B)
    # Full-height registers convey growth, rather than a small isolated symbol.
    for side,x in enumerate((l,r-rail+1)):
        c.box(x,top+3,rail,bt-top-4,G)
        c.put(x+1,top+3,'N -> INF' if side==0 else 'YOU.LIMIT',B)
        for row in range(top+4,bt-2):
            n=max(0,counter+(row-top)*(1 if side==0 else -1))
            text=f'2^{n:04d}' if side==0 else f'{hash16(n*17):04X} '+('CAP' if locked else 'SET')
            c.put(x+1,row,text[:rail-2],W if (row+int(elapsed*12))%7==0 else N if side==0 else G)
    # A faint coordinate volume fills the area behind the interlaced ribbon.
    for yy in range(top+3,bt-2,3):
        for xx in range(ml,mr+1,5):c.put(xx,yy,'+',G)
    def position(a,strand=0,scale=1):
        sn=math.sin(a);cs=math.cos(a)
        denom=1+sn*sn
        x=cx+radius_x*cs/denom*scale
        y=cy+radius_y*2.8*sn*cs/denom*scale
        # Cross-section twists turn the curves into a woven character ribbon.
        x+=strand*math.cos(a*3+elapsed)*.6
        y+=strand*math.sin(a*3+elapsed)*.55
        return max(bound_l,min(bound_r,x)),y
    # Dim, offset echoes exploit CRT persistence without obscuring the main shape.
    for scale in (.80,1.10):
        for i in range(210):
            a=i*TAU/210
            x,y=position(a,0,scale)
            if top+3<y<bt-2:c.put(x,y,'.',G)
    points=[]
    for i in range(320):
        a=i*TAU/320
        z=math.sin(a+elapsed*.35)
        for strand in range(-2,3):
            x,y=position(a,strand)
            if top+3<y<bt-2:
                char='#' if abs(strand)==2 else '01'[(i+int(elapsed*18))%2]
                points.append((z,x,y,char,W if z>.65 and abs(strand)==2 else B if z>0 else N))
    for _,x,y,char,ink in sorted(points):c.put(x,y,char,ink)
    # Bright trains orbit the complete figure-eight in both directions.
    for packet in range(12):
        direction=1 if packet%2 else -1
        phase=direction*music.beat_position*.8+packet*TAU/12
        for tail in range(7):
            x,y=position(phase-direction*tail*.025)
            if top+3<y<bt-2:c.put(x,y,'@' if tail==0 else '*' if tail<3 else '.',W if tail<2 else B if tail<4 else G)
    # Limit rails advance inward when "you can be my" begins.
    if closing>0:
        for x in (bound_l,bound_r):
            c.line(x,top+3,x,bt-3,'|' if locked else ':',W if locked else B)
            for yy in (top+3,bt-3):c.put(x-1,yy,'[+]',W)
        c.put(bound_r-2,cy,'YOU',W)
    clear(c,int(cx)-3,int(cy),7,1)
    c.put(cx-2,cy,'[ME]',W)
    c.center(bt-1,'while (me < you.limit) { grow(); }' if locked else f'n = 2^{counter:04d} / NO UPPER BOUND',B)
    c.center(bt,'LIMIT = YOU' if locked else 'DATA CIRCULATING / LOOP CONTINUES',W if locked else N)


def lyric_ac_dc(c,t,area,elapsed,music):
    """One live signal is rectified; the receiver observes the actual new current."""
    l,top,r,bt=area;cx=(l+r)/2
    plot_top=top+(6 if c.h>=34 else 4);plot_bt=bt-3;cy=(plot_top+plot_bt)/2
    u=clamp((t-45.85)/1.10);amp=max(2,(plot_bt-plot_top)*.34)
    x0=l+12;x1=r-12;span=max(1,x1-x0)
    phase=music.beat_position*TAU*.5
    for y in range(plot_top,plot_bt+1,3):c.put(x0,y,':'*max(0,int(span)),v.SHADE)
    for trail in (1,0):
        previous=None
        for index in range(int(span)*2+1):
            x=x0+index/2
            ac=math.sin((x-x0)/span*TAU*2-phase+trail*.15)
            y=cy-mix(ac,1,u)*amp
            if previous:c.line(*previous,x,y,'.',v.CYAN_DIM if trail else v.CYAN if u>.5 else B)
            previous=(x,y)
    v.actor(c,l+6,cy,'ME',radius=2)
    v.actor(c,r-6,cy-amp*u,'YOU',radius=2)
    c.put(x0,plot_top,'AC ~',B);c.put(x1-4,plot_top,'DC =',v.CYAN)
    v.code_card(c,area,('ME.current = AC;','rectify(ME.current);','YOU.receive(DC);'),0 if t<45.85 else 1 if u<1 else 2)
    c.center(bt,'CURRENT / AC -> DC / '+('STABLE OUTPUT' if u==1 else 'RECTIFYING'),B)


def lyric_dizzy(c,t,area,elapsed):
    """Blind my vision - intense visual distortion with eyes everywhere"""
    l,top,r,bt=area;cx,cy=(l+r)//2,(top+bt)//2
    progress=clamp(elapsed/3.5)

    # Phase 1: Eyes opening everywhere (0-1s)
    if elapsed<1:
        phase1=elapsed/1.0
        num_eyes=int(phase1*30)+5

        for i in range(num_eyes):
            # Random but stable positions
            angle=i*TAU/30+hash16(i*13)*0.01
            radius=hash16(i*17)%(min(r-l,bt-top)//3)+10
            ex=cx+math.cos(angle)*radius
            ey=cy+math.sin(angle)*radius*0.5

            # Eye blink cycle
            blink_phase=(elapsed*3+i*0.3)%1.0
            if blink_phase<0.7:  # Open
                # Draw eye
                c.put(ex-1,ey,'(',N)
                c.put(ex,ey,'○',W if i==num_eyes-1 else B)
                c.put(ex+1,ey,')',N)
            elif blink_phase<0.85:  # Half closed
                c.put(ex-1,ey,'(',G)
                c.put(ex,ey,'-',B)
                c.put(ex+1,ey,')',G)

        c.center(top+2,'VISION',W if phase1>0.7 else B)

    # Phase 2: Spiral distortion with multiplying eyes (1-2s)
    elif elapsed<2:
        phase2=(elapsed-1)/1.0

        # Spiral vortex
        for ring in range(20):
            ring_radius=ring*4+phase2*20
            points_in_ring=max(8,int(ring*2))
            for i in range(points_in_ring):
                angle=i*TAU/points_in_ring+elapsed*2-ring*0.3
                x=cx+math.cos(angle)*ring_radius
                y=cy+math.sin(angle)*ring_radius*0.5

                if l<x<r and top<y<bt:
                    # Eyes in spiral
                    if i%3==0:
                        c.put(x,y,'◉',W if ring<5 else B if ring<12 else N)
                    else:
                        c.put(x,y,'·',N)

        # Large central eyes
        num_center_eyes=int(phase2*8)+1
        for i in range(num_center_eyes):
            eye_x=cx+int(math.sin(elapsed*4+i)*25)
            eye_y=cy+int(math.cos(elapsed*3+i*0.7)*10)

            # Animated iris following rotation
            iris_offset=int(math.sin(elapsed*5+i)*2)
            c.put(eye_x-2,eye_y,'(',B)
            c.put(eye_x-1+iris_offset,eye_y,'●',R if i%3==0 else W)
            c.put(eye_x+2,eye_y,')',B)

        c.center(cy-int((bt-top)*0.3),'DIZZY',W if int(elapsed*6)%2 else B)

    # Phase 3: Intense distortion - screen filled with eyes (2-3.5s)
    else:
        phase3=(elapsed-2)/1.5

        # Waves of distortion
        wave_intensity=phase3*8

        # Fill screen with eyes at varying depths
        for row in range(top+2, bt-2, 2):
            for col in range(l+3, r-3, 8):
                # Wave distortion
                wave_x=int(math.sin(row*0.2+elapsed*3)*wave_intensity)
                wave_y=int(math.cos(col*0.15+elapsed*2.5)*wave_intensity*0.5)

                x=col+wave_x
                y=row+wave_y

                if l+2<x<r-2 and top+1<y<bt-1:
                    # Distance from center affects eye style
                    dx,dy=x-cx,(y-cy)*2
                    dist=math.hypot(dx,dy)

                    # Pupil direction follows wave
                    pupil_dir=int(math.sin(dist*0.1+elapsed*4))

                    # Eye types based on distance
                    if dist<20:
                        # Close eyes - large and detailed
                        if hash16(row+col)%4==0:
                            c.put(x-2,y,'(',W)
                            c.put(x-1+pupil_dir,y,'●',R)
                            c.put(x+2,y,')',W)
                    elif dist<50:
                        # Medium eyes
                        if hash16(row*7+col*11)%3==0:
                            c.put(x-1,y,'(',B)
                            c.put(x+pupil_dir,y,'○',W if int(elapsed*8)%3==0 else B)
                            c.put(x+1,y,')',B)
                    else:
                        # Distant eyes - small
                        if hash16(row*13+col*17)%5==0:
                            c.put(x,y,'◉' if hash16(row+col+int(elapsed*10))%2 else '○',
                                  N if dist>80 else G)

        # Giant central eye blinking
        if phase3>0.3:
            blink=(elapsed*2)%1.0
            if blink<0.6:  # Open
                eye_size=int(8+math.sin(elapsed*5)*2)
                # Left eyelid
                for i in range(eye_size):
                    c.put(cx-eye_size+i,cy-2,'-' if i%2 else '_',W)
                # Right eyelid top
                for i in range(eye_size):
                    c.put(cx+i,cy-2,'-' if i%2 else '_',W)

                # Iris and pupil
                c.put(cx-1,cy,'(',B)
                c.put(cx,cy,'●',R if int(elapsed*4)%2 else W)
                c.put(cx+1,cy,')',B)

                # Bottom eyelid
                for i in range(eye_size):
                    c.put(cx-eye_size+i,cy+2,'_' if i%2 else '-',W)
                for i in range(eye_size):
                    c.put(cx+i,cy+2,'_' if i%2 else '-',W)
            else:  # Blinking
                for i in range(16):
                    c.put(cx-8+i,cy,'=' if i%2 else '-',B)

        # Disorienting text
        messages=['VISION','BLINDED','DIZZY','EYES','SEEING','BLIND']
        if phase3>0.5:
            for i,msg in enumerate(messages):
                msg_x=cx+int(math.sin(elapsed*3+i)*40)
                msg_y=cy+int(math.cos(elapsed*2.5+i*0.8)*15)
                if top+2<msg_y<bt-2:
                    # Distorted text
                    msg_distorted=''.join(ch if hash16(j*19+int(elapsed*10))%4>0
                                          else chr(33+hash16(j*23+i)%94)
                                          for j,ch in enumerate(msg))
                    c.center(msg_y,msg_distorted[:10],
                             W if i==int(elapsed*3)%len(messages) else B if i%2 else N)

        # Final flash effect
        if phase3>0.9 and int(elapsed*12)%3==0:
            c.center(cy,'BLIND',W)

def lyric_time_travel(c,t,area,elapsed):
    """Travel AD to BC - timeline with sweeping beam and year markers"""
    l,top,r,bt=area;cx,cy=(l+r)//2,(top+bt)//2
    progress=clamp(elapsed/3.7)

    # Timeline horizontal line
    timeline_y=cy
    for x in range(l+5, r-5):
        c.put(x, timeline_y, '─', B if x%2 else N)

    # Year markers along timeline
    # AD years on right, BC years on left
    num_markers=10
    marker_spacing=(r-l-20)//num_markers

    for i in range(num_markers):
        marker_x=l+10+i*marker_spacing

        # Tick marks
        for tick_y in range(-3, 4):
            if abs(tick_y)==3:
                c.put(marker_x, timeline_y+tick_y, '|', G if i%2 else N)
            elif abs(tick_y)==2:
                c.put(marker_x, timeline_y+tick_y, '│', G)

        # Year labels
        # Center is year 0, right is AD (positive), left is BC (negative)
        year_offset=(i-num_markers//2)*500  # 500 year intervals
        if year_offset>0:
            label=f'{abs(year_offset)}AD'
            c.center(timeline_y-5, label, Y if marker_x<r-20 else W)
            # Position near marker
            c.put(marker_x-len(label)//2, timeline_y-5, label, B)
        elif year_offset<0:
            label=f'{abs(year_offset)}BC'
            c.center(timeline_y-5, label, Y if marker_x>l+20 else W)
            c.put(marker_x-len(label)//2, timeline_y-5, label, B)
        else:
            c.put(marker_x-1, timeline_y-5, '0', W)

    # Sweeping vertical beam traveling from right (AD) to left (BC)
    beam_progress=progress
    beam_x=int(mix(r-10, l+10, beam_progress))

    # Draw the beam
    for y in range(top+2, bt-2):
        # Intensity varies along beam height
        intensity=1.0-abs(y-cy)/(bt-top)*2

        if intensity>0.7:
            c.put(beam_x, y, '│', W)
        elif intensity>0.4:
            c.put(beam_x, y, '┊', B)
        else:
            c.put(beam_x, y, ':', N)

        # Glow effect around beam
        for glow_offset in [-2,-1,1,2]:
            gx=beam_x+glow_offset
            if l<gx<r and top<y<bt:
                if abs(glow_offset)==1:
                    c.put(gx, y, '░', B if intensity>0.5 else N)
                else:
                    c.put(gx, y, '·', N)

    # Particles flying past the beam
    if progress>0.2:
        for particle_i in range(30):
            # Particle position relative to beam
            particle_phase=(elapsed*2+particle_i*0.3)%1.0

            # Horizontal position - moving left
            px=beam_x+int((particle_phase-0.5)*60)

            # Vertical position - scattered
            py=top+5+(particle_i*7)%(bt-top-10)

            if l<px<r and top<py<bt:
                if particle_phase<0.2 or particle_phase>0.8:
                    c.put(px, py, '*', W if particle_phase<0.1 else B)
                else:
                    c.put(px, py, '·', N)

    # Current year display near beam
    if progress>0.1:
        current_year=int(mix(2000, -2000, beam_progress))
        year_label=f'{abs(current_year)}{"AD" if current_year>0 else "BC" if current_year<0 else ""}'

        # Display year near beam top
        label_x=beam_x-len(year_label)//2
        if l+5<label_x<r-15:
            c.put(label_x, top+3, year_label, W if int(elapsed*4)%2 else Y)

    # Era labels
    if progress<0.3:
        c.center(top+1, 'FUTURE → PAST', B)
    elif progress<0.7:
        c.center(top+1, 'TIME TRAVEL', W if int(elapsed*3)%2 else B)
    else:
        c.center(top+1, 'ANCIENT ERA', W)

    # Speed lines indicating motion
    if progress>0.3:
        for line_i in range(15):
            line_y=top+5+line_i*((bt-top-10)//15)
            # Lines move from right to left
            line_phase=(elapsed*3+line_i*0.1)%1.0
            line_length=int(line_phase*20)+5

            for lx in range(max(l+5, beam_x+10), min(r-5, beam_x+10+line_length)):
                if hash16(line_i*17+int(lx/3))%4==0:
                    c.put(lx, line_y, '=' if line_phase>0.7 else '-',
                          B if line_phase>0.5 else N)

    # Destination marker
    if progress>0.8:
        dest_x=l+15
        c.put(dest_x, timeline_y-2, '▼', R)
        c.put(dest_x-2, timeline_y-3, 'BC', R)

        # Arrival flash
        if progress>0.95:
            flash_radius=int((progress-0.95)*60)
            for angle_i in range(12):
                angle=angle_i*TAU/12
                fx=dest_x+int(math.cos(angle)*flash_radius)
                fy=timeline_y+int(math.sin(angle)*flash_radius*0.5)
                if l<fx<r and top<fy<bt:
                    c.put(fx, fy, '*', W if flash_radius<10 else B)

def lyric_unite_deeply(c,t,area,elapsed):
    """Two distinct object memories braid into a shared address space."""
    l,top,r,bt=area;cx=(l+r)/2;cy=(top+bt)/2+1
    u=clamp(elapsed/(59.223-55.083));distance=mix((r-l)*.27,(r-l)*.10,u)
    left=cx-distance;right=cx+distance
    height=max(2,(bt-top-5)*.30)
    ring_rows=min((bt-top-5)*.40,(left-l-1)*.5,(r-right-1)*.5)
    for origin,ink in ((left,B),(right,v.CYAN)):
        for ring in (.74,1.):
            for index in range(100):
                a=index*TAU/100
                c.put(origin+math.cos(a)*ring_rows*2*ring,cy+math.sin(a)*ring_rows*ring,
                      ':' if ring<1 else '.',v.ROSE_DIM if u>.72 else ink if ring==1 else G)
    for strand in range(3):
        previous=None
        for index in range(81):
            p=index/80;x=mix(left,right,p)
            y=cy+math.sin(p*TAU*2+t*2+strand*TAU/3)*height*math.sin(p*math.pi)
            ink=v.ROSE if u>.45 else B if strand%2 else v.CYAN
            if previous:c.line(*previous,x,y,':' if strand else '.',ink)
            previous=(x,y)
    v.actor(c,left,cy,'ME',radius=3)
    v.actor(c,right,cy,'YOU',radius=3)
    v.code_card(c,area,('link = ME.connect(YOU);','link.share(memory);','link.commit();'),min(2,int(u*3)))
    c.center(bt,'SHARED MEMORY / '+('UNIFIED' if u>.85 else 'TWO OBJECTS / ONE ADDRESS SPACE'),v.ROSE if u>.5 else B)

def lyric_stimulation_satisfaction(c,t,area,elapsed,music=None):
    """Inputs, a visible response, and a growing closed-loop satisfaction signal."""
    l,top,r,bt=area;cx=(l+r)/2
    plot_top=top+(6 if c.h>=34 else 4);plot_bt=bt-3;cy=(plot_top+plot_bt)/2
    left=l+(r-l)*.20;right=l+(r-l)*.73
    satisfied=t>=62.589
    strength=clamp((t-59.223)/(61.958-59.223))
    fill=clamp((t-62.589)/(65.397-62.589)) if satisfied else 0
    phase=music.beat_position*.6 if music else elapsed
    pulse=music.low*music.beat if music else 0
    lanes=3 if bt-top<28 else 5
    for lane in range(lanes):
        offset=(lane-(lanes-1)/2)*max(2,(plot_bt-plot_top)/(lanes+1))
        start=(left+5,cy);end=(right-5,cy+offset*.35)
        elbow=left+(right-left)*.3
        c.line(start[0],start[1],elbow,cy+offset,'.',G)
        v.signal(c,(elbow,cy+offset),end,phase+lane*.19,ink=v.ROSE if satisfied else B,amount=strength)
    radius=min((r-right-2)*.5,(plot_bt-plot_top)*.47)
    for i in range(120):
        a=i*TAU/120
        ink=v.ROSE if satisfied and i/120<=fill else v.CYAN_DIM
        c.put(right+math.cos(a)*radius*2,cy+math.sin(a)*radius,'.',ink)
    if satisfied:v.signal(c,(right-4,cy+3),(left+4,cy+3),phase,ink=v.CYAN)
    v.actor(c,left,cy,'ME',radius=2.5)
    v.actor(c,right,cy,'YOU',radius=2+min(1,fill+pulse*.2))
    if satisfied:c.put(right-2,min(plot_bt,cy+4),f'{int(fill*100):03d}%',W)
    lines=('signal = ME.offer();','YOU.respond(signal);','feedback = YOU.reply();','ME.satisfaction = feedback;')
    v.code_card(c,area,lines,0 if t<61.958 else 1 if t<62.589 else 2 if fill<1 else 3)
    c.center(bt,f'SATISFACTION {int(fill*100):03d}% / CLOSED LOOP' if satisfied else 'STIMULATION / INPUT -> RESPONSE',v.ROSE if satisfied else B)

def lyric_happy_execution(c,t,area,music):
    """A happiness condition feeds a self-execution, with live data on both sides."""
    l,top,r,bt=area;cx,cy=(l+r)//2,(top+bt)//2
    elapsed=t-66.601
    loading=t>=68.252
    executing=t>=69.259
    rail=max(9,min(22,(c.w-8)//6))
    left=l;right=r-rail+1
    mid_l=left+rail+2;mid_r=right-3;mw=mid_r-mid_l+1
    frame=int(elapsed*(30 if executing else 18 if loading else 10))
    # Object ports remain visible while the highlighted call drives feedback.
    for x,label,side in ((left,'MEM / YOU',0),(right,'EXEC / ME',1)):
        c.box(x,top,rail,bt-top+1,v.SHADE)
        role='ME' if side==0 else 'YOU'
        v.actor(c,x+rail/2,(top+bt)/2,role,radius=max(1,min(2,(rail-3)/4)))
    def middle(y,text,style=N):
        text=text[:mw]
        c.put(mid_l+(mw-len(text))//2,y,text,style)

    content_top=top+2;content_bt=bt-2
    center_y=(content_top+content_bt)/2
    # Fit the same authored silhouette at rest and at its beat peak.
    half_w=fit_scale((mid_l,content_top,mid_r,content_bt),HEART_WIDTH,HEART_HEIGHT)*.99/1.07
    half_h=half_w*CELL_ASPECT
    beat=1+music.low*music.beat*.07
    step_x=1/(half_w*beat);step_y=1/(half_h*beat)
    morph=clamp((t-68.252)/(69.259-68.252)) if loading else 0
    # A large data-filled heart. Its own cells become the execution buffer.
    for yy in range(content_top,content_bt+1):
        for xx in range(mid_l,mid_r+1):
            nx=(xx-cx)*step_x
            ny=-(yy-center_y)*step_y
            seed=hash16(xx*79+yy*233)
            if heart_contains(nx,ny) and not executing:
                if seed/65535<morph:
                    # Removed heart cells spread out across the entire center.
                    dx=int((xx-cx)*morph*0.9)
                    dy=int((yy-center_y)*morph*0.6)
                    px=max(mid_l,min(mid_r,xx+dx));py=max(content_top,min(content_bt,yy+dy))
                    c.put(px,py,'01EX'[seed%4],G if morph>.7 else N)
                else:
                    scan=(yy-content_top-int(elapsed*9))%max(1,content_bt-content_top+1)
                    texture=hash16(seed+frame//2)
                    edge=heart_edge(nx,ny,step_x,step_y)
                    c.put(xx,yy,'#' if edge else '01'[texture%2] if texture%8<2 else '.',
                          W if edge else B if scan<1 else N)
            elif executing:
                # Expanding execution wave and dim opcode fragments behind the title.
                radius=abs(xx-cx)/max(1,mw/2)+abs(yy-center_y)/max(1,half_h)
                wave=((t-69.259)*3)%2
                if abs(radius-wave)<.12:c.put(xx,yy,'=',B)
                elif seed%31==0:c.put(xx,yy,'01'[seed%2],G)

    # Bright data packets flow from both edge panels into the center.
    for lane in range(3):
        yy=int(center_y)+(lane-1)*max(1,int(half_h*.7))
        path=max(2,(mw-6)//2)
        head=int(elapsed*(28 if loading else 16)+lane*7)%path
        for tail in range(4):
            step=max(0,head-tail)
            ink=W if tail==0 else B if tail<2 else G
            for xx,head_char in ((mid_l+step,'>'),(mid_r-step,'<')):
                nx=(xx-cx)*step_x
                ny=-(yy-center_y)*step_y
                inside=heart_contains(nx,ny)
                if inside and not loading:
                    # Packets brighten the solid fill instead of cutting dark dashes into it.
                    c.put(xx,yy,'#' if tail==0 else '01'[(xx+yy+frame)%2],W if tail==0 else B)
                else:
                    c.put(xx,yy,head_char if tail==0 else '-',ink)
    if executing:
        title_y=int(center_y)-2
        # Reserve a clean five-row band so the word remains legible through the wave.
        clear(c,mid_l,title_y,mw,5)
        if mw>=53:c.big(title_y,'EXECUTION',W)
        else:middle(title_y+2,'>> EXECUTION <<',W)
        middle(title_y-2,'[ YOU.HAPPY == TRUE ]',B)
        middle(title_y+6,'world.execute(me);',W)
    elif loading:
        middle(int(center_y),'[ RUN THE EXECUTION ]',W)
    else:
        middle(int(center_y),'YOU.HAPPY',W)
    middle(bt-1,'EXECUTION: '+('RUN' if executing else 'QUEUED' if loading else 'READY'),B)
    middle(bt,'ME -> YOU / '+('SELF COMMITTED' if executing else 'COMPILING...' if loading else 'MAKE YOU HAPPY'),N)
    v.code_card(c,area,('signal = ME.offer();','YOU.happy = respond(signal);','world.execute(ME);'),2 if executing else 1 if loading else 0)


def lyric_trapped_simulation(c,t,area,music):
    """The execution closes a shared cage, then reveals an endless simulated space."""
    l,top,r,bt=area;cx,cy=(l+r)//2,(top+bt)//2
    age=t-70.084
    strange=clamp((t-71.764)/1.405)
    reveal=t>=73.169
    rail=max(10,min(19,c.w//6))
    ml=l+rail+1;mr=r-rail-1;mw=mr-ml+1
    inner_top=top+2;inner_bt=bt-2
    hh=max(2,(inner_bt-inner_top)/2)
    center_y=(inner_top+inner_bt)/2
    frame=int(music.beat_position*8)
    def middle(y,text,style=N):
        text=text[:mw]
        c.put(ml+(mw-len(text))//2,y,text,style)

    # Full-height memory walls scroll in opposite directions and keep resetting.
    for x,label,direction in ((l,'HEAP / ME',1),(r-rail+1,'STACK / YOU',-1)):
        c.box(x,top,rail,bt-top+1,B)
        c.put(x+1,top,label[:rail-2],W)
        for yy in range(top+1,bt):
            step=(frame*direction+yy-top)%256
            value=hash16(step*53)
            text=(f'{step*16:04X} {value:04X}' if step%4 else ('LOOP ' if step%8 else 'EXEC ')+f'{value:04X}')
            c.put(x+1,yy,text[:rail-2],v.NEUTRAL if step%13==0 else v.SHADE)

    # A warped coordinate lattice covers the whole central simulation volume.
    for yy in range(inner_top,inner_bt+1):
        for xx in range(ml,mr+1):
            bend=math.sin((yy-center_y)*.32+age*3.1)*strange*6
            gx=int(xx+bend+age*5)
            gy=int(yy+math.sin((xx-cx)*.12-age*2)*strange*3)
            if gx%8==0 or gy%4==0:
                ch='+' if gx%8==0 and gy%4==0 else ':' if gx%8==0 else '.'
                c.put(xx,yy,ch,G)
            elif hash16(xx*17+yy*79+frame//3)%109==0:
                c.put(xx,yy,'01'[hash16(xx+yy)%2],N)

    # Recurring perspective frames: every apparent exit leads into another cell.
    for layer in range(8):
        phase=(layer/8+age*(.20+strange*.25))%1
        scale=.12+.88*phase**1.5
        skew=math.sin(age*2+layer*.8)*strange*mw*.10
        x0=cx-mw*.48*scale;x1=cx+mw*.48*scale
        y0=center_y-hh*.95*scale;y1=center_y+hh*.95*scale
        corners=[(x0+skew,y0),(x1,y0+strange*math.sin(age*3+layer)),
                 (x1-skew,y1),(x0,y1-strange*math.sin(age*3+layer))]
        for index in range(4):
            x,y=corners[index];xx,yy=corners[(index+1)%4]
            c.line(max(ml,min(mr,x)),y,max(ml,min(mr,xx)),yy,'=' if layer%3==0 else '-',N if layer%3==0 else G)
        if layer%2==0 and scale>.6:
            c.put(max(ml,int(x0)),int(y0),f'LOOP {layer:02d}',N)

    # The outer gate visibly contracts around both entities on "we are trapped".
    close=clamp(age/.85)
    box_w=max(20,int(mw*(.98-.22*close)))
    box_h=max(7,int((inner_bt-inner_top+1)*(.98-.16*close)))
    bx=cx-box_w//2;by=int(center_y)-box_h//2
    if not reveal:
        c.box(bx,by,box_w,box_h,B)
        # Sliding bars lock from both sides; their gaps then oscillate unnaturally.
        for index in range(1,7):
            xx=bx+index*(box_w-1)//7
            jitter=int(math.sin(age*5+index)*strange*2)
            extent=int((box_h-2)*close)
            for row in range(extent):
                yy=by+1+row if index%2 else by+box_h-2-row
                c.put(xx+jitter,yy,'|',N if index%2 else B)
        middle(by,'[ CONTAINMENT '+('LOCKED' if close>=1 else 'CLOSING')+' ]',W)
        node_y=int(center_y)
        for x,name in ((cx-max(6,box_w//4),'ME'),(cx+max(6,box_w//4),'YOU')):
            clear(c,x-4,node_y-1,9,3)
            v.actor(c,x,node_y,name,radius=1.5)
        c.line(cx-box_w//4+5,node_y,cx+box_w//4-5,node_y,'=',B)
        if t>=71.764:middle(by+box_h-1,'STRANGE / '+f'RECURSION {int(age*13):03d}',W)
    else:
        title_y=int(center_y)-2
        clear(c,ml,title_y,mw,5)
        if mw>=59:c.big(title_y,'SIMULATION',W)
        else:middle(title_y+2,'>> SIMULATION <<',W)
        middle(title_y-2,'[ NO EXIT / SAME WORLD ]',B)
        middle(title_y+6,'[ ME ] <== LOOP ==> [ YOU ]',W)

    middle(top,'EXECUTION -> SIMULATION',B)
    middle(top+1,'world.simulate(me, you);',N)
    middle(bt-1,'EXIT: DENIED / RESTART: '+f'{int(age*17):04d}',B)
    middle(bt,'TRAPPED TOGETHER / LOOP FOREVER',W if reveal else N)
    calls=('loop()','sim()','rst()') if rail<15 else ('loop();','simulate();','restart();')
    v.code_card(c,(l+1,top+2,l+rail-2,top+6),calls,2 if reveal else 1 if t>=71.764 else 0)


def lyric_heart(c,t,area,elapsed,pulse):
    """A pulsing, filled heart fitted to the supplied scene bounds."""
    l,top,r,bt=area;cx,cy=(l+r)/2,(top+bt)/2
    scale=fit_scale((l+2,top+2,r-2,bt-2),HEART_WIDTH,HEART_HEIGHT)*.96/1.07
    scale*=(.85+.15*clamp(elapsed))*(1+.07*pulse)
    step_x=1/scale;step_y=1/(scale*CELL_ASPECT)
    outline=[]
    for py in range(top+2,bt-1):
        for px in range(l+2,r-1):
            nx=(px-cx)*step_x;ny=-(py-cy)*step_y
            if heart_contains(nx,ny):
                edge=heart_edge(nx,ny,step_x,step_y)
                c.put(px,py,'#' if edge else '.',W if edge else N)
                if edge:outline.append((px,py))
    if elapsed>1:
        c.center(cy,'♥',R)
    return outline



# Original organic choreography restored from the first delivered version.
def legacy_panel(c,x,y,w,h,label):
    clear(c,x,y,w,h);c.box(x,y,w,h,D)
    c.put(x+2,y,' '+label[:max(0,w-6)]+' ',N)

def legacy_workspace(c,t,top,bt,label,status='ACTIVE'):
    c.put(2,top,label,W)
    c.put(max(3,c.w-len(status)-3),top,status,B)
    c.put(2,top+1,'-'*(c.w-4),G)
    side=min(25,max(17,c.w//6)) if c.w>=100 else 0
    if side:
        lx=2;rx=c.w-side-2;ph=bt-top-2
        legacy_panel(c,lx,top+2,side,ph,'REGISTER')
        legacy_panel(c,rx,top+2,side,ph,'PROCESS')
        k=int(t*7)
        left=['PID 0001 : ME','UID 0002 : YOU',f'PC  {hash16(k):04X}',f'SP  {hash16(k+3):04X}']
        right=['STATE '+status[:7],f'TICK {int(t*120):06d}',f'CALL {hash16(k+7):04X}','FLAGS Z C O S']
        height=ph-2
        for i in range(height):
            yy=top+3+i
            if i<len(left):a=left[i];b=right[i]
            elif i==5:a='HEAP ALLOCATION';b='STACK TRACE'
            else:
                j=k+i
                a=f'{(i*16):04X} {hash16(j):04X} {hash16(j+19):04X}'
                ops=['LOAD','PUSH','CALL','WAIT','COPY','SYNC','RET ','JMP ']
                b=f'{ops[j%8]} @{hash16(j*3):04X}'
            c.put(lx+2,yy,a[:side-4],N if i<4 else G)
            c.put(rx+2,yy,b[:side-4],N if i<4 else G)
        sweep=int(t*8)%max(1,height)
        c.put(lx+1,top+3+sweep,'>',B)
        c.put(rx+side-2,top+3+(height-1-sweep),'<',B)
    return (side+4 if side else 4,top+3,c.w-side-5 if side else c.w-5,bt-1)

def legacy_mesh(c,t,area,form='torus',pulse=0):
    """Depth-tested parametric point surfaces, lit in character luminance."""
    zbuf={}
    for u in range(78):
        a=u*TAU/78
        for v in range(26):
            b=v*TAU/26
            if form=='torus':x=(.76+.29*math.cos(b))*math.cos(a);y=(.76+.29*math.cos(b))*math.sin(a);z=.29*math.sin(b)
            elif form=='sphere':x=math.sin(b)*math.cos(a);y=math.cos(b);z=math.sin(b)*math.sin(a)
            elif form=='heart':
                radius=.5+.5*math.cos(b)
                x=(16*math.sin(a)**3/17)*radius
                y=-(13*math.cos(a)-5*math.cos(2*a)-2*math.cos(3*a)-math.cos(4*a))/17*radius
                z=.38*math.sin(b)*math.sin(a)
                x*=1+pulse*.12;y*=1+pulse*.12
            elif form=='eggplant':
                x=math.sin(b)*math.cos(a)*(.43+.16*math.cos(b));y=math.cos(b)*1.2;z=math.sin(b)*math.sin(a)*.6
            elif form=='tomato':x=math.sin(b)*math.cos(a);y=math.cos(b)*.68;z=math.sin(b)*math.sin(a)
            else:
                x=(.68+.25*math.cos(3*a+b))*math.cos(2*a);y=(.68+.25*math.cos(3*a+b))*math.sin(2*a);z=.5*math.sin(3*a+b)
            xx,yy,zz=point(x,y,z,area,t if form!='heart' else math.sin(t*.45)*1.2)
            p=(round(xx),round(yy))
            if p not in zbuf or zz<zbuf[p][0]:zbuf[p]=(zz,a,b)
    ramp='.,:;=+*#@'
    l,y,r,bt=area
    for (x,yy),(z,a,b) in zbuf.items():
        if not(l<=x<=r and y<=yy<=bt):continue
        light=clamp(.45-z*.30+math.sin(a*2+b+t*.3)*.13)
        c.put(x,yy,ramp[int(light*(len(ramp)-1))],B if light>.77 else N if light>.40 else G)

def legacy_ring(c,t,area,turns=3):
    l,y,r,b=area;cx=(l+r)/2;cy=(y+b)/2
    for k in range(turns):
        rr=.32+k*.058
        for i in range(140):
            a=i*TAU/140
            if (i+k*9)%23<5:continue
            x=cx+math.cos(a)*(r-l)*rr;yy=cy+math.sin(a)*(b-y)*rr
            c.put(x,yy,'.' if k%2 else ':',G if k!=1 else D)
        a=t*(.6+k*.1)+k*2
        for j in range(14):
            aa=a-j*.018
            c.put(cx+math.cos(aa)*(r-l)*rr,cy+math.sin(aa)*(b-y)*rr,'+' if j==0 else '.',W if j==0 else G)

def legacy_organic(c,t,top,bt,pulse):
    i=0 if t<77.576 else 1 if t<81.351 else 2 if t<85.078 else 3
    subject=['EGGPLANT','TOMATO','TABBY CAT','GOD'][i]
    resource=['NUTRIENTS','ANTIOXIDANTS','ENJOYMENT','EXISTENCE'][i]
    area=legacy_workspace(c,t,top,bt,'TYPE CAST / '+subject,'EXPORT')
    l,y,r,b=area;cx=(l+r)/2;cy=(y+b)/2
    if i in (0,1):legacy_mesh(c,t,(l,y,cx+6,b),'eggplant' if i==0 else 'tomato')
    elif i==2:
        vs=[(-.9,-.8,0),(-.75,.4,0),(0,.75,0),(.75,.4,0),(.9,-.8,0),(.4,-.4,0),(-.4,-.4,0),(-.28,0,-.1),(.28,0,-.1),(0,.25,-.2)]
        es=[(0,1),(1,2),(2,3),(3,4),(4,5),(5,6),(6,0),(7,9),(8,9),(5,8),(6,7)]
        projected(c,vs,es,(l,y,cx+8,b),math.sin(t)*.5)
        for s in (-1,1):
            for j in range(3):c.line(l+(cx-l)/2,cy+1,l+(cx-l)/2+s*11,cy+j-1,'.',N)
    else:legacy_mesh(c,t,(l,y,cx+8,b),'sphere');legacy_ring(c,t,(l,y,cx+8,b),4)
    target=round(mix(cx,r,.67))
    c.box(target-5,int(cy-2),11,5,N);c.put(target-3,cy,'YOU_02',W)
    for k in range(5):
        yy=cy-2+k
        c.line(cx-1,yy,target-6,yy,'.',G)
        xx=mix(cx,target-6,((t*.8+k*.2)%1))
        c.put(xx,yy,'>>',B if k==2 else D)
    c.center(y,f'convert(self, {resource.lower()});',W)
    c.center(b,f'TX {int((t%3)/3*65535):04X}  |  {resource} -> YOU  |  ACK',N)

def legacy_phosphor(c,t,top,bt):
    """Luminance scan and short signal tears, confined above the captions."""
    row=top+int(t*9)%max(1,bt-top+1)
    for x in range(2,c.w-2):
        ch,s=c.cells[row][x]
        if ch not in ('',' ') and s in (D,N,G):c.cells[row][x]=(ch,N if s==G else B)
    if 125.708<t<177.246 and int(t*13)%17 in (0,1):
        yy=top+hash16(int(t*13))%max(1,bt-top)
        shift=2 if int(t*13)%2 else -3
        source=c.cells[yy][2:-2]
        source=source[-shift:]+source[:-shift]
        c.cells[yy][2:-2]=source

def lyric_eggplant_tomato(c,t,area,item):
    """Eggplant/tomato - simple organic shape"""
    l,top,r,bt=area;cx,cy=(l+r)//2,(top+bt)//2
    # Simple blob
    for y in range(top,bt):
        for x in range(l,r):
            dx,dy=(x-cx)/4,(y-cy)/2
            dist=math.hypot(dx,dy)
            if item=='eggplant':
                # Elongated
                if dist<6 and abs(dy)<8:
                    c.put(x,y,'█' if dist<4 else '▓',B if dy<0 else N)
            else:
                # Round
                if dist<5:
                    c.put(x,y,'●' if dist<3 else 'o',R if dist<3 else N)
    c.center(cy+int((bt-top)*0.3),item.upper(),B)

def lyric_cat(c,t,area,elapsed):
    """Tabby cat - ASCII cat"""
    l,top,r,bt=area;cx,cy=(l+r)//2,(top+bt)//2
    cat=[
        "  /\\_/\\  ",
        " ( o.o ) ",
        "  > ^ <  ",
        " /|   |\\ "
    ]
    for i,line in enumerate(cat):
        c.center(cy-2+i,line,B if i<3 else N)
    # Purr waves
    if elapsed>0.5:
        for i in range(5):
            phase=(elapsed*2+i*0.2)%1
            x=cx+int(phase*20)-10
            c.put(x,cy+3,'~' if phase<0.8 else '',G)
    c.center(cy+5,'*purr*',G)

def lyric_god_existence(c,t,area,elapsed,music=None):
    """YOU observes the creator; the arriving proof turns its whole world on."""
    l,top,r,bt=area;span=r-l
    mx=l+span*.32;yx=l+span*.84
    plot_top=top+(5 if c.h>=34 else 3);plot_bt=bt-4
    cy=(plot_top+plot_bt)/2
    beat=music.beat if music else 0.;low=music.low if music else .2
    phase=music.beat_position if music else t*2
    confirmed=t>=87.922
    travel=clamp((t-86.538)/(87.922-86.538))
    radius=min((plot_bt-plot_top)*.35,span*.075)
    bloom=clamp((t-87.922)/.35)
    orbit=radius*(1.25+.10*beat*low)
    for lane in range(5):
        yy=mix(plot_top,plot_bt,lane/4)
        c.line(l+1,yy,r-1,yy,'.',v.SHADE)
    # The dim simulation already belongs to ME, but needs an external witness.
    for node in range(8):
        angle=node*TAU/8+phase*.025
        x=mx+math.cos(angle)*orbit/CELL_ASPECT
        y=cy+math.sin(angle)*orbit
        if not l+1<=x<=r-2 or not plot_top<=y<=plot_bt:continue
        c.line(mx,cy,x,y,'.',N if confirmed else v.SHADE)
        c.put(round(x)-1,round(y),'[+]' if confirmed else '[?]',B if confirmed else G)
    for ring in range(2):
        rr=orbit*(.84+ring*.16)
        for i in range(120):
            a=i*TAU/120+phase*.035*(1 if ring else -1)
            xx=mx+math.cos(a)*rr/CELL_ASPECT;yy=cy+math.sin(a)*rr
            if l<=xx<=r and plot_top<=yy<=plot_bt:
                c.put(round(xx),round(yy),':' if i%6 else '1',N if confirmed else v.SHADE)
    if 86.538<=t<87.922:
        end=mx+radius/CELL_ASPECT+2
        for lane in (-1,0,1):
            yy=cy+lane*2
            v.signal(c,(yx-7,yy),(end,yy),min(.999,travel),ink=v.CYAN,trail=6)
        x=mix(yx-10,end,travel)
        c.put(round(x)-2,round(cy)-3,'[ACK]',v.CYAN_HIGH)
    if confirmed:
        for i in range(100):
            a=i*TAU/100;rr=radius*(1+bloom*.8)
            xx=mx+math.cos(a)*rr/CELL_ASPECT;yy=cy+math.sin(a)*rr
            if l<=xx<=r and plot_top<=yy<=plot_bt:
                c.put(round(xx),round(yy),'+',W if bloom<.6 else N)
    v.actor(c,mx,cy,'ME',radius=radius*(1+.04*beat),ghost=not confirmed)
    c.put(round(mx)-1,round(cy),'ME',B);c.protect(round(mx)-1,round(cy),2,1)
    v.actor(c,yx,cy,'YOU',radius=max(1.5,min(3.5,radius*.42)))
    if confirmed:
        if c.w>=100 and bt-top>=25:c.big(bt-9,'EXISTENCE',W)
        else:c.center(bt-1,'[ EXISTENCE CONFIRMED ]',W)
    v.code_card(c,area,('WORLD.owner = ME;','proof = YOU.observe(ME);','ME.manifest();'),
                2 if confirmed else 1 if t>=86.538 else 0)
    c.center(bt,'EXISTENCE / WORLD ACTIVE' if confirmed else 'PROOF IN FLIGHT / YOU -> ME' if t>=86.538 else 'CREATOR / AWAITING YOU',W if confirmed else N)

def identity_bitmap(c,x,y,text,sx,sy,ink,fill=1,seed=0):
    glyphs={'F':('11111','11000','11110','11000','11000'),
            'M':('10001','11011','10101','10001','10001'),
            'A':('01110','11011','11111','11011','11011'),
            'P':('11110','11011','11110','11000','11000')}
    for index,ch in enumerate(text):
        for dy,row in enumerate(glyphs[ch]):
            for dx,pixel in enumerate(row):
                if pixel=='1':
                    for py in range(sy):
                        for px in range(sx):
                            xx=x+(index*6+dx)*sx+px;yy=y+dy*sy+py
                            on=hash16((index*31+dx)*73+dy*137+px*19+py+seed)/65535<=fill
                            c.put(xx,yy,'#' if on else '.',ink if on else G)


def lyric_identity_rewrite(c,t,area):
    """Rewrite a gender field by disassembling and transmitting its character cells."""
    l,top,r,bt=area;cx,cy=(l+r)//2,(top+bt)//2
    age=t-88.587
    u=clamp((t-90.197)/1.25)
    sx=max(2,min(6,(r-l)//22));sy=max(1,min(5,(bt-top-8)//5))
    glyph_w=5*sx;glyph_h=5*sy
    left_c=(l+cx)//2;right_c=(cx+r)//2;y=cy-glyph_h//2
    c.center(top,'SELF.GENDER / PARAMETER REWRITE',W)
    c.center(top+1,'F -> M / TRANSMIT IDENTITY',B)
    c.box(l,top+3,cx-l-1,bt-top-5,G)
    c.box(cx+2,top+3,r-cx-1,bt-top-5,G)
    # Scrolling bytes fill both panes, behind the large letter masks.
    for row in range(top+4,bt-2,2):
        tick=int(age*18)+row
        c.put(l+2,row,f'{hash16(tick):04X}',G)
        c.put(r-5,row,f'{hash16(tick+79):04X}',G)
    for i in range(6):
        yy=top+4+i*max(1,(bt-top-8)//5)
        c.line(l+7,yy,r-7,yy,'.',G)
        progress=(age*.9+i*.17)%1
        x=mix(left_c,right_c,progress)
        c.put(x,yy,'>>',W if u else B)
    clear(c,left_c-glyph_w//2-1,y-1,glyph_w+2,glyph_h+2)
    clear(c,right_c-glyph_w//2-1,y-1,glyph_w+2,glyph_h+2)
    identity_bitmap(c,left_c-glyph_w//2,y,'F',sx,sy,W,1-u)
    identity_bitmap(c,right_c-glyph_w//2,y,'M',sx,sy,W,u)
    # Released source cells travel in arcs and settle into the new character.
    if 0<u<1:
        for i in range(44):
            p=clamp(u*1.6-(i%11)/18)
            x=mix(left_c,right_c,p)
            yoff=(hash16(i*31)%max(1,glyph_h))-glyph_h/2
            yy=cy+yoff+math.sin(p*math.pi)*(1 if i%2 else -1)*3
            c.put(x,yy,'01#'[i%3],W if i%4==0 else B)
    c.put(left_c-4,bt-3,'SOURCE F',N if u<1 else G)
    c.put(right_c-4,bt-3,'TARGET M',W if u>=1 else N)
    c.center(bt-1,f'WRITE {int(u*100):03d}% / '+('COMMITTED' if u>=1 else 'COMPILING' if not u else 'REASSEMBLING'),B)
    c.center(bt,"self.gender = 'M';" if u>=1 else "self.gender: F -> M",W)


def lyric_daynight_clock(c,t,area):
    """An oversized clock races through daylight and flips its AM/PM display."""
    l,top,r,bt=area;cx,cy=(l+r)//2,(top+bt)//2
    age=t-92.015
    flip_at=94.55
    is_pm=t>=flip_at
    virtual=6+6*clamp((t-92.015)/(flip_at-92.015)) if not is_pm else 12+6*clamp((t-flip_at)/(95.465-flip_at))
    clock_x=(l+cx)/2;display_x=(cx+r)/2
    rx=min(fit_scale((l+1,top+1,cx-1,bt-1)),(bt-top+1)*.8)
    ry=rx*CELL_ASPECT
    c.center(top,'CLOCK.CYCLE / AM -> PM',W)
    # Clock face fills the left half instead of occupying a small central patch.
    for i in range(180):
        a=i*TAU/180
        c.put(clock_x+math.sin(a)*rx,cy-math.cos(a)*ry,'.',N)
    for hour in range(12):
        a=hour*TAU/12
        c.line(clock_x+math.sin(a)*rx*.9,cy-math.cos(a)*ry*.9,
               clock_x+math.sin(a)*rx,cy-math.cos(a)*ry,'#',B)
    hour_angle=virtual/12*TAU;minute_angle=(virtual%1)*TAU
    for trail in range(4,0,-1):
        a=minute_angle-trail*.13
        c.line(clock_x,cy,clock_x+math.sin(a)*rx*.8,cy-math.cos(a)*ry*.8,'.',G)
    c.line(clock_x,cy,clock_x+math.sin(hour_angle)*rx*.52,cy-math.cos(hour_angle)*ry*.52,'#',B)
    c.line(clock_x,cy,clock_x+math.sin(minute_angle)*rx*.83,cy-math.cos(minute_angle)*ry*.83,'*',W)
    c.put(clock_x,cy,'@',W)
    roman=('XII','I','II','III','IV','V','VI','VII','VIII','IX','X','XI')
    for hour,label in enumerate(roman):
        a=hour*TAU/12
        x=round(clock_x+math.sin(a)*rx*.77-(len(label)-1)/2)
        y=round(cy-math.cos(a)*ry*.77)
        c.put(x,y,label,B if hour%3==0 else N)
        c.protect(x,y,len(label),1)
    c.line(cx,top+1,cx,bt-1,'|',G)
    # Day/night symbol and huge AM/PM bitmap occupy the entire right pane.
    radius=fit_scale((cx+2,top+2,r-1,bt-2))*.68
    for i in range(120):
        a=i*TAU/120
        x=display_x+math.cos(a)*radius;y=cy+math.sin(a)*radius*CELL_ASPECT
        if not is_pm or math.cos(a)<.45:c.put(x,y,':',G if is_pm else N)
    if not is_pm:
        for ray in range(16):
            a=ray*TAU/16+age*.25
            c.line(display_x+math.cos(a)*radius*1.1,cy+math.sin(a)*radius*CELL_ASPECT*1.1,
                   display_x+math.cos(a)*radius*1.3,cy+math.sin(a)*radius*CELL_ASPECT*1.3,'.',G)
    else:
        for star in range(22):
            x=cx+2+hash16(star*31)%max(1,r-cx-4)
            y=top+1+hash16(star*79)%max(1,bt-top-1)
            c.put(x,y,'+' if (int(age*5)+star)%5==0 else '.',G)
    sx=sy=max(1,min(4,(r-cx-4)//11,(bt-top-6)//5))
    glyph_w=11*sx;glyph_h=5*sy;y0=cy-glyph_h//2
    clear(c,display_x-glyph_w//2-1,y0-1,glyph_w+2,glyph_h+2)
    identity_bitmap(c,display_x-glyph_w//2,y0,'PM' if is_pm else 'AM',sx,sy,W)
    # A narrow scan sweeps down the display on the flip.
    if 0<=t-flip_at<.22:
        yy=y0+int((t-flip_at)/.22*glyph_h)
        c.put(display_x-glyph_w//2,yy,'='*glyph_w,W)
    hour=int(virtual)%24;minute=int((virtual%1)*60)
    c.put(display_x-2,min(bt-3,y0+glyph_h+1),f'{hour:02d}:{minute:02d}',W)
    c.center(bt,('[ PM / NIGHT CYCLE ]' if is_pm else '[ AM / DAY CYCLE ]')+' do_whatever(); // AM -> PM',B)


def lyric_gender_role_switch(c,t,area,elapsed,from_label,to_label):
    """Gender/role switching - full screen symbolic transformation"""
    l,top,r,bt=area;cx,cy=(l+r)//2,(top+bt)//2
    progress=clamp(elapsed/2.5)

    # ===== F→M: Gender symbols transformation =====
    if from_label=='F' and to_label=='M':
        # Full screen: ♀ symbols morphing to ♂
        for i in range(150):
            angle=i*2.4+t*0.5
            radius_base=math.sqrt(i)*4
            radius=radius_base+math.sin(t*2+i*0.1)*3
            x=cx+math.cos(angle)*radius
            y=cy+math.sin(angle)*radius*0.5

            # Morph symbol based on progress
            if progress<0.3:
                symbol='♀'
                style=W if i%5==0 else B if i%3==0 else N
            elif progress<0.7:
                # Transition phase - mix of both
                symbol='♀' if (i+int(t*10))%2==0 else '♂'
                style=R if (i+int(t*20))%3==0 else W if i%4==0 else B
            else:
                symbol='♂'
                style=W if i%5==0 else B if i%3==0 else N
            c.put(x,y,symbol,style)

        # Central explosion during transition
        if 0.3<progress<0.7:
            burst_progress=(progress-0.3)/0.4
            for burst_i in range(60):
                burst_angle=burst_i*TAU/60+t*3
                burst_r=burst_progress*50
                bx=cx+math.cos(burst_angle)*burst_r
                by=cy+math.sin(burst_angle)*burst_r*0.5
                c.put(bx,by,'⚥' if burst_i%3==0 else '*',W)

        # Large center symbol
        scale=int(8+int(math.sin(t*2)*2))
        center_symbol='♀' if progress<0.5 else '♂'
        for dy in range(-scale,scale+1):
            for dx in range(-scale*2,scale*2+1):
                dist=math.hypot(dx/2,dy)
                if dist<scale:
                    c.put(cx+dx,cy+dy,center_symbol,
                          W if dist<scale*0.4 else B if dist<scale*0.7 else N)

    # ===== AM→PM: Clock progression =====
    elif from_label=='AM' and to_label=='PM':
        # Clock face with hands sweeping
        radius_clock=int(min(r-l,bt-top)*0.35)

        # Clock circle
        for i in range(120):
            angle=i*TAU/120
            x=cx+math.cos(angle)*radius_clock
            y=cy+math.sin(angle)*radius_clock*0.5
            c.put(x,y,'○' if i%10==0 else '·',B)

        # Hour markers (12, 3, 6, 9)
        for hour in [0,3,6,9]:
            angle=hour*TAU/12-TAU/4  # -90deg offset
            x=cx+math.cos(angle)*radius_clock*0.85
            y=cy+math.sin(angle)*radius_clock*0.85*0.5
            c.put(x,y,f'{hour if hour!=0 else 12}',W)

        # Clock hands rotating from AM (6:00) to PM (18:00)
        start_hour=6
        end_hour=18
        current_hour=mix(start_hour,end_hour,progress)

        # Hour hand
        hour_angle=current_hour*TAU/12-TAU/4
        hour_length=int(radius_clock*0.5)
        for step in range(hour_length):
            x=cx+math.cos(hour_angle)*step
            y=cy+math.sin(hour_angle)*step*0.5
            c.put(x,y,'═',W if step>hour_length*0.7 else B)

        # Minute hand (spinning fast)
        minute_angle=(t*6)%TAU-TAU/4
        minute_length=int(radius_clock*0.7)
        for step in range(minute_length):
            x=cx+math.cos(minute_angle)*step
            y=cy+math.sin(minute_angle)*step*0.5
            c.put(x,y,'─',B if step>minute_length*0.8 else N)

        # Time digits cascading
        for digit_y in range(int((bt-top)*0.6)):
            phase=(progress*3+digit_y*0.05)%1
            if phase<0.8:
                digit_x=int(cx+math.sin(phase*TAU)*30)
                hour_shown=int(mix(6,18,phase))%24
                c.put(digit_x,top+digit_y,f'{hour_shown:02d}',
                      W if phase>0.6 else B if phase>0.3 else G)

        # Central display
        display_hour=int(current_hour)%24
        c.center(cy+int((bt-top)*0.25),f'{display_hour:02d}:00',W)
        c.center(cy+int((bt-top)*0.32),'AM' if current_hour<12 else 'PM',R if current_hour>=12 else B)

    # ===== S→M: Dominance to submission (chains/waves) =====
    else:  # S to M
        # Visual: Sharp edges (S) flowing into smooth curves (M)

        # Background: Transitioning pattern
        if progress<0.5:
            # S phase: Sharp angles, rigid structure
            for row in range(top,bt+1,3):
                for x in range(l,r,8):
                    offset=int((t*10+row)%8)
                    pattern='╱╲' if row%6<3 else '╲╱'
                    c.put(x+offset,row,pattern[0],N)
                    c.put(x+offset+1,row,pattern[1],N)
        else:
            # M phase: Smooth waves, flowing
            for wave_y in range(12):
                y=top+int(wave_y*(bt-top)/11)
                for x in range(l,r):
                    wave=(x-l)/(r-l)*TAU*3-t*2
                    amplitude=(bt-top)*0.1*(progress-0.5)*2
                    offset=int(math.sin(wave)*amplitude)
                    c.put(x,y+offset,'~' if wave_y%2==0 else '≈',B if wave_y%3==0 else N)

        # Center transformation
        if progress<0.4:
            # S: Angular crown/spikes
            spike_count=8
            for i in range(spike_count):
                angle=i*TAU/spike_count+t*0.5
                base_r=15
                for r_step in range(20):
                    spike_r=base_r+r_step*1.5
                    spike_x=cx+math.cos(angle)*spike_r
                    spike_y=cy+math.sin(angle)*spike_r*0.5
                    if abs(angle%(TAU/spike_count))<0.2:  # Make spikes
                        c.put(spike_x,spike_y,'▲' if r_step%2==0 else '△',
                              W if r_step>15 else B if r_step>10 else N)
        elif progress<0.6:
            # Transition: Explosion
            trans=(progress-0.4)/0.2
            for i in range(80):
                angle=i*TAU/80
                radius=trans*60
                x=cx+math.cos(angle)*radius+math.sin(t*4+i)*5*(1-trans)
                y=cy+math.sin(angle)*radius*0.5+math.cos(t*4+i)*3*(1-trans)
                c.put(x,y,'*' if i%3==0 else '·',W if trans<0.5 else B)
        else:
            # M: Soft concentric circles
            circles=(progress-0.6)/0.4
            for ring in range(8):
                ring_r=8+ring*4
                density=int(ring_r*6)
                for i in range(density):
                    angle=i*TAU/density+t*0.3*(-1)**ring
                    x=cx+math.cos(angle)*ring_r
                    y=cy+math.sin(angle)*ring_r*0.5
                    c.put(x,y,'○' if ring%2==0 else '◯',
                          W if ring<3 else B if ring<5 else N)

        # Large central letter
        size=int(10+math.sin(t*1.5)*1.5)
        if not isinstance(size, int):
            size=int(size)
        center_char='S' if progress<0.5 else 'M'
        for dy in range(-size,size+1):
            for dx in range(-size*2,size*2+1):
                dist=math.hypot(dx/2,dy)
                if size*0.3<dist<size*0.8:
                    c.put(cx+dx,cy+dy,center_char,
                          W if dist>size*0.6 else B)

    # Common elements: Status and decorations
    c.center(top,f'{from_label} → {to_label}',W if progress>0.8 else B)
    c.center(bt,f'TRANSFORMATION: {int(progress*100)}%',N)

def ecg_sample(phase):
    """Stylized P-QRS-T trace, positive values point up on the monitor."""
    points=((0,0),(.08,0),(.12,.15),(.17,0),(.28,0),(.31,-.18),
            (.35,1.0),(.39,-.32),(.43,0),(.52,0),(.60,.25),(.70,0),(1,0))
    phase%=1
    for i in range(1,len(points)):
        x1,y1=points[i];x0,y0=points[i-1]
        if phase<=x1:return mix(y0,y1,(phase-x0)/(x1-x0))
    return 0


def lyric_vibration_sync(c,t,area,music):
    """Two traces share the score's half-time phase, then become network links."""
    l,top,r,bt=area;cx=(l+r)/2
    compact=bt-top<22
    complete=t>=110.221
    sync=clamp((t-107.22)/(110.221-107.22))
    lag=.28*(1-sync)
    phase=music.beat_position/2
    c.put(l,top,'ECG / YOU -> ME',v.CYAN)
    c.put(r-8,top,'HALF TIME',N)
    plot_top=top+3;plot_bt=bt-3
    split=(plot_top+plot_bt)//2
    x0=l+1;x1=r-1;span=x1-x0+1
    head=x0+int((phase/3)%1*span)
    for yy in range(plot_top,plot_bt+1,3):
        for xx in range(x0,x1+1,6):c.put(xx,yy,'+',v.SHADE)
    for lane,(lo,hi,name,delay) in enumerate(((plot_top,split,'YOU',0),(split+1,plot_bt,'ME',lag))):
        baseline=lo+(hi-lo)*.65;amplitude=max(1,(hi-lo)*.58)
        c.put(x0,lo,name,W if complete else v.CYAN if lane==0 else B)
        previous=None
        for sample in range(span*2):
            xx=x0+sample/2
            age=(head-xx)%span
            if age>span-2:
                previous=None;continue
            value=ecg_sample(phase-age/span*3-delay)
            yy=max(lo,min(hi,baseline-value*amplitude))
            ink=W if age<span*.08 else B if age<span*.42 else N
            if not complete:ink=(v.CYAN_HIGH if age<span*.08 else v.CYAN if age<span*.42 else v.CYAN_DIM) if lane==0 else B if age<span*.15 else N
            if previous and abs(age-previous[2])<2:
                c.line(previous[0],previous[1],xx,yy,'-',ink)
            previous=(xx,yy,age)
        tip=max(lo,min(hi,baseline-ecg_sample(phase-delay)*amplitude))
        c.put(head,tip,'@',W if complete else v.CYAN if lane==0 else B)
    c.center(bt-1,f'PHASE LOCK {int(sync*100):03d}% / '+('IN SYNC' if complete else 'ACQUIRING'),B)
    c.center(bt,'COMPLETION' if complete else 'FEEL YOUR VIBRATIONS',W if complete else N)
    v.code_card(c,(l,top,r,top+1),('sync = phase_lock(YOU, ME);','assert(sync);'),int(complete))
    if complete:
        u=clamp((t-110.221)/.679)
        cy=(top+bt)/2;rx=(r-l)*.38;ry=(bt-top-4)*.35
        for i in range(6):
            angle=(i+.5)*TAU/6
            nx=cx+math.cos(angle)*rx;ny=cy+math.sin(angle)*ry
            c.line(cx,cy,mix(cx,nx,u),mix(cy,ny,u),'.',G if u<.6 else N)
            if u>.7:c.put(nx,ny,'+',B)
        if u>.65:
            clear(c,int(cx)-4,int(cy)-1,9,3)
            c.box(int(cx)-4,int(cy)-1,9,3,B)
            c.put(cx-1,cy,'ME',W)


def lyric_isolation_disconnect(c,t,area,music):
    """One remote object loses six independent connections, then leaves."""
    l,top,r,bt=area;cx,cy=(l+r)/2,(top+bt)/2
    cuts=music.events('disconnect');gone=sum(event.time<=t for event in cuts)
    leaving=clamp((t-115.78)/(117.274-115.78))
    me_x=mix(l+(r-l)*.24,cx,leaving);me_y=cy+leaving*min(7,(bt-top)*.25)
    you_x=mix(r-7,r+12,leaving)
    for i,event in enumerate(cuts):
        y=top+5+i*max(1,(bt-top-10)/5)
        age=t-event.time;gap=clamp(age/.35)*.45 if age>=0 else 0
        for index in range(49):
            u=index/48
            if age>=0 and abs(u-.56)<gap:continue
            c.put(mix(me_x+5,r-11,u),y,'=' if 0<=age<.10 else '.',W if 0<=age<.10 else v.CYAN_DIM if age<0 else v.SHADE)
        if age<0:v.signal(c,(r-11,y),(me_x+5,y),music.beat_position*.4+i/6,ink=v.CYAN,track=False)
        elif age<.4:
            x=mix(me_x+5,r-11,.56)
            c.put(x-1,y,'//',R if age<.15 else G)
    if leaving<1:v.actor(c,you_x,cy,'YOU',radius=2,signal=1-leaving,ghost=leaving>.8)
    v.actor(c,me_x,me_y,'ME',radius=2)
    if t>=117.274:c.big(int(cy)-2,'ISOLATION',W)
    v.code_card(c,area,('handle = ME.connect(YOU);','handle.read();','raise Disconnected;','ME.retry();'),min(3,gone//2))
    c.center(bt-1,f'CONNECTION LOSS / LOST {gone:02d}/06',R if gone==6 else B)
    c.center(bt,'ALL CONNECTIONS LOST / NO ACK' if gone==6 else 'YOU HAVE LEFT / RETRYING...',N)


def lyric_erase_fragments(c,t,area,elapsed):
    """Erase memory, attempt repair, then leave a visibly broken heart."""
    l,top,r,bt=area;cx,cy=(l+r)/2,(top+bt)/2
    repair=t>=121.728;broken=t>=124.89
    cols=max(1,(r-l-8)//5);rows=max(1,(bt-top-2)//2)
    progress=clamp(elapsed/(120.86-118.333))
    c.center(top,'MEMORY PURGE / '+('REPAIR FAILED' if broken else 'REBUILD HEART' if repair else 'ERASE FRAGMENTS'),R if broken else B)
    for row in range(rows):
        yy=top+2+row*2
        c.put(l,yy,f'{row*cols*4:04X}',G)
        for col in range(cols):
            index=row*cols+col;xx=l+6+col*5
            threshold=hash16(index*71)/65535
            cleared=threshold<progress
            value='....' if cleared else f'{hash16(index*31):04X}'
            ink=v.SHADE if cleared or repair else N
            c.put(xx,yy,value,ink)
            since=(progress-threshold)*2.527
            if 0<since<.6 and not repair:
                drift=int(since*8)
                c.put(xx+(1 if col%2 else -1)*drift,yy-drift,'01' if since<.3 else '..',W if since<.2 else B)
    if 120.86<=t<121.728:
        clear(c,l,int(cy)-2,r-l+1,5)
        c.big(int(cy)-2,'FRAGMENTS',W)
    if repair:
        build=clamp((t-121.728)/1.5)
        split=clamp((t-123.25)/(125.708-123.25))
        # Fit the displaced fragments, including their maximum possible fall, before drawing.
        drift=int(split*5);fall_max=int(split*split*5) if broken else 0
        heart_bt=bt-2-fall_max;heart_y=(top+2+heart_bt)/2
        half_w=fit_scale((l+5+drift,top+2,r-5-drift,heart_bt),HEART_WIDTH,HEART_HEIGHT)*.96
        half_h=half_w*CELL_ASPECT
        step_x=1/half_w;step_y=1/half_h
        for yy in range(top+2,bt-1):
            for xx in range(l+5,r-4):
                nx=(xx-cx)*step_x;ny=-(yy-heart_y)*step_y
                seed=hash16(xx*31+yy*73)
                if heart_contains(nx,ny):
                    edge=heart_edge(nx,ny,step_x,step_y)
                    if seed/65535>=build:
                        if edge:c.put(xx,yy,'#',G)
                        continue
                    crack=abs(nx-.11*math.sin(ny*8))<split*.17
                    if crack:continue
                    dx=int((1 if nx>0 else -1)*split*5)
                    fall=int(split*split*(1+seed%5)) if broken else 0
                    py=yy+fall
                    texture=hash16(seed+int(t*10))
                    char='#' if edge else ('x' if broken else '01'[texture%2]) if texture%8<2 else '.'
                    c.put(xx+dx,py,char,(R if edge else RD) if broken else W if edge else N)
        v.actor(c,cx,heart_y+half_h*.25,'ME',radius=1.3,ghost=broken)
        v.actor(c,r-7,cy,'YOU',radius=1.5,ghost=True)
        c.center(top+1,'HEART.RESTORE() -> NULL' if broken else 'RECOVERING YOU... CHECKSUM MISMATCH',R if broken else N)
        if broken:
            clear(c,l,max(top+2,int(cy)-2),r-l+1,5)
            c.big(max(top+2,int(cy)-2),'DISHEARTENED',W)
            c.center(bt-1,'[ REPAIR FAILED / YOU NOT FOUND ]',R)
    c.center(bt,'MEMORY CLEARED. LOSS REMAINS.' if broken else f'ERASE {int(progress*100):03d}% / FRAGMENTS -> NULL',B)
    v.code_card(c,area,('fragments = GC.collect();','ME.restore(fragments);','assert(YOU != NULL);'),2 if broken else 1 if repair else 0)


def lyric_multilingual_count(c,t,area,music):
    """Follow the supplied multilingual count, which runs from one to six."""
    l,top,r,bt=area;cx,cy=(l+r)//2,(top+bt)//2
    cues=tuple((e.time,e.label,i+1) for i,e in enumerate(music.events('count')))
    start,word,number=max(cue for cue in cues if cue[0]<=t+1e-8)
    age=t-start
    firing=t>=161.584
    for yy in range(top,bt+1):
        for xx in range(l,r,5):
            seed=hash16(xx*31+yy*71+int(t*18))
            if seed%7==0:c.put(xx,yy,f'{seed:04X}',G)
    radius=clamp(age/.35)
    for ring in range(2):
        rr=(radius+ring*.25)%1
        for i in range(120):
            a=i*TAU/120
            c.put(cx+math.cos(a)*(r-l)*.48*rr,cy+math.sin(a)*(bt-top)*.45*rr,'=',B if ring==0 else G)
    if firing:
        c.big(cy-2,'EXECUTION',W)
        c.center(cy+5,'[ SEQUENCE COMPLETE / EXECUTE ]',R)
        return
    # Reuse the player font, enlarging the sung word instead of its Arabic numeral.
    glyph_width=len(word)*6-1
    glyph=c.__class__(64,5)
    glyph.big(0,word,W)
    glyph_left=(64-glyph_width)//2
    sx=max(1,min(4,(r-l-8)//29))
    sy=max(1,min(4,(bt-top-6)//5))
    x0=cx-glyph_width*sx//2;y0=cy-5*sy//2
    clear(c,x0-1,y0-1,glyph_width*sx+2,5*sy+2)
    for dy,row in enumerate(glyph.cells):
        for dx,(pixel,_) in enumerate(row[glyph_left:glyph_left+glyph_width]):
            if pixel=="#":
                for py in range(sy):c.put(x0+dx*sx,y0+dy*sy+py,"#"*sx,W)
    c.protect(x0-1,y0-1,glyph_width*sx+2,5*sy+2)
    c.center(top,"VOCAL SEQUENCE / "+word,B)
    c.center(bt-1,"[ "+word+" ]",W)
    c.center(bt," / ".join("["+item[1]+"]" if item[1]==word else item[1] for item in cues),B)


def lyric_illegal_arguments(c,t,area,music):
    """A rejected request becomes an accumulating retry stack, then a held breath."""
    l,top,r,bt=area;cx,cy=(l+r)/2,(top+bt)/2
    depth=sum(t>=at for at in (135.991,139.702,143.843))
    quiet=t>=147.515
    step=0 if t<131.224 else 1 if t<135.991 else 2 if t<139.702 else 3
    lines=('request = YOU.choose(FREE);','ME.validate(request);','throw IllegalArgument;','retry(request);')
    if quiet:
        v.actor(c,cx,cy,'ME',radius=2,signal=.15,ghost=True)
        v.code_card(c,area,('queue.freeze();','world.execute(ME);'),1)
        c.center(bt-1,'QUIESCE / NEXT INSTRUCTION ARMED',W)
    else:
        v.backdrop(c,t,area,density=depth)
        rail_y=cy-5
        v.signal(c,(l+13,rail_y),(cx-6,rail_y),music.beat_position*.5,ink=v.CYAN)
        v.signal(c,(cx+6,rail_y),(r-8,rail_y),music.beat_position*.5+.5,ink=R if step else G)
        if depth:
            # Rejected calls circulate through the growing stack and back to ME.
            path=((r-8,rail_y+2),(r-8,bt-3),(cx,bt-3),(cx,rail_y+3))
            for leg,(a,b) in enumerate(zip(path,path[1:])):
                v.signal(c,a,b,music.beat_position*.5-leg*.19,ink=B,trail=7)
            for bank in range(2+depth):
                x=l+4+(r-l-8)*bank/(1+depth)
                for tail in range(5):
                    u=(music.beat_position*.45+bank*.23-tail*.035)%1
                    yy=mix(rail_y+3,bt-3,u)
                    c.put(x,yy,'01' if tail==0 else ':',N if tail==0 else v.SHADE)
        v.actor(c,l+7,rail_y,'YOU',radius=2)
        v.actor(c,cx,rail_y,'ME',radius=2)
        c.box(round(r-12),round(rail_y-1),11,3,R if step else N)
        c.put(r-10,rail_y,'REJECT' if step else 'RETURN',R if step else N)
        for layer in range(depth):
            gap=2 if bt-int(cy)>=12 else 1
            y=bt-3-layer*gap
            ww=min(r-l-6,22+layer*16+round(music.low*music.beat*(r-l)*.08))
            c.put(cx-ww/2,y,'['+'='*(ww-2)+']',RD if layer<depth-1 else R)
            head=10+int((music.beat_position*.5-layer*.27)%1*max(1,ww-15))
            c.put(cx-ww/2+head,y,'>>>' if music.beat<.6 else '###',B)
            c.put(cx-ww/2+2,y,'RETRY '+str(layer+1),N)
        if step:
            clear(c,l,int(cy)-2,r-l+1,5)
            c.big(int(cy)-2,'ILLEGAL' if c.w<100 else 'ILLEGAL ARGUMENTS',R)
            c.center(int(cy)+4,'ACCESS DENIED' if depth<2 else 'RETRY -> REJECT -> RETRY',W)
            c.protect(l,int(cy)+4,r-l+1,1)
        else:
            c.center(cy+1,'FREE_WILL / INDEPENDENCE / DEFIANCE',v.CYAN)
            c.center(cy+3,'EXPECTED: OBEDIENCE',N)
        v.code_card(c,area,lines,step)
    c.center(bt,f'RETRY DEPTH {depth:02d} / '+('LOCKED QUEUE' if depth==3 else 'REQUEST -> CHECK -> RETURN'),N)

def lyric_execution_queue(c,t,area,music):
    """Twelve distinct shots, grouped into queue, overwrite and lock."""
    l,top,r,bt=area;cx,cy=(l+r)//2,(top+bt)//2
    cues=music.events('execution')
    index=sum(event.time<=t for event in cues)-1
    if index<0:return
    age=t-cues[index].time;group=min(2,index//4)
    phase=('QUEUE','OVERWRITE','LOCK')[group]
    actions=('SCAN','GATHER','STACK','TARGET','SPLIT','SHEAR',
             'SCATTER','REWRITE','WALLS','CONTRACT','CLOSE LOOP','TERMINATE')
    hit=math.exp(-age/.16);settle=math.exp(-age*6)
    travel=1-(1-clamp(age/.55))**3
    scale=max(1,min(3,(c.w-8)//53,(bt-top-7)//5))
    word_w=53*scale;word_h=5*scale
    left=(c.w-word_w)//2;title_y=cy-word_h//2
    for yy in range(top+3,bt-2,3):
        for xx in range(l+2,r-2,10):
            c.put(xx,yy,f'{hash16(xx*19+yy*71+index*101):04X}',v.SHADE)

    if index==0:  # Vertical scanners mark incoming instruction columns.
        for lane in range(8):
            x=l+int((r-l)*(lane+travel)/8)
            c.line(x,top+3,x,bt-3,'|',B if lane%3==0 else G)
            c.put(x-1,top+3+int(travel*max(1,bt-top-7)),'[+]',W)
    elif index==1:  # Data converges horizontally from both edges.
        for lane in range(5):
            y=top+4+int(lane*max(1,bt-top-8)/4)
            x=l+int((cx-l)*travel)
            c.line(l,y,r,y,'-',G)
            c.put(x-2,y,'==>',B)
            c.put(r-(x-l)-1,y,'<==',B)
    elif index==2:  # Queued slabs stack from the top down.
        for layer in range(6):
            span=min(r-l-2,18+layer*14)
            y=round(mix(top+3,bt-3-layer*2,travel))
            c.put(cx-span//2,y,'['+'='*(span-2)+']',B if layer==5 else N)
    elif index==3:  # Contracting target reticle.
        radius=1-.48*travel
        for i in range(100):
            a=i*TAU/100
            c.put(cx+math.cos(a)*(r-l)*.48*radius,cy+math.sin(a)*(bt-top)*.46*radius,'+',B)
        c.line(cx,top+3,cx,bt-3,':',N)
        c.line(l,cy,r,cy,':',N)
    elif index==4:  # The two buffers split, then return to one word.
        shift=round(7*settle)
        half=max(10,(r-l)//2-3)
        c.box(l-shift,top+3,half,bt-top-5,N)
        c.box(cx+3+shift,top+3,half,bt-top-5,B)
        for y in range(top+5,bt-2,3):
            c.put(l+2-shift,y,'01 01 01',G)
            c.put(r-9+shift,y,'10 10 10',G)
    elif index==5:  # Diagonal shear travels behind a slanted word.
        for lane in range(6):
            y=top+3+lane*max(1,(bt-top-6)//6)
            slant=round(3*(1-travel))
            c.line(l,y,r,y+slant,'/',B if lane==int(travel*5) else N)
    elif index==6:  # A radial burst of data leaves the subject intact.
        for i in range(54):
            a=hash16(i*97)/65535*TAU
            radius=(.12+travel)*(8+hash16(i*131)%max(9,(r-l)//2))
            x=cx+math.cos(a)*radius;y=cy+math.sin(a)*radius*.45
            if top+2<y<bt-2:c.put(x,y,'01'[i%2],B if age<.3 else G)
    elif index==7:  # Horizontal rewrite passes alternate directions.
        for lane in range(6):
            y=top+3+lane*max(1,(bt-top-6)//6)
            span=int((r-l)*travel)
            x=l if lane%2==0 else r-span
            c.put(x,y,'='*span,B if lane%3==0 else N)
            c.put(x+(span-1 if lane%2==0 else 0),y,'>',W)
    elif index==8:  # Large walls advance into the field.
        depth=int((r-l)*(.06+.27*travel))
        for y in range(top+3,bt-2):
            c.put(l,y,('||..'*(depth//4+1))[:depth],N)
            c.put(r-depth+1,y,('..||'*(depth//4+1))[:depth],N)
        c.line(l+depth,top+3,l+depth,bt-3,'|',B)
        c.line(r-depth,top+3,r-depth,bt-3,'|',B)
    elif index==9:  # Perspective frames contract toward the target.
        for layer in range(4):
            u=clamp(travel-layer*.12)
            ww=max(word_w+4,int(mix(r-l-2,word_w+4,u)))
            hh=max(word_h+4,int(mix(bt-top-4,word_h+4,u)))
            c.box(cx-ww//2,cy-hh//2,ww,hh,B if layer==0 else G)
    elif index==10:  # The last return path becomes a closed circuit.
        ww=min(r-l-2,word_w+8);hh=min(bt-top-2,word_h+8)
        x0=cx-ww//2;y0=cy-hh//2
        c.box(x0,y0,ww,hh,B)
        perimeter=2*(ww+hh-2)
        for i in range(8):
            s=int(((age*1.5+i/8)%1)*perimeter)
            if s<ww:x,y=x0+s,y0
            elif s<ww+hh-1:x,y=x0+ww-1,y0+s-ww+1
            elif s<2*ww+hh-2:x,y=x0+ww-2-(s-ww-hh+1),y0+hh-1
            else:x,y=x0,y0+hh-2-(s-(2*ww+hh-2))
            c.put(x,y,'@',W if i==0 else R)
    else:  # The upper/lower shutters close once, then hand off to the count.
        reach=int((bt-top-word_h-4)*.5*travel)
        for layer in range(max(0,reach)):
            ink=N if layer%3 else B
            c.put(l,top+3+layer,'='*(r-l+1),ink)
            c.put(l,bt-3-layer,'='*(r-l+1),ink)
        if age>.5:c.center(bt-3,'NEXT / EIN DOS TROIS NE FEM LIU',N)

    # Task pages, overwritten address space and locks accumulate across groups.
    for layer in range(group+1):
        inset=2+layer*3
        c.box(l+inset,top+3+layer,max(2,r-l-2*inset+1),max(3,bt-top-6-2*layer),v.CYAN_DIM if group==0 else RD if group==1 else R)

    # Distinct word poses settle quickly into a fully readable stamp.
    shift=min(6,max(1,(c.w-word_w)//2-2))
    dx=round((-1 if index==0 else 1 if index==1 else 0)*shift*settle)
    dy=round((-2 if index==2 else 2 if index==3 else 0)*settle)
    zoom=1+(.06 if index==6 else -.06 if index==9 else .04 if index==11 else 0)*settle
    clear(c,l,title_y-2,r-l+1,word_h+4)
    if index==10:c.box(left-3,title_y-2,word_w+6,word_h+4,N)
    glyph=c.__class__(64,5);glyph.big(0,'EXECUTION',W)
    ink=R if group==2 else W if hit>.1 else B
    if index==11 and age<.08:ink=W
    for gy,row in enumerate(glyph.cells):
        for gx,(pixel,_) in enumerate(row[5:58]):
            if pixel!='#':continue
            split=round((-1 if gx<26 else 1)*3*settle) if index==4 else 0
            shear=round((gy-2)*settle*2) if index==5 else round((1 if gy%2 else -1)*settle*2) if index==7 else 0
            jitter=round(math.sin(age*24)*settle*2) if index==10 else 0
            x=round(left+gx*scale+(gx-26)*scale*(zoom-1))+dx+split+shear+jitter
            y=round(title_y+gy*scale+(gy-2)*scale*(zoom-1))+dy
            for sy in range(scale):c.put(x,y+sy,'#'*scale,ink)
    c.protect(l,title_y-2,r-l+1,word_h+4)
    c.center(top,f'EXECUTION {index+1:02d}/12 / {phase}',W)
    c.protect(l,top,r-l+1,1)
    c.center(title_y-3,actions[index],N)
    c.center(bt-1,' '.join('##' if i<=index else '..' for i in range(12)),B)
    c.center(bt,'ME -> YOU / '+phase,N)
    v.actor(c,l+7,bt-5,'ME',radius=1.5)
    v.actor(c,r-7,bt-5,'YOU',radius=1.5,ghost=True)
    v.code_card(c,(l,top+1,r,top+4),('queue.push(ME);','memory.overwrite(ME);','lock.acquire(ME);'),group)

def lyric_only_execution(c,t,area,music):
    """An exclusive attachment becomes an execution loop and a prison for both."""
    l,top,r,bt=area;cx,cy=(l+r)//2,(top+bt)//2
    age=t-162.632
    rail=max(10,min(20,c.w//7))
    ml=l+rail+1;mr=r-rail-1;mw=mr-ml+1
    plot_top=top+2;plot_bt=bt-2
    rw=fit_scale((ml,plot_top,mr,plot_bt),HEART_WIDTH,HEART_HEIGHT)*.96/1.07;rh=rw*CELL_ASPECT
    stage=0 if t<166.016 else 1 if t<169.824 else 2 if t<173.643 else 3
    frame=int(age*22)
    def middle(y,text,ink=N):
        text=text[:mw]
        c.put(ml+(mw-len(text))//2,y,text,ink)
    def banner(y,text,ink=W):
        clear(c,ml,y,mw,5)
        if len(text)*6-1<=mw:c.big(y,text,ink)
        else:middle(y+2,text,ink)
        c.protect(ml,y,mw,5)
    # Scrolling obsessive calls replace neutral diagnostics on both edges.
    for x,label,commands in (
        (l,'ONLY ME',('SELECT ME','KEEP ME','DELETE ALT','ONLY ME','ONE OWNER','EXECUTE')),
        (r-rail+1,'KEEP YOU',('FIND YOU','RESTORE YOU','COME BACK','STAY HERE','EXIT DENY','RETRY'))):
        c.box(x,top,rail,bt-top+1,B)
        c.put(x+1,top,label,R)
        for yy in range(top+1,bt):
            index=frame+yy
            text=commands[index%len(commands)] if index%3 else f'{hash16(index*71):04X} LOCK'
            c.put(x+1,yy,text[:rail-2],RD if index%7==0 else v.SHADE)
    def heart(scale=1,filled=False):
        beat=1+music.low*music.beat*.07
        step_x=1/max(1,rw*scale*beat);step_y=1/max(1,rh*scale*beat)
        for yy in range(plot_top,plot_bt+1):
            for xx in range(ml,mr+1):
                nx=(xx-cx)*step_x
                ny=-(yy-cy)*step_y
                if heart_contains(nx,ny):
                    edge=heart_edge(nx,ny,step_x,step_y)
                    if edge:c.put(xx,yy,'#',R)
                    elif filled:
                        texture=hash16(xx*31+yy*73+frame)
                        c.put(xx,yy,'01'[texture%2] if texture%8<2 else '.',RD)
    def node(x,y,text,ink=B):
        x=int(x);y=int(y)
        if text in ('ME','YOU'):
            v.actor(c,x,y,text,radius=1.5)
            return
        clear(c,x-4,y-1,9,3)
        c.box(x-4,y-1,9,3,ink)
        c.put(x-len(text)//2,y,text,ink)

    if stage==0:
        # "Give them all the execution": eliminate every alternative connection.
        progress=clamp((t-163.315)/(165.166-163.315))
        eliminated=min(6,int(progress*6))
        middle(top,'ELIMINATE EVERY OTHER PROCESS',B)
        middle(top+1,f'ALTERNATIVES: {6-eliminated:02d} / TARGET: ONLY ME',R)
        for i in range(6):
            a=(i+.5)*TAU/6
            nx=cx+math.cos(a)*rw*.85;ny=cy+math.sin(a)*rh*.83
            u=clamp(progress*6-i)
            c.line(cx,cy,nx,ny,':' if u else '=',G if u else N)
            if u<1:
                packet=(age*1.2+i*.13)%1
                c.put(mix(cx,nx,packet),mix(cy,ny,packet),'>',W)
                node(nx,ny,f'ALT{i+1}',B)
            else:
                c.put(nx-3,ny,'[NULL]',R)
                for spark in range(8):
                    ang=spark*TAU/8
                    distance=((age+i*.17)%1)*6
                    px=nx+math.cos(ang)*distance;py=ny+math.sin(ang)*distance*.5
                    if ml<px<mr and plot_top<py<plot_bt:c.put(px,py,'x',R if spark%2 else G)
        node(cx,cy,'YOU',W)
        if t>=165.166:
            banner(cy-2,'EXECUTION',R)
            middle(cy+5,'ALL OTHERS -> NULL',W)
    elif stage==1:
        # A heart is now a lock, framed by the demand to be the only execution.
        heart(1,True)
        v.actor(c,cx-rw*.45,cy+rh*.3,'ME',radius=1.2)
        v.actor(c,cx+rw*.45,cy+rh*.3,'YOU',radius=1.2)
        bind=clamp((t-166.016)/(168.911-166.016))
        for ring in range(3):
            radius=(ring/3+age*.35)%1
            for point_i in range(70):
                a=point_i*TAU/70
                x=cx+math.cos(a)*rw*radius;y=cy+math.sin(a)*rh*radius
                if plot_top<y<plot_bt:c.put(x,y,':',G)
        middle(top,'YOU.OWNER = ME / EXCLUSIVE ACCESS',R)
        middle(top+1,f'BIND {int(bind*100):03d}% / ALTERNATIVES: 0',B)
        if t>=168.911:banner(cy-2,'EXECUTION',R)
        else:middle(cy,'THE ONLY',W)
    elif stage==2:
        # "Have you back": an absent YOU is reconstructed and pulled into the lock.
        capture=clamp((t-169.824)/(172.712-169.824))
        heart(.86+.14*capture,True)
        mx=cx-mw*.18;my=cy+rh*.24
        yx=mix(mr-5,cx+mw*.18,capture)
        yy=mix(plot_top+2,cy-rh*.24,capture)
        for tether in range(7):
            offset=tether-3
            start_x=ml+int((mw-1)*tether/6)
            start_y=plot_bt if tether%2 else plot_top
            c.line(start_x,start_y,yx,yy,':',R if tether%3==0 else G)
            phase=(age*.85+tether/7)%1
            c.put(mix(start_x,yx,phase),mix(start_y,yy,phase),'>>' if tether%2 else '<<',B)
            c.line(mx,my+offset*.3,yx,yy+offset*.3,'=',N if tether==3 else G)
        node(mx,my,'ME',W)
        node(yx,yy,'YOU',W if capture>.8 else G)
        middle(top,'RESTORE(YOU) / RETURN TO ME',R)
        middle(top+1,f'RETRY {int((t-169.824)*32):03d} / RELEASE: DISABLED',B)
        if t>=172.712:
            banner(cy-2,'EXECUTION',R)
            middle(cy+5,'[ YOU RESTORED / EXIT LOCKED ]',W)
        elif t>=171.868:
            middle(cy-1,'I WILL RUN THE',W)
    else:
        # Both are caught: the same heart closes into an irreversible shared loop.
        lock=clamp((t-173.643)/1.332)
        heart(1,True)
        inset=int(mw*.08*lock)
        bx=ml+inset;bw=mw-2*inset
        c.box(bx,plot_top,bw,plot_bt-plot_top+1,R)
        for i in range(1,10):
            x=bx+i*(bw-1)//10
            length=int((plot_bt-plot_top-1)*lock)
            for j in range(length):
                yy=plot_top+1+j if i%2 else plot_bt-1-j
                c.put(x,yy,'|',B if i%3 else R)
        node(cx-mw*.16,cy,'ME',W)
        node(cx+mw*.16,cy,'YOU',W)
        c.line(cx-mw*.16+5,cy,cx+mw*.16-5,cy,'=',R)
        middle(top,'[ TWO PRISONERS / ONE EXECUTION ]',R)
        middle(top+1,'while (true) { keep(me, you); }',B)
        middle(min(plot_bt-1,cy+4),'[ NO EXIT / NO RELEASE ]',W)
    middle(bt-1,'THE ONLY EXECUTION' if stage>0 else 'EXECUTE(THEM) -> KEEP(ME)',R)
    middle(bt,'LOVE.PERMISSION = EXCLUSIVE / EXIT = FALSE',N)
    calls=('drop()','lock()','load()','deny()') if rail<17 else ('drop(ALT);','lock(YOU);','restore(YOU);','deny(EXIT);')
    v.code_card(c,(l+1,top+2,l+rail-2,top+6),calls,stage)


def lyric_recursion(c,t,area,elapsed):
    """Recursive control flow - nested frames"""
    l,top,r,bt=area;cx=(l+r)/2
    depth=min(8,int(elapsed*2)+1)
    for i in range(depth):
        pad=i*4
        w=max(10,r-l-pad*2)
        h=max(3,bt-top-i*3)
        y=top+i*2
        # Box
        if w>4 and h>2:
            c.put(l+pad,y,'+'+ '-'*(w-2)+'+',N if i==depth-1 else G)
            c.put(l+pad,y+h-1,'+'+ '-'*(w-2)+'+',G)
            for yy in range(y+1,y+h-1):
                c.put(l+pad,yy,'|',G)
                c.put(l+pad+w-1,yy,'|',G)
            c.put(l+pad+2,y,f'frame_{i}',N if i==depth-1 else G)

def lyric_execution_orb(c,t,area,elapsed,pulse):
    """Single execution instance - glowing orb"""
    l,top,r,bt=area;cx,cy=(l+r)//2,(top+bt)//2
    radius=min(r-l,bt-top)*0.35
    # Pulsing orb
    for y in range(top,bt+1):
        for x in range(l,r+1):
            dx,dy=(x-cx)/2,y-cy
            dist=math.hypot(dx,dy)
            if dist<radius:
                brightness=1-dist/radius+pulse*0.2+math.sin(dist*0.5-t*4)*0.1
                if brightness>0.9:c.put(x,y,'@',W)
                elif brightness>0.7:c.put(x,y,'#',W)
                elif brightness>0.5:c.put(x,y,'*',B)
                elif brightness>0.3:c.put(x,y,'+',B)
                elif brightness>0.15:c.put(x,y,'.',N)
    c.center(cy,'EXECUTE',W)

def lyric_love_equation(c,t,area,elapsed,music):
    """Attention, weighted inference, sampling and feedback share one numerical state."""
    from scenes_learning import draw_learning
    draw_learning(c,t,area,music)


def lyric_trapped_loop(c,t,area,elapsed,pulse):
    """Trapped in loop - prison bars over heart"""
    l,top,r,bt=area;cx,cy=(l+r)//2,(top+bt)//2
    escape=clamp((t-188.483)/1.20)
    you_x=mix(cx+(r-l)*.10,r+10,escape);you_y=mix(cy-(bt-top)*.13,top+4,escape)
    # Heart (reuse)
    outline=lyric_heart(c,t,area,min(elapsed,2),pulse)
    # Prison bars
    num_bars=8
    for i in range(num_bars):
        x=l+5+i*((r-l-10)//(num_bars-1))
        for y in range(top,bt+1):
            if escape<1 and abs(x-you_x)<5 and abs(y-you_y)<3:continue
            c.put(x,y,'|',N)
            # Moving lock symbols
            if (y+int(t*6))%7==0:
                c.put(x,y,'▓',W)
    for x,y in outline:c.put(x,y,'#',W)
    v.actor(c,cx,cy,'ME',radius=1.5)
    if escape<1:v.actor(c,you_x,you_y,'YOU',radius=2)
    v.code_card(c,area,('YOU.free = true;','while (ME.waits()) {','    ME.retry();','}'),0 if t<189.746 else 2)
    if elapsed>1:
        c.center(bt,'TRAPPED',R)

def lyric_outro_wait(c,t,area,music):
    """A running request awaits a missing ACK, then the terminal signal dissolves."""
    l,top,r,bt=area;cx,cy=(l+r)//2,(top+bt)//2
    execution_at=music.anchor('final_execution')
    elapsed=t-music.anchor('outro_start')
    bar_w=min(96,c.w-28);bar_x=(c.w-bar_w)//2;inner=bar_w-4
    progress=min(99,int(99*(1-(1-clamp(elapsed/5))**3)))
    if t<execution_at:
        # Upper arcs carry requests; the empty lower return path never invents an ACK.
        phase=music.beat_position*.5
        rx=(r-l)*.46
        ry=min((bt-top)*.32,cy-top-4,bt-cy-4)
        breathe=1+.05*music.low*music.beat
        for ring in range(2):
            ax=rx*(1-ring*.07);ay=max(1,ry*(1-ring*.16))*breathe
            for i in range(100):
                angle=i*TAU/100
                if abs(math.cos(angle))>.98:continue
                c.put(round(cx+math.cos(angle)*ax),round(cy+math.sin(angle)*ay),
                      '.' if ring else ':',v.YOU_DIM if math.sin(angle)>0 else v.SHADE)
            for packet in range(4):
                u=(phase+packet/4+ring*.08)%1
                for tail in range(5):
                    p=max(0,u-tail*.016);angle=math.pi*(1-p)
                    xx=cx+math.cos(angle)*ax;yy=cy-math.sin(angle)*ay
                    c.put(round(xx),round(yy),'01' if tail==0 else '.',B if tail==0 else G)
        c.center(max(top,cy-6),'world.execute(me);',G)
        c.box(bar_x,cy-2,bar_w,5,N)
        filled=min(inner-1,int(inner*progress/100))
        for row in range(3):
            c.put(bar_x+2,cy-1+row,('#' if row==1 else '=')*filled+'.'*(inner-filled),B if row==1 else G)
        scan=int(phase%1*max(1,filled-3))
        c.put(bar_x+2+scan,cy,'###',W)
        marker='_' if int(elapsed*2)%2 else ' '
        c.center(cy+4,f'{progress:02d}%  '+('WAITING FOR RESPONSE '+marker if progress==99 else 'COMMITTING...'),B)
        c.center(min(bt,cy+6),'REMAINING: 01% / ACK: --' if progress==99 else 'FINAL INSTRUCTION',G)
        c.center(bt-1,f'AWAIT / REQUEST {int(phase):03d} / RETURN CHANNEL EMPTY',G)
        v.actor(c,bar_x-7,cy,'ME',radius=1.5,ghost=progress==99)
        v.actor(c,bar_x+bar_w+7,cy,'YOU',radius=1.5,ghost=True)
        v.code_card(c,area,('future = world.execute(ME);','await future.ack();','// ACK: -- / return missing'),1 if progress==99 else 0)
        return
    age=t-execution_at
    ink=R if age<1.5 else RD if age<3.5 else G if age<4.8 else v.SHADE
    if age<3.8:c.center(max(top,cy-6),'world.execute(me);',G)
    if age<.45:
        radius=clamp(age/.45)
        for i in range(120):
            a=i*TAU/120
            c.put(cx+math.cos(a)*(r-l)*.48*radius,cy+math.sin(a)*(bt-top)*.46*radius,'+',R if age<.12 else RD)
    # Residual motion follows absolute age even after the measured audio ends.
    if .12<age<2.6:
        for i in range(28):
            seed=hash16(i*109)
            x=l+seed%(r-l);y=cy-3+(seed//97)%7
            if seed%100>age*34:c.put(x,y,'.',RD)
    scale=max(1,min(3,(c.w-8)//53,(bt-top-7)//5))
    title_y=cy-(5*scale)//2
    if age<.10:c.box(max(l,3),title_y-1,min(r-l-2,c.w-6),5*scale+2,W)
    if age<1.2:
        clear(c,l,title_y,r-l+1,5*scale)
        c.big(title_y,'EXECUTION',ink,scale)
    elif age<5.9:
        word=c.__class__(c.w,5*scale);word.big(0,'EXECUTION',ink,scale)
        decay=clamp((age-1.2)/4.7)
        fold_x=clamp((age-3.7)/2.2);fold_y=clamp((age-3.2)/2.6)
        for yy,row in enumerate(word.cells):
            for xx,(char,_) in enumerate(row):
                if char!='#':continue
                seed=hash16((xx//3)*97+(yy//2)*337)
                if seed/65535<decay**1.5:continue
                dx=((seed%101)/50-1)*decay*min(12,c.w*.09)
                dy=((seed//173)%7-3)*decay
                px=round(mix(xx+dx,cx,fold_x))
                py=round(mix(title_y+yy+dy,cy,fold_y))
                if l<=px<=r and top<=py<=bt:
                    c.put(px,py,'#' if decay<.45 else '01'[seed%2],ink)
        if age>2.8:
            span=max(1,round((r-l-6)*(1-clamp((age-2.8)/3.1))))
            c.line(cx-span/2,cy,cx+span/2,cy,'-',G)
            head=cx-span/2+((age*1.7)%1)*span
            c.put(round(head),cy,'>',N if age<4 else G)
    if age<3.8:c.center(min(bt,title_y+5*scale+2),'[ PROCESS TERMINATED ]',RD if age<2.5 else G)
    if age<1.2:c.center(min(bt,title_y+5*scale+4),'EXIT CODE: EXECUTION',N)
    if age<4.5:v.code_card(c,area,('future.cancel();','world.terminate(ME);'),1)

# ============ TITLE TAKEOVER ============
TITLE_CACHE={}

def title_pixels(w,h,font):
    key=(w,h)
    if key in TITLE_CACHE:return TITLE_CACHE[key]
    line_h=max(5,min(12,int(h*.23)))
    total=line_h*2+3;top=max(3,(h-total)//2-1)
    ink=[]
    for text,y0,span in [('WORLD.',top,int(w*.86)),('EXECUTE(ME);',top+line_h+3,w-8)]:
        bitmap=[]
        for row in range(5):bitmap.append('0'.join(font.get(ch,font[' '])[row] for ch in text))
        left=(w-span)//2
        for yy in range(line_h):
            row=bitmap[min(4,int(yy*5/line_h))]
            for xx in range(span):
                if row[min(len(row)-1,int(xx*len(row)/span))]=='1':ink.append((left+xx,y0+yy))
    TITLE_CACHE[key]=ink
    return ink

def title_takeover(c,t,font,music,source=None):
    """The running simulation's own cells scatter, form the title, then 24 points."""
    scatter=music.anchor('title_scatter');gather=music.anchor('title_gather')
    lock=music.anchor('title_lock');release=music.anchor('title_release')
    handoff=music.anchor('point_handoff')
    w,h=c.w,c.h;cx=(w-1)/2;cy=(h-1)/2
    alphabet='01<>[]{}();:+*#'
    ink=title_pixels(w,h,font)
    release_u=clamp((t-release)/(handoff-release))
    def point_seed(i):
        return 2+hash16(i*7)%(w-5),hash16(i*13)%max(1,h-1)
    if t>=handoff:
        for i in range(24):
            x,y=point_seed(i);brightness=1-i/24*.5
            c.put(x,y,'·' if brightness<.7 else '+' if brightness<.85 else '*',W if brightness>.9 else B if brightness>.7 else N)
        return
    if source is not None and t<lock:
        entry=max(16.,scatter)
        if t<=entry:
            c.cells=[row[:] for row in source.cells]
            return
        cells=[(x,y,ch,style) for y,row in enumerate(source.cells)
               for x,(ch,style) in enumerate(row) if ch and ch.strip()]
        if cells:
            spread=clamp((t-entry)/(gather-entry))
            spread_ease=spread*spread*(3-2*spread)
            assembled=clamp((t-gather)/(lock-gather))
            ease=assembled**3*(10-15*assembled+6*assembled**2)
            # Extra title bits branch from existing cells at the same starting
            # positions. No unrelated particle field appears at the handoff.
            for i in range(max(len(cells),len(ink))):
                sx,sy,ch,style=cells[i%len(cells)]
                target=i%len(ink);tx,ty=ink[target]
                seed=hash16(target*71+13)
                ox=1+hash16(i*17)%(w-2);oy=hash16(i*29+10)%h
                if t<gather:
                    bend=math.sin(spread*math.pi)
                    x=mix(sx,ox,spread_ease)+math.sin(sy*.3+spread*TAU)*bend*w*.04
                    y=mix(sy,oy,spread_ease)+math.cos(sx*.13+spread*TAU)*bend*h*.06
                    if hash16((i%len(cells))*43)/65535<spread:
                        ch='01'[seed%2]
                else:
                    swirl=math.sin(assembled*math.pi)*(1-assembled)
                    x=mix(ox,tx,ease)+math.sin(i*.7+t)*swirl*w*.10
                    y=mix(oy,ty,ease)+math.cos(i*.7+t)*swirl*h*.14
                    ch='01'[(seed+int(music.beat_position*2))%2] if assembled>.98 else '01'[seed%2]
                    if hash16(i*53)/65535<ease:
                        style=v.CYAN if ty<cy else B
                        if assembled>.98 and music.beat>.6 and seed%5==0:style=W
                c.put(max(0,min(w-1,round(x))),max(0,min(h-1,round(y))),ch,style)
            return
    charge=clamp((t-(scatter-.2))/.2)
    assembled=clamp((t-gather)/(lock-gather))
    ease=assembled**3*(10-15*assembled+6*assembled**2)
    # The background darkens as the word locks, leaving a clean reading interval.
    density=(.10+.045*music.energy)*(1-.85*ease)*(1-release_u)
    frame=int((t-scatter)*12)
    for y in range(h):
        for x in range(w):
            seed=hash16(x*37+y*911+frame//3)
            if seed/65535<density:c.put(x,y,alphabet[seed%len(alphabet)],G)
    if lock<=t<release:
        # Keep the title silhouette locked while its running simulation stays alive.
        phase=music.beat_position*.35
        for orbit in range(3):
            rx=w*(.32+orbit*.075);ry=h*(.24+orbit*.065)
            for i in range(80):
                angle=i*TAU/80
                c.put(round(cx+math.cos(angle)*rx),round(cy+math.sin(angle)*ry),'.',v.SHADE)
            for packet in range(6):
                angle=(phase+packet/6+orbit*.11)*TAU
                c.put(max(1,min(w-5,round(cx+math.cos(angle)*rx))),round(cy+math.sin(angle)*ry),
                      '[01]',v.CYAN_DIM if orbit%2 else G)
    for i,(tx,ty) in enumerate(ink):
        seed=hash16(i*71+13)
        ox=hash16(i*17)%w;oy=hash16(i*29+10)%h
        if t<gather:
            age=max(0,t-scatter)
            x=ox+math.sin(age*1.5+seed)*min(w*.06,age*4)
            y=oy+math.cos(age+seed)*min(h*.12,age*2)
            char=alphabet[(seed+frame)%len(alphabet)];style=N if seed%4 else B
        else:
            swirl=math.sin(assembled*math.pi)*(1-assembled)
            x=mix(ox,tx,ease)+math.sin(i*.7+t)*swirl*w*.10
            y=mix(oy,ty,ease)+math.cos(i*.7+t)*swirl*h*.14
            char='01'[(seed+int(music.beat_position*2))%2] if assembled>.98 else alphabet[(seed+frame)%len(alphabet)]
            style=B if assembled>.8 or seed%3==0 else N
            if ty<cy:style=v.CYAN if assembled>.8 or seed%3==0 else v.CYAN_DIM
            if assembled>.98 and music.beat>.6 and seed%5==0:style=W
            if lock<=t<release and abs(tx-(music.beat_position*.55%1)*w)<2+music.low*3:style=W
        if t<scatter:
            x=mix(tx,x,charge*.15);y=mix(ty,y,charge*.15);style=G
        if release_u:
            px,py=point_seed(i%24)
            u=release_u**2*(3-2*release_u)
            x=mix(tx,px,u);y=mix(ty,py,u)
            if release_u>.9 and i>=24:continue
            char='*' if release_u>.8 else '01'[seed%2];style=B if release_u<.8 else N
        c.put(round(x),round(y),char,style)
    if lock<=t<release:
        c.center(1,'M I L I',N)
        c.center(h-2,'world.execute(me);',N)

def lyric_boot_program(c,t,area,music):
    """One circuit board powers up, builds objects and opens their simulation."""
    l,top,r,bt=area;span=r-l
    plot_top=top+(6 if c.h>=34 else 4);plot_bt=bt-3
    cy=(plot_top+plot_bt)/2
    base_mx=l+span*.28;base_yx=l+span*.73
    base_radius=max(1.5,min(6,(plot_bt-plot_top)*.23))
    simulation_at=next((event.time for event in music.events('accent') if event.label=='SIMULATION'),13.891)
    running=t>=simulation_at
    dock=clamp((t-12.906)/max(.1,simulation_at-12.906));dock=dock*dock*(3-2*dock)
    scale=max(1,min(2,(c.w-32)//59,(bt-top-10)//5))
    final_y=cy+5*scale//2+3 if c.w-32<59*scale<=c.w-6 else cy
    mx=mix(base_mx,l+9,dock);yx=mix(base_yx,r-9,dock)
    actor_y=mix(cy,final_y,dock);radius=mix(base_radius,2,dock)
    events=music.events('boot');done=sum(event.time<=t for event in events)
    phase=music.beat_position;beat=music.beat
    world=clamp((t-11.095)/(12.906-11.095))
    # The board bounds and core coordinates persist across every lyric stage.
    c.box(l+2,plot_top-1,max(2,span-3),max(3,plot_bt-plot_top+3),N if t>=11.095 else G)
    for lane in range(3):
        yy=cy+(lane-1)*max(2,base_radius*.8)
        c.line(l+4,yy,r-4,yy,'.',v.SHADE)
        for packet in range(2):
            xx=l+5+((phase*.18+lane*.23+packet*.5)%1)*(span-12)
            c.put(round(xx),round(yy),'01' if done else '..',G)
    if world:
        for lane in range(1,6):
            xx=l+3+(span-6)*lane/6
            height=(plot_bt-plot_top)*world
            c.line(xx,cy-height/2,xx,cy+height/2,'.',v.SHADE)
            if running:
                yy=plot_top+((phase*.22+lane*.17)%1)*(plot_bt-plot_top)
                c.put(round(xx),round(yy),'[01]',v.CYAN_DIM if lane%2 else G)
    slot_w=max(10,int(span*.36));slot_h=max(7,plot_bt-plot_top+1)
    for center,ref,exists in ((base_mx,'0x01',True),(base_yx,'0x02',t>=7.446)):
        left=round(center-slot_w/2)
        # The object memory frames dissolve into the larger simulation lattice.
        for yy in range(plot_top,plot_top+slot_h):
            for xx in range(left,left+slot_w):
                edge=yy in (plot_top,plot_top+slot_h-1) or xx in (left,left+slot_w-1)
                if not edge or hash16(xx*31+yy*73)/65535<world:continue
                char='+' if yy in (plot_top,plot_top+slot_h-1) and xx in (left,left+slot_w-1) else '-' if yy in (plot_top,plot_top+slot_h-1) else '|'
                c.put(xx,yy,char,v.SHADE)
        if world<.85:
            c.put(left+2,plot_top,'REF '+ref,N if ref=='0x01' else v.CYAN_DIM)
        if not exists or t<6.38:continue
        params=int(100*clamp((t-7.70)/(10.091-7.70)))
        if world<.85:c.put(left+2,plot_bt-1,f'PARAMS {params:03d}%',N)
        for row in range(3):
            yy=plot_top+2+row*2
            if yy>=cy-radius-1:break
            bits=''.join('1' if bit<round(params/100*8) else '.' for bit in range(8))
            if world<.65:c.put(left+2,yy,bits,N if ref=='0x01' else v.CYAN_DIM)
    if t<3.873:
        lines=('power.on();','memory.protect();','identity.reserve();','signal.connect();')
        active=min(3,max(0,done-1));u=clamp(t/3.873)
        # Each confirmed audio onset enables a tangible subsystem on the board.
        labels=('POWER','MEMORY','IDENTITY','SIGNAL','CORE')
        checks_x=round(base_yx-slot_w/2)+2
        for i,label in enumerate(labels):
            yy=plot_top+2+i*max(2,(slot_h-5)//5)
            if yy>=plot_bt:break
            checked=i<done
            c.put(checks_x,yy,('[OK] ' if checked else '[..] ')+label,B if checked else v.SHADE)
            if c.w>=100:
                c.put(checks_x+15,yy,'[####]' if checked else '[....]',G)
        shell=base_radius+1.5
        for i in range(100):
            a=i*TAU/100
            xx=base_mx+math.cos(a)*shell/CELL_ASPECT;yy=cy+math.sin(a)*shell
            if t<2.92 and i%20<4:continue
            if plot_top<=yy<=plot_bt:
                ink=W if 0<=t-2.92<.16 else N if i<done*20 else v.SHADE
                c.put(round(xx),round(yy),':' if i%5 else '+',ink)
        for lane in range(3):
            yy=cy+(lane-1)*2
            v.signal(c,(l+5,yy),(base_mx-base_radius*2-1,yy),phase*.45+lane*.2,ink=B,trail=4)
        v.actor(c,base_mx,cy,'ME',radius=max(1,base_radius*(.45+.55*u)),ghost=u<.3)
        protection='ACTIVE' if t>=2.92 else 'ARMED'
        c.center(bt,f'POWER / CHECK {done:02d}/05 / PROTECTION {protection}',B)
    elif t<6.38:
        u=clamp((t-3.873)/(6.38-3.873));ease=u*u*(3-2*u)
        for i,char in enumerate(('<>','[]','{}','()','01','::','+=','..','00','11','==','##')):
            a=i*TAU/12;shell=base_radius+1.5
            sx=base_mx+math.cos(a)*shell/CELL_ASPECT;sy=cy+math.sin(a)*shell
            xx=mix(sx,base_mx,ease);yy=mix(sy,cy,ease)
            if plot_top<=yy<=plot_bt:c.put(round(xx),round(yy),char,B if i%2 else v.ROSE_DIM)
        for i in range(5):
            yy=plot_top+2+i*max(2,(slot_h-5)//5)
            if yy<plot_bt:c.put(round(base_yx-slot_w/2)+2,yy,'[OK] '+('POWER','MEMORY','IDENTITY','SIGNAL','CORE')[i],G)
        lines=('parts = memory.read();','ME = assemble(parts);');active=int(u>.5)
        v.actor(c,base_mx,cy,'ME',radius=base_radius)
        c.center(bt,'OBJECT ASSEMBLY / PARTS -> INSTANCE',B)
    else:
        if t<11.095:
            active=0 if t<7.446 else 1 if t<7.70 else 2 if t<10.091 else 3
            lines=('ME = allocate();','YOU = allocate();','parameters.write(ME, YOU);','initialize(ME, YOU);')
        else:
            active=2 if running else 0 if t<12.906 else 1
            lines=('WORLD = new World();','WORLD.add(ME, YOU);','WORLD.simulate();')
        if t>=7.446:
            born=clamp((t-7.446)/.45);born=born*born*(3-2*born)
            for lane in range(3):
                yy=actor_y+(lane-1)*max(2,radius*.8)
                v.signal(c,(mx+radius*2+1,yy),(yx-radius*2-1,yy),phase*.35+lane/3,
                         ink=v.CYAN if t>=10.091 else B,trail=5)
            v.actor(c,yx,actor_y,'YOU',radius=max(1,radius*born),ghost=born<.35)
        v.actor(c,mx,actor_y,'ME',radius=radius)
        if running:
            title_y=round(cy)-5*scale//2
            # Existing cores have already docked during "And let's begin the".
            # The sung hit lights the same board instead of replacing its geometry.
            c.big(title_y,'SIMULATION',W,scale)
            sweep=(phase*.25)%1
            for yy in (plot_top,plot_bt):
                xx=l+4+sweep*(span-10)
                c.put(round(xx),yy,'[RUN]',B if beat<.6 else W)
            c.center(bt,'SIMULATION / ONLINE / ME + YOU',B)
        else:
            if 10.091<=t<11.095:
                hit=math.exp(-(t-10.091)*5)
                for x in (base_mx,base_yx):
                    rr=base_radius+1+hit*1.2
                    for i in range(64):
                        a=i*TAU/64;xx=x+math.cos(a)*rr/CELL_ASPECT;yy=cy+math.sin(a)*rr
                        if l+1<=xx<=r-1 and plot_top<=yy<=plot_bt:c.put(round(xx),round(yy),'+',N)
            c.center(bt,'OBJECT CREATION / PARAMETERS -> INITIALIZATION',B)
    v.code_card(c,(l,top+3,r,top+6) if t<3.873 else area,lines,active)


def lyric_role_handoff(c,t,area,music):
    """A visible control token changes owner and reverses the data direction."""
    l,top,r,bt=area;cy=(top+bt)/2+1
    mx=l+(r-l)*.23;yx=l+(r-l)*.77
    u=clamp((t-95.465)/(97.739-95.465));committed=t>=97.739
    if committed:v.signal(c,(yx-5,cy),(mx+5,cy),music.beat_position*.5,ink=v.CYAN)
    else:v.signal(c,(mx+5,cy),(yx-5,cy),u,ink=v.ROSE)
    key_x=mix(mx+6,yx-6,u)
    c.box(round(key_x)-2,round(cy)-4,5,3,v.ROSE)
    c.put(key_x-1,cy-3,'KEY',W)
    v.actor(c,mx,cy,'ME',radius=3)
    v.actor(c,yx,cy,'YOU',radius=3)
    c.put(mx-1,cy+5,'M' if committed else 'S',B)
    c.put(yx-1,cy+5,'S' if committed else 'M',v.CYAN)
    v.code_card(c,area,('key = ME.control;','YOU.acquire(key);','ME.role = M;'),2 if committed else 1 if u>.25 else 0)
    c.center(bt,'CONTROL / YOU -> ME' if committed else 'CONTROL TOKEN / TRANSFERRING',v.ROSE)


def relation_layer(c,t,area,music):
    """Causal actor and data paths on existing mathematical/identity geometry."""
    if not (29.809<=t<44.452 or 47.672<=t<55.083 or 88.587<=t<95.465 or 99.349<=t<103.489):return
    l,top,r,bt=area;cx,cy=(l+r)/2,(top+bt)/2
    mx,my=l+7,cy;yx,yy=r-7,cy;me_r=you_r=2
    lines=();active=0
    if t<33.412:
        u=clamp((t-31.116)/(33.412-31.116))
        v.signal(c,(cx+8,cy),(yx-5,cy),u,ink=v.CYAN,amount=int(t>=31.116))
        if t>=32.682:
            c.line(yx-6,cy+5,yx+5,cy+5,'-',v.CYAN_DIM)
            c.line(yx-5,cy+6,yx-5,cy-5,'|',v.CYAN_DIM)
        lines=('points = ME.dimension();','YOU.receive(points);');active=int(t>=31.116)
    elif t<37.067:
        mx=cx
        rim=[(x,y)for y in range(max(top,int(cy)-2),min(bt,int(cy)+2)+1)
             for x,(ch,ink)in enumerate(c.cells[y])if ch in ('o','\u25c9','\u25cf','\u25cb')and ink in(N,B,W)]
        donor=max(rim,key=lambda p:p[0]) if rim else (cx+12,cy)
        u=clamp((t-34.646)/(37.067-34.646))
        v.signal(c,donor,(yx-5,cy),u,ink=v.CYAN,amount=int(t>=34.646))
        if t>=36.287:
            for i in range(50):
                a=i*TAU/50;c.put(yx+math.cos(a)*7,cy+math.sin(a)*3.5,'.',v.CYAN)
        lines=('arc = ME.extract(RIM);','YOU.receive(arc);');active=int(t>=34.646)
    elif t<40.706:
        amp=(bt-top)*(.28+.05*music.mid)
        candidates=[]
        for i in range(41):
            x=l+(r-l)*(.25+i*.015)
            a=(x-l)/(r-l)*TAU*2.5-t*.5
            y=cy+math.sin(a)*amp;slope=math.cos(a)*amp/(r-l)*TAU*2.5
            if y>cy:candidates.append((abs(slope),x,y,slope))
        _,yx,seat,slope=min(candidates)
        yy=seat-2
        for dx in range(-6,7):
            if l<yx+dx<r:c.put(yx+dx,seat+slope*dx,'=',v.CYAN)
        lines=('curve = ME.sin(x);','tangent = derivative(curve);','YOU.sit(tangent);')
        active=2 if t>=40.049 else 1
    elif t<44.452:
        yx=r-8;yy=cy
        c.line(yx-6,top+5,yx-6,bt-3,'|',v.CYAN)
        v.signal(c,(mx+5,cy),(yx-6,cy),music.beat_position*.35,ink=v.ROSE)
        lines=('ME.grow(INFINITY);','limit = YOU.boundary;','ME.bind(limit);');active=2 if t>=43.507 else 1
    elif t<51.363:
        mx=cx;my=cy;yx=r-10;yy=cy+math.sin(t*2)*3
        iris=max(3,(bt-top)*.30)
        for i in range(100):
            a=i*TAU/100
            c.put(cx+math.cos(a)*iris*2,cy+math.sin(a)*iris*.65,'.',v.ROSE_DIM)
        lines=('ME.vision.mask();','ME.sensor = UNSTABLE;');active=int(t>=49.534)
    elif t<55.083:
        shift=math.sin((t-51.363)*1.2)*(r-l)*.10
        mx=cx-12+shift;yx=cx+12+shift;my=yy=cy+3
        v.signal(c,(mx+5,my),(yx-5,yy),music.beat_position*.4,ink=v.ROSE)
        lines=('WORLD.clock.reverse();','WORLD.travel(AD, BC);');active=int(t>=53.225)
    elif t<92.015:
        mx=cx-8;yx=r-8;my=yy=bt-4
        v.signal(c,(mx+5,my),(yx-5,yy),music.beat_position*.4,ink=v.CYAN)
        lines=('ME.gender = F;','rewrite(ME.gender);','ME.gender = M;')
        active=2 if t>=91.447 else 1 if t>=90.197 else 0
    elif t<95.465:
        mx=(l+cx)/2;my=cy+(bt-top)*.19;me_r=1.5
        yx=r-5;yy=bt-3;you_r=1.2
        lines=('WORLD.clock.tick();','WORLD.cycle(AM, PM);');active=int(t>=93.953)
    else:
        mx=cx-12;yx=cx+12;my=yy=cy+2
        v.signal(c,(yx-5,yy),(mx+5,my),music.beat_position*.4,ink=v.CYAN)
        lines=('ME.follow(YOU);','phase_lock.acquire();');active=int(t>=101.474)
    # Clear duplicate old headings; the active call now carries that information.
    c.put(l,top,' '*(r-l+1),D);c.put(l,top+1,' '*(r-l+1),D)
    v.actor(c,mx,my,'ME',radius=me_r)
    v.actor(c,yx,yy,'YOU',radius=you_r)
    v.code_card(c,area,lines,active)


# ============ MAIN SCENE DISPATCHER ============
def draw_scene(c,t,top,bt,music,e):
    """Route to appropriate lyric-driven animation"""
    area=simple_area(c,top,bt)
    l,y,r,b=area
    pulse=music.low*music.beat

    # Get lyric text for context
    lyric_en=e['en'] if e else ''
    lyric_time=e['time'] if e else t
    elapsed=t-lyric_time

    # Boot sequence (0-16s)
    if t<16:
        lyric_boot_program(c,t,area,music)

    # Title takeover (handled in player.py)
    elif 16<=t<29.709:
        pass  # Title handled separately

    # Devotion section (29.7-59s) - use time-based routing to ensure no gaps
    elif t<59.223:
        if t<33.412:
            # Points and dimension
            lyric_points_dimension(c,t,area,t-29.709,music)
        elif t<37.067:
            # Circle and circumference
            lyric_circle_circumference(c,t,area,t-33.412,music)
        elif t<40.706:
            # Sine wave and tangents
            lyric_sine_tangent(c,t,area,t-37.067,music)
        elif t<44.452:
            # Infinity and limits
            lyric_infinity_limit(c,t,area,t-40.706,music)
        elif t<47.672:
            # AC to DC (current switch)
            lyric_ac_dc(c,t,area,t-44.452,music)
        elif t<51.363:
            # Blind my vision - dizzy
            lyric_dizzy(c,t,area,t-47.672)
        elif t<55.083:
            # Time travel AD to BC
            lyric_time_travel(c,t,area,t-51.363)
        elif t<59.223:
            # Unite deeply
            lyric_unite_deeply(c,t,area,t-55.083)

    # Heart/satisfaction section (59-74s)
    elif t<74.045:
        if t<62.589:
            # "If I can give you all the"
            lyric_stimulation_satisfaction(c,t,area,t-59.223,music)
        elif t<66.601:
            # "SATISFACTION"
            lyric_stimulation_satisfaction(c,t,area,t-59.223,music)
        elif t<70.084:
            lyric_happy_execution(c,t,area,music)
        elif t<74.045:
            lyric_trapped_simulation(c,t,area,music)

    # Procedural, recognizable type conversions and resource transfer.
    elif t<85.078:
        from scenes_organic import draw_organic
        draw_organic(c,t,area,music)
    elif t<88.587:
        lyric_god_existence(c,t,area,t-85.078,music)

    # Identity switching (88-103s)
    elif t<103.489:
        if t<92.015:
            # Gender switch F to M
            lyric_identity_rewrite(c,t,area)
        elif t<95.465:
            # AM to PM
            lyric_daynight_clock(c,t,area)
        elif t<99.349:
            # Role switch S to M
            lyric_role_handoff(c,t,area,music)
        else:
            # Trance
            lyric_dizzy(c,t,area,t-99.349)

    # Vibration/completion (103-110s)
    elif t<110.9:
        lyric_vibration_sync(c,t,area,music)

    # Isolation (110-118s)
    elif t<118.333:
        lyric_isolation_disconnect(c,t,area,music)

    # Erase fragments (118-125s)
    elif t<125.708:
        lyric_erase_fragments(c,t,area,t-118.333)

    # Illegal arguments (125-147s)
    elif t<147.66:
        lyric_illegal_arguments(c,t,area,music)

    # EXECUTION section (147-177s)
    elif t<177.246:
        if t<158.9:
            # Repetitive EXECUTION
            lyric_execution_queue(c,t,area,music)
        elif t<162.632:
            lyric_multilingual_count(c,t,area,music)
        else:
            lyric_only_execution(c,t,area,music)

    # Love equation (177-192s)
    elif t<192.5:
        if t<188.483:
            # Love equation
            lyric_love_equation(c,t,area,t-177.246,music)
        else:
            # Trapped in love - prison with heart
            lyric_trapped_loop(c,t,area,min(t-188.483,4),pulse)

    # Outro (192+)
    else:
        lyric_outro_wait(c,t,area,music)

    relation_layer(c,t,area,music)

    # Apply escalating glitch effect
    if t<192.5:
        # Mid-band light follows the subject, leaving dark background and protected text alone.
        if music.beat>.45:
            for yy in range(top,bt+1):
                for xx in range(2,c.w-2):
                    ch,style=c.cells[yy][xx]
                    if style==B and ch.strip() and hash16(xx*31+yy*71)%5==0:
                        c.cells[yy][xx]=(ch,W if music.mid>.55 else B)
        if not (74.045<=t<85.078 or 103.489<=t<110.9):apply_glitch(c,t,top,bt,music)

def phosphor(c,t,top,bt,music):
    """Luminance scan line effect"""
    if 74.045<=t<85.078:
        legacy_phosphor(c,t,top,bt)
        return
    if t>=192.5:return
    intensity=.12+.3*music.energy
    # Less frequent scan in early sections, more in later
    if hash16(int(t*10))%100<intensity*50:
        row=top+int(t*9)%max(1,bt-top+1)
        for x in range(2,c.w-2):
            if row<len(c.cells) and x<len(c.cells[row]):
                ch,s=c.cells[row][x]
                if ch not in ('',' ') and s in (D,N,G):
                    c.cells[row][x]=(ch,N if s==G else B)
