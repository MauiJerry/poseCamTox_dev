# Build PoseEffect_MASTER

### Overview

You’ll make a **PoseEffect template COMP**, save it as a `.tox`, and then **instantiate** it for each effect (Dots, HandEmitter, Skeleton, TexSkel). The two clean patterns you can use are:

- **External .tox pattern (recommended):** Each instance loads its logic from a .tox on disk (easy to share/version).
- **Clone pattern (good for live dev):** Instances “Clone” from a master COMP in the same .toe; mark sub‑areas as **Clone Immune** to customize per effect.

Below are the exact, click‑by‑click steps for both patterns—plus how to hook up your `/data/*.csv` filters and the `skeleton_edges.csv` for lines.

------

### Part A — Build the PoseEffect template COMP

1. **Create the template container**

   - Add a **Base/Container COMP** and name it `PoseEffect`.
   - Set **Cook Type** = `Selective`. (no such thing)
   - Add **Tags**: `PoseEffect`.

2. **Inside `PoseEffect` create a stable interface**

   - **Inputs:**
     - `in1` (**CHOP In**) – person‑routed channels (e.g., `p1_*`).
     - `in2` (**TOP In**, optional) – background/camera.
   - **Selector sub‑comp:** `landmarkSelect` (the CSV‑aware selector you built).
     - Wire: `in1` → `landmarkSelect` → `outCHOP` (a **Null CHOP**).
   - **Core:** `fxCore` (Base/Container). Leave as a stub in the template.
   - **Output:** `fxOut` (**TOP Out**) – the final image TOP.
   - **Wiring:** `landmarkSelect/outCHOP` → `fxCore` (as CHOP input) → render/composite → `fxOut`.

3. **Add custom parameters on `PoseEffect` (Customize Component…)**

   - Page **POSEFX**
     - `Active` (Pulse)
     - `Bypassinactive` (Toggle, default On)
     - `Filtermode` (Menu: `All`, `Hands`, `BasicPose`, `Face`, `CustomCSV`)
     - `Filtercsv` (File Path)
     - `Personid` (Int, default 1)
   - (Optional) **Help** page with a short “how to wire” note.

4. **Add the template extension (PoseEffectExt)**

   - Create a **Text DAT** `PoseEffectExt.py` with this minimal control surface:

     ```python
     class PoseEffectExt:
         def __init__(self, owner): self.owner = owner
         def SetActive(self, active: bool):
             self.owner.allowCooking = bool(active)
             core = self.owner.op('fxCore')
             if core: core.par.bypass = not active
         def ApplyFilter(self):
             sel = self.owner.op('landmarkSelect')
             if not sel: return
             sel.par.Personid  = self.owner.par.Personid.eval()
             sel.par.Filtermode = self.owner.par.Filtermode.eval()
             sel.par.Filtercsv  = self.owner.par.Filtercsv.eval()
             if hasattr(sel.ext, 'LandmarkSelectExt'):
                 sel.ext.LandmarkSelectExt.Rebuild()
     ```

   - Drag `PoseEffectExt.py` onto the COMP **Extensions** list.

   - Turn on: **Re-Init Extensions on Start**.

5. **LandmarkSelect as a re‑usable sub‑COMP**

   - Use your CSV‑aware `landmarkSelect` from earlier:
     - **Parameters:** `Filtermode`, `Filtercsv`, `Personid`.
     - Internals: `table_names` (points to `data/landmark_names.csv`), `table_mask` (points to masks or custom), `select1` (Select CHOP), `outCHOP` (Null).
     - **Extension** `LandmarkSelectExt` builds the `channame` string for `select1` from either names or fully‑qualified channels.
   - Save `landmarkSelect` as its own `.tox` too (optional, but handy).

------

### Part B — Save the template to disk (.tox)

1. **Set external scripting paths (optional)**
   - If you want the extension files external, put them under `/scripts` and set the COMP’s **Python Custom Module** path as needed.
2. **Save the component as a .tox**
   - **Right‑click** on the `PoseEffect` COMP → **Save Component…**
   - Choose: `tox/PoseEffect.tox`
   - In the save dialog, **uncheck** anything you don’t want embedded (e.g., media). Keep it lean.
3. **(Optional) Make it auto‑reload**
   - On the `PoseEffect` COMP: set **Operator Parameters ▸ External ▸ External .tox** to `tox/PoseEffect.tox`.
   - Turn on **Reload Custom Parameters**, **Reload Definitions**, **Load on Start**.
   - Now any edits to `tox/PoseEffect.tox` will reload across instances.

------

### Part C — Create each variant (Dots, HandEmitter, Skeleton, TexSkel)

#### Option 1 — External .tox per variant (most portable)

1. **Instantiate from the template**
   - Drag `tox/PoseEffect.tox` into your project (or create a new Base and set External .tox to that path).
   - Rename the new COMP to `PoseEffect_Dots` (for example).
