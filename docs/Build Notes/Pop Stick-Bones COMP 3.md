# Pop **Stick-Bones COMP** 3

yeah v2 was crap. too high level, asked for explicit directions

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

### Inside BoneUnit — operator list (no SOPs, no MATs)

**A) Sample the 2 landmarks (CHOP logic only; you already have this)**

1. **Script CHOP** `landmarkSample`

   - Paste in your `landmarkSampleByDat.py`.
   - It reads:
     - the parent component to find the landmark source (we’ll point it to `../inLandmarks`),
     - `start_landmark`, `end_landmark`,
     - `image_width`, `image_height`, `flipy`.
   - **Outputs** (channel names from your script):
      `center_x_px, center_y_px, length_px, angle_deg, alpha, start_x_px, start_y_px, end_x_px, end_y_px` 

   > If your script currently searches for `inLandmark` vs `lag1`, you can either keep a `Null CHOP` called `inLandmark` inside `BoneUnit` that references `../inLandmarks`, or edit the script to point to `../inLandmarks` explicitly. (Your script is otherwise fine.) 

   <u>Currently the script gives an error saying  parent comp has on start_landmark parameter</u>

     `start_landmark_name = owner_comp.par.start_landmark.eval().strip()`

   <u>oh, its TD Parameter naming.  forces name to be Startlandmark, Endlandmark</u>

   <u>be ware for others lower down?</u>

   <u>it looked for parent.parent to get par for image_*</u>

   <u>and of course it got the TD parameter names wrong.</u>

   <u>and it still has more errors, asking for inChop.channels</u>

2. **Math CHOP** `angleToVec`
   <u>this is bit wrong. the input channels include angle_deg added by the previous script, we can easily add these two channels, eliminating need for merge after</u>

   - Create `dir_x` and `dir_y` from `angle_deg` (degrees):
     - `dir_x = cos(radians(angle_deg))`
     - `dir_y = sin(radians(angle_deg))`
   - In TouchDesigner: easiest is an **Expression CHOP**:
     - Channel 1 (name: `dir_x`): `cos(radians(ch("../landmarkSample/angle_deg")))`
     - Channel 2 (name: `dir_y`): `sin(radians(ch("../landmarkSample/angle_deg")))`

3. **Merge CHOP** `boneAttrsCHOP`

   - Merge: `landmarkSample` + `angleToVec`
   - We now have in one CHOP:
      `center_x_px, center_y_px, length_px, angle_deg, alpha, dir_x, dir_y`

**B) Turn those channels into a single POP “template point” with attributes**

1. **CHOP to POP** `attrs_chop2pop`

   - **Input:** `boneAttrsCHOP`
   - **Samples:** your channels are single-sample — that will produce exactly **1 POP point**.
   - **New Attributes (add entries):**
     - `C` (float3): `P(0) = center_x_px`, `P(1) = center_y_px`, `P(2) = 0`
     - `V` (float3): `P(0) = dir_x`, `P(1) = dir_y`, `P(2) = 0`
     - `Len` (float): `length_px`
     - `Alpha` (float): `alpha`
     - `R0` (float): later provided (start radius)
     - `R1` (float): later provided (end radius)

   (You can add all these in the CHOP to POP’s **Attributes** page by creating attributes and pointing to channel names.)

2. **DAT to CHOP** `radii_dat2chop`

   - Extract the `start_radius` & `end_radius` for this bone:
     - **If you want per-clone parameters:** Just use a **Constant CHOP** with
       - `R0 = ch("../start_radius")`
       - `R1 = ch("../end_radius")`
     - **If you prefer reading the row DAT:** Use a small **Select DAT** to isolate this bone’s row and a **DAT to CHOP** to channels `start_radius` → `R0`, `end_radius` → `R1`.

3. **Attribute POP** `attach_radii`

   - **Input 0:** `attrs_chop2pop`
   - **Input 1:** `radii_dat2chop` (converted to POP first via an extra `CHOP to POP` OR simply append the `R0/R1` channels to `boneAttrsCHOP` before step 4)
   - **Purpose:** Ensure the single template point has `R0` and `R1`.
      (Simpler path: add `R0/R1` channels into `boneAttrsCHOP` first, then step 4 maps them all at once.)

> After step 4 (and either 5/6 or the simpler pre-merge), you have **one POP point** carrying attributes:
>  `C` (center), `V` (unit direction), `Len`, `R0`, `R1`, `Alpha`.

**C) Make a unit tube once, copy to template (POP geometry)**

1. **Tube POP** `unit_tube`
   - **Axis:** +Y
   - **Height:** `1`
   - **Radius:** `0.5` (ends equal; this is a unit base shape)
   - **Polygons:** Triangles or Quads; set rows/cols (keep light)
