# PoseEffect_Dots Design

### PoseEffect_Dots — Script CHOP code + fxCore wiring

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

#### `landmark_to_instances` (Script CHOP) — `cook()` implementation

```python
# PoseEffect_Dots / fxCore / landmark_to_instances (Script CHOP)
# Builds instancing attributes from a single-person skeleton CHOP.

import math, hashlib

def _fx():
    # The fxCore COMP (parent of this Script CHOP)
    return parent()

def _par_val(name, default=None):
    # Case-insensitive accessor for custom pars (CanvasH vs Canvash, etc.)
    core = _fx()
    for p in core.customPars:
        if p.name.lower() == name.lower():
            try:  # try tuple first (e.g., Color RGBA)
                return p.eval() if p.tupletSize == 1 else tuple(p.eval())
            except:
                return p.eval()
    return default

def _meta_dim(dim_name, fallback):
    # If meta CHOP (input 1) has image_{width,height}, use those; else fallback parm
    if len(scriptOP.inputs) >= 2 and scriptOP.inputs[1] is not None:
        meta = scriptOP.inputs[1]
        ch = meta.chan(dim_name)
        if ch and ch.numSamples > 0:
            return max(1, int(ch[0]))
    return int(fallback)

def _uv_to_ndc(x, y):
    # Convert UV [0..1] to NDC [-1..1] with Y-up
    return (x * 2.0 - 1.0, (1.0 - y) * 2.0 - 1.0)

def _hash_color(name):
    # Deterministic pseudo-random color per landmark name (pastel-ish)
    h = hashlib.md5(name.encode('utf8')).digest()
    r = (h[0] / 255.0) * 0.7 + 0.3
    g = (h[1] / 255.0) * 0.7 + 0.3
    b = (h[2] / 255.0) * 0.7 + 0.3
    return (r, g, b)

def cook(scriptOP):
    scriptOP.clear()

    # --- Inputs & config ---
    skel = scriptOP.inputs[0] if scriptOP.numInputs >= 1 else None
    if skel is None or skel.numChans == 0:
        return  # nothing to do

    origin = (_par_val('Origin', 'UV_0_1') or 'UV_0_1').upper()
    canvas_w = _meta_dim('image_width',  _par_val('CanvasW', 1280))
    canvas_h = _meta_dim('image_height', _par_val('CanvasH', 720))

    colorMode = (_par_val('ColorMode', 'Fixed') or 'Fixed').upper()
    baseColor = _par_val('Color', (1.0, 1.0, 1.0, 1.0))
    opacity   = float(_par_val('Opacity', 1.0))
    dotSizePx = float(_par_val('DotSize', 8.0))

    # --- Derive landmark base names from *_x channels ---
    # A landmark is present if we have <name>_x and <name>_y (z is optional/confidence)
    lm_names = []
    for ch in skel.chans():
        nm = ch.name
        if nm.endswith('_x'):
            base = nm[:-2]
            if skel.chan(base + '_y') is not None:  # must have y
                lm_names.append(base)

    lm_names.sort()  # stable ordering (optional)
    n = len(lm_names)
    if n == 0:
        return

    # Each sample corresponds to one instance
    scriptOP.numSamples = n

    # Create output channels
    tx   = scriptOP.appendChan('tx')
    ty   = scriptOP.appendChan('ty')
    scl  = scriptOP.appendChan('scale')  # uniform instancing scale
    rch  = scriptOP.appendChan('r')
    gch  = scriptOP.appendChan('g')
    bch  = scriptOP.appendChan('b')
    ach  = scriptOP.appendChan('a')

    # Compute per-pixel scale in NDC (orthographic camera width=2)
    # Pixel height in NDC ≈ 2/canvas_h. We want 'dotSizePx' pixels.
    pixel_to_ndc = 2.0 / max(1.0, float(canvas_h))
    per_inst_scale = dotSizePx * pixel_to_ndc

    # Output per landmark
    for i, base in enumerate(lm_names):
        x = skel[base + '_x'][0] if skel.chan(base + '_x') else 0.5
        y = skel[base + '_y'][0] if skel.chan(base + '_y') else 0.5

        if origin.startswith('UV'):
            X, Y = _uv_to_ndc(float(x), float(y))
        else:
            # assume already NDC
            X, Y = float(x), float(y)

        tx[i] = X
        ty[i] = Y
        scl[i] = per_inst_scale

        if colorMode.startswith('RANDOM'):
            cr, cg, cb = _hash_color(base)
            rch[i], gch[i], bch[i] = cr, cg, cb
            ach[i] = opacity
        else:
            # Fixed color (RGB[A]); TD RGB custom par yields a 3‑tuple,
            # RGBA may yield 4; fall back to opacity for alpha if not provided.
            if isinstance(baseColor, (tuple, list)):
                cr = float(baseColor[0]) if len(baseColor) > 0 else 1.0
                cg = float(baseColor[1]) if len(baseColor) > 1 else 1.0
                cb = float(baseColor[2]) if len(baseColor) > 2 else 1.0
                ca = float(baseColor[3]) if len(baseColor) > 3 else opacity
            else:
                cr, cg, cb, ca = 1.0, 1.0, 1.0, opacity
            rch[i], gch[i], bch[i], ach[i] = cr, cg, cb, ca

    return
```

