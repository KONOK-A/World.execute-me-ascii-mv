"""Shared semantic ink and small, audio-time-driven program-world primitives."""
import math

D,N,B,W,R,G,K,RD=range(8)
CYAN,CYAN_DIM,CYAN_HIGH,ROSE,ROSE_DIM,GREEN,GREEN_HIGH,VIOLET,VIOLET_HIGH,SHADE,NEUTRAL=range(8,19)
TOMATO,TOMATO_DIM,TOMATO_HIGH=range(19,22)
ME,ME_DIM,YOU,YOU_DIM=B,D,CYAN,CYAN_DIM
CELL_ASPECT=.5
STYLES={
    D:'\x1b[0;38;5;137m',N:'\x1b[0;38;5;215m',B:'\x1b[1;38;5;221m',
    W:'\x1b[1;38;5;230m',R:'\x1b[1;38;5;203m',G:'\x1b[0;38;5;94m',
    K:'\x1b[0;38;5;58m',RD:'\x1b[0;38;5;131m',
    CYAN:'\x1b[1;38;5;81m',CYAN_DIM:'\x1b[0;38;5;24m',CYAN_HIGH:'\x1b[1;38;5;159m',
    ROSE:'\x1b[1;38;5;175m',ROSE_DIM:'\x1b[0;38;5;132m',
    GREEN:'\x1b[0;38;5;71m',GREEN_HIGH:'\x1b[1;38;5;114m',
    VIOLET:'\x1b[0;38;5;97m',VIOLET_HIGH:'\x1b[1;38;5;141m',
    SHADE:'\x1b[0;38;5;238m',NEUTRAL:'\x1b[0;38;5;244m',
    TOMATO:'\x1b[1;38;5;202m',TOMATO_DIM:'\x1b[0;38;5;124m',TOMATO_HIGH:'\x1b[1;38;5;209m',
}


def clamp(x,a=0.,b=1.):return min(b,max(a,x))
def mix(a,b,u):return a+(b-a)*u


def actor(c,x,y,role='ME',radius=2,signal=1.,label=True,ghost=False):
    """Draw distinct object cores; returns the complete character-space bounds."""
    if role not in ('ME','YOU'):raise ValueError('unknown object role: '+role)
    r=max(1.,float(radius));rx=r/CELL_ASPECT
    ink,dim=(ME,ME_DIM) if role=='ME' else (YOU,YOU_DIM)
    if ghost or signal<.25:ink=dim
    x0,x1=math.ceil(x-rx),math.floor(x+rx)
    y0,y1=math.ceil(y-r),math.floor(y+r)
    def inside(xx,yy):
        dx=abs(xx-x)/rx;dy=abs(yy-y)/r
        return dx+dy<=1 if role=='ME' else dx*dx+dy*dy<=1
    for yy in range(y0,y1+1):
        for xx in range(x0,x1+1):
            if not inside(xx,yy):continue
            edge=not all(inside(xx+dx,yy+dy) for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)))
            c.put(xx,yy,'#' if edge else '.',ink if edge else dim)
    if label:
        left=round(x)-len(role)//2;row=round(y)
        c.put(left,row,role,ink)
        c.protect(left,row,len(role),1)
    return x0,y0,x1,y1


def code_card(c,area,lines,active=0):
    """Show the current causal step, with four lines at most (two on small grids)."""
    l,top,r,bt=area
    count=min(2 if c.w<100 or c.h<34 else 4,bt-top+1)
    width=min(r-l+1,max(24,c.w//2),54)
    if not lines or count<1:return l,top,l,top
    active=max(0,min(len(lines)-1,active));start=max(0,active-count+1)
    shown=lines[start:start+count]
    for offset,line in enumerate(shown):
        selected=start+offset==active
        text=('> ' if selected else '  ')+line[:max(0,width-2)]
        c.put(l,top+offset,text,W if selected else SHADE)
        c.protect(l,top+offset,len(text),1)
    return l,top,l+width-1,top+len(shown)-1


def signal(c,start,end,phase,ink=B,trail=3,track=True,amount=1.):
    """A directed packet and its trail; all positions derive from the supplied phase."""
    x0,y0=start;x1,y1=end
    if track:c.line(x0,y0,x1,y1,'.',SHADE)
    if amount<=0:return
    u=phase%1
    for tail in range(max(1,trail),-1,-1):
        p=max(0,u-tail*.035)
        c.put(round(mix(x0,x1,p)),round(mix(y0,y1,p)),
              '>' if tail==0 and x1>=x0 else '<' if tail==0 else '.',ink if tail==0 else G)


def backdrop(c,t,area,density=1):
    """Quiet circuit traces; never a competing wall of random log text."""
    l,top,r,bt=area;span=r-l
    if span<8 or bt-top<7:return
    count=min(8,3+int(density*2)) if c.w>=100 else 3
    for i in range(count):
        x=l+2+int((span-5)*(i+.5)/count)
        y=top+4+(i*7+int(t*.5))%max(1,bt-top-6)
        c.put(x,y,'01' if i%2 else '..',SHADE)
