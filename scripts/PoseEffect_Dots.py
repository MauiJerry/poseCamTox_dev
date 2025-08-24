# PoseEffect_Dots.py
# Script CHOP for PoseEffect_Dots / fxCore
# Input 0: single-person skeleton CHOP with channels like "<name>_x", "<name>_y" in UV [0..1]
# Optional meta sources (priority):
#   1) inMeta Table DAT inside fxCore: rows: image_width|value, image_height|value, aspect|value
#   2) Input 1 CHOP with channels image_width, image_height
#   3) CanvasW / CanvasH custom parameters on fxCore
#
# Visual params (fxCore custom parameters; 'Ui' prefix is fine too):
#   - ColorType  (menu: 'solid' | 'random')    # also accepts ColorMode ('Fixed'|'RandomPerLandmark')
#   - Color      (RGB or RGBA)
#   - DotSize    (float, pixels)
# Optional extras supported if present:
#   - Opacity (float 0..1)   # if not present, alpha comes from Color[3] or defaults to 1
#   - Origin  (menu UV_0_1 | NDC_-1_1), default UV_0_1
#   - CanvasW / CanvasH (ints) used as fallback if meta missing

import hashlib

# ---------- helpers ----------

def _fx():
    return parent()

def _get_par_case_insensitive(name, default=None):
    core = _fx()
    # direct attribute first (fast path)
    p = getattr(core.par, name, None)
    if p is not None:
        return p
    # case-insensitive scan
    lname = name.lower()
    for cp in core.customPars:
        if cp.name.lower() == lname:
            return cp
    return default

def _eval_par_value(name, default=None):
    p = _get_par_case_insensitive(name)
    if not p:
        return default
    try:
        # tuple vs scalar
        if getattr(p, 'tupletSize', 1) > 1:
            return tuple(p.eval())
        return p.eval()
    except Exception:
        try:
            return p.eval()
        except Exception:
            return default

def _meta_from_inMeta(row_name, fallback):
    """Read numeric value from local inMeta Table DAT (rows: name | value)."""
    try:
        meta = op('inMeta')
        if not meta or not meta.isDAT:
            return int(fallback)
        cell = meta[row_name, 'value']
        if not cell or cell.val.strip() == '':
            return int(fallback)
        return max(1, int(float(cell.val)))
    except Exception:
        return int(fallback)

def _meta_from_input_chop(chop_input, chan_name, fallback):
    try:
        if chop_input:
            ch = chop_input.chan(chan_name)
            if ch and ch.numSamples > 0:
                return max(1, int(float(ch[0])))
    except Exception:
        pass
    return int(fallback)

def _image_dims(scriptOP):
    """image_width/height: inMeta DAT → input1 CHOP → CanvasW/H params → safe defaults."""
    # 1) inMeta DAT
    cw = _eval_par_value('CanvasW', 1280)
    ch = _eval_par_value('CanvasH', 720)
    w = _meta_from_inMeta('image_width',  cw if cw is not None else 1280)
    h = _meta_from_inMeta('image_height', ch if ch is not None else 720)

    # 2) CHOP input 1 (override if present)
    if len(scriptOP.inputs) >= 2 and scriptOP.inputs[1] is not None:
        w = _meta_from_input_chop(scriptOP.inputs[1], 'image_width',  w)
        h = _meta_from_input_chop(scriptOP.inputs[1], 'image_height', h)

    # 3) final guard
    return max(1, int(w)), max(1, int(h))

def _uv_to_ndc(x, y):
    """UV [0..1] → NDC [-1..1], Y up."""
    return (x * 2.0 - 1.0, (1.0 - y) * 2.0 - 1.0)

def _hash_color(name):
    """Deterministic pastel color per landmark base name."""
    h = hashlib.md5(name.encode('utf8')).digest()
    r = (h[0] / 255.0) * 0.7 + 0.3
    g = (h[1] / 255.0) * 0.7 + 0.3
    b = (h[2] / 255.0) * 0.7 + 0.3
    return (r, g, b)

# ---------- main ----------

def cook(scriptOP):
    debug("PoseEffect_Dots onCook")
    scriptOP.clear()

    # Input 0 (skeleton)
    skel = scriptOP.inputs[0] if (len(scriptOP.inputs) >= 1 and scriptOP.inputs[0] is not None) else None
    if not skel or skel.numChans == 0:
        return

    # Meta dims (from inMeta DAT / input1 CHOP / CanvasW,H)
    img_w, img_h = _image_dims(scriptOP)

    # Origin handling
    origin = str(_eval_par_value('Origin', 'UV_0_1') or 'UV_0_1').upper()

    # Visual params (read both new + legacy names)
    color_type = str(_eval_par_value('ColorType', None) or _eval_par_value('ColorMode', 'solid')).strip().lower()
    # Normalize to 'solid' | 'random'
    if color_type in ('fixed', 'solid', 'solidcolor'):
        color_type = 'solid'
    elif color_type in ('randomperlandmark', 'rand', 'random'):
        color_type = 'random'
    else:
        color_type = 'solid'

    base_color = _eval_par_value('Color', (1.0, 1.0, 1.0))  # RGB or RGBA
    opacity    = float(_eval_par_value('Opacity', 1.0))
    dot_size   = float(_eval_par_value('DotSize', 8.0))     # pixels

    # Collect landmark base names from *_x/*_y pairs
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

    # Prepare output channels
    scriptOP.numSamples = n
    tx = scriptOP.appendChan('tx')
    ty = scriptOP.appendChan('ty')
    sc = scriptOP.appendChan('scale')
    rc = scriptOP.appendChan('r')
    gc = scriptOP.appendChan('g')
    bc = scriptOP.appendChan('b')
    ac = scriptOP.appendChan('a')

    # Pixel→NDC scale (ortho camera width=2)
    pixel_to_ndc = 2.0 / float(max(1, img_h))
    inst_scale   = float(dot_size) * pixel_to_ndc

    # Unpack base color
    if isinstance(base_color, (tuple, list)):
        br = float(base_color[0] if len(base_color) > 0 else 1.0)
        bg = float(base_color[1] if len(base_color) > 1 else 1.0)
        bb = float(base_color[2] if len(base_color) > 2 else 1.0)
        ba = float(base_color[3] if len(base_color) > 3 else opacity)
    else:
        br, bg, bb, ba = 1.0, 1.0, 1.0, opacity

    # Emit per landmark
    for i, base in enumerate(names):
        x = skel[base + '_x'][0] if skel.chan(base + '_x') else 0.5
        y = skel[base + '_y'][0] if skel.chan(base + '_y') else 0.5
        if origin.startswith('UV'):
            X, Y = _uv_to_ndc(float(x), float(y))
        else:
            X, Y = float(x), float(y)

        tx[i], ty[i], sc[i] = X, Y, inst_scale

        if color_type == 'random':
            r, g, b = _hash_color(base)
            rc[i], gc[i], bc[i], ac[i] = r, g, b, 1.0
        else:
            rc[i], gc[i], bc[i], ac[i] = br, bg, bb, ba

    return
