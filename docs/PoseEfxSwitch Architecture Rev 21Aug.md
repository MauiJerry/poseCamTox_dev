# PoseEfxSwitch Architecture Rev 21Aug (b)

love it — putting the menu in **PoseEfxSwitch** makes the whole thing cleaner and truly reusable.

Below is a compact architecture + the exact code you need so you can wire the switch once, drop in a few effects, and demo.

Yeah but it was unclear how this grows from the PoseEffectMaster to multiple PoseEffect_??? 

so ask for clarification, and revise a few prompts

after (b) post I realize, perhaps the EfxSwitch will need a UI with menu to select which of the Effects will be active.  Lets make this a custom thing after we build up working stuff and then build the showControl UX

------

# PoseEfxSwitch — Architecture & Build Guide (Option A, ship-it edition)

This doc walks you from a blank network to a working **PoseEfxSwitch** with:

- one reusable **PoseEffect_Master** template,
- a child **LandmarkSelect** selector,
- and a first concrete effect **PoseEffect_Dots** (clone of Master).

You can then clone more (StickMan, HandEmitters, TexturedMutant) and fill in their `fxCore` networks.

> Design notes:
>
> - **Filters (LandmarkFilter / Landmarkfiltercsv) live per-effect**, not on the switch. Each PoseEffect can choose a different mask.
> - A single menu table (`LandmarkFilterMenu_csv`) lives on the **PoseEfxSwitch** and feeds menu items to every PoseEffect.
> - The **LandmarkSelect** inside each PoseEffect reads its parent PoseEffect’s parameters (simple expressions), so you only change the filter on the effect.

------

## 0) Files & params you’ll use

- `/data/landmark_names.csv` (column: `name`)

- `/data/masks_hands.csv`, `/data/masks_basicpose.csv`, … (columns: `name` or `chan`)

- `/data/skeleton_edges.csv` (columns: `a,b`) — for StickMan

- A small CSV for the menu definition (you choose the path), e.g. `/config/LandmarkFilterMenu.csv` with header: `key,label,csv`

  ```
  key,label,csv
  all,All,
  hands,Hands,data/masks_hands.csv
  basicpose,Basic Pose,data/masks_basicpose.csv
  custom,Custom CSV,
  ```

another confg/EffectNames.csv might have key, lable, opName for the UI

Custom parameter *Names* (case-sensitive):

- `LandmarkFilter` (Menu)
- `Landmarkfiltercsv` (File)

------

## 1) Build the PoseEfxSwitch component (parent/orchestrator)

**Create:** a `Base COMP` named `PoseEfxSwitch`.

**Inside PoseEfxSwitch add:**

- `LandmarkFilterMenu_csv` (Table DAT) → set **File** to your `/data/LandmarkFilterMenu.csv`
- `inCHOP` (CHOP In) — person-routed, unprefixed channels
- `inTOP`  (TOP In)  — camera/background (optional)
- `effects` (Base COMP) — will hold all PoseEffect_* COMPs
- `out_switch` (Switch TOP) → `outTOP` (TOP Out)

**Add a single custom parameter on PoseEfxSwitch:**

- Page **SWITCH** → `ActiveIndex` (Int)
- ui here will link name, lable, EffectOp, Index

**Attach an extension to PoseEfxSwitch:**

- Component Editor… → **Extensions**
- Class Name: `PoseEfxSwitchExt` → **Add**
- Select the created Text DAT and set **File** to `ext/PoseEfxSwitchExt.py` (code below)

**Add an Execute DAT \*inside PoseEfxSwitch\* (encapsulated onStart):**

- Name it `exec_init`, click **Edit…** and paste:

  ```python
  def onStart():
      op('.').ext.PoseEfxSwitchExt.Initialize()
      return
  ```

**(Optional) Add a Parameter Execute DAT on PoseEfxSwitch** (only for the switch index):

```python
def onValueChange(par, prev):
    if par.name == 'ActiveIndex':
        op('.').ext.PoseEfxSwitchExt.SetActiveIndex(int(par.eval()))
    return
```

### `ext/PoseEfxSwitchExt.py` (drop-in)

