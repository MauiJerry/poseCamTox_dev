# td/scripts/efx_lines_sop.py
# Create poly lines between landmark pairs defined in td/data/skeleton_edges.csv

def onCook(scriptOp):
    ch = op('in_chop'); edges = op('skeleton_edges')
    scriptOp.clear()
    if not ch or not edges or edges.numRows < 2:
        return

    # Build a quick name → (x,y,z) lookup for person 1
    def get(a): return ch[a].eval() if a in ch else None
    pos = {}
    for c in ch.chans:
        if c.name.startswith('p1_') and (c.name.endswith('_x') or c.name.endswith('_y') or c.name.endswith('_z')):
            base = c.name[:-2]
            if base not in pos:
                x = get(base + 'x'); y = get(base + 'y'); z = get(base + 'z')
                if x is not None and y is not None and z is not None:
                    pos[base.replace('p1_', '')] = (x, y, z)

    # Edges CSV has headers: a,b (landmark names)
    for r in range(1, edges.numRows):
        a = edges[r, 'a'].val; b = edges[r, 'b'].val
        pa = pos.get(a); pb = pos.get(b)
        if not pa or not pb: continue
        i0 = scriptOp.appendPoint(pa); i1 = scriptOp.appendPoint(pb)
        prim = scriptOp.appendPoly(2, closed=False, addPoints=False)
        prim[0].point = i0; prim[1].point = i1
    return
