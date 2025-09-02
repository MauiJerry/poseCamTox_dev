
import math
def cook(scriptOP):
    owner = scriptOP.parent()
    parent = owner.parent()
    src = parent.op('pose_landmarks_in') or parent.op('lag1')
    if src is None:
        return

    start = owner.par.start_lm.eval().strip()
    end   = owner.par.end_lm.eval().strip()

    def ch(name):
        c = src.channels.get(name)
        return c[0] if c and len(c) else 0.0

    def get_xyv(label):
        if label == 'hips_mid':
            lx, ly, lv = get_xyv('left_hip'); rx, ry, rv = get_xyv('right_hip')
            return ((lx+rx)*0.5, (ly+ry)*0.5, min(lv,rv))
        if label == 'shoulders_mid':
            lx, ly, lv = get_xyv('left_shoulder'); rx, ry, rv = get_xyv('right_shoulder')
            return ((lx+rx)*0.5, (ly+ry)*0.5, min(lv,rv))
        x = ch(f'{label}_x'); y = ch(f'{label}_y'); v = ch(f'{label}_z')
        v = max(0.0, min(1.0, v))
        return (x,y,v)

    outW = max(1, int(parent.par.output_resx))
    outH = max(1, int(parent.par.output_resy))
    flip = bool(parent.par.flip_y)

    Ax, Ay, Av = get_xyv(start)
    Bx, By, Bv = get_xyv(end)

    Axp = Ax * outW; Ayp = (1.0 - Ay) * outH if flip else Ay*outH
    Bxp = Bx * outW; Byp = (1.0 - By) * outH if flip else By*outH

    Tx = 0.5*(Axp+Bxp); Ty = 0.5*(Ayp+Byp)
    dx = (Bxp-Axp); dy = (Byp-Ayp)
    LenPx = (dx*dx+dy*dy)**0.5
    AngDeg = math.degrees(math.atan2(dy,dx))

    vis = min(Av,Bv); vt = float(parent.par.vis_thresh)
    Alpha = 0.0 if vis<=1e-6 else max(0.0, min(1.0,(vis-vt)/max(1e-6,1.0-vt)))

    scriptOP.clear()
    for n,v in [('Tx',Tx),('Ty',Ty),('LenPx',LenPx),('AngDeg',AngDeg),('Alpha',Alpha),
                ('Ax',Axp),('Ay',Ayp),('Bx',Bxp),('By',Byp)]:
        c = scriptOP.appendChan(n); c[0]=v