```python
# ext/PoseEfxSwitchExt.py
# Drives menu items to all PoseEffects, binds child selectors, and switches which effect cooks.

class PoseEfxSwitchExt:
    def __init__(self, owner):
        self.owner = owner

    # ---------- entry point from exec_init ----------
    def Initialize(self):
        self.InitMenus()
        self.EnsureBindings()
        idx = int(self.owner.par.ActiveIndex.eval() if hasattr(self.owner.par, 'ActiveIndex') else 0)
        self.SetActiveIndex(idx)

    # ---------- menus ----------
    def InitMenus(self):
        """
        Read keys/labels from PoseEfxSwitch/LandmarkFilterMenu_csv and set menu items
        on every PoseEffect's LandmarkFilter (and mirror to its child landmarkSelect).
        Does NOT set any filter on the switch itself (filters are per-effect).
        If an effect's current selection is invalid, set the first key and seed its file param.
        """
        table = self.owner.op('LandmarkFilterMenu_csv')
        if not table or table.numRows < 2:
            print("[PoseEfxSwitchExt.InitMenus] Missing/empty LandmarkFilterMenu_csv")
            return

        heads = [c.val.lower() for c in table.row(0)]
        try:
            ki = heads.index('key'); li = heads.index('label'); ci = heads.index('csv')
        except ValueError:
            print("[PoseEfxSwitchExt.InitMenus] CSV must have key,label,csv")
            return

        keys, labels, csvs = [], [], []
        for r in table.rows()[1:]:
            k = r[ki].val.strip()
            if not k: continue
            keys.append(k)
            labels.append((r[li].val or k).strip())
            csvs.append((r[ci].val or '').strip())

        for fx in self._effects():
            # stamp menu items on the PoseEffect param UI
            fx.par.LandmarkFilter.menuNames  = keys
            fx.par.LandmarkFilter.menuLabels = labels
            # also mirror to the child for consistent UI
            ls = fx.op('landmarkSelect')
            if ls:
                ls.par.LandmarkFilter.menuNames  = keys
                ls.par.LandmarkFilter.menuLabels = labels

            # validate effect's current selection
            cur = (fx.par.LandmarkFilter.eval() or '').strip()
            if cur not in keys:
                fx.par.LandmarkFilter = keys[0]
                cur = keys[0]
                if cur != 'custom':
                    idx = keys.index(cur); defcsv = csvs[idx] if idx < len(csvs) else ''
                    if defcsv:
                        fx.par.Landmarkfiltercsv = defcsv

    # ---------- bindings ----------
    def EnsureBindings(self):
        """
        Ensure each landmarkSelect reads its parent PoseEffect params via expressions.
        (No bindings from effects back to the switch — filters are per-effect.)
        """
        for fx in self._effects():
            ls = fx.op('landmarkSelect')
            if not ls: 
                continue
            if not ls.par.LandmarkFilter.expr:
                ls.par.LandmarkFilter.expr = "op('..').par.LandmarkFilter.eval()"
            if not ls.par.Landmarkfiltercsv.expr:
                ls.par.Landmarkfiltercsv.expr = "op('..').par.Landmarkfiltercsv.eval() or ''"

    # ---------- switching ----------
    def SetActiveIndex(self, idx: int):
        """Select which PoseEffect cooks and which fxOut is routed to out_switch."""
        sw = self.owner.op('out_switch')
        if sw: sw.par.index = int(idx)

        for i, fx in enumerate(self._effects()):
            active = (i == idx)
            fx.allowCooking = active
            core = fx.op('fxCore')
            if core: core.par.bypass = not active
            # let the effect do its own activation work (rebuild selector, etc.)
            if hasattr(fx.ext, 'PoseEffectMasterExt'):
                fx.ext.PoseEffectMasterExt.SetActive(active)

    # ---------- service for children ----------
    def ResolveMenuCSV(self, key: str) -> str:
        """Lookup a menu key in LandmarkFilterMenu_csv and return its csv value."""
        key = (key or '').strip().lower()
        table = self.owner.op('LandmarkFilterMenu_csv')
        if not table or table.numRows < 2: return ''
        heads = [c.val.lower() for c in table.row(0)]
        try:
            ki = heads.index('key'); ci = heads.index('csv')
        except ValueError:
            return ''
        for r in table.rows()[1:]:
            if r[ki].val.strip().lower() == key:
                return (r[ci].val or '').strip()
        return ''

    # ---------- helpers ----------
    def _effects(self):
        eff = self.owner.op('effects')
        return [c for c in (eff.children if eff else []) if c.isCOMP]
```

