# MediaPipe Pose UV to TouchDesigner TOP space

### Goal

Map **MediaPipe Pose** UVs (origin **top-left**) to **TouchDesigner TOP** space (origin **bottom-left**) so dots/overlays line up with your image.

------

### CHOP-only recipe (no Python)

1. **Shuffle → rename to `tx`, `ty`, `tz`**
    Your stream is 0–1 UVs with Y top-origin.
2. **Flip Y**
    Add a **Math CHOP** (`flipY`) and set:
   - *From Range*: **0 to 1**
   - *To Range*: **1 to 0**
      (equivalent to `ty = 1 - ty`)
3. **Center (optional, if your render expects a centered origin)**
    Add a **Math CHOP** (`center_stream`):
   - *Combine Channels*: **Add** with a **Constant CHOP** supplying `-0.5` to `tx` and `ty`.
      Result:
     - `tx_centered = tx - 0.5`
     - `ty_centered = (1 - ty) - 0.5`
4. **Aspect correction (only if you’re converting to camera/NDC space)**
    If you’ll instance in a **Geo COMP** with an **orthographic camera** (i.e., using NDC −1..1), scale X by the render aspect so circles don’t squash:
   - Add a **TOP Info CHOP** reading your background TOP → this gives `width` & `height`.
   - Use a **Math CHOP** to compute `aspect = width/height`.
   - Multiply `tx_centered` by `aspect`.
      End state for NDC instancing (−0.5..0.5, aspect-corrected).
5. **Pixels instead of UVs (for direct TOP overlay)**
    If you want pixel coords:
   - Multiply `tx` by **width** and `ty_flipped` by **height** (export `width/height` from TOP Info CHOP into a Math CHOP set to Multiply).
   - Now you have `(px, py)` in pixels with origin bottom-left.

------

### Expression CHOP equivalents

If you prefer a single **Expression CHOP** after your `tx, ty`:

- **Flip only (UV out):**
  - Channel Names: `tx ty`
  - `tx` expr: `me.inputs[0]['tx'][i]`
  - `ty` expr: `1 - me.inputs[0]['ty'][i]`
- **Flip + center (−0.5..0.5):**
  - `tx`: `me.inputs[0]['tx'][i] - 0.5`
  - `ty`: `0.5 - me.inputs[0]['ty'][i]`   *(note: `1 - ty - 0.5`)*
- **To pixels using a TOP named `inTop`:**
  - `px`: `me.inputs[0]['tx'][i] * op('inTop').width`
  - `py`: `(1 - me.inputs[0]['ty'][i]) * op('inTop').height`

------

### Which path should you use?

- **Overlay dots in a TOP** (e.g., using **Point Sprite / GLSL TOP**):
   Use **UV flip only** (`ty = 1 - ty`). Draw in UV space.
- **Geo instancing in a Render TOP** (camera space):
   Use **flip + center**, then (optionally) **aspect-correct X** before mapping to NDC/orthographic units.

------

### Quick sanity checks

- A landmark at MediaPipe `(0,0)` (top-left) should become `(0,1)` in UV after flip, or `(−0.5,+0.5)` after flip+center.
- A landmark at `(0.5,0.5)` should remain centered: `(0.5,0.5)` → `(0.5,0.5)` (flip keeps it), or `(0,0)` after center.

If you paste your current `flipY` and `center_stream` operator settings, I’ll align the exact toggles to your network names.

---

### Single **Expression CHOP** (flip, center, aspect on X)

Assume the input to the Expression CHOP has channels `tx` and `ty` in **MediaPipe UV (0–1, origin top-left)**, and your aspect ratio (width/height) lives in a **DAT** named `inMeta` under a cell labeled **`Aspect`**.

Set **Channel Names** in the Expression CHOP to: `x y` and use these expressions:

- **x**

  ```python
  (me.inputs[0]['tx'][i] - 0.5) * (
      float(op('inMeta')['Aspect', 1].val) if op('inMeta') and op('inMeta').numRows > 1 else 1.0
  )
  ```

  *(center X → tx-0.5, then multiply by aspect)*

- **y**

  ```python
  0.5 - me.inputs[0]['ty'][i]
  ```

  *(flip Y → 1-ty, then center → -0.5; combined as 0.5 - ty)*

> Notes
>
> - If your `inMeta` is a key/value table with header row and the value on row 1, the `['Aspect', 1]` access is correct.
> - If your layout differs, adjust the cell index (e.g., `[1, 'Aspect']` or direct row/col indices) accordingly.
> - Add a third channel for `z` if needed: `me.inputs[0]['tz'][i]` (typically left unscaled here).

------

### **Math CHOP** pipeline (equivalent result, no expressions)

