# Dots fxCore instancing 23Aug

Here’s the `fx_dots` code you asked for — this is the **Script CHOP** (`landmark_to_instances`) from the Dots design doc.

Put this inside `PoseEffect_Dots/fxCore/landmark_to_instances`:

```python
# fx_dots_landmark_to_instances.py
# PoseEffect_Dots / fxCore / landmark_to_instances (Script CHOP)
# Builds instancing attributes from a single-person skeleton CHOP.

import math, hashlib

def _fx():
    return parent()  # the fxCore COMP

def _par_val(name, default=None):
    core = _fx()
    for p in core.customPars:
        if p.name.lower() == name.lower():
            try:
                return p.eval() if p.tupletSize == 1 else tuple(p.eval())
            except:
                return p.eval()
    return default

def _meta_dim(dim_name, fallback):
    if len(scriptOP.inputs) >= 2 and scriptOP.inputs[1] is not None:
        meta = scriptOP.inputs[1]
        ch = meta.chan(dim_name)
        if ch and ch.numSamples > 0:
            return max(1, int(ch[0]))
    return int(fallback)

def _uv_to_ndc(x, y):
    return (x * 2.0 - 1.0, (1.0 - y) * 2.0 - 1.0)

def _hash_color(name):
    h = hashlib.md5(name.encode('utf8')).digest()
    r = (h[0] / 255.0) * 0.7 + 0.3
    g = (h[1] / 255.0) * 0.7 + 0.3
    b = (h[2] / 255.0) * 0.7 + 0.3
    return (r, g, b)

def cook(scriptOP):
    scriptOP.clear()

    skel = scriptOP.inputs[0] if scriptOP.numInputs >= 1 else None
    if skel is None or skel.numChans == 0:
        return

    origin    = (_par_val('Origin', 'UV_0_1') or 'UV_0_1').upper()
    canvas_w  = _meta_dim('image_width',  _par_val('CanvasW', 1280))
    canvas_h  = _meta_dim('image_height', _par_val('CanvasH', 720))

    colorMode = (_par_val('ColorMode', 'Fixed') or 'Fixed').upper()
    baseColor = _par_val('Color', (1.0, 1.0, 1.0, 1.0))
    opacity   = float(_par_val('Opacity', 1.0))
    dotSizePx = float(_par_val('DotSize', 8.0))

    # Collect landmark bases
    lm_names = []
    for ch in skel.chans():
        nm = ch.name
        if nm.endswith('_x') and skel.chan(nm[:-2] + '_y'):
            lm_names.append(nm[:-2])
    lm_names.sort()
    n = len(lm_names)
    if n == 0: return

    scriptOP.numSamples = n

    tx   = scriptOP.appendChan('tx')
    ty   = scriptOP.appendChan('ty')
    scl  = scriptOP.appendChan('scale')
    rch  = scriptOP.appendChan('r')
    gch  = scriptOP.appendChan('g')
    bch  = scriptOP.appendChan('b')
    ach  = scriptOP.appendChan('a')

    pixel_to_ndc   = 2.0 / max(1.0, float(canvas_h))
    per_inst_scale = dotSizePx * pixel_to_ndc

    for i, base in enumerate(lm_names):
        x = skel[base + '_x'][0] if skel.chan(base + '_x') else 0.5
        y = skel[base + '_y'][0] if skel.chan(base + '_y') else 0.5
        if origin.startswith('UV'):
            X, Y = _uv_to_ndc(float(x), float(y))
        else:
            X, Y = float(x), float(y)

        tx[i], ty[i], scl[i] = X, Y, per_inst_scale

        if colorMode.startswith('RANDOM'):
            cr, cg, cb = _hash_color(base)
            rch[i], gch[i], bch[i], ach[i] = cr, cg, cb, opacity
        else:
            if isinstance(baseColor, (tuple, list)):
                cr = float(baseColor[0]) if len(baseColor) > 0 else 1.0
                cg = float(baseColor[1]) if len(baseColor) > 1 else 1.0
                cb = float(baseColor[2]) if len(baseColor) > 2 else 1.0
                ca = float(baseColor[3]) if len(baseColor) > 3 else opacity
            else:
                cr, cg, cb, ca = 1.0, 1.0, 1.0, opacity
            rch[i], gch[i], bch[i], ach[i] = cr, cg, cb, ca
```

------

This script emits **tx, ty, scale, r, g, b, a** channels for instancing. Wire it into a `Geometry COMP` that instances a quad or point sprite, and render with an ortho camera (width=2).

Do you also want me to hand you the **DAT-based `expose_params` template** for Dots (`UiColor`, `UiDotSize`, `UiOpacity`, `UiColorMode`, plus Origin/CanvasW/H) so your UI builder will auto-surface these?