> **OnStart placement:** you asked to encapsulate it — we did. The `exec_init` inside PoseEfxSwitch runs `Initialize()` on project start. You don’t need a root Execute DAT. (If you do want one later, it can be a single line: `op('/project1/PoseEfxSwitch').ext.PoseEfxSwitchExt.Initialize()`.)

------

## 2) Build the PoseEffect_Master (template) once

**Create:** `Base COMP` named `PoseEffect_Master` under `PoseEfxSwitch/effects`.

**Add custom params on PoseEffect_Master (page “FILTER”):**

- `LandmarkFilter` (Menu)
- `Landmarkfiltercsv` (File)

**Inside PoseEffect_Master add:**

- `in1` (CHOP In), `in2` (TOP In)
- `landmarkSelect` (Base COMP)
  - Add the same two custom params (`LandmarkFilter`, `Landmarkfiltercsv`)
  - **Inside `landmarkSelect`:**
    - `landmark_names` (Table DAT) → set **File** to `/data/landmark_names.csv`
    - `landmark_mask` (Table DAT)  → (leave File blank; extension sets it)
    - `select1` (Select CHOP) → set `par.op = ../in1` (leave `channame` empty)
    - `outCHOP` (Null CHOP)
  - Attach **LandmarkSelectExt** (below) via Component Editor → Extensions → Class `LandmarkSelectExt` (File: `ext/LandmarkSelectExt.py`)
- `fxCore` (Base COMP) — **leave empty** in the master; each concrete effect fills this.
- `fxOut` (TOP Out)

**Attach an extension to PoseEffect_Master:**

- Component Editor → Extensions → Class `PoseEffectMasterExt` (File: `ext/PoseEffectMasterExt.py`)

### `ext/PoseEffectMasterExt.py`

```python
# ext/PoseEffectMasterExt.py
# Lives on each PoseEffect_* (including PoseEffect_Master template).
# Responsible for gating cooking and coordinating child rebuilds.

class PoseEffectMasterExt:
    def __init__(self, owner):
        self.owner = owner

    def SetActive(self, active: bool):
        """Called by the switch when this effect becomes (in)active."""
        self.owner.allowCooking = bool(active)
        core = self.owner.op('fxCore')
        if core: core.par.bypass = not active
        if active:
            self.ApplyFilter()

    def ApplyFilter(self):
        """Ask landmarkSelect to rebuild its Select CHOP pattern."""
        ls = self.owner.op('landmarkSelect')
        if ls and hasattr(ls.ext, 'LandmarkSelectExt'):
            ls.ext.LandmarkSelectExt.Rebuild()

    def ResolveMenuCSV(self, key: str) -> str:
        """Delegate menu CSV lookup to the PoseEfxSwitch parent."""
        switch = self.owner.parent()  # PoseEfxSwitch
        if hasattr(switch.ext, 'PoseEfxSwitchExt'):
            return switch.ext.PoseEfxSwitchExt.ResolveMenuCSV(key)
        return ''
```

> **Param change trigger (per effect):** Add a Parameter Execute DAT inside each PoseEffect_* with:

```python
def onValueChange(par, prev):
    if par.name in ('LandmarkFilter','Landmarkfiltercsv'):
        op('.').ext.PoseEffectMasterExt.ApplyFilter()
    return
```

### `ext/LandmarkSelectExt.py`