2. **Mark `fxCore` as custom**
   - **Inside** `PoseEffect_Dots`, select `fxCore` and set **Clone Immune = On** (prevents it from being overwritten on reload, so you can build the unique graph per effect).
3. **Build the variant’s core**
   - **Dots:** Instancing points from `landmarkSelect/outCHOP`.
   - **HandEmitter:** particle/feedback network fed by hand tip CHOP channels.
   - **Skeleton:** (see Part D) use `data/skeleton_edges.csv` + an instanced bar or lines.
   - **TexSkel:** atlas/UV cards driven by limb vectors.
4. **Save as its own .tox (recommended)**
   - Right‑click `PoseEffect_Dots` → **Save Component…** → `tox/PoseEffect_Dots.tox`.
   - Repeat for `PoseEffect_HandEmitter`, `PoseEffect_Skeleton`, `PoseEffect_TexSkel`.

> Result: Each effect is a self‑contained .tox that still shares the same interface/extension semantics from the template.

#### Option 2 — Clone from a master in‑toe (good for quick iteration)

1. Keep a single `PoseEffect` **master** in the .toe (named `PoseEffect_MASTER`).
2. For each effect, create a new Base COMP and set **Clone** = `/path/to/PoseEffect_MASTER`, and **Enable Cloning** = On.
3. Inside each effect, set `fxCore` (and any per‑effect assets) **Clone Immune** and build the unique graph.

> This saves disk writes. When the master changes, all clones update—except any **Clone Immune** areas you customize per effect.

------

### Part D — Wire in `/data` CSVs (filters + edges)

- Your **initial filters** already exist in `/data`:
  - `masks_hands.csv`, `masks_basicpose.csv`, (add `masks_face.csv` when ready).
  - `landmark_names.csv` (canonical names).
  - `skeleton_edges.csv` (two columns `a,b` of landmark **names**).

**In each effect** you can set:

- `Filtermode = Hands/BasicPose/Face/CustomCSV`.
- If `CustomCSV`, set `Filtercsv` (e.g., `data/markSelect_custom.csv`).
- Call `ext.PoseEffectExt.ApplyFilter()` (or just toggle the parameter) to rebuild the Select CHOP list.

**Skeleton edges**

- In `PoseEffect_Skeleton/fxCore` add `edges` (Table DAT) → `data/skeleton_edges.csv`.

- Add a **Script CHOP** to compute per‑edge tx/ty/rz/scale from the two named landmarks:

  ```python
  # pairEval_callbacks.py
  import math
  def onCook(scriptOp):
      src = op('../landmarkSelect/outCHOP'); edges = op('edges')
      scriptOp.clear()
      tx = scriptOp.appendChan('tx'); ty = scriptOp.appendChan('ty')
      rz = scriptOp.appendChan('rz'); sc = scriptOp.appendChan('s')
      pid = int(parent().parent().par.Personid)
      for r in edges.rows()[1:]:
          a, b = r[0].val, r[1].val
          ax = src.get(f"p{pid}_{a}_x"); ay = src.get(f"p{pid}_{a}_y")
          bx = src.get(f"p{pid}_{b}_x"); by = src.get(f"p{pid}_{b}_y")
          if None in (ax,ay,bx,by): tx.append(0); ty.append(0); rz.append(0); sc.append(0); continue
          ax,ay,bx,by = ax[0],ay[0],bx[0],by[0]
          cx,cy = (ax+bx)/2,(ay+by)/2; dx,dy = (bx-ax),(by-ay)
          tx.append(cx); ty.append(cy); rz.append(math.degrees(math.atan2(dy,dx))); sc.append((dx*dx+dy*dy)**0.5)
  ```

- Use an **Instanced Geo** (rectangle bar) driven by those channels, then **Render TOP** → `fxOut`.

------

### Part E — Register variants with your Efx Switch

1. Drop your four effect COMPs (`PoseEffect_Dots`, …) into `EfxSwitch/effects`.

2. Wire each effect’s `TOP out` into a **Switch TOP** in order.

3. On `EfxSwitch`’s Active control callback:

   ```python
   def onValueChange(par, prev):
       comp = par.owner
       names = ['PoseEffect_Dots','PoseEffect_Skeleton','PoseEffect_HandEmitter','PoseEffect_TexSkel']
       idx = names.index(par.eval()) if par.name=='Activeefx' else comp.op('out_switch').par.index
       comp.op('out_switch').par.index = idx
       # allow only one to cook
       for i, n in enumerate(names):
           fx = comp.op('effects/' + n)
           if fx:
               fx.ext.PoseEffectExt.SetActive(i == idx)
               fx.ext.PoseEffectExt.ApplyFilter()
   ```

4. Confirm: only the active effect has non‑zero cook time; `out_switch` shows the correct TOP.

------

### Part F — Practical tips & gotchas