------

## Other operators inside `PoseEffect_Dots/fxCore`

Build the `fxCore` like this:

```
fxCore/
  CHOP In (0): skeleton_in     # from PersonRouter (single person)
  CHOP In (1): meta_in         # optional: image_width, image_height
  Null CHOP: null_skel         # pass-through of skeleton_in
  Switch CHOP: meta_mux        # meta_in if connected else Constant
  Constant CHOP: meta_fallback # image_width/height from CanvasW/H pars
  Script CHOP: landmark_to_instances  # code above (inputs: null_skel, meta_mux)
  Rectangle SOP: dot_rect      # unit quad
  Geometry COMP: dot_geo
      - Instance OP = landmark_to_instances
      - Instance Translate X = tx
      - Instance Translate Y = ty
      - Instance Uniform Scale = scale
  Constant MAT: dot_mat
      - Enable Blending (Over or Add)
      - Color from instancing: toggle "Use Point Color" (or bind to r/g/b/a)
  Camera COMP: cam
      - Orthographic, width = 2 (to match NDC)
  Render TOP: render1 (cam + dot_geo)
  Out TOP: out_color
```

**Notes**

- The Script CHOP sets `scale` so dots measure in pixels regardless of render size (assuming an **ortho** camera width = 2).
- If you prefer **sprite points**: use a Point SOP → Geo with **Point Sprite MAT**; still drive `scale` and color from the Script CHOP.

------

## Promoting parameters to the UI Builder (through `PoseEffect_Dots`)

You have two solid options. Both play nicely with your **UI Builder** and **ShowControl** layer.

### Option A — Explicit expose table (recommended)

Inside `PoseEffect_Dots/fxCore`, create a **Table DAT** named `expose_params` with **one parameter per row** (the parameter **names** as they appear on `fxCore`):

```
UiColor
UiDotSize
UiOpacity
UiColorMode
Origin
CanvasW
CanvasH
```

### Option B — Implicit prefix

Name the parameters you want to expose with a **`Ui\*` prefix**, e.g., `UiColor`, `UiDotSize`, `UiOpacity`, `UiColorMode`. The UI Builder can auto‑discover these by prefix.

> Either path lets your master `PoseEfxSwitcher` auto‑surface the active effect’s parameters into a single “FX_Active” parameter page (bound 1:1 back to the `fxCore`). The control flow then works for both **panel UI** and **OSC show control** without extra glue.

------

## Hooking it into the PoseCam architecture

1. **Data flow**
   - `OSC In DAT` (bundles) → `Script CHOP (fanout)` → `PersonRouter` → **`PoseEffect_Dots/fxCore/skeleton_in`**.
   - Optional meta (`image_width/height`) into `fxCore/meta_in`. If not connected, the Script CHOP uses `CanvasW/H`.
2. **Switching**
   - Your `PoseEfxSwitcher` keeps one child per effect (e.g., `PoseEffect_Dots`, `PoseEffect_Skeleton`, …).
   - Only the selected effect is cooked (others set to **Selective Cook**).
3. **UI / ShowControl**
   - After adding/renaming pars or the `expose_params` table, rebuild the UI page:
     - Rebuild effect menu (if needed).
     - Rebuild active FX page to pull controls from `fxCore`.
   - Upstream controllers can call your OSC endpoints to select the effect and set parameters; the **feedback** echoes changes back.

------

## Quick checklist

-  Add custom pars on `fxCore`: `UiColor (RGB)`, `UiDotSize (Float)`, `UiOpacity (Float)`, `UiColorMode (Menu: Fixed|RandomPerLandmark)`, `Origin (Menu: UV_0_1|NDC_-1_1)`, `CanvasW/H (Int)`.
-  Create `expose_params` (or prefix with `Ui*`).
-  Paste the Script CHOP code into `landmark_to_instances` and wire inputs (skeleton/meta).
-  Configure `dot_geo` instancing (Translate X/Y, Uniform Scale=scale).
-  Ortho camera width=2 → pixel sizing works.
-  Add **Out TOP**.

If you want the **Skeleton** Script CHOP next (instanced quads with length/angle), say the word and I’ll drop in that code too.