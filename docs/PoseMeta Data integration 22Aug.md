# PoseMeta Data integration 

chat 22 aug 4pm

backup and revise PoseCamIn with revised script

### Goal

Make `PoseCamIn` publish a tiny **poseMeta CHOP** (`image_width`, `image_height`, `aspect_ratio`), and make `PoseEffect_MASTER` own the **Canvas defaults** and **bind** them up to `PoseEfxSwitch` (UI) and down into each `fxCore`. Effects prefer live meta when present, and fall back to the Canvas pars.

------

### Part A — Add `poseMeta` in PoseCamIn

(removed original, it didnt know we had posefanout.py)

### Plan

Yes—do it right in `pose_fanout.py`: keep emitting the fast numeric meta as CHOP channels, **and** mirror the slow-changing bits into a **PoseMeta Table DAT** (key/value) that only updates when a value actually changes. Downstream COMPs (PoseEfxSwitch, UI, etc.) can reference that DAT without forcing per-frame cooks. Your current script already extracts these fields and writes `timestamp_str` to a text DAT; we’ll extend it to also maintain a key/value table. 

------

### TouchDesigner edits (one-time)

1. **Inside `/PoseCamIn`**, add a **Table DAT** named `poseMetaDAT` with a header row:

   ```
   key    value
   ```

2. (Optional but recommended) Add an **Out DAT** named `outMetaDAT`. Set its **DAT** parameter to `poseMetaDAT` so `/PoseCamIn` exposes a clean DAT output connector.

3. Ensure `/PoseCamIn`’s **Node View → Connectors** has **DAT** turned on so the DAT output jack is visible.

> Keep your existing OSC In DAT (`poseoscIn1`) and Script CHOP that runs `pose_fanout.py` as-is.

------

### Patch `pose_fanout.py`

Add the constant for the table name, a small “upsert” helper, and call it after you parse values.

> Below shows only the **additions/changes** (search for `# NEW` comments).

```python
# --- add near other constants -----------------------------------------------
POSE_META_DAT_NAME   = 'poseMetaDAT'   # NEW  (Table DAT with header: key,value)

# --- add helper near other helpers ------------------------------------------
def _upsert_meta(key, value):  # NEW
    """
    Upsert key->value into the poseMetaDAT table, writing only when changed.
    Initializes the header if the table was empty or wrong shape.
    """
    t = _op_lookup(POSE_META_DAT_NAME)
    if not t:
        return
    # Ensure header exists and is correct
    if _nrows(t) == 0 or _ncols(t) < 2 or (t[0,0].val.strip().lower() != 'key'):
        t.clear()
        t.appendRow(['key', 'value'])

    sval = str(value)
    # find existing row
    row_index = None
    for r in range(1, _nrows(t)):
        if t[r, 0].val == key:
            row_index = r
            break
    if row_index is None:
        t.appendRow([key, sval])
    else:
        if t[row_index, 1].val != sval:
            t[row_index, 1].val = sval

# --- in onCook(), keep your existing parsing; then below your meta outputs ---
    # counts & metadata  prefix with m_ so as not to muck with later wild card p*
    if num_persons is None:
        num_persons = len(present)
    _append_scalar(scriptOp, 'm_n_people', float(num_persons))

    if frame_count is not None:
        _append_scalar(scriptOp, 'm_frame_count', float(frame_count))
    if img_w is not None:
        _append_scalar(scriptOp, 'm_img_w', float(img_w))
    if img_h is not None:
        _append_scalar(scriptOp, 'm_img_h', float(img_h))
    if ts_sec is not None:
        _append_scalar(scriptOp, 'm_ts_sec', ts_sec)
        _append_scalar(scriptOp, 'm_ts_ms', ts_sec * 1000.0)
    if ts_str:
        _set_text_dat(TS_STR_DAT_NAME, ts_str)

    # --- NEW: mirror slow-changing items into poseMetaDAT (key/value table) ---
    # Only updates when value actually changes (cheap for TD’s cook graph)
    if img_w is not None:
        _upsert_meta('image_width', int(img_w))
    if img_h is not None:
        _upsert_meta('image_height', int(img_h))
    if num_persons is not None:
        _upsert_meta('num_persons', int(num_persons))
    if ts_str:
        _upsert_meta('timestamp_str', ts_str)
    # Optional: if you want a coarse numeric timestamp that updates ~1 Hz:
    if ts_sec is not None:
        _upsert_meta('timestamp_sec', int(ts_sec))   # comment out if too chatty
```

**What this gives you**

- The Script CHOP still outputs **fast** meta as channels (`m_*`) for any per-frame consumers.
- `poseMetaDAT` holds **slow-changing** meta as strings/numbers (`image_width`, `image_height`, `num_persons`, `timestamp_str`, optional `timestamp_sec`) and only updates when values change—so downstream UI/FX that depend on table cells won’t recook every frame. 

------

### Downstream usage examples

- **Wired approach:** In a consumer COMP, drop an **In DAT** named `inMeta` and wire from `/PoseCamIn/outMetaDAT`. Then:

  - Parameter expression (Python):

    ```python
    float(op('inMeta')['num_persons','value'])
    ```

  - Label text (Python):

    ```python
    op('inMeta')['timestamp_str','value']
    ```

- **By path (no wire):**

  ```python
  float(op('/project1/PoseCamIn/poseMetaDAT')['image_width','value'])
  ```

------

### Notes & options

- If you decide `frame_count` should also be in the DAT, add `_upsert_meta('frame_count', int(frame_count))`. It will update every frame, which is fine for a table but does trigger dependent cooks each time—use only where needed.
- You can compute and store convenience values here too (e.g., `aspect_ratio = img_w / img_h` when both are non-zero) via `_upsert_meta('aspect_ratio', img_w / img_h)`.
- Keeping `timestamp_str` in **both** a Text DAT (for simple UI binds) and the table is harmless; many UIs prefer a single `poseMetaDAT` source. 

------

If you want, I can also add a tiny **DAT Execute** to throttle `timestamp_str` updates to 1 Hz, but with the upsert guard it’s already efficient unless you bind dozens of params to it.



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