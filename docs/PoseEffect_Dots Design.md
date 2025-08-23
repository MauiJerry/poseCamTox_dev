# PoseEffect_Dots Design

### PoseEffect_Dots — Script CHOP code + fxCore wiring

how to wire up the DOTS effect

revised 23Aug

Below is a **drop‑in Script CHOP** for the `PoseEffect_Dots/fxCore/landmark_to_instances` node.
 It consumes a single‑person skeleton CHOP (channels like `head_x, head_y, head_z, …`) and produces **per‑instance** channels for a GEO instancing rig:

- `tx, ty` (position in NDC)
- `scale` (uniform instancing scale for pixel‑sized dots)
- `r, g, b, a` (per‑instance color)

> Assumptions:
>  • The `fxCore` component has custom pars: `Origin` (UV_0_1|NDC_-1_1), `CanvasW`, `CanvasH`, `ColorMode` (Fixed|RandomPerLandmark), `Color` (RGBA), `Opacity`, `DotSize`.
>  • CHOP input 0 is the single‑person skeleton (from your PersonRouter).
>  • Optional CHOP input 1 provides meta channels `image_width`, `image_height`.
>  • You’ll wire the produced channels into a **Geometry COMP** set to **Instance** using this Script CHOP.

------

Perfect—here’s a drop‑in **fx_dots** Script CHOP that matches your parameter names and reads render dimensions from the **inMeta Table DAT** (per your comment). I also included the tiny DAT you’ll add inside `fxCore` so EfxSwitch can **promote and bind** the controls up to the Effects menu.

# 1) Script CHOP (fxCore/landmark_to_instances)

Paste this into a **Script CHOP** named `landmark_to_instances` inside `PoseEffect_Dots/fxCore`. Wire its input to your single‑person skeleton CHOP (from your `landmarkSelect/outCHOP` or equivalent).

```python
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
```

**Why this matches your stack:**

- It looks up `image_width`/`image_height` directly from the **inMeta Table DAT** you forward into each effect (your guard makes those always present), so dot size is **pixel‑true** without needing extra CHOPs.
- Parameter names are exactly: `ColorType` (solid|random), `Color` (RGB), `DotSize` (float). The Script CHOP only reads these three, per your request.

# 2) Minimal fxCore wiring (TD editor clicks)

Inside `PoseEffect_Dots/fxCore`:

1. Add the Script CHOP above and wire its **Input 0** to the single‑person skeleton (e.g., `../landmarkSelect/outCHOP`). Your `landmarkSelect` lives in the effect template and is driven by `LandmarkFilter`, default **ALL**.
2. SOP/Instancing:

- Add a **Rectangle SOP** (unit quad) → **Geometry COMP** (`dot_geo`).
- In `dot_geo ▸ Instance`:
  - **Instance OP** = `landmark_to_instances`
  - **Translate X** = `tx`, **Translate Y** = `ty`
  - **Uniform Scale** = `scale`
- Add a **Constant MAT** (`dot_mat`), enable **Blending: Over** (or Add), and tick **Use Point Color** (so r/g/b/a from the instance CHOP drive color).
- Add an **Orthographic Camera** with **Width = 2** and a **Render TOP** → **fxOut**.

This is the same instancing pattern we designed for Dots.

# 3) Promote & bind parameters to the EfxSwitch menu

To surface and bind your three controls from the active effect **up into the EfxSwitch UI page**, add either:

**Option A (explicit table, recommended):**
 Create a **Table DAT** named `expose_params` **inside `PoseEffect_Dots/fxCore`** with one parameter name per row:

```
ColorType
Color
DotSize
```

Your existing switch/UI scripts can read this table and build the bound “FX_Active” page so changes at the switch propagate down and vice‑versa.

**Option B (implicit prefix):**
 Rename your pars to `UiColorType`, `UiColor`, `UiDotSize` and let the switcher auto‑discover by prefix. (The explicit table is cleaner and avoids renames.)

> If you’re using the **FX_Active page builder** from the UI/ShowControl guide, it will copy menu items, colors, ranges, etc., and **bind** the master page parameters back to the `fxCore` pars automatically.

# 4) Create the three custom parameters on fxCore

In the TD editor: **fxCore → right‑click → Customize Component…**

- Page **Style** (or “Dots”):
  - **ColorType** (Menu): items `solid` and `random`. Default `solid`.
  - **Color** (RGB): default `1,1,1`.
  - **DotSize** (Float): default `8.0` (set a slider range like 1–64).

Update `expose_params` (Option A) to list those names. Rebuild your FX page on the switch if you’re using the helper.

# 5) Default Landmark Type = ALL

On the effect’s `landmarkSelect` (child COMP in the template), set **LandmarkFilter** default to `all`. That ensures Dots starts with every landmark shown. (The switch template seeds and syncs that menu across effects.)

------

If you want, I can also drop a tiny **Point Sprite** variant (no Render TOP) or a **GLSL TOP** version later—this one is the cleanest to get you live quickly and matches your inMeta DAT + EfxSwitch exposure model.