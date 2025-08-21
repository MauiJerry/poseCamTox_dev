# Build Guide: `PoseEffect_MASTER` Template (TouchDesigner)

> This doc shows how to build a reusable **PoseEffect** template in-toe, wire it to a disk `.tox`, and clone it for concrete effects (Dots, Skeleton, HandEmitter, TexSkel). It uses **COMP `allowCooking`** (cook flag) to gate whole effects and **Cook Type: Selective** on heavy nodes inside each effect.

------

#### Goals

- One **master** component, `PoseEffect_MASTER`, whose logic lives in `tox/PoseEffect.tox`.
- N **clones** (`PoseEffect_Dots`, `PoseEffect_Skeleton`, …) that inherit from the master, with only their `fxCore` marked **Clone Immune**.
- A clean **input/output interface** identical across effects.
- CSV-driven **LandmarkSelect** sub-component that maps `/data/*.csv` to CHOP channel lists.

------

#### Folder Layout (recommended)

```
/project
  /tox
    PoseEffect.tox              # template saved to disk
  /data
    landmark_names.csv
    masks_basicpose.csv
    masks_hands.csv
    skeleton_edges.csv
  /scripts
    PoseEffectExt.py
    LandmarkSelectExt.py
```

------

#### 1) Create `PoseEffect_MASTER` (COMP)

1. Add a **Base** (or Container) COMP at `/project1/PoseEffects/` and name it `PoseEffect_MASTER`.
2. On `PoseEffect_MASTER`:
   - **External .tox**: set to `tox/PoseEffect.tox`.
   - Enable: **Load on Start**, **Reload Custom Parameters**, **Reload Definitions**.
   - (You won’t find “Cook Type” here—COMPs don’t have it. We’ll use `allowCooking` later.)

------

#### 2) Define the Interface (inside `PoseEffect_MASTER`)

Create this exact node scaffold:

- `in1` — **CHOP In** *(required)* : person-routed channels (`p1_*`).
- `in2` — **TOP In** *(optional)* : camera/background feed.
- `landmarkSelect` — **Base COMP** (CSV-aware selector; see §3).
- `fxCore` — **Base/Container** (put effect-specific graph here).
- `fxOut` — **TOP Out** *(required)* : final image frame of the effect.
- `diag` — **Null CHOP** *(optional)* : debug metrics.

Wiring:

- `in1` → `landmarkSelect` → `outCHOP` → into `fxCore` (CHOP input).
- `in2` → into `fxCore` as needed (TOP input).
- `fxCore` → **Render/Composite** chain → `fxOut`.

**Inside `fxCore` (best practice):**

- Turn **Viewer** OFF on nonessential nodes.
- On heavy TOPs/CHOPs (Render, Composite, Feedback, large Script CHOPs), set **Common ▸ Cook Type = Selective**.

------

#### 3) `landmarkSelect` sub-component

**Purpose:** Turn `/data/*.csv` into a Select CHOP pattern of channels for a given person.

1. Create a Container COMP called landmarkSelect

2. in Component Editor

   - add Parameters

     - Filtermode` (Menu): `All Hands BasicPose CustomCSV
     - Filtercsv: (File ) set by code

   - Add Extension

     - enter name LandmarkSelectExt, ADD

       it creates extension with Object 

       op('./LandmarkSelectExt').module.LandmarkSelectExt(me)
       which will point to a Text DAT in the comp 

3. Inside `landmarkSelect`:

- `in1` — **CHOP In**
- `table_names` — **Table DAT** → `data/landmark_names.csv` (columns must include `name`)
- `table_mask` — **Table DAT** (file set by mode; accepts `name` or `chan` columns)
- `select1` — **Select CHOP** (`op` → `../in1`, `channame` set by extension)
- `outCHOP` — **Null CHOP**
- LandmarkSelectExt - Text DAT pointing to file /ext/LandmarkSelectExt.py

```python
# /ext/LandmarkSelectExt.py
class LandmarkSelectExt:
    def __init__(self, owner): self.owner = owner

    def _rows(self, tab):
        if tab.numRows <= 1: return []
        heads = [c.val.lower() for c in tab.row(0)]
        out = []
        for r in tab.rows()[1:]:
            out.append({heads[i]: r[i].val for i in range(min(len(heads), len(r)))})
        return out

    def _expand(self, name, pid):  # build pN_name_x/y(/z)
        base = f"p{pid}_{name}_"
        return [base+"x", base+"y", base+"z"]

    def Rebuild(self):
        par = self.owner.par
        pid = int(par.Personid)
        mode = par.Filtermode.eval()

        # choose CSV
        tmask = self.owner.op('table_mask')
        if mode == 'Hands':
            tmask.par.file = 'data/masks_hands.csv'
        elif mode == 'Basicpose':
            tmask.par.file = 'data/masks_basicpose.csv'
        elif mode == 'Customcsv':
            tmask.par.file = par.Filtercsv.eval()
        else:
            tmask.par.file = ''   # All

        # build channel list
        chans = []
        if mode == 'All':
            for row in self._rows(self.owner.op('table_names')):
                nm = row.get('name', '').strip()
                if nm: chans += self._expand(nm, pid)
        else:
            for row in self._rows(tmask):
                ch = (row.get('chan') or '').strip()
                nm = (row.get('name') or '').strip()
                if ch:
                    chans.append(ch)        # accepts wildcards if you use them
                elif nm:
                    chans += self._expand(nm, pid)

        # de-dup preserve order
        seen, final = set(), []
        for c in chans:
            if c and c not in seen:
                seen.add(c); final.append(c)

        self.owner.op('select1').par.channame = ' '.join(final)
```

