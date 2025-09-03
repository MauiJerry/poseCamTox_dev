# Pop **Stick-Bones COMP** 3

yeah v2 was crap. too high level, asked for explicit directions

yeah v3 fell apart half way thru so v4 pick up new receipe at inside BoneUnit

# Prompt

That is incomplete, but remember it.  BoneUnit Comp exists inside the fxCore Comp, which has inputs inLandmark Chop, inMeta Dat, and loads the SkeletonPairs Table Dat.  We were making a BoneUnit as a template and were then going to replicate it somehow. The BoneUnit is a Base Comp with inputs (inLandmarks Chop and SkeletonPairs Dat), we created parameters on the BoneUnit (start_landmark str, end_landmark str, start_radius float, end_radius float, image_width int, image_height int, aspect float, flipy toggle).  inside BoneUnit we created a Script Chop containing the landmarkSampleByDat.py.  That was where I noticed you were going down the SOP path.
How much of that do we still need?  What does the Pop BoneUnit look like and how is it used in the parent fxCore to replicate and get the proper row data from the SkeletonPairs Dat?
Please give detailed instructions on the BoneUnit (parameters, in, outs, and the ops inside).  Check your design against the Derivative.ca touchdesigner wiki for accurate use of Ops.  Check the naming conventions used in the landmarkSampleByDat and in skeletonPairs. ideally bone units would get named by the name column in skeletonPairs.csv

## Response

Perfect—here’s a clean, **POP-only geometry** BoneUnit that still uses your existing **`landmarkSampleByDat.py`** to get the bone’s center/length/angle from the incoming landmark CHOP, but then switches to **POP operators** (Tube + Copy) for the mesh. This slots inside your existing **`fxCore`** exactly as you described.



------

### Where everything lives (context)

- **`fxCore` COMP (parent)**
  - **Inputs**
    - `inLandmarks` (CHOP): named channels like `shoulder_l_x, shoulder_l_y, shoulder_l_z`, etc.
    - `inMeta` (DAT): contains `image_width`, `image_height`, `aspect`, `flipy` (or those exposed as custom pars on `fxCore`)
  - **Tables**
    - `skeletonPairs` (Table DAT): rows with at least
       `bone, start_landmark, end_landmark, start_radius, end_radius`
  - **Children**
    - `BoneUnit` (a **Base COMP** template) — we will **replicate** one per row in `skeletonPairs`.

------

## BoneUnit (Base COMP) — definitive POP version

#### Inputs to BoneUnit (from parent wiring)

- **`inLandmarks` (CHOP In)** — connect from `fxCore/inLandmarks`
- **`skeletonPairs` (DAT In)** — connect from `fxCore/skeletonPairs` (the whole table is fine)

#### Custom parameters on BoneUnit

Keep these (same names you’ve been using so far), and we’ll auto-fill them from each row at replicate time:

- `start_landmark` (Str) — e.g., `shoulder_l`
- `end_landmark`   (Str) — e.g., `elbow_l`
- `start_radius`   (Float) — pixels (or your chosen unit)
- `end_radius`     (Float)
- `image_width`    (Int) — read from parent `fxCore` (bind to `op('..').par.image_width`)
- `image_height`   (Int) — bind to parent
- `aspect`         (Float) — bind to parent if you need it for other logic
- `flipy`          (Toggle) — bind to parent

> You **still want** these parameters because `landmarkSampleByDat.py` uses `start_landmark`/`end_landmark` and `image_*`/`flipy` to produce center/length/angle consistently. 

------

Yes—since `start_radius` / `end_radius` live as **BoneUnit parameters**, the cleanest way to finish **B (Attributes → POP)** is to pull those params as CHOP channels and feed **one** `CHOP to POP`. No extra Attribute POP or DAT plumbing needed.

# Minimal inside-BoneUnit wiring (POP-only mesh, no SOP)

**Prereqs:** your updated `landmarkSampleByDat.py` already outputs
 `center_x_px, center_y_px, length_px, dir_x, dir_y, alpha, …` (so no angle→dir math nodes). 

## Nodes

1. **CHOP In** `inLandmarks`
    (wired from `fxCore/inLandmarks`)

2. **Script CHOP** `landmarkSample`

   - Script: your `landmarkSampleByDat.py` (updated version that emits `dir_x/dir_y`) 
   - Reads BoneUnit pars: `start_landmark`, `end_landmark`, `image_width`, `image_height`, `flipy`.