**Goal:** produce centered, aspect-corrected X and flipped/centered Y for instancing in Geo/NDC-like space.

1. **Flip Y (0–1 → 1–0)**
   - Add a **Math CHOP** named `flipY`.
   - **Scope**: `ty` only.
   - **From Range**: `0 to 1`
   - **To Range**: `1 to 0`
      *(This yields `ty_flipped = 1 - ty`.)*
2. **Center X & Y (shift by −0.5)**
   - Add a **Constant CHOP** named `center_offsets` with channels:
     - `tx` = `-0.5`
     - `ty` = `-0.5`
   - Add a **Math CHOP** named `center_stream`.
     - Connect `flipY` (left input) and `center_offsets` (right input).
     - **Combine Channels**: `Add`
     - **Scope**: `tx ty`
        *(Now `tx = tx - 0.5`, `ty = (1 - ty) - 0.5` → same as `0.5 - ty_original`.)*
3. **Aspect-correct X**
   - Bring aspect into CHOPs:
     - **DAT to CHOP** (`meta_to_chop`) reading `inMeta` → make sure it outputs a channel named `Aspect` with a constant value (set *Channel per Column*, use *First Row is Names* if applicable).
     - (Optional) **Select CHOP** to keep just `Aspect`.
     - (Optional) **Rename CHOP** to rename `Aspect` → `scale_x` (for clarity).
   - Add a **Math CHOP** named `mul_aspect`.
     - Connect `center_stream` (left) and `scale_x` (right).
     - **Combine Channels**: `Multiply`
     - **Align**: `Shortest` (so the single-sample `scale_x` multiplies all samples)
     - **Scope**: `tx` only
        *(Now `tx = (tx - 0.5) \* aspect`; `ty` is unchanged from step 2.)*

**Output:**

- `tx`: centered and aspect-scaled X
- `ty`: flipped & centered Y

------

If you share your exact `inMeta` table layout (rows/cols), I can tweak the Expression CHOP’s cell access so it’s bulletproof for your project.

---

### Expression CHOP: flip, center, and aspect-correct X (using your `inMeta.csv`)

Your CSV is a 2-column table with headers `key,value` and a row where `key=aspect` (e.g., `1.775`). Given input channels `tx, ty` in MediaPipe UV (0–1, origin top-left), put these two expressions in a single **Expression CHOP** (set Channel Names to `x y`):

- **x**

  ```python
  (me.inputs[0]['tx'][i] - 0.5) * (
      float(op('inMeta')[op('inMeta').findCell('aspect', col=0).row, 1].val)
      if op('inMeta').findCell('aspect', col=0) is not None else 1.0
  )
  ```

- **y**

  ```python
  0.5 - me.inputs[0]['ty'][i]
  ```

Notes:

- This looks up the row where the **first column (`key`) equals `'aspect'`**, then takes the **second column (`value`)**.
- If the row isn’t found, it safely falls back to `aspect = 1.0`.
- Result is centered coords (−0.5..+0.5), Y flipped to bottom-left origin, with X scaled by aspect.

------

### Math CHOP pipeline (no expressions), equivalent result

1. **Flip Y**
   - **Math CHOP** `flipY`
     - *Scope*: `ty`
     - *From Range*: `0 → 1`
     - *To Range*: `1 → 0`
        → `ty = 1 - ty`
2. **Center X & Y**
   - **Constant CHOP** `center_offsets` with channels:
     - `tx = -0.5`
     - `ty = -0.5`
   - **Math CHOP** `center_stream`
     - Connect `flipY` (left) and `center_offsets` (right)
     - *Combine Channels*: **Add**
     - *Scope*: `tx ty`
        → `tx = tx - 0.5`, `ty = (1 - ty) - 0.5` (same as `0.5 - ty_original`)
3. **Bring `aspect` in as a CHOP channel**
   - **Select DAT** `select_aspect` on `inMeta`
     - *Select Rows by Values*: `aspect`
     - *Select Columns by Name*: `value`
   - **DAT to CHOP** `meta_to_chop`
     - *Channel per Column*
     - *First Row is Names*: **Off**
     - Rename the output channel to `aspect` (via a **Rename CHOP** if needed)
4. **Multiply X by aspect**
   - **Math CHOP** `mul_aspect`
     - Connect `center_stream` (left) and `meta_to_chop` (right)
     - *Combine Channels*: **Multiply**
     - *Align*: **Shortest**
     - *Scope*: `tx`
        → `tx = (tx - 0.5) * aspect`; `ty` unchanged from step 2

**Output:** `tx` (centered, aspect-scaled) and `ty` (flipped, centered), ready for Geo instancing / NDC-like use.