```python
# ext/LandmarkSelectExt.py
# Lives on each landmarkSelect (child of a PoseEffect_*).
# Builds Select CHOP channame based on parent's filter settings and menu CSV resolution.

class LandmarkSelectExt:
    def __init__(self, owner):
        self.owner = owner

    def Rebuild(self):
        key = (self.owner.par.LandmarkFilter.eval() or '').strip().lower()
        custom_csv = (self.owner.par.Landmarkfiltercsv.eval() or '').strip()

        # ask parent PoseEffect to resolve default csv for key via the switch
        posefx = self.owner.parent()
        default_csv = ''
        if hasattr(posefx.ext, 'PoseEffectMasterExt'):
            default_csv = posefx.ext.PoseEffectMasterExt.ResolveMenuCSV(key)

        sel  = self.owner.op('select1')
        mask = self.owner.op('landmark_mask')
        names = self.owner.op('landmark_names')
        if not sel or not mask or not names:
            self._log("Missing select1/landmark_mask/landmark_names.")
            return

        # choose mask file
        if key in ('', 'all'):
            mask.par.file = ''
        elif key == 'custom':
            mask.par.file = custom_csv
        else:
            mask.par.file = default_csv or ''

        # build channel list
        if key in ('', 'all'):
            nlist = _col_as_list(names, 'name')
            chans = _flatten([_xyz(n) for n in nlist])
        else:
            rows = _rows_as_dicts(mask)
            chans = []
            for r in rows:
                ch = (r.get('chan') or '').strip()
                nm = (r.get('name') or '').strip()
                if ch: chans.append(ch)
                elif nm: chans += _xyz(nm)

        # apply
        sel.par.op = '../in1'
        sel.par.channame = ' '.join(_dedup(chans))
        self._log(f"Rebuild key='{key}', file='{mask.par.file.eval()}', count={len(chans)}")

    def _log(self, msg):
        logdat = self.owner.op('log')
        try:
            if logdat and hasattr(logdat, 'write'): logdat.write(str(msg)+'\n')
            else: print(str(msg))
        except Exception: pass

# helpers
def _rows_as_dicts(tab):
    try:
        if tab.numRows <= 1 or tab.numCols <= 0: return []
        heads = [c.val.lower() for c in tab.row(0)]
        out = []
        for r in tab.rows()[1:]:
            d = {}
            for i in range(min(len(heads), len(r))):
                d[heads[i]] = r[i].val
            out.append(d)
        return out
    except Exception:
        return []

def _col_as_list(tab, colname):
    try:
        if tab.numRows <= 1 or tab.numCols <= 0: return []
        heads = [c.val.lower() for c in tab.row(0)]
        if colname.lower() not in heads: return []
        ci = heads.index(colname.lower())
        return [r[ci].val.strip() for r in tab.rows()[1:] if r[ci].val.strip()]
    except Exception:
        return []

def _xyz(name):
    b = f"{name}_"; return [b+'x', b+'y', b+'z']

def _dedup(seq):
    seen, out = set(), []
    for s in seq:
        if s and s not in seen:
            seen.add(s); out.append(s)
    return out

def _flatten(xxs):
    out = []; [out.extend(x) for x in xxs]; return out
```

> **About sharing `/data/landmark_names.csv`:**
>  It’s tiny and cached — simplest is: each LandmarkSelect has its own `landmark_names` Table DAT pointing at the same file. If you prefer one shared copy later, put a `landmark_names` Table DAT in `PoseEfxSwitch` and tweak `LandmarkSelectExt` to fall back to `op('../../landmark_names')` if the local one is missing.

------

## 3) Smoke test — make `PoseEffect_Dots` (clone of Master)

**Clone from the template:**

1. Under `PoseEfxSwitch/effects`, create `PoseEffect_Dots` (Base COMP).
2. Set **Clone** = `PoseEffect_Master`; **Enable Cloning**.
3. Dive in and set only `fxCore` **Clone Immune = On**.

**Build a minimal `fxCore` (Dots):**

- Add `landmarks_sop` (**Script SOP**) and paste:

  ```python
  def cook(scriptOp):
      scriptOp.clear()
      src = op('../landmarkSelect/outCHOP')
      xch = [c for c in src.chans if c.name.endswith('_x')]
      for cx in xch:
          base = cx.name[:-2]; cy = src.get(base + '_y')
          if not cy: continue
          scriptOp.appendPoint([float(cx[0]), float(cy[0]), 0.0])
      return
  ```

- Add `dot` (**Circle SOP**) radius ~0.005

- Add `copy` (**Copy SOP**): left = `dot`, right = `landmarks_sop`

- Add `geo` (Geometry COMP) → SOP path `copy`

- Add `rend` (Render TOP) → `null` → connect to `../fxOut`

- (Optional) Composite with `../inTOP`

**Wire output into the switch:**

- Connect `PoseEffect_Dots/fxOut` to `PoseEfxSwitch/out_switch` input 0.
- In `PoseEfxSwitch`, set `ActiveIndex = 0`.

**Pick a filter for Dots:**

- Open `PoseEffect_Dots` → set `LandmarkFilter = all` (or `hands`, etc.).
- The child `landmarkSelect/select1.channame` should fill with the matching channels.
- You should see dots render; only Dots cooks (others are cold).