------

#### 4) Custom Parameters on `PoseEffect_MASTER`

**Page: POSEFX**

- `Active` (Pulse) — to be triggered by the switch manager.
- `Bypassinactive` (Toggle, default On) — optional extra gate on `fxCore`.
- `Filtermode` (Menu): `All Hands BasicPose CustomCSV`
- `Filtercsv` (File Path)
- `Personid` (Int, default 1)

------

#### 5) `PoseEffectExt` (master extension)

Attach to `PoseEffect_MASTER`:

```python
# /scripts/PoseEffectExt.py
class PoseEffectExt:
    def __init__(self, owner): self.owner = owner

    def SetActive(self, active: bool):
        # Gate the entire effect (COMP-level cook flag)
        self.owner.allowCooking = bool(active)
        # Optional: bypass heavy core when inactive
        core = self.owner.op('fxCore')
        if core:
            core.par.bypass = not active

    def ApplyFilter(self):
        sel = self.owner.op('landmarkSelect')
        if not sel: return
        sel.par.Personid   = self.owner.par.Personid.eval()
        sel.par.Filtermode = self.owner.par.Filtermode.eval()
        sel.par.Filtercsv  = self.owner.par.Filtercsv.eval()
        if hasattr(sel.ext, 'LandmarkSelectExt'):
            sel.ext.LandmarkSelectExt.Rebuild()
```

------

#### 6) Save as `.tox` (template on disk)

- Right-click `PoseEffect_MASTER` → **Save Component…** → `tox/PoseEffect.tox`.
- The master should also **load** from this path (External .tox set earlier).
- (Optional) Auto-save master back to disk on project save: add an **Execute DAT** at root with:

```python
def onProjectPreSave():
    m = op('PoseEffect_MASTER')
    p = m.par.externaltox.eval()
    if p: m.save(p)
    return
```

------

#### 7) Make Concrete Effects (clones)

For each variant (e.g., Dots):

1. Create a new **Base** COMP `PoseEffect_Dots`.
2. Set **Clone** = path to `PoseEffect_MASTER` (e.g., `/project1/PoseEffects/PoseEffect_MASTER`).
3. Turn **Enable Cloning** = On.
4. Dive into `PoseEffect_Dots` → set only `fxCore` **Clone Immune = On**.
5. Build the unique internals in `fxCore`:
   - **Dots:** instance small rectangles/points from `landmarkSelect/outCHOP`.
   - **Skeleton:** read `data/skeleton_edges.csv` (columns `a,b` of landmark names) → compute per-edge tx/ty/rz/scale via Script CHOP → instanced bar Geo → Render → `fxOut`.
   - **HandEmitter:** particle/feedback tox fed by `*_handtip_*`.
   - **TexSkel:** atlas/UV cards driven by limb vectors.

> Heavy nodes inside `fxCore` → **Cook Type = Selective**.

(Optionally) Save each as its own distributable: **Save Component…** → `tox/PoseEffect_Dots.tox`, etc.

------

#### 8) Hook into `EfxSwitch`

Inside your `EfxSwitch` COMP’s parameter callback (e.g., when `ActiveIndex` or `ActiveEfx` changes):

```python
def onValueChange(par, prev):
    comp = par.owner
    names = ['PoseEffect_Dots','PoseEffect_Skeleton','PoseEffect_HandEmitter','PoseEffect_TexSkel']
    idx = names.index(par.eval()) if par.name == 'Activeefx' else int(par.eval())

    # select TOP
    comp.op('out_switch').par.index = idx

    # gate effects
    for i, n in enumerate(names):
        fx = comp.op('effects/' + n)
        if not fx: continue
        active = (i == idx)
        # COMP cook flag
        fx.allowCooking = active
        # optional: also bypass heavy core
        core = fx.op('fxCore')
        if core: core.par.bypass = not active

        # re-apply filters on (re)activation
        if hasattr(fx.ext, 'PoseEffectExt') and active:
            fx.ext.PoseEffectExt.ApplyFilter()
```

**Notes**

- Flip `allowCooking` only when selection changes (not per frame).
- A **Switch TOP** will pull only the selected input chain; the above gates ensure non-selected effects stay cold.

------

#### 9) Quick Test Checklist

-  `PoseEffect_MASTER` loads from `tox/PoseEffect.tox`.
-  `landmarkSelect` rebuilds its Select CHOP when `Filtermode/Personid` changes.
-  Each effect has `fxOut` TOP and heavy nodes set to **Selective**.
-  Clones exist; only `fxCore` is **Clone Immune** in each.
-  `EfxSwitch` changes selection → only one effect’s **Cook Time** increases; others stay 0 ms.

------

#### 10) Troubleshooting

- **Channels missing?** Confirm CSV column names: `name` for landmark names or `chan` for explicit channels.
- **Nothing renders on resume?** With `allowCooking=False`, internals won’t update. Reactivate, then ensure a downstream pull (via the Switch TOP) to trigger cooking.
- **Clone updates not propagating?** Check that only `fxCore` is Clone Immune; interface pieces should remain cloneable.
- **Template edits don’t hit disk?** Use the **pre-save hook** (§6) or manually **Save Component…** back to `tox/PoseEffect.tox`.