# PoseEffect_Dots / fxCore / landmark_to_instances (Script CHOP)
# Builds instancing attributes for a dot per landmark.
# Uses inMeta (Table DAT) for image_width/height as per PoseEffectMASTER guidance.

import hashlib

def _fx(): return parent()  # fxCore COMP

def _par_val(name, default=None):
    p = getattr(_fx().par, name, None)
    if not p: return default
    try:
        # return tuple for color, scalar otherwise
        return tuple(p.eval()) if getattr(p, 'tupletSize', 1) > 1 else p.eval()
    except:
        return p.eval() if hasattr(p, 'eval') else default

def _meta_int(row, default):
    """Read guarded meta from inMeta Table DAT (row key, 'value' column)."""
    meta = op('inMeta')  # this is provided/guarded by MASTER
    try:
        cell = meta[row, 'value']
        return int(cell.val) if cell and cell.val != '' else int(default)
    except:
        return int(default)

def _uv_to_ndc(x, y):
    # UV [0..1] → NDC [-1..1], Y-up
    return (x * 2.0 - 1.0, (1.0 - y) * 2.0 - 1.0)

def _hash_color(name):
    # Deterministic pastel-ish color per landmark name
    h = hashlib.md5(name.encode('utf8')).digest()
    r = (h[0] / 255.0) * 0.7 + 0.3
    g = (h[1] / 255.0) * 0.7 + 0.3
    b = (h[2] / 255.0) * 0.7 + 0.3
    return (r, g, b)

def cook(scriptOP):
    scriptOP.clear()

    # --- Inputs ---
    skel = scriptOP.inputs[0] if scriptOP.numInputs >= 1 else None
    if not skel or skel.numChans == 0:
        return

    # --- Read meta via inMeta (guarded) ---
    canvas_w = _meta_int('image_width',  1280)
    canvas_h = _meta_int('image_height', 720)

    # --- Style params ---
    colorType = str(_par_val('ColorType', 'solid')).strip().lower()   # 'solid'|'random'
    baseColor = _par_val('Color', (1.0, 1.0, 1.0))                    # RGB
    dotSizePx = float(_par_val('DotSize', 8.0))

    # --- Landmark list from *_x / *_y pairs ---
    names = []
    for ch in skel.chans():
        nm = ch.name
        if nm.endswith('_x'):
            base = nm[:-2]
            if skel.chan(base + '_y') is not None:
                names.append(base)
    names.sort()
    n = len(names)
    if n == 0:
        return

    # --- Output channels (1 sample per landmark / instance) ---
    scriptOP.numSamples = n
    tx  = scriptOP.appendChan('tx')
    ty  = scriptOP.appendChan('ty')
    scl = scriptOP.appendChan('scale')
    rch = scriptOP.appendChan('r')
    gch = scriptOP.appendChan('g')
    bch = scriptOP.appendChan('b')
    ach = scriptOP.appendChan('a')

    # Pixel-to-NDC scale (ortho camera width = 2)
    pixel_to_ndc = 2.0 / max(1.0, float(canvas_h))
    per_instance_scale = dotSizePx * pixel_to_ndc

    # Solid color (RGB) → use full alpha by default
    if isinstance(baseColor, (tuple, list)):
        base_r = float(baseColor[0] if len(baseColor) > 0 else 1.0)
        base_g = float(baseColor[1] if len(baseColor) > 1 else 1.0)
        base_b = float(baseColor[2] if len(baseColor) > 2 else 1.0)
    else:
        base_r, base_g, base_b = 1.0, 1.0, 1.0

    for i, base in enumerate(names):
        x = skel[base + '_x'][0] if skel.chan(base + '_x') else 0.5
        y = skel[base + '_y'][0] if skel.chan(base + '_y') else 0.5

        X, Y = _uv_to_ndc(float(x), float(y))
        tx[i], ty[i], scl[i] = X, Y, per_instance_scale

        if colorType.startswith('random'):
            cr, cg, cb = _hash_color(base)
            rch[i], gch[i], bch[i], ach[i] = cr, cg, cb, 1.0
        else:
            rch[i], gch[i], bch[i], ach[i] = base_r, base_g, base_b, 1.0

    return
