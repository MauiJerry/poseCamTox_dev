# Pop **Stick-Bones COMP** 2

went a few rounds in ChatGPT with changes in code for landmarkSampleByDat.  Chat got waaay off track and hand me building a BoneUnit with SOP etc.

so 2Sept 9pm I redirected it...

but this seems to have lost context. very different Bone Unit Comp than we were building inside the fxCore.

So will go back for round 3.

You’re right—let’s keep **BoneUnit** 100% POP (no SOP/GLSL). Here’s an all-POP wiring that takes your **named CHOP landmarks** and the **SkeletonPairs DAT**, and outputs tube-bones via POPs only.



------

### BoneUnit (POP-only) — I/O

**Inside a `BoneUnit` COMP** (replicated per CSV row), wire these POP operators:

#### Inputs

- **CHOP to POP** (`lm_chop2pop`)
  - **In:** your landmarks CHOP (e.g., parent `pose_landmarks_in`) with channels like `shoulder_l_x/y/z`, `elbow_l_x/y/z`, etc.
  - **Map channels → position:** set “New Attribute” = `P`, with `P(0)=*_x`, `P(1)=*_y`, `P(2)=*_z` (if z is not depth/space, you can still store it; we won’t use it for P).
  - **Output:** a POP point cloud, one point per landmark (index = landmark index).
- **DAT to POP** (`bone_spec`)
  - **In:** a one-row DAT (the row for this bone) with at least:
    - `start_idx` (int) – index of start landmark
    - `end_idx` (int) – index of end landmark
    - `start_d` (float) – start diameter (px)
    - `end_d` (float) – end diameter (px)
  - **Create attributes:** `Aidx` (int), `Bidx` (int), `D0` (float), `D1` (float)
  - **Output:** one POP point carrying the bone spec as attributes

> If your CSV has **names** (e.g., `shoulder_l`, `elbow_l`) not indices, resolve to indices once (upstream) and feed this BoneUnit a single-row DAT with the **indices**. That keeps BoneUnit GPU-native.

------

### Build per-bone transform (POP attributes only)

1. **Lookup Attribute POP** (`lookupA`)
   - **Index Stream:** `bone_spec` (has `Aidx`)
   - **Value Stream:** `lm_chop2pop` (has `P`)
   - **Lookup by:** `Point Index` = `Aidx`
   - **Attributes to fetch:** `P` → **write to** `Pa` (float3) on the bone_spec point
2. **Lookup Attribute POP** (`lookupB`)
   - Same, but `Point Index` = `Bidx` and write `P` → `Pb` (float3)
3. **Math POP** (`bone_math`)
   - **In:** the bone_spec stream now with `Pa` and `Pb`
   - **Create attributes:**
     - `C` = midpoint = `(Pa + Pb) * 0.5` (float3)
     - `V` = direction = `normalize(Pb - Pa)` (float3)
     - `Len` = `length(Pb - Pa)` (float)
     - `Dia` = `(D0 + D1) * 0.5` (float)  *(POP can’t taper a copied primitive natively; use avg for now—see note below)*
   - (You can add tiny smoothing here with an **Attribute Filter POP** if you want per-bone stability.)

------

### Make a unit tube once, then copy to the bone (still POP-only)

1. **Tube POP** (`unit_tube`)
   - **Axis:** +Y
   - **Height:** `1`
   - **Radius:** `0.5` (both ends)
   - **Tessellation:** set rows/cols as you like (keeps it tubular, not just a line)
   - **Output:** a small tube primitive centered at origin, pointing +Y
2. **Copy POP** (`copy_to_bone`)
   - **Input 0 (Source):** `unit_tube` (the mesh to copy)
   - **Input 1 (Template):** bone_spec stream (after `bone_math`, which has `C`, `V`, `Len`, `Dia`)
   - **Template settings:**
     - **Rotate to Vector:** On
     - **Rotate to Vector Attribute:** `V`
     - **Forward Direction:** `+Y` (matches Tube axis)
     - **Template Translate Attribute:** `C`  (places tube at bone midpoint)
     - **Template Scale Attribute:** create `S = (Dia, Len, Dia)` (float3) in `bone_math`, and use it here to scale X/Z by diameter and Y by length

> **Result:** a correctly placed, aimed, and scaled **tube bone** rendered entirely via POPs.

------

### Outputs (from BoneUnit)

- **Out POP** (`out_bone`) — connect from `copy_to_bone`.
   This single POP stream is the bone geometry. When you replicate BoneUnit per CSV row, merge all `Out POP` into your parent’s scene or feed a downstream **Geometry COMP** that renders POP geometry.

> If this lives inside a higher-level `StickBones` COMP, you’ll typically collect all `BoneUnit*/out_bone` with a **Merge POP** (or simply connect them into a **Geometry COMP**’s POP parameter) and render once in the parent. That keeps it fast and tidy.

------

## Notes on taper (start/end radii)

- **POP Copy** supports uniform per-axis scale (`S=(sx,sy,sz)`), which is why we do the average diameter (`Dia`) and set X/Z = `Dia`, Y = `Len`.
- If you truly need a **taper** (start vs end diameters) **without SOPs/GLSL**, the POP toolset doesn’t expose a per-vertex scale along Y during copy. Two practical POP-only workarounds:
  1. **Split the bone into 2 segments** (two template rows), and set different `Dia` for each half. Visually close enough for many rigs.
  2. **Pre-author the Tube POP** with slight taper baked (top vs bottom radii) and **flip** it when start/end order reverses. This still yields a single uniform taper (not dynamic per bone), so it’s only useful if your bones share one taper profile.

If you’re okay letting the **shader** do taper, the earlier billboard approach gives perfect start/end radius interpolation—but that reintroduces a MAT. Since you asked for **POP-only geometry**, the average-diameter copy is the cleanest and most performant.

------

## Quick checklist (per BoneUnit)

1. `lm_chop2pop` — make landmark points with `P`
2. `bone_spec` — one bone row with `Aidx, Bidx, D0, D1`
3. `lookupA/lookupB` — fetch `Pa`, `Pb`
4. `bone_math` — compute `C, V, Len, Dia, S`
5. `unit_tube` — a 1×1 tube on +Y
6. `copy_to_bone` — rotate to `V`, translate to `C`, scale by `S=(Dia,Len,Dia)`
7. `out_bone` — Out POP

Replicate this **BoneUnit** per row in `SkeletonPairs` (via a **Replicator COMP** that feeds each clone a single-row DAT), then merge all `Out POP`s to render.