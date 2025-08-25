# Implement PoseEffect_Dots 24Aug

great — if `fxCore/landmark_to_instances` is cooking and you see `tx/ty/scale/r/g/b/a`, you’re one sprint from pixels on screen. Here’s the exact next sequence in TD, click‑by‑click.

### 1) Build the instancing rig inside `PoseEffect_Dots/fxCore`

1. Add **Rectangle SOP** → name it `dot_rect`.
2. Add **Geometry COMP** → name it `dot_geo`. In `dot_geo ▸ Instance`:
   - **Instance OP** = `landmark_to_instances`
   - **Translate X** = `tx`, **Translate Y** = `ty`
   - **Uniform Scale** = `scale`  
3. Add **Constant MAT** → name it `dot_mat`, assign to `dot_geo`. In the MAT:
   - Enable **Blending** (`Over` or `Add`)
   - Turn on **Use Point Color** so instanced `r/g/b/a` drive color  
4. Add **Camera COMP** (Orthographic) with **Width = 2**.
5. Add **Render TOP** (cam + `dot_geo`) → wire to `../fxOut`.  

> Why width=2? Your Script CHOP’s `scale` is in NDC pixels (2 / CanvasH), so dots are pixel‑true in ortho. ****

### 2) Make sure the Script CHOP is wired as designed

- **Input 0**: single‑person skeleton CHOP (typically `../landmarkSelect/outCHOP`).
- **Input 1 (optional)**: a meta CHOP (`image_width`, `image_height`)—or keep using the `inMeta` Table DAT / `CanvasW/H`. The script supports all three and converts UV→NDC for you.  

### 3) Expose the effect’s controls to your switch/UI

Pick **one** method:

- **Option A (recommended)**: add a **Table DAT** `expose_params` inside `fxCore` with one name per row:

  ```
  ColorType
  Color
  DotSize
  ```

  Then run your UI builder’s rebuild; it will bind a master `FX_Active` page back to these pars. 

- **Option B**: rename those pars to `UiColorType`, `UiColor`, `UiDotSize` and let the builder auto‑discover by prefix. 

(If you haven’t created the pars yet: **Customize Component…** on `fxCore` → Page “Dots”. Add: `ColorType` (menu: `solid|random`), `Color` (RGB), `DotSize` (float 1–64).) 

### 4) Landmark selection default

In the child `landmarkSelect` (inside your effect template), set **LandmarkFilter** default to `all` so Dots shows everything on first run. 

### 5) Hook the effect to the switcher

- In `/PoseEfxSwitch`, wire `PoseEffect_Dots/fxOut` into the next free input of the output Switch TOP, and select it via the **ActiveEffect** menu. (Your architecture expects each `PoseEffect_*` to feed the switch.)

### 6) Sanity checks

- In `landmark_to_instances`, verify you see 33 samples (MediaPipe body) and non‑zero `scale`. The script computes `scale = DotSize * (2/CanvasH)`; if Camera Width ≠ 2, the dots will look off. 
- In `dot_geo ▸ Instance`, if nothing renders: confirm `Instance OP` path, and that `dot_geo` has `dot_mat` applied with blending + “Use Point Color.” 
- If your UI page doesn’t show the new controls, rebuild the “FX_Active” page per the UI/ShowControl guide (it consumes `expose_params` / `Ui*` prefix).

That’s it. After those clicks you should see dots on screen, sized in pixels, colorable via the exposed params, and switchable/OSC‑controllable through the same UI plumbing you already have.