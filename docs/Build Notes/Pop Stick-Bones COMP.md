# Pop **Stick-Bones COMP** 

### Goal

Build a **Stick-Bones COMP** that renders a stickman using **per-bone quads** (camera-facing “tubes”), driven by your **named landmark x/y/z CHOP channels**, with **start/end radii** (taper) and a **material TOP** (e.g., fur/scale tile). It’s one reusable bone “op chain” cloned for every row in `skeletonPairs.csv` via a **Replicator COMP**. No POPs required.

------

### Files / tables

**`skeletonPairs.csv` (recommended schema)**

```
bone,start_lm,end_lm,start_r,end_r,uv_tile(optional)
L_UpperArm,left_shoulder,left_elbow,0.055,0.045,0
L_Forearm,left_elbow,left_wrist,0.045,0.040,1
R_UpperArm,right_shoulder,right_elbow,0.055,0.045,0
R_Forearm,right_elbow,right_wrist,0.045,0.040,1
L_Thigh,left_hip,left_knee,0.065,0.055,2
L_Shin,left_knee,left_ankle,0.055,0.045,2
R_Thigh,right_hip,right_knee,0.065,0.055,2
R_Shin,right_knee,right_ankle,0.055,0.045,2
Spine,hips_mid,shoulders_mid,0.080,0.080,3
Clavicle,left_shoulder,right_shoulder,0.050,0.050,3
Pelvis,left_hip,right_hip,0.060,0.060,3
```

> Note: If you don’t already publish `hips_mid` / `shoulders_mid`, we’ll compute those from pairs.

------

### Top-level COMP: `stickBones`

leaving these off for now. get it working first

**Inputs**

- **CHOP In**: `pose_landmarks_in` (your OSC/MediaPipe stream with channels like `left_shoulder_x`, `left_shoulder_y`, `left_shoulder_z`, …)
- **DAT In**: `skeletonPairs_in` (load `skeletonPairs.csv`)

**Custom Parameters (on the `stickBones` COMP)**

- **Material**
  - `mat_top` (TOP Path): default to some tile in your sample library, e.g. `/project1/SampleLibrary/fur_01`
  - `mat_tiling_x` (float, 1..8, default 1.0)
  - `mat_tiling_y` (float, 1..8, default 1.0)
  - `alpha_cut` (0..1, default 0.2) – discard threshold in shader
- **Thickness & Taper**
  - `width_global` (float, default 1.0) – multiplies all radii
  - `use_taper` (toggle, default On) – if Off, use average of start/end
- **Coordinates**
  - `output_resx` / `output_resy` (int) – render size used to scale normalized [0..1] x/y
  - `flip_y` (toggle, default On) – if your source y=top-down, keep On
- **Smoothing / Visibility**
  - `lag` (ms, default 80) – light smoothing
  - `vis_thresh` (0..1, default 0.3) – fade out limbs if either endpoint below vis
- **Debug**
  - `show_debug` (toggle) – draw joints/lines overlay

**Outputs**

- **Out TOP**: the rendered stickman (with alpha)
- **Out CHOP** (optional): per-bone computed transforms & radii for downstream logic (`bone_name/tx,ty,rz,len,start_r,end_r,alpha`)
- out POP? combined Bones in one Pop Object?

------

### Inside `stickBones` (node sketch)

#### 1) Inputs & prep

- `pose_landmarks_in` (CHOP In) → `filter1` (Lag/Filter CHOP, driven by `par.lag`)
- `skeletonPairs_in` (Table DAT) → `selectPairs` (optional Select DAT) – you can filter/enable subsets here
- `nameIndex DAT` (small table mapping landmark names → channel stems), only needed if naming varies

#### 2) Landmark sampler (Base COMP: `lmSample`)

- **Purpose:** Tiny Script CHOP that, given two landmark names, outputs the two 2D points, their visibility, and derived midpoint/length/angle.
- **Inputs:** `pose_landmarks_in` + parameters `start_lm`, `end_lm`
- **Outputs (CHOP):**
  - `Ax, Ay, Az, Avis`
  - `Bx, By, Bz, Bvis`
  - `Tx, Ty` (midpoint in pixels), `LenPx` (pixels), `AngDeg` (atan2 in degrees)
