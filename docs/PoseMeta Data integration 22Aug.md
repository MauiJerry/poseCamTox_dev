# PoseMeta Data integration 22Aug

### Goal

Make `PoseCamIn` publish a tiny **poseMeta CHOP** (`image_width`, `image_height`, `aspect_ratio`), and make `PoseEffect_MASTER` own the **Canvas defaults** and **bind** them up to `PoseEfxSwitch` (UI) and down into each `fxCore`. Effects prefer live meta when present, and fall back to the Canvas pars.

------

### Part A — Add `poseMeta` in `/PoseCamIn`

#### A1) Ensure you have the OSC receiver

1. In `/PoseCamIn`, drop an **OSC In DAT** named `osc_pose`.
   - Set **Network Port** to your pose sender port (e.g., `7400`).
   - Set **Maximum Messages** to something modest (e.g., `500`) to avoid huge tables.
2. Confirm it’s **Active** (green flag).

#### A2) Build a tiny Script CHOP that emits meta

1. Still inside `/PoseCamIn`, drop a **Script CHOP** named `pose_meta_build`.
2. Click **Edit…** and paste:

```python
# /PoseCamIn/pose_meta_build (Script CHOP)

def cook(scriptOP):
    d = op('osc_pose')  # OSC In DAT with pose bundles
    scriptOP.clear()

    # Find latest values in the OSC DAT (scan from bottom up)
    def _find_latest(addr):
        if not d or d.numRows == 0:
            return None
        for i in range(d.numRows - 1, -1, -1):
            a = d[i, 0].val if d.numCols > 0 else ''
            if a == addr:
                # Find first numeric arg in the row
                for c in range(1, d.numCols):
                    v = d[i, c].val
                    try:
                        return float(v)
                    except Exception:
                        pass
        return None

    w = _find_latest('/pose/image_width')
    h = _find_latest('/pose/image_height')
    fps = _find_latest('/pose/fps')

    # Hold last-known values so a momentary drop doesn't zero things
    if w is None:
        w = scriptOP.storage.get('w', 1280.0)
    if h is None:
        h = scriptOP.storage.get('h', 720.0)

    # Emit channels
    ch_w = scriptOP.appendChan('image_width');  ch_w[0] = w
    ch_h = scriptOP.appendChan('image_height'); ch_h[0] = h
    ch_ar = scriptOP.appendChan('aspect_ratio'); ch_ar[0] = (w / h) if h else 1.7778
    if fps is not None:
        ch_fps = scriptOP.appendChan('fps'); ch_fps[0] = fps

    # Remember for next cook
    scriptOP.storage['w'] = w
    scriptOP.storage['h'] = h
    if fps is not None:
        scriptOP.storage['fps'] = fps
    return
```

1. Add a **Null CHOP** after it named `pose_meta_out`.

> Optional (nice to have): add a **Constant CHOP** `pose_meta_fallback` with `image_width=1280`, `image_height=720`, and switch to it if the OSC DAT is inactive. For now, the storage fallback above is enough.

------

### Part B — Upgrade `PoseEffect_MASTER` to own the Canvas and meta mux

> You’ll do this once in the **clone master** so all `PoseEffect_*` get it for free.

#### B1) Create/Update custom parameters on `PoseEffect_MASTER`

1. Open **`/EfxSwitch/effects/PoseEffect_MASTER`**.
2. RMB the COMP ▸ **Customize Component…**
3. Add a page **Canvas** with:
   - `Canvasw` (Int, default `1280`)
   - `Canvash` (Int, default `720`)
   - `Usemeta` (Toggle, default `On`) — “Prefer live meta when available”
   - `Origin` (Menu: `UV_0_1`, `NDC_-1_1`; default `UV_0_1`)
   - `Aspect` (Float, **Expr**: `me.par.Canvasw / me.par.Canvash if me.par.Canvash else 1`), disable **Enable** so it’s read‑only.
   - (Optional) common style defaults used by many FX, e.g. `Dotsizepx` (Float `8`), `Linewidthpx` (Float `4`).

#### B2) Bind these up to `PoseEfxSwitch` (global defaults)

1. On **`/EfxSwitch`**, RMB ▸ **Customize Component…**, add page **Defaults**:

   - `Defaultcanvasw` (Int `1280`)
   - `Defaultcanvash` (Int `720`)
   - (Optional) `Defaultdotsizepx`, `Defaultlinewidthpx`.

2. Back on **`PoseEffect_MASTER` ▸ Canvas** page, **Bind**:

   - `Canvasw` → `../..` (the switch) ▸ `Defaultcanvasw`.
   - `Canvash` → `../..` ▸ `Defaultcanvash`.
   - (Optional) style pars → corresponding defaults.

   > To bind: RMB the parameter ▸ **Bind…** ▸ pick the target operator & parameter.