3. **Parameter CHOP** `pars`

   - Channels to fetch: `start_radius`, `end_radius`
   - (This brings your BoneUnit parameters in as CHOP channels automatically; no Expressions needed.)

4. **Constant CHOP** `zeros`

   - Make two channels: `cz = 0`, `vz = 0` (we’ll use these for `C.z` and `V.z` so the mapper is explicit)

5. **Merge CHOP** `boneAttrsCHOP`

   - Inputs: `landmarkSample`, `pars`, `zeros`
   - After this you have one CHOP bundle with:
      `center_x_px, center_y_px, length_px, dir_x, dir_y, alpha, start_radius, end_radius, cz, vz`.

6. **CHOP to POP** `attrs_to_pop`

   - **Samples:** single-sample → creates **1 template POP point**
   - **Attributes tab → Add the mappings below:**

   | POP Attribute   | Component | Source channel |
   | --------------- | --------- | -------------- |
   | `C` (float3)    | x         | `center_x_px`  |
   |                 | y         | `center_y_px`  |
   |                 | z         | `cz`           |
   | `V` (float3)    | x         | `dir_x`        |
   |                 | y         | `dir_y`        |
   |                 | z         | `vz`           |
   | `Len` (float)   | –         | `length_px`    |
   | `Alpha` (float) | –         | `alpha`        |
   | `R0` (float)    | –         | `start_radius` |
   | `R1` (float)    | –         | `end_radius`   |

   > That’s the whole “B” stage in one node: no Attribute POP, no extra Math/Rename needed.

7. **Math POP** `makeScale`

   - On that single template point, create `S` (float3) for Copy scale:
     - `Ravg = (R0 + R1) * 0.5`
     - `S = ( Ravg, Len, Ravg )`

8. **Tube POP** `unit_tube`

   - Axis: `+Y`, Height: `1`, Radius: `0.5` (ends equal), modest rows/cols.

9. **Copy POP** `copy_to_bone`

   - **Input 0 (Source):** `unit_tube`
   - **Input 1 (Template):** the template point stream (from `attrs_to_pop/makeScale`)
   - **Settings:**
     - Rotate to Vector: **On**
     - Rotate to Vector Attribute: `V`
     - Forward Direction: **+Y**
     - Template Translate Attribute: `C`
     - Template Scale Attribute: `S`

10. **Out POP** `out_bone`

> POP geometry only: Tube + Copy use those attributes directly; no SOPs or materials involved. Your Script CHOP keeps the name-based landmark sampling and pixel conversion consistent with the rest of your pipeline. 

# Using this in `fxCore` with Replicator (unchanged, just simpler)

- **`fxCore`** holds `inLandmarks` (CHOP), `inMeta` (if you expose image params there), and `skeletonPairs` (Table DAT).

- **Replicator**: Template = `BoneUnit`, Template DAT = `skeletonPairs`. In `onCreate`, set BoneUnit pars from the row and **rename the clone from the `bone` column** so units become `Pelvis`, `L_UpperArm`, etc.—exactly matching your CSV naming. 

  ```python
  # boneRep_callbacks (fxCore)
  def onCreate(comp, template, master, row):
      comp.name                = row['bone']          # name clone by CSV 'bone'
      comp.par.start_landmark  = row['start_landmark']
      comp.par.end_landmark    = row['end_landmark']
      comp.par.start_radius    = float(row['start_radius'])
      comp.par.end_radius      = float(row['end_radius'])
      return
  ```

- Each clone’s **Parameter CHOP** will pull its own `start_radius`/`end_radius` (already set by the callbacks), so **B** remains a single `CHOP to POP` mapping.

# Why this is the simplest correct version

- Your Python already outputs `dir_x/dir_y` and all the pixel-space values, so **no extra CHOP math** is needed before POP. 
- `Parameter CHOP` is the most direct way to surface per-clone **parameters** as channels for the attribute mapper, avoiding extra DAT→CHOP boilerplate.
- POP Copy reads one **template point** worth of attributes; giving it `C`, `V`, `Len`, and `S` is exactly what’s needed for a single-pass tube placement/aim/scale.

If you later want a POP-only “two-segment taper” (R0→Ravg, then Ravg→R1) without SOPs/GLSL, say the word and I’ll bolt it on top of this with just one extra template point and a second Copy POP.