- **Implementation notes:**
  - Convert normalized `x,y` → pixels with `* output_resx/y`.
  - If `flip_y`: `py = (1.0 - y) * output_resy`.
  - `Avis/Bvis` use your `*_z` if that’s confidence, otherwise derive from MediaPipe visibility if available.
  - **Alpha** per bone = smoothstep of `min(Avis,Bvis)` vs `vis_thresh`.

#### 3) Bone Unit (template) – Base COMP: `boneUnit`

This is the **one** bone op chain we’ll replicate.

**Custom parameters on `boneUnit`**

- `start_lm` (str), `end_lm` (str)
- `start_r` (float), `end_r` (float)
- (optional) `uv_tile` (int) – if using atlas rows/tiles
- All of the parent’s global params are **promoted references** (material, tiling, width_global, use_taper, alpha_cut, etc.) reading `op('..').par.*`

**Inside `boneUnit`**

- `lmSample1` (reference to parent module or a local Script CHOP) → gives `Tx,Ty,LenPx,AngDeg,Alpha`
- `radii1` (Math/Expression CHOP):
  - `R0 = start_r * parent.width_global`
  - `R1 = end_r * parent.width_global`
  - If `!use_taper`: set both to `(R0+R1)/2`
- `geo1` (Geometry COMP)
  - Contains a **Rectangle SOP** (unit 1×1 aligned along local Y, centered at 0, with UV [0..1])
  - **Instancing OFF** here (one rect per bone simplifies the per-bone taper shader)
- **Material**
  - `boneMat` (GLSL MAT or PBR MAT with custom vertex/frag)
    - **Vertex shader**: scale the unit rect so **Y-scale = LenPx**, **X-scale varies from R0 (at v=0) to R1 (at v=1)**. You can do pure vertex deformation (capsule-ish) by pushing X outward by a linear factor based on `v` (the rect’s vertical UV).
    - **Fragment shader**: sample `par.mat_top` with tiling; apply `alpha_cut` discard; optional soft edge by multiplying alpha with a radial mask `smoothstep(1.0, 0.0, distance_to_center / width_at_v)`.
  - Bind uniforms/attributes:
    - `uLen`, `uR0`, `uR1`, `uTiling` (vec2), `uAlpha`, `uTex` (sampler2D)
- **Xform**
  - On `geo1`, drive:
    - **Translate X/Y** = `Tx, Ty`
    - **Rotate Z** = `AngDeg`
    - **Uniform scale** = 1 (we scale in shader)
- **Cull when invisible**
  - Use `Switch TOP` or simply set `uAlpha=0` and shader discards when `Alpha < 0.01`.

**Output**

- `Out TOP` (from a local `Render TOP` if you choose to render per bone), but preferred: **no render here**. Let the parent render all bones in a single scene.

> **Recommended render pattern**: One **shared** Camera/Light/Render TOP at the parent level that includes all `boneUnit/*/geo1` via a **Render Select TOP** (or by parenting all `geo1` under a single `renderScene` COMP). This keeps it one draw scene.

#### 4) Replication (Replicator COMP: `boneRep`)

- **Template OP**: `/stickBones/boneUnit`

- **Template DAT**: `/stickBones/selectPairs` (one row per bone)

- **Callbacks DAT**: sets each clone’s parameters using `parent().digits` to pick the correct row; e.g.:

  ```python
  def onCreate(comp, template, master, row):
      t = op('selectPairs')
      r = row  # row is a Row object
      comp.par.start_lm = r['start_lm']
      comp.par.end_lm   = r['end_lm']
      comp.par.start_r  = float(r['start_r'])
      comp.par.end_r    = float(r['end_r'])
      if 'uv_tile' in r.cells: comp.par.uv_tile = int(r['uv_tile'])
      return
  ```

- **Auto-fill by op.num**: Replicator names clones like `boneUnit1`, `boneUnit2`, ...; inside `boneUnit`, you can also read `parent().digits` if you want to index a CHOP table directly.

#### 5) Shared Render

- **Camera COMP** (orthographic; size matches `output_resx/y`)
- **Light COMP** (optional if using unlit GLSL; for a toon PBR look, keep one Directional)
- **Render TOP** → `Out TOP`
  - **Resolution** = `output_resx/y`
  - **Alpha premultiplied** enabled
  - **Render objects**: either parent all `geo1` under a `Scene` COMP, or use a `Render Select` to collect them.