------

## 4) Next effects (quick recipes)

### A) StickMan (simple skeleton)

- Clone `PoseEffect_Master` → `PoseEffect_StickMan`

- Set `fxCore` Clone Immune.

- Inside `fxCore`:

  - `edges` (Table DAT) → File: `/data/skeleton_edges.csv` (cols `a,b`)

  - `pairEval` (Script CHOP):

    ```python
    import math
    def onCook(scriptOp):
        scriptOp.clear()
        src = op('../landmarkSelect/outCHOP'); edges = op('edges')
        tx=scriptOp.appendChan('tx'); ty=scriptOp.appendChan('ty')
        rz=scriptOp.appendChan('rz'); sc=scriptOp.appendChan('s')
        for r in edges.rows()[1:]:
            a,b = r[0].val, r[1].val
            ax,ay = src.get(f"{a}_x"), src.get(f"{a}_y")
            bx,by = src.get(f"{b}_x"), src.get(f"{b}_y")
            if None in (ax,ay,bx,by): tx.append(0); ty.append(0); rz.append(0); sc.append(0); continue
            ax,ay,bx,by = ax[0],ay[0],bx[0],by[0]
            cx,cy = (ax+bx)/2,(ay+by)/2; dx,dy = (bx-ax),(by-ay)
            tx.append(cx); ty.append(cy)
            rz.append(math.degrees(math.atan2(dy,dx)))
            sc.append((dx*dx+dy*dy)**0.5)
        return
    ```

  - `bar` (Rectangle SOP) size X≈0.015 Y≈0.001 → `geo` (Instancing ON)

    - Instance CHOP = `pairEval`
    - Tx=tx, Ty=ty, Rz=rz, Sx=s

  - `Render TOP` → `fxOut`

### B) HandEmitters (quick trails)

- Clone → `PoseEffect_HandEmit`
- In PoseEffect params, set `LandmarkFilter = hands`.
- In `fxCore`:
  - `hands` (Select CHOP) op= `../landmarkSelect/outCHOP`, channame = `*hand*_*`
  - Simple feedback trail:
    - `feedback` (Feedback TOP)
    - `level` (opacity 0.95)
    - `composite` (Add): place “dot” TOPs at hand positions via two **Transform TOPs** whose `tx/ty` expressions read the `hands` channels multiplied by render size.
    - Feedback loop: `composite → level → feedback → composite`
  - Output composite to `fxOut`.

### C) TexturedMutant (textured bones)

- Clone → `PoseEffect_TexturedMutant`
- Reuse StickMan’s `pairEval`.
- Replace `bar` with `grid` (Grid SOP, with UVs) + **Material** (Phong/Constant with a texture).
- Instance the grid cards with the same `tx,ty,rz,scale` mapping; optionally use `Scale Y` to control thickness, animate shader.

> Heavy nodes: set **Cook Type = Selective** (Common page) so only the active effect pays.

------

## 5) FAQ & tips

- **Where does onStart live?** Inside `PoseEfxSwitch` — see `exec_init`. That encapsulates initialization so the root stays clean.
- **Why no LandmarkFilter on the switch?** Filters are per-effect; some effects need different inputs (e.g., Hands vs All). The switch just routes and manages cooking.
- **Sharing `landmark_names`?** Easiest: each LandmarkSelect has its own `landmark_names` Table DAT pointing at the same CSV. It’s tiny and cached. If you want one shared copy later, move a single `landmark_names` DAT into PoseEfxSwitch and tweak `LandmarkSelectExt` to read that when present.
- **Clones vs tox:** During dev, keep **clones of Master** and only `fxCore` Clone Immune. When satisfied, you can export each effect as a `.tox` for portability.
- **COMP cook control:** Use `fx.allowCooking` (COMP cook flag) at effect level and **Selective** on heavy nodes. There is no “Cook Type” on a COMP.

------

You now have a minimal, modular scaffold that’s fast to iterate:

1. Wire **PoseCam → PoseEfxSwitch.inCHOP / inTOP**
2. Clone **PoseEffect_Master → PoseEffect_Dots**, build dots `fxCore`, connect to `out_switch[0]`
3. Set **ActiveIndex = 0** and pick a **LandmarkFilter** on the effect
4. Rinse, clone, and fill `fxCore` for StickMan / HandEmitters / TexturedMutant.