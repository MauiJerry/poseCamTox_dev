# PoseEffect_Dots fromm old OSC_Dots

Great—since you’re reusing the old **OSC_Dots** pattern, here’s exactly what to do next and how to fix those two snags.

------

## 1) Read `image_width/height` from your `inMeta` **Table DAT**

In TD, a **DAT cell** is a string; you just cast it in the parameter expression.
 For the **Camera COMP** (the one that used to read from a CHOP):

- Camera → **View** page → **Resolution → Width**
   Set the expression to:

  ```
  int(op('inMeta')['image_width','value'])
  ```

- Camera → **View** page → **Resolution → Height**

  ```
  int(op('inMeta')['image_height','value'])
  ```

Both expressions grab the cell at **row = 'image_width' (or 'image_height')**, **col = 'value'**, then cast to `int`. (DAT cells are strings by default; that’s why you saw the “Invalid Number: … 'image_width' Type class 'str'” when you tried to use the literal label.)
 If your table’s second column isn’t literally named `value`, swap `'value'` for the actual column name or numeric index, e.g. `op('inMeta')['image_width',1]`.

> Alternative (no expressions on the Camera): drop a **DAT to CHOP** reading `inMeta`, and **export** the `image_width/height` channels to the Camera’s Width/Height. Same result, just channel‑based if you prefer that style.
>  For pixel‑true dots, our design assumes an **ortho camera width=2** while dot scale is computed from **image_height** .

------

## 2) Y is inverted — flip it once

Since your `shuffle_landmarks` outputs `tx, ty, tz` in **UV space** (0..1, Y down), flip Y before instancing:

- Insert a **Math CHOP** after `shuffle_landmarks`.
- On the **Multiply** page, set **Channel Mask** to `ty` and **Value** to `-1`.
   Or keep it in the Geo’s field with an expression:
   **Translate Y** = `-op('shuffle_landmarks')['ty']`.

(Our docs use UV→NDC mapping `(x*2-1, (1-y)*2-1)` which includes the flip; since you’re keeping the old network, the simple **-1** multiply is perfect.)

------

## 3) Hook instancing on the Geometry COMP (and where “Uniform Scale” lives)

- Open **geo1 → Instance** page
   (make sure **Instancing** is On)
  - **Instance OP** = `shuffle_landmarks` (or your post‑Math CHOP)
  - **Translate X** = `tx`
  - **Translate Y** = `ty`
  - **Uniform Scale** = the channel name that carries size (see next step)

The **Uniform Scale** field is right under the Translate/Rotate/Scale mappings on the **Instance** page of the **Geometry COMP**. You can ignore per‑axis **Scale X/Y/Z** when you use **Uniform Scale**. (This is exactly how the Dots effect is specced.)

------

## 4) Drive dot size from a **Dotsize** parameter (pixel‑accurate)

Add a custom **Float** parameter `DotSize` on your effect (e.g., on `PoseEffect_Dots/fxCore`). Then create a single‑channel CHOP named `scale` and feed it to instancing:

**Option A (CHOP):**

- Add a **Constant CHOP** named `dot_scale`.

- Add a channel **`scale`** with this expression:

  ```
  me.parent().par.DotSize * 2 / float(op('inMeta')['image_height','value'])
  ```

- Use `dot_scale` as a **second input** to your instancing CHOP (merge it so the CHOP has `tx ty tz scale`), and set **geo1 → Instance → Uniform Scale** = `scale`.

**Option B (no CHOP):**

- Leave your instancing CHOP as‑is and put the expression directly in **geo1 → Instance → Uniform Scale**:

  ```
  me.parent().par.DotSize * 2 / float(op('inMeta')['image_height','value'])
  ```

This matches the design: dot scale in NDC is `DotSize / CanvasH`, and with an **orthographic camera width = 2**, that becomes `DotSize * (2 / image_height)` for pixel‑true dots.

------

## 5) Material: blending + per‑instance color

Make sure you actually created a **Constant MAT** (Material family), not a Constant **TOP**.

- On **Constant MAT**:
  - **Color** page → **Use Point Color** = On (so it reads per‑instance `r,g,b,a`).
  - **Blending** page → **Enable Blending** = On, set the blend you want (**Over**/Alpha or **Add**).
- On **geo1 → Instance** page:
  - Set **Color** fields to `r g b` and **Alpha** to `a` so those channels from your CHOP are bound to the instance color.
     (This is the pattern we documented for Dots.)

If you don’t have `r,g,b,a` yet (old network only had `tx,ty,tz`), just add a **Constant CHOP** with those channels (or switch to the provided `landmark_to_instances` Script CHOP which outputs `tx,ty,scale,r,g,b,a` in one go).

------

### Tiny checklist (old OSC_Dots network)

-  **Camera Width/Height** expressions read `inMeta` as ints (above).
-  **Math CHOP** flips `ty` by **–1** (or do it in the Geo field).
-  **Uniform Scale** on geo1 = `DotSize * 2 / image_height`.
-  **Constant MAT** (not TOP) → **Use Point Color** + **Enable Blending**.
-  **Instance Color/Alpha** mapped to `r g b` / `a` (or add a Constant CHOP to supply them).

If/when you want to modernize this effect, you can replace `shuffle_landmarks` with the drop‑in `landmark_to_instances` Script CHOP from the design—same wiring, but it computes the pixel‑true `scale` and handles color modes for you.