#### 6) Optional CHOP export (telemetry)

- Merge each `boneUnit`’s computed channels (`Tx,Ty,LenPx,AngDeg,R0,R1,Alpha`) into a **Fan CHOP** → **Out CHOP**. Name them `bone/tx`, `bone/ty`, etc. Useful for debugging and post-FX.

------

### Minimal GLSL (concept)

**Vertex** (pseudo-code; TD GLSL 3.30)

```glsl
// in attributes from rectangle: aPos (x,y), aUV (u,v)
uniform float uLen;       // pixels
uniform float uR0;        // start radius (pixels)
uniform float uR1;        // end   radius (pixels)
uniform mat4  uMVP;       // TD's camera MVP
// local billboard quad: y in [0..1], x in [-1..+1] scaled by radius

in vec2 aPos;  // assume aPos = (x in [-1,1], y in [0,1])
in vec2 aUV;

out vec2 vUV;
out float vV;   // carry vertical coordinate for frag

void main(){
    float t = clamp(aPos.y, 0.0, 1.0);       // 0 at start, 1 at end
    float radius = mix(uR0, uR1, t);         // linear taper
    vec2 pos = vec2(aPos.x * radius, aPos.y * uLen);
    gl_Position = uMVP * vec4(pos, 0.0, 1.0);
    vUV = aUV;
    vV  = t;
}
```

**Fragment**

```glsl
uniform sampler2D uTex;
uniform vec2  uTiling;   // mat_tiling_x/y
uniform float uAlpha;
uniform float uAlphaCut;

in vec2 vUV;
in float vV;
out vec4 fragColor;

void main(){
    // Optional soft edge mask across width (x in [-1,1] encoded into UV if needed)
    // Here we just sample a tiled texture:
    vec4 tex = texture(uTex, vUV * uTiling);
    float a = tex.a * uAlpha;
    if (a < uAlphaCut) discard;
    fragColor = vec4(tex.rgb, a);
}
```

> You can enhance with a **width mask** (round capsule) by passing normalized X as an attribute or rebuilding from `gl_FragCoord` space; the simple version above already looks good with alpha textures (fur/scale).

------

### How start/end radii work

- From CSV: `start_r`, `end_r` (in **relative units**). Multiply them by `width_global` (GUI) and optionally by **bone length fraction** if you want limbs to thicken with length.
- Shader linearly interpolates `uR0 → uR1` along the bone.

------

### Auto-filling from the DAT (per row)

- **Yes**: the **Replicator** sets each clone’s `start_lm`, `end_lm`, `start_r`, `end_r` from the corresponding `skeletonPairs.csv` row. This is the TD-native equivalent of “use TD copy to replicate and auto-fill by `op.num`”.
- You can **hot-reload** by editing the CSV; pulse the replicator to rebuild.

------

### Material source (fur/scale) & atlas option

- Point the top-level `mat_top` to any **tileable** texture TOP.
- If you prefer a **texture atlas** (multiple looks in one sheet), add a per-bone `uv_tile` column and offset the UVs in the shader by a tile table (e.g., 4×1 strip → `uv += vec2(tileIndex,0)/vec2(4,1)`).

------

### Debug overlay (optional)

- A small **TOP network** draws circles at joints and lines A→B using the same `lmSample` outputs; composited over the Render TOP when `show_debug` is on.

------

### Hooking up your poseCam pipeline

- Ensure landmark channel names in the CHOP match the CSV `start_lm/end_lm`.
   Example channels expected: `left_shoulder_x`, `left_shoulder_y`, `left_shoulder_z` (and same for end).
- If your naming differs, adapt the `lmSample` Script CHOP to build the proper channel names.

------

### Performance notes

- This approach avoids SOP cooking per frame; all deformation is in **GPU shaders**.
- One scene render for all bones; the number of bones in your CSV sets the clone count.
- The texture tile keeps bandwidth low; use 8-bit or 16-bit as needed.

------

If you want, I can package a **starter `.tox`**:

- `stickBones` COMP with custom parameters,
- `boneUnit` template,
- Replicator callbacks,
- Minimal GLSL MAT,
- Tiny `skeletonPairs.csv` example wired to MediaPipe landmark names.