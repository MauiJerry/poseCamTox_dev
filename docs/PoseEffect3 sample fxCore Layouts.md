### PoseEffect fxCore Layouts (Dots, Skeleton, Hand Emitter)

Below are three **fxCore** component specs that share a **common interface** so they can be hot-swapped behind your `EfxSwitch`. Each fxCore is a **Base COMP** with identical inputs/outputs and a small, consistent parameter set. Internal networks are listed operator-by-operator so you can build quickly.

------

### 1) Shared fxCore Interface (all effects)

**COMP name:** `PoseEffect_<Name>` (e.g., `PoseEffect_Dots`)

**Inputs (TOP/CHOP):**

- **CHOP In (index 0)** — `skeleton_in`
   Expects channels for **one person** from your PersonRouter, named:
   `head_x, head_y, head_z, shoulder_l_x, ...` (normalized **u,v** in [0..1], z=confidence or depth).
- **CHOP In (index 1) [optional]** — `meta_in`
   Channels: `image_width`, `image_height` (if provided by your pipeline), otherwise use parms.

**Output (TOP):**

- **TOP Out** — `out_color` (RGBA)
   A self-contained image stream suitable for compositing.

**fxCore Parameters (Pages / Pars):**

- **Pose**
  - `LandmarkSet` (Menu: `MediaPipe33`, `COCO17`) — for downstream mapping, default `MediaPipe33`.
  - `DebugView` (Toggle) — overlay labels/lines helpful during dev.
- **Framing**
  - `CanvasW`, `CanvasH` (Int) — render resolution if no meta input (default 1280×720).
  - `Origin` (Menu: `UV_0_1`, `NDC_-1_1`) — how to interpret incoming coords (default `UV_0_1`).
- **Style**
  - (Effect-specific, detailed per effect below.)

**Utility DATs (inside each fxCore):**

- `landmark_names` (Text DAT) — single-column list in fixed order (matches your mapping).
- `connections` (Table DAT) — 2 columns: `from`, `to` landmark names (Skeleton only).
- `hands` (Table DAT) — landmark names for L/R hands used by emitters.

**Common Pre-processing (inside each fxCore):**

- `null_skel` (Null CHOP) — hold incoming skeleton.
- `meta_fallback` (Constant CHOP) — `image_width`, `image_height` default.
- `meta_mux` (Switch CHOP) — choose `meta_in` if connected else `meta_fallback`.
- `uv_to_ndc` (Math CHOP) —
   If `Origin=UV_0_1`:
  - x: `(x * 2) - 1`
  - y: `((1 - y) * 2) - 1` (flip Y for TD camera)
     Else pass-through.
- `pack_xyz` (Reorder/Combine CHOP) — ensure triplets per landmark are grouped and named cleanly.

> **Tip:** keep **Selective Cook** on everywhere you can; effects update only when selected.

------

### 2) PoseEffect_Dots

**Goal:** Draw 1 dot per landmark. Color can be fixed or random-per-landmark.

**Extra Style Parameters:**

- `DotSize` (Float) — default 8 px.
- `ColorMode` (Menu) — `Fixed`, `RandomPerLandmark` (default `Fixed`).
- `Color` (RGBA) — default white.
- `Opacity` (0–1) — default 1.0.

**Internal Operators:**

1. `landmark_to_instances` (CHOP Execute DAT or simple Script CHOP)
   - Build **instance data** CHOP with channels: `tx, ty, tz, r, g, b, a, psize`.
   - Mapping: `tx,ty` from `uv_to_ndc`; `r,g,b,a` from style; if `RandomPerLandmark`, seed a deterministic color per channel set (e.g., hash of name).
2. `dot_geo` (Geometry COMP)
   - **Instance** a simple sprite (Rectangle SOP or Point SOP).
   - Instance X/Y from `tx/ty`; Uniform Scale from `psize / CanvasH` (so dot size is pixel-ish).
3. `dot_mat` (Constant MAT) or `Point Sprite MAT`
   - Color = `r,g,b,a` instances; enable **Add** or **Over** blend.