Now changing the Switch defaults ripples to every effect (unless a clone breaks the bind).

#### B3) Inside `PoseEffect_MASTER/fxCore` add the meta mux

1. Dive into **`PoseEffect_MASTER/fxCore`**.

2. Add **CHOP In** (index 0) named `skeleton_in` (already there in most templates).

3. Add **CHOP In** (index 1) named `meta_in`.

4. Add **Constant CHOP** `meta_fallback` with channels:

   - `image_width` = `op('..').par.Canvasw.eval()`
   - `image_height` = `op('..').par.Canvash.eval()`

5. Add **Switch CHOP** `meta_mux`:

   - **Input 0** = `meta_fallback`

   - **Input 1** = `meta_in`

   - **Index** expression:

     ```
     1 if op('..').par.Usemeta and op('meta_in') and len(op('meta_in').channels) >= 2 else 0
     ```

6. Set your **Render TOP** (inside `fxCore`) ▸ **Common ▸ Resolution = Specify**:

   - **W**: `int(op('meta_mux')['image_width'][0])`
   - **H**: `int(op('meta_mux')['image_height'][0])`

7. Ensure your landmark pre‑process (Script CHOP) converts **UV → NDC** and uses **pixel size from CanvasH**:

   - Per‑pixel NDC scale ≈ `2 / image_height` → `DotSizePx * (2 / image_height)`.

> If your effect composites over a background TOP (`../in2`), keep doing that. The meta just sets the render size & pixel math.

------

### Part C — Wire the meta from PoseCamIn into effects

#### C1) Make the connection once in a tidy way

- In `/PoseEfxSwitch/effects`, select **all `PoseEffect_\*`** (including the MASTER), then:
  1. Drag `/PoseCamIn/pose_meta_out` into the network.
  2. Connect it to each effect’s **`fxCore/meta_in`** (CHOP In 1).
      (If you keep effects in their own COMPs, connect to the inner `meta_in` CHOP.)
- Or add a tiny extension on `PoseEffect_MASTER` to auto‑connect `meta_in` on clone create (optional future nicety).

#### C2) Verify

- With PoseCamPC running, open any `PoseEffect_* / fxCore/meta_mux`. You should see `image_width`, `image_height` changing (or static).
- Toggle `Usemeta` on the effect (or MASTER) to confirm fallback works (Render TOP resolution should jump between live and CanvasW/H).

------

### Part D — PersonRouter and skeleton input (reminder)

- Your **PersonRouter** should output a single‑person CHOP with **unprefixed** channels (`head_x`, `head_y`, `head_z`, …).
- Wire that to each effect’s **`fxCore/skeleton_in`** (CHOP In 0).
- The effect’s pre‑process Script CHOP should:
  - Find base landmark names by scanning `*_x` channels.
  - Convert UV→NDC: `X=(u*2)-1`, `Y=((1-u_y)*2)-1`.
  - Compute pixel‑true sizes using `image_height` from `meta_mux`.

------

### Part E — Quick TD editor clicks (cheat sheet)

- **Create a custom parameter page:** RMB COMP ▸ Customize Component… ▸ **+** Page ▸ **+** Parameters.
- **Bind a parameter:** RMB the source param ▸ **Bind…** ▸ pick target (operator+param).
   (Bound params show a little link icon; break the bind by RMB ▸ **Unbind** if an instance needs local override.)
- **Feed CHOP to CHOP In:** Drag the source CHOP onto the `CHOP In` operator, drop to connect.
- **Expression in a parameter cell:** Click the parameter’s value box, type the Python expression (no backticks), press Enter.
- **Clone propagation:** After changing `PoseEffect_MASTER`, **RMB it ▸ Reinit Network** so clones update. Mark only `fxCore` as **Clone Immune** in concrete effects.

------

### Part F — Optional: also mirror meta into a DAT (for UI/diagnostics)

If you want a DAT view:

1. In `/PoseCamIn`, add a **DAT to CHOP**? Not needed; you already have a CHOP. Instead, add a **CHOP to DAT** named `pose_meta_dat` and point it at `pose_meta_out`.
2. Now you have a neat table of the same values for UI/status panels.

------

### Smoke Test

1. Start PoseCamPC. Confirm `/PoseCamIn/osc_pose` is active and rows are updating.
2. Check `/PoseCamIn/pose_meta_out` → `image_width/height` non‑zero.
3. Activate `PoseEffect_Dots`. In its `fxCore`, open the **Render TOP**—resolution should match meta.
4. Toggle `Usemeta` off on the effect (or master) → Render TOP should revert to `Canvasw/h` values.
5. Resize your camera source (if supported) → `image_width/height` update → dots stay pixel‑true.

That’s it. You’ve now got a clean, clone‑friendly master that owns the canvas, and every effect can dial in pixel accuracy by reading the live meta—without ever re‑scaling the underlying skeleton data.