2. **Math POP** `makeScale`
   - **Input:** the **single template point** stream (from `attrs_chop2pop`)
   - **Create attribute** `S` (float3) to be used by Copy:
     - If you accept **uniform thickness** (no taper) in POP:
        `S = ( Ravg, Len, Ravg )` where `Ravg = (R0 + R1)/2`
     - If you want a coarse 2-segment taper in POP: you’ll do two copies (see tip below).
3. **Copy POP** `copy_to_bone`
   - **Input 0 (Source):** `unit_tube`
   - **Input 1 (Template):** the **template point** (with `C`, `V`, `Len`, `S`)
   - **Template settings:**
     - **Rotate to Vector:** On
     - **Rotate to Vector Attribute:** `V`
     - **Forward Direction:** +Y
     - **Template Translate Attribute:** `C`
     - **Template Scale Attribute:** `S`  (so X/Z scale to radius, Y to length)
4. **Out POP** `out_bone`

- Output of `copy_to_bone`.

> **About taper (R0 → R1) in POP:** Copy POP supports a single scale vector, not a per-vertex profile. Two easy POP-only options:
>
> - **Two copies method**: create two template points (one with `S=(R0, Len*0.5, Ravg)` and another with `S=(Ravg, Len*0.5, R1)`) and place the second’s `C` offset along +Y by `Len*0.25` and the first by `-Len*0.25`. You’ll get a crude linear taper in two segments.
> - **Uniform thickness**: use `Ravg` for X/Z and keep it simple (often looks fine with a decent tube tessellation).

All the geometry here is POP; no SOPs or MATs. (You can still render via a Geometry COMP that points to this POP stream in the **parent** scene.)

------

## Using BoneUnit inside `fxCore` and replicating from `skeletonPairs`

**A) Replicator setup in `fxCore`**

1. **Replicator COMP** `boneRep`
   - **Template OP:** `./BoneUnit`
   - **Template DAT:** `./skeletonPairs` (the full table)
   - **Callbacks DAT:** `boneRep_callbacks` with:

```python
# boneRep_callbacks
def onCreate(comp, template, master, row):
    # Name the clone after the bone (nice for debugging and selection)
    comp.name = row['bone']

    # Set BoneUnit parameters from the row
    comp.par.start_landmark = row['start_landmark']
    comp.par.end_landmark   = row['end_landmark']
    comp.par.start_radius   = float(row['start_radius'])
    comp.par.end_radius     = float(row['end_radius'])

    # Inherit image size/flip from fxCore parent (already bound)
    # Nothing else needed here since BoneUnit reads ../inLandmarks

    return
```

> This ensures **clone names** match the `bone` column in the CSV (as you wanted) and that each BoneUnit has the correct landmark names and radii.

**B) Connecting inputs**

- Inside each clone, create:
  - **CHOP In** `inLandmarks` → connect from `fxCore/inLandmarks`
  - (If you want to also read the table to confirm, a **DAT In** `skeletonPairs` can be connected too, but not required because we set pars on create.)

**C) Collect all bones and render**

- In `fxCore`, add a **Geometry COMP** pointing to a **Merge POP** that merges `BoneUnit*/out_bone`. Then use your existing Camera/Render TOP pipeline in `fxCore`. (Or, if you already do that in a higher layer, simply expose an **Out POP** from `fxCore` and render elsewhere.)

------

## Why keep `landmarkSampleByDat.py`?

- It already performs robust name-based sampling (`start_landmark`, `end_landmark`), pixel conversion using `image_width/height`, and flip-Y treatment—so you don’t need to invent a fragile index mapping inside POP. It outputs everything we need to drive the POP copy (`center`, `length`, `angle` → `dir_x/dir_y`). 

## Why this is “POP-only geometry”

- The only geometry creation/manipulation nodes are **Tube POP** and **Copy POP**. We never touch SOPs or GPU shaders here. That matches your earlier constraint (“not SOP; all POP”). For tapered profiles beyond the 2-segment trick, we’d need either SOP deformation or a shader—but you explicitly asked to avoid those here. 

------

### Quick verification checklist

- Open one clone `BoneUnit/landmarkSample` and confirm channels update from your live `inLandmarks`.
- In `BoneUnit/attrs_chop2pop`, open the POP viewer: you should see **1 template point** (with attributes).
- In `BoneUnit/copy_to_bone`, POP viewer should show a tube aligned between the two landmarks.
- After replicating, confirm each clone is **named** from the `bone` column (e.g., `L_UpperArm`, `Pelvis`, etc.).
- In the parent, merge `BoneUnit*/out_bone` and render. If Y is inverted, toggle `fxCore.par.flipy`.

------

If you want, I can also give the tiny “two-segment taper” add-on (adds a second template point + second Copy POP) that reads both `R0` and `R1` to fake a visible taper while staying strictly in POPs.