4. `cam` (Camera COMP) — default ortho; viewport matches `CanvasW/H`.
5. `light` (Light COMP) — optional (Constant MAT doesn’t need it).
6. `render` (Render TOP) — outputs `out_color`.
7. `comp_bg` (Over TOP) — optional; composite dots over a flat or incoming background.

**Notes:**

- If you want **pixel-accurate** dots in orthographic, compute per-instance scale as `DotSize / CanvasH` and set camera width = 2 with NDC input.

------

### 3) PoseEffect_Skeleton

**Goal:** Tubes/lines joining landmark pairs (MediaPipe POSE_CONNECTIONS-esque).

**Extra Style Parameters:**

- `LineMode` (Menu) — `Tube3D`, `FlatLine`.
- `LineWidth` (Float) — default 4 px.
- `ColorMode` (Menu) — `Fixed`, `ByConfidence` (lerp low→high).
- `ColorLo` (RGBA) — default (0.2,0.2,0.2,1).
- `ColorHi` (RGBA) — default (1,1,1,1).
- `Opacity` (Float) — default 1.0.
- `CornerJoin` (Menu) — `Miter`, `Bevel`, `Round` (for FlatLine compositor).

**Internal Operators:**

1. `connections` (Table DAT)
   - Two columns: `from`, `to`. Populate with your pose edge list (e.g., `shoulder_l → elbow_l`, `elbow_l → wrist_l`, …).
2. `pair_sampler` (Script CHOP)
   - For each row in `connections`, fetch `from_x/y/z` and `to_x/y/z` from `uv_to_ndc`.
   - Output channels per segment: `x1,y1,z1,x2,y2,z2,conf` (conf = min(z1,z2) if z=confidence).
3. **If `LineMode=FlatLine`**
   - `seg_geo` (Geometry COMP with Instancing) + `Line MAT` or `Wireframe MAT` won’t give thick billboard. Instead:
   - **Use Instanced Quads:**
     - Compute per-segment: midpoint (tx,ty), length (L), angle (θ).
     - Instance a unit rectangle and scale X=L, Y=LineWidth/CanvasH; rotate by θ.
     - Color via `ByConfidence` → lerp `ColorLo/ColorHi` with `conf`.
4. **If `LineMode=Tube3D`**
   - Build a dynamic SOP network (optional heavier):
     - For each segment, generate a small polyline (Add SOP from two points) → Sweep SOP with radius = `LineWidth/CanvasH`.
     - Merge all; render via Phong MAT.
   - This is slower; prefer FlatLine instanced quads.
5. `skeleton_mat` (Constant MAT or PBR) — color as above; **Blend** enabled.
6. `cam`, `light`, `render`, `out_color` — as with Dots.

**Notes:**

- Instanced quads give you **fast thick lines** and easy width control in pixels.
- If you later move to GLSL, a single draw-call line-strip with geometry shader billboarding is even faster.

------

### 4) PoseEffect_HandEmitter

**Goal:** Use hand landmarks as **emitters** and output a **particle TOP** (e.g., nice glow trails).

**Extra Style Parameters:**

- `Emitter` (Menu) — `RightHand`, `LeftHand`, `Both`.
- `Rate` (Float) — particles/sec per hand (default 200).
- `Speed` (Float) — initial speed (default 0.25).
- `Spread` (Float) — emission cone (default 0.2 rad equiv).
- `Life` (Float) — seconds (default 1.5).
- `SizeRange` (2-Float) — min/max size in px (default 2–8).
- `ColorMode` (Menu) — `Fixed`, `HandSideTwoColor`.
- `ColorR` (RGBA) — default warm.
- `ColorL` (RGBA) — default cool.
- `Trail` (Float 0–1) — feedback persistence (default 0.85).
- `Glow` (Float) — post bloom intensity (default 0.6).

**Internal Operators (TOP‑centric, fast and pretty):**