- **Nulls everywhere:** end your CHOP/TOP chains on **Null** for stable references.
- **Reload buttons:** expose a `Reload` pulse on each effect to re‑init extensions (bind to `par.reinitextensions.pulse()`).
- **Relative paths:** keep paths like `data/*.csv` and `tox/*.tox` **relative** to the .toe for portability.
- **Versioning:** name your .tox files semver‑ish (`PoseEffect_Skeleton-0.1.0.tox`) if you plan to ship them externally.
- **Clone vs External .tox:** You can combine them—develop with **Clones**, then **Save Component…** as external .tox for distribution.

------

### TL;DR checklist

-  Build `PoseEffect` template with `in1`, `landmarkSelect`, `fxCore`, `fxOut`, custom pars, and `PoseEffectExt`.
-  **Save Component…** → `tox/PoseEffect.tox`.
-  Instantiate four variants from the template; mark `fxCore` **Clone Immune**; build each core; save each as its own `.tox`.
-  Wire all into `EfxSwitch` with a **Switch TOP** and an activate callback that flips `allowCooking` and reapplies filters.
-  Point `landmarkSelect` at `/data` CSVs; for skeleton, read `skeleton_edges.csv` to build lines.

# prompt

if i use Option 2 clone from master in-toe, can that master be an instantiation of the PoseEffect.tox or bound to it such that if the master changes then the PoseEffect.tox is updated?  This would modularize the PoseEffect for use in other projects, while making the internal faster?

###### 

## Short answer

Yes—do this:

- Make a single **master** COMP in‑toe (e.g. `PoseEffect_MASTER`) whose **External .tox** points to `tox/PoseEffect.tox`.
- Make all effect instances **Clone** from `PoseEffect_MASTER`.
- When the **.tox file** changes → reload the master → all clones update.
- When you change the **master in‑toe**, it will **not** auto‑write back to the .tox; you must explicitly **Save Component…** (or script it). That’s the only missing “auto” link.

This gives you modularity across projects (the .tox on disk) and fast dev (clones update instantly).

------

### Recommended setup (once)

1. **Master that is “bound” to the .tox**

- Create `PoseEffect_MASTER` (Base/Container).
- Parameters → **External .tox**: `tox/PoseEffect.tox`.
- Turn on: **Load on Start**, **Reload Custom Parameters**, **Reload Definitions**.

1. **Clones for each effect**

- For `PoseEffect_Dots`, `PoseEffect_HandEmitter`, etc.:
  - Create a Base.
  - Set **Clone** = `/path/to/PoseEffect_MASTER`.
  - Turn **Enable Cloning** = On.
  - Inside each effect, mark only the per‑effect area (e.g. `fxCore`) **Clone Immune** so you can customize without breaking the shared scaffolding.

> Flow: `.tox` → (reloads into) **MASTER** → (propagates via clone) **ALL INSTANCES**.

------

### Keep .tox and master in sync

#### A) Pull changes from disk → master (and clones)

- **Manual:** right‑click `PoseEffect_MASTER` → **Reload** (or toggle the External .tox path).

- **Scripted:** `op('PoseEffect_MASTER').par.reload.pulse()`

- **Auto on start:** add an **Execute DAT** with:

  ```python
  def onStart():
      op('PoseEffect_MASTER').par.reload.pulse()
      return
  ```

#### B) Push changes from master → .tox (write file)

- **Manual:** right‑click `PoseEffect_MASTER` → **Save Component…** → `tox/PoseEffect.tox`.

- **Scripted (recommended):** store the path in the parameter and save to that path:

  ```python
  toxpath = op('PoseEffect_MASTER').par.externaltox.eval()
  op('PoseEffect_MASTER').save(toxpath)
  ```

- **Auto on project save:** in an **Execute DAT**:

  ```python
  def onProjectPreSave():
      m = op('PoseEffect_MASTER')
      if m.par.externaltox.eval():
          m.save(m.par.externaltox.eval())
      return
  ```

Now the workflow is clean:

- Edit internals in **MASTER** during dev → **Ctrl+S project** → pre‑save hook writes the master back to `PoseEffect.tox` → next boot (or reload) every clone in this and other projects picks up the same template.

------

### Practical tips

- **Dev loop speed:** leave clones enabled. Cloning is light; only the selected upstream network cooks. Your Efx Switch should still set `allowCooking` so only the active effect runs.
- **Per‑effect drift control:** Only mark `fxCore` (and any variant assets) **Clone Immune**. Keep interface bits (inputs, `landmarkSelect`, `fxOut`, extension) **not** immune so fixes in the template always flow down.
- **Version the .tox:** e.g., `tox/PoseEffect-0.2.1.tox`. Keep `PoseEffect_MASTER.externaltox` pointing at the current version; you can swap versions to test.
- **Reload button:** expose a `Reload` pulse on the master UI that does `par.reload.pulse()` and then forces your EfxSwitch to reapply filters to the newly reloaded clones.

------

### TL;DR

- **Yes**, your master can be an instantiation of `PoseEffect.tox` and all instances clone from it.
- **Changes to the .tox**: reload master → clones update.
- **Changes inside the master**: **explicitly save** back to the .tox (manual or scripted); there’s no automatic two‑way binding.