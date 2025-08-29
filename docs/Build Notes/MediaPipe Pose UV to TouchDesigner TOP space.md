# MediaPipe Pose UV to TouchDesigner TOP space

### Goal

Map **MediaPipe Pose** UVs (origin **top-left**) to **TouchDesigner TOP** space (origin **bottom-left**) so dots/overlays line up with your image.

While an Expression CHOP can do this, a Math pipeline is faster, avoiding the complex python expression

------

### Goal

Produce centered, aspect-corrected X and flipped/centered Y for MediaPipe UVs (0–1, origin **top-left**) so they align in TouchDesigner TOP/Geo space (origin **bottom-left**). **Math CHOP–only**, plus a tiny DAT→CHOP pipeline for `aspect`.

------

### A) `inMeta` DAT → `aspect` CHOP (single channel)

**Assumes** your `inMeta` table has headers `key,value` and a row `aspect,<number>`.

1. **Select DAT** `select_aspect`
   - *DAT*: `inMeta`
   - *Select Rows by Values*: `aspect`
   - *Select Columns by Name*: `value`
      → Output: 1×1 table with just the numeric aspect value.
2. **DAT to CHOP** `aspect_chop`
   - *DAT*: `select_aspect`
   - *Channel per Column*: **On**
   - *First Row is Names*: **Off**
      → Output: single channel (usually `chan1`) with one sample.
3. **Rename CHOP** `aspect` *(optional but recommended)*
   - Rename `chan1` → `aspect`
      → Output: CHOP with channel `aspect` (constant value).

> This `aspect` CHOP will be used to multiply X later.

------

### B) Landmark UVs → flipped/centered/asp-corrected CHOPs

**Assumes** your UV CHOP has channels `tx` and `ty` in 0–1 top-left space (from MediaPipe).

1. **Math CHOP** `flipY`
   - **Input**: your UV CHOP (`tx`, `ty`)
   - *Scope*: `ty`
   - *From Range*: `0 → 1`
   - *To Range*: `1 → 0`
      → Result: `ty = 1 - ty` (origin moved toward bottom-left, still 0–1).
2. **Constant CHOP** `center_offsets`
   - Channels:
     - `tx = -0.5`
     - `ty = -0.5`
3. **Math CHOP** `center_stream`
   - **Inputs**: Left = `flipY`, Right = `center_offsets`
   - *Combine Channels*: **Add**
   - *Scope*: `tx ty`
      → Result:
     - `tx = tx - 0.5`
     - `ty = (1 - ty) - 0.5` (i.e., `0.5 - ty_original`)
        → Coordinates now in **−0.5..+0.5** centered, bottom-left origin.
4. **Math CHOP** `mul_aspect`
   - **Inputs**: Left = `center_stream`, Right = `aspect` (from section A)
   - *Combine Channels*: **Multiply**
   - *Align*: **Shortest** (so the single-sample `aspect` multiplies all samples)
   - *Scope*: **`tx` only**
      → Result:
     - `tx = (tx - 0.5) * aspect`
     - `ty = 0.5 - ty_original` (unchanged from step 3)

**Output of `mul_aspect`**:

- `tx`: centered & aspect-corrected X
- `ty`: flipped & centered Y
   (Optionally pass `tz` through unchanged if you have it; it doesn’t need any of the above transforms.)

------

### Optional: also produce pixel coordinates (if you need them)

If you need `(px, py)` in pixels to draw in a TOP directly:

- Add a **TOP Info CHOP** `bg_info` reading your background/top image (the one you’re overlaying on).
- Use a **Select CHOP** to keep `width` and `height`.
- To compute pixels, multiply **pre-centered** UVs (i.e., use `flipY` output, *not* `center_stream`) by width/height:
  1. **Math CHOP** `pix_x`
     - Left = `flipY` (scope `tx`)
     - Right = `bg_info` (scope `width`)
     - *Combine*: **Multiply**
     - *Scope*: `tx`
     - Rename `tx` → `px`
  2. **Math CHOP** `pix_y`
     - Left = `flipY` (scope `ty`)
     - Right = `bg_info` (scope `height`)
     - *Combine*: **Multiply**
     - *Scope*: `ty`
     - Rename `ty` → `py`

This yields `px = tx * width`, `py = (1 - ty_original) * height` in bottom-left pixel space.

------

### Node list you can mirror (suggested names)

- `inMeta` (Table DAT)
- `select_aspect` (Select DAT) → `aspect_chop` (DAT to CHOP) → `aspect` (Rename CHOP)
- `uv_in` (your UV CHOP with `tx, ty`) → `flipY` (Math) → `center_offsets` (Constant) + `center_stream` (Math/Add) → `mul_aspect` (Math/Multiply with `aspect`) → **final `tx, ty`**

This setup is fast, robust, and easy to reason about when debugging.