1. **Hand Position Extraction**
   - `hands` (Table DAT) lists `handtip_r`, `handtip_l` (or whichever tip indices you use).
   - `hand_picker` (Script CHOP) ⇒ produce `emit_r_tx, emit_r_ty, emit_l_tx, emit_l_ty` in **NDC** from `uv_to_ndc`.
2. **Particle Field (TOP feedback approach)**
   - `emit_canvas` (Constant TOP) — small res (e.g., 640×360) for fluid framerate.
   - `emit_splats` (Composite TOP pipeline)
     - Create two **Circle TOPs** (or GLSL points) positioned with **Transform TOP** using `emit_*` values (use CHOP-to TOP Xform via expressions or Panel/Instancing).
     - Modulate alpha by `Rate`, `Life`. For **Both**, composite additively.
   - `velocity_field` (Noise TOP) — animating noise scaled by `Speed/Spread` for pseudo-flow.
   - `advect` (Displace TOP) — displace previous frame by `velocity_field`.
   - `fade` (Level TOP) — multiply by `Trail`.
   - `accumulate` (Add TOP) — `fade + emit_splats` → persistent trails.
   - `glow` (Bloom TOP) — tune with `Glow`.
3. **Hand Color**
   - If `ColorMode=HandSideTwoColor`, tint each emitter path by `ColorR/ColorL` before `accumulate`.
4. `out_color` — final TOP out.

**Alternative (SOP Particle system):**

- Use **Particle SOP** with emitters at hand points → **Render TOP**. Looks classic but typically heavier vs TOP feedback.

**Notes:**

- This TOP feedback rig is **GPU-cheap** and resolution-independent for the rest of your scene.
- You can gate emission by confidence (`z`) to avoid jittery hands: scale splat alpha by `max(conf,0)`.

------

### 5) Landmark/Connection Tables (drop-in examples)

**`landmark_names` (Text DAT; 33 MediaPipe order):**

```
head
mp_eye_inner_l
eye_l
mp_eye_outer_l
mp_eye_inner_r
eye_r
mp_eye_outer_r
mp_ear_l
mp_ear_r
mp_mouth_l
mp_mouth_r
shoulder_l
shoulder_r
elbow_l
elbow_r
wrist_l
wrist_r
mp_pinky_l
mp_pinky_r
handtip_l
handtip_r
thumb_l
thumb_r
hip_l
hip_r
knee_l
knee_r
ankle_l
ankle_r
mp_heel_l
mp_heel_r
foot_l
foot_r
```

**`connections` (Table DAT; 2 cols):**

```
shoulder_l	shoulder_r
shoulder_l	elbow_l
elbow_l	wrist_l
wrist_l	handtip_l
shoulder_r	elbow_r
elbow_r	wrist_r
wrist_r	handtip_r
hip_l	hip_r
hip_l	knee_l
knee_l	ankle_l
hip_r	knee_r
knee_r	ankle_r
shoulder_l	hip_l
shoulder_r	hip_r
```

*(Add torso/head as you prefer.)*

**`hands` (Table DAT):**

```
right	handtip_r
left	handtip_l
```

------

### 6) Channel → Instance Mapping (expressions you’ll reuse)

- **UV→NDC (per channel)**
   `ndc_x = (uv_x * 2) - 1`
   `ndc_y = ((1 - uv_y) * 2) - 1`
- **Pixel-sized dots in ortho camera**
   `scale = DotSize / CanvasH`
- **Segment orientation (for instanced quads)**
   `dx = x2 - x1`
   `dy = y2 - y1`
   `length = sqrt(dx*dx + dy*dy)`
   `angle = atan2(dy, dx)`
   `mid_x = (x1 + x2) * 0.5`
   `mid_y = (y1 + y2) * 0.5`

------

### 7) Performance Notes

- Prefer **instancing** (Dots, Skeleton quads) over per-landmark SOP cooking.
- Keep emitter canvas smaller (e.g., 640×360) and upscale if needed.
- Enable **Selective Cook** on non-active effects and heavy subnets.
- Cache static DATs (names, connections).

------

