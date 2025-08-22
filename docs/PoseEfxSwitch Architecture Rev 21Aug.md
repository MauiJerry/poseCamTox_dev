# PoseEfxSwitch Architecture Rev 21Aug (c)

this arch/guide to building the PoseEfxSwitch component keeps getting revised as I work thru implementing it.  Older versions (in docs/*.md) or in the git history are for background. This one I'll keep for today.

after (b) post I realize, perhaps the EfxSwitch will need a UI with menu to select which of the Effects will be active.  Lets make this a custom thing after we build up working stuff and then build the showControl UX  thus (c)

------

# PoseEfxSwitch — Architecture & Build Guide (Option A, UI + Red Fallback)

This guide gets you from zero to a working **PoseEfxSwitch** with a user-friendly **ActiveEffect** menu, per-effect filter control, a **red fallback** when camera TOP isn’t present, and a clean path to grow new effects fast.

------

## Goals & conventions

- **Switch owns the UI** for choosing which effect is active (by name, not index).
- **Filters are per-effect** (`LandmarkFilter`, `Landmarkfiltercsv`). The switch does **not** have those params.
- **One menu table** for landmark filters lives in the **switch** and is stamped into each effect.
- Each **PoseEffect** contains a child **LandmarkSelect** that builds the CHOP channel list.
- **Master** effect is a clone source; concrete effects are clones with only `fxCore` marked **Clone Immune**.
- **Master’s default output** passes the input TOP through; at the **switch** we also provide a **red fallback** if the camera TOP is missing (obvious “not wired yet” indicator).
- **Channel names are unprefixed** (`wrist_l_x`, not `p*_wrist_l_x`).

Parameter names (case-sensitive):

- `LandmarkFilter`  (Menu)
- `Landmarkfiltercsv` (File)

------

## 1) Build the PoseEfxSwitch (parent/orchestrator)

Create a `Base COMP` named **`PoseEfxSwitch`**.

### Inside `PoseEfxSwitch` add nodes

- **Input nodes**

  - `inCHOP` — CHOP In from PoseCam/person router (unprefixed channels)
  - `inTOP`  — TOP In from PoseCam (camera/NDI)

- **Red fallback (obvious when no camera)**

  - `redConst` — Constant TOP (set RGBA to 1,0,0,1)

  - `guardTOP` — Switch TOP
     Inputs: `inTOP` (index 0) and `redConst` (index 1)
     Set **Index (expression)** to:

    ```python
    1 if (not op('inTOP').inputs or op('inTOP').width == 0) else 0
    ```

    Use `guardTOP` as the “safe camera feed” you send to each effect’s `in2`.

- **Effects container & output**

  - `effects` — Base COMP (will hold all PoseEffect_*)
  - `out_switch` — Switch TOP (selects one effect’s output)
  - `outTOP` — TOP Out (from `out_switch`)

**Wiring overview**

- `guardTOP` → (to each effect’s `in2`)
- `inCHOP`  → (to each effect’s `in1`)
- Each `PoseEffect_*/fxOut` → `out_switch` input (0…N)
- `out_switch` → `outTOP`

### Add UI parameters on the switch

Customize Component… (page **SWITCH**):

- `ActiveEffect` (Menu) — user-facing selection by name
- `ActiveIndex`  (Int)  — internal, useful for debugging
- `RebuildEffectsMenu` (Pulse) — optional “refresh” button

### Add tables in the switch

- `LandmarkFilterMenu_csv` — **Table DAT** → **File** = `data/LandmarkFilterMenu.csv`
   Columns: `key,label,csv` (e.g., `all,All,` / `hands,Hands,data/masks_hands.csv` / …)
- *(Optional)* `PoseEffectsMenu_csv` — **Table DAT** → **File** = `config/PoseEffectsMenu.csv`
   Columns: `key,label,opName,index`
   If present, this dictates the ActiveEffect menu; otherwise the switch **auto-discovers** child `PoseEffect_*` under `effects/`.

### Add the switch extension and init

- Component Editor → **Extensions**
   Add Class **`PoseEfxSwitchExt`** and point its **File** to `ext/PoseEfxSwitchExt.py` (below).

- Inside `PoseEfxSwitch`, add an **Execute DAT** named `exec_init`, click **Edit…**, paste:

  ```python
  def onStart():
      op('.').ext.PoseEfxSwitchExt.Initialize()
      return
  ```

- Add a **Parameter Execute DAT** (still inside `PoseEfxSwitch`) and paste:

  ```python
  def onValueChange(par, prev):
      if par.name == 'ActiveEffect':
          op('.').ext.PoseEfxSwitchExt.OnActiveEffectChanged()
      elif par.name == 'ActiveIndex':
          op('.').ext.PoseEfxSwitchExt.OnActiveIndexChanged()
      elif par.name == 'RebuildEffectsMenu':
          op('.').ext.PoseEfxSwitchExt.BuildEffectsMenu()
      return
  ```

### `ext/PoseEfxSwitchExt.py` (drop-in)

```python
# ext/PoseEfxSwitchExt.py
# PoseEfxSwitch UI + orchestration:
# - ActiveEffect menu from PoseEffectsMenu_csv (or auto-discover children).
# - Keeps ActiveEffect (menu) and ActiveIndex (int) in sync.
# - Activates exactly one PoseEffect_* (allowCooking/bypass, routes out_switch).
# - Stamps LandmarkFilter menu items into each PoseEffect and its landmarkSelect.
# - Ensures landmarkSelect params read their parent PoseEffect (expressions).

class PoseEfxSwitchExt:
    def __init__(self, owner):
        self.owner = owner

    # ----- lifecycle entry (called by exec_init.onStart) -----
    def Initialize(self):
        self.InitLandmarkMenus()
        self.EnsureLandmarkBindings()
        self.BuildEffectsMenu()
        # Pick initial effect
        key = (self.owner.par.ActiveEffect.eval() or '').strip()
        keys = self._menuKeys()
        if key in keys:
            self.SetActiveEffect(key)
        elif keys:
            self.SetActiveEffect(keys[0])
        else:
            self.SetActiveIndex(0)

    # ----- landmark filter menus (per-effect) -----
    def InitLandmarkMenus(self):
        tbl = self.owner.op('LandmarkFilterMenu_csv')
        if not tbl or tbl.numRows < 2:
            print("[PoseEfxSwitchExt.InitLandmarkMenus] Missing/empty LandmarkFilterMenu_csv")
            return
        heads = [c.val.lower() for c in tbl.row(0)]
        try:
            ki = heads.index('key'); li = heads.index('label'); ci = heads.index('csv')
        except ValueError:
            print("[PoseEfxSwitchExt.InitLandmarkMenus] CSV needs key,label,csv")
            return
        keys, labels, csvs = [], [], []
        for r in tbl.rows()[1:]:
            k = r[ki].val.strip()
            if not k: continue
            keys.append(k)
            labels.append((r[li].val or k).strip())
            csvs.append((r[ci].val or '').strip())

        for fx in self._effects():
            fx.par.LandmarkFilter.menuNames  = keys
            fx.par.LandmarkFilter.menuLabels = labels
            ls = fx.op('landmarkSelect')
            if ls:
                ls.par.LandmarkFilter.menuNames  = keys
                ls.par.LandmarkFilter.menuLabels = labels
            # seed default csv if effect chose a non-custom key with a mapping
            cur = (fx.par.LandmarkFilter.eval() or '').strip()
            if cur in keys and cur != 'custom':
                idx = keys.index(cur); defcsv = csvs[idx] if idx < len(csvs) else ''
                if defcsv:
                    fx.par.Landmarkfiltercsv = defcsv

    def EnsureLandmarkBindings(self):
        # child landmarkSelect params mirror their parent PoseEffect (one-way expressions)
        for fx in self._effects():
            ls = fx.op('landmarkSelect')
            if not ls: continue
            if not ls.par.LandmarkFilter.expr:
                ls.par.LandmarkFilter.expr = "op('..').par.LandmarkFilter.eval()"
            if not ls.par.Landmarkfiltercsv.expr:
                ls.par.Landmarkfiltercsv.expr = "op('..').par.Landmarkfiltercsv.eval() or ''"

    # ----- effect menu (ActiveEffect) -----
    def BuildEffectsMenu(self):
        """Populate ActiveEffect from config/PoseEffectsMenu.csv, else auto-discover."""
        keys, labels, ops, idxs = [], [], [], []
        table = self.owner.op('PoseEffectsMenu_csv')

        def add_row(k, lab, opName, ix):
            if not k: return
            keys.append(k); labels.append(lab or k); ops.append(opName or '')
            idxs.append(int(ix) if str(ix).isdigit() else len(idxs))

        if table and table.numRows > 1:
            heads = [c.val.lower() for c in table.row(0)]
            ki = heads.index('key')    if 'key'    in heads else -1
            li = heads.index('label')  if 'label'  in heads else -1
            oi = heads.index('opname') if 'opname' in heads else -1
            ii = heads.index('index')  if 'index'  in heads else -1
            rows = table.rows()[1:]
            try:
                rows = sorted(rows, key=lambda r: int(r[ii].val)) if ii >= 0 else rows
            except Exception:
                pass
            for r in rows:
                k  = r[ki].val.strip() if ki >= 0 else ''
                lb = (r[li].val or '').strip() if li >= 0 else ''
                op = (r[oi].val or '').strip() if oi >= 0 else ''
                ix = r[ii].val.strip() if ii >= 0 else ''
                add_row(k, lb, op, ix)
        else:
            # auto-discover PoseEffect_* children
            for i, fx in enumerate(self._effects()):
                nm  = fx.name
                key = nm.replace('PoseEffect_', '').lower()
                lab = key.title().replace('_',' ')
                add_row(key, lab, nm, i)

        # stamp menu
        self.owner.par.ActiveEffect.menuNames  = keys
        self.owner.par.ActiveEffect.menuLabels = labels

        # build/update a local dispatch table for debugging
        disp = self._ensureDispatchTable()
        disp.clear(); disp.appendRow(['key','label','op','index'])
        for i in range(len(keys)):
            disp.appendRow([keys[i], labels[i], ops[i], idxs[i]])

        # keep in sync
        cur = (self.owner.par.ActiveEffect.eval() or '').strip()
        if cur not in keys and keys:
            self.owner.par.ActiveEffect = keys[0]
        self.OnActiveEffectChanged()

    def OnActiveEffectChanged(self):
        key = (self.owner.par.ActiveEffect.eval() or '').strip()
        idx = self._indexForKey(key)
        if idx is not None and int(self.owner.par.ActiveIndex.eval() or -1) != idx:
            self.owner.par.ActiveIndex = idx
        self.SetActiveIndex(int(self.owner.par.ActiveIndex.eval() or 0))

    def OnActiveIndexChanged(self):
        idx = int(self.owner.par.ActiveIndex.eval() or 0)
        key = self._keyForIndex(idx)
        if key and (self.owner.par.ActiveEffect.eval() or '') != key:
            self.owner.par.ActiveEffect = key
        self.SetActiveIndex(idx)

    def SetActiveEffect(self, key: str):
        key = (key or '').strip()
        keys = self._menuKeys()
        if not keys: return
        if key not in keys: key = keys[0]
        self.owner.par.ActiveEffect = key
        self.OnActiveEffectChanged()

    def SetActiveIndex(self, idx: int):
        # route output & gate cooking
        sw = self.owner.op('out_switch')
        if sw: sw.par.index = int(idx)
        for i, fx in enumerate(self._effects()):
            active = (i == idx)
            fx.allowCooking = active
            core = fx.op('fxCore')
            if core: core.par.bypass = not active
            if hasattr(fx.ext, 'PoseEffectMasterExt'):
                fx.ext.PoseEffectMasterExt.SetActive(active)

    # ----- service for children (csv resolve) -----
    def ResolveMenuCSV(self, key: str) -> str:
        key = (key or '').strip().lower()
        tbl = self.owner.op('LandmarkFilterMenu_csv')
        if not tbl or tbl.numRows < 2: return ''
        heads = [c.val.lower() for c in tbl.row(0)]
        try:
            ki = heads.index('key'); ci = heads.index('csv')
        except ValueError:
            return ''
        for r in tbl.rows()[1:]:
            if r[ki].val.strip().lower() == key:
                return (r[ci].val or '').strip()
        return ''

    # ----- helpers -----
    def _effects(self):
        eff = self.owner.op('effects')
        return [c for c in (eff.children if eff else []) if c.isCOMP and c.name.startswith('PoseEffect_')]

    def _ensureDispatchTable(self):
        disp = self.owner.op('EffectDispatch_csv')
        if not disp:
            disp = self.owner.create(tableDAT, 'EffectDispatch_csv')
        return disp

    def _menuKeys(self):
        return list(self.owner.par.ActiveEffect.menuNames or [])

    def _indexForKey(self, key):
        disp = self.owner.op('EffectDispatch_csv')
        if not disp or disp.numRows < 2: return None
        heads = [c.val.lower() for c in disp.row(0)]
        try:
            ki = heads.index('key'); ii = heads.index('index')
        except ValueError:
            return None
        for r in disp.rows()[1:]:
            if r[ki].val == key:
                try: return int(r[ii].val)
                except: return None
        return None

    def _keyForIndex(self, idx):
        disp = self.owner.op('EffectDispatch_csv')
        if not disp or disp.numRows < 2: return ''
        heads = [c.val.lower() for c in disp.row(0)]
        try:
            ki = heads.index('key'); ii = heads.index('index')
        except ValueError:
            return ''
        for r in disp.rows()[1:]:
            try:
                if int(r[ii].val) == int(idx):
                    return r[ki].val
            except:
                pass
        return ''
```

### CAUTION: update wondering about both onActive*Changed

Short answer: you won’t get an infinite loop if you (a) only write the “other” param when it actually differs and (b) optionally use a tiny re-entrancy guard. Here’s a safe pattern you can paste in.

### Why this works

- Changing **ActiveEffect** calls `OnActiveEffectChanged()`. That computes the mapped index and **only sets ActiveIndex if it’s different**.
- That fires `OnActiveIndexChanged()`, which computes the mapped key and **only sets ActiveEffect if it’s different** (it won’t be, so it’s a no-op).
- Result: 2 callbacks, 1 actual activation, no ping-pong.

To be extra bulletproof (e.g., if someone later tweaks code and forgets the equality checks), add a simple `_syncing` flag.

------

### Drop-in: safer callbacks with guard

In `PoseEfxSwitchExt.py`:

```python
class PoseEfxSwitchExt:
    def __init__(self, owner):
        self.owner = owner
        self._syncing = False  # re-entrancy guard

    def OnActiveEffectChanged(self):
        if self._syncing:
            return
        self._syncing = True
        try:
            key = (self.owner.par.ActiveEffect.eval() or '').strip()
            idx = self._indexForKey(key)
            # Only set if different to avoid loops
            if idx is not None and int(self.owner.par.ActiveIndex.eval() or -1) != idx:
                self.owner.par.ActiveIndex = idx
            # Activate (idempotent if already active)
            self.SetActiveIndex(int(self.owner.par.ActiveIndex.eval() or 0))
        finally:
            self._syncing = False

    def OnActiveIndexChanged(self):
        if self._syncing:
            return
        self._syncing = True
        try:
            idx = int(self.owner.par.ActiveIndex.eval() or 0)
            key = self._keyForIndex(idx) or ''
            # Only set if different to avoid loops
            if key and (self.owner.par.ActiveEffect.eval() or '') != key:
                self.owner.par.ActiveEffect = key
            # Activate (idempotent if already active)
            self.SetActiveIndex(idx)
        finally:
            self._syncing = False
```

Keep the rest of your `SetActiveIndex`, `_indexForKey`, `_keyForIndex`, etc., as-is.

------

### Minimal Parameter Execute DAT (unchanged)

Inside `PoseEfxSwitch`:

```python
def onValueChange(par, prev):
    if par.name == 'ActiveEffect':
        op('.').ext.PoseEfxSwitchExt.OnActiveEffectChanged()
    elif par.name == 'ActiveIndex':
        op('.').ext.PoseEfxSwitchExt.OnActiveIndexChanged()
    elif par.name == 'RebuildEffectsMenu':
        op('.').ext.PoseEfxSwitchExt.BuildEffectsMenu()
    return
```

------

### Practical notes

- You can pick a single “source of truth” (e.g., **ActiveEffect**) and hide **ActiveIndex** from UI. The guard still lets you script either one safely.
- `SetActiveIndex()` should be idempotent (it only flips cooking and the output switch if the target actually changes).
- If you later add “programmatic” activations (e.g., a hotkey that sets `ActiveIndex` directly), the same guard keeps everything stable.

With these checks (and the guard), you won’t see race conditions or feedback loops.



------

## 2) Build the PoseEffect_Master (template)

Create **`PoseEffect_Master`** (Base COMP) under `PoseEfxSwitch/effects`.

### PoseEffect_Master — parameters & extensions

- Custom params (page **FILTER**):

  - `LandmarkFilter` (Menu)
  - `Landmarkfiltercsv` (File)

- Extension: **PoseEffectMasterExt** (Component Editor → Extensions → Class name `PoseEffectMasterExt`, File `ext/PoseEffectMasterExt.py`)

- Add a **Parameter Execute DAT** inside `PoseEffect_Master`:

  ```python
  def onValueChange(par, prev):
      if par.name in ('LandmarkFilter','Landmarkfiltercsv'):
          op('.').ext.PoseEffectMasterExt.ApplyFilter()
      return
  ```

### PoseEffect_Master — nodes

- Inputs: `in1` (CHOP In), `in2` (TOP In)
- **landmarkSelect** (Base COMP)
  - Custom params: `LandmarkFilter` (Menu), `Landmarkfiltercsv` (File)
  - Inside `landmarkSelect`:
    - `landmark_names` — **Table DAT** → **File** = `data/landmark_names.csv`  ← *(local copy, simple & cached)*
    - `landmark_mask`  — **Table DAT** (File left blank; set by ext)
    - `select1` — **Select CHOP** → `par.op = ../in1` (leave `channame` blank)
    - `outCHOP` — **Null CHOP**
  - Extension: **LandmarkSelectExt** (Class `LandmarkSelectExt`, File `ext/LandmarkSelectExt.py`)
- **fxOut** — TOP Out

> **Master default output:** Simply pass `in2` to `fxOut` (so unimplemented effects visibly show the camera feed).
>  Add a **Null TOP** `fxPass` and connect: `in2 → fxPass → fxOut`.

> **Feeding inputs from the Switch:** The switch will connect `inCHOP → PoseEffect_*/in1` and **`guardTOP → PoseEffect_\*/in2`** (so you see **red** when the camera is missing).

### `ext/PoseEffectMasterExt.py` (drop-in)

```python
# ext/PoseEffectMasterExt.py
# Lives on each PoseEffect_* (including the Master). Gates cooking and coordinates child rebuilds.

class PoseEffectMasterExt:
    def __init__(self, owner):
        self.owner = owner

    def SetActive(self, active: bool):
        self.owner.allowCooking = bool(active)
        core = self.owner.op('fxCore')
        if core: core.par.bypass = not active
        if active:
            self.ApplyFilter()

    def ApplyFilter(self):
        ls = self.owner.op('landmarkSelect')
        if ls and hasattr(ls.ext, 'LandmarkSelectExt'):
            ls.ext.LandmarkSelectExt.Rebuild()

    def ResolveMenuCSV(self, key: str) -> str:
        # Ask the PoseEfxSwitch parent to resolve csv for 'key'
        switch = self.owner.parent()
        if hasattr(switch.ext, 'PoseEfxSwitchExt'):
            return switch.ext.PoseEfxSwitchExt.ResolveMenuCSV(key)
        return ''
```

### `ext/LandmarkSelectExt.py` (drop-in)

```python
# ext/LandmarkSelectExt.py
# Builds Select CHOP channame based on parent's filter settings and menu resolution.

class LandmarkSelectExt:
    def __init__(self, owner):
        self.owner = owner

    def Rebuild(self):
        key = (self.owner.par.LandmarkFilter.eval() or '').strip().lower()
        custom_csv = (self.owner.par.Landmarkfiltercsv.eval() or '').strip()

        posefx = self.owner.parent()
        default_csv = ''
        if hasattr(posefx.ext, 'PoseEffectMasterExt'):
            default_csv = posefx.ext.PoseEffectMasterExt.ResolveMenuCSV(key)

        sel  = self.owner.op('select1')
        mask = self.owner.op('landmark_mask')
        names= self.owner.op('landmark_names')
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

        # build channels
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
    b=f"{name}_"; return [b+'x', b+'y', b+'z']

def _dedup(seq):
    seen,out=set(),[]
    for s in seq:
        if s and s not in seen:
            seen.add(s); out.append(s)
    return out

def _flatten(xxs):
    out=[]; [out.extend(x) for x in xxs]; return out
```

> **Landmark names source:** Each `landmarkSelect` keeps its own local `landmark_names` (simple + cached). If you later want a shared table, you can adjust the ext to fall back to `op('../../landmark_names')`.

------

## 3) Grow concrete effects (Option A: clones of Master)

For each effect:

1. Under `PoseEfxSwitch/effects`, create `PoseEffect_<Name>` (Base COMP).
2. Set **Clone** = `PoseEffect_Master`. Enable **Cloning**.
3. Dive in → set **only** `fxCore` to **Clone Immune = On**.
    *(No change to this policy—the red fallback & pass-through do not alter Clone Immune requirements.)*
4. Build the effect’s unique network **inside `fxCore`** and wire its final TOP to `../fxOut`.
5. In the switch, wire `PoseEffect_<Name>/fxOut` to the next input of `out_switch`.
6. Use the **ActiveEffect** menu to activate it.

------

## 4) Minimal `fxCore` recipes

### A) **Dots** (one dot per landmark)

Inside `PoseEffect_Dots/fxCore`:

- `landmarks_sop` (**Script SOP**):

  ```python
  def cook(scriptOp):
      scriptOp.clear()
      src = op('../landmarkSelect/outCHOP')
      for cx in [c for c in src.chans if c.name.endswith('_x')]:
          base = cx.name[:-2]; cy = src.get(base + '_y')
          if not cy: continue
          scriptOp.appendPoint([float(cx[0]), float(cy[0]), 0.0])
      return
  ```

- `dot` (Circle SOP, small) → `copy` (Copy SOP to `landmarks_sop`)

- `geo` (Geometry COMP with SOP = `copy`) → `Render TOP` → `Null TOP` → `../fxOut`

- (Optional) Composite with `../in2` for over-camera effect.

### B) **StickMan** (simple skeleton)

Inside `fxCore`:

- `edges` (Table DAT) → File: `data/skeleton_edges.csv` (`a,b`)

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

- `bar` (Rectangle SOP, thin) → `geo` (Instancing ON)

  - Instance CHOP = `pairEval`
  - Tx=tx, Ty=ty, Rz=rz, Scale X = s

- `Render TOP` → `../fxOut`

### C) **HandEmitters** (quick trails)

Inside `fxCore`:

- `hands` (Select CHOP) from `../landmarkSelect/outCHOP` with `channame = *hand*_*`
- Simple feedback:
  - `feedback` (Feedback TOP)
  - `level` (opacity 0.95)
  - `dotL`, `dotR` (small Constant TOPs) → two **Transform TOPs** whose Translate X/Y expressions read selected hand channels scaled by resolution (e.g., `op('../hands')['handtip_l_x'][0]*width` / `*height`)
  - `comp` (Composite TOP, Add): `feedback + dotL + dotR` → `level` → back to `feedback`
- Output `comp` (or a copy) to `../fxOut`

### D) **TexturedMutant** (textured bones)

- Reuse `pairEval` from StickMan.
- `grid` (Grid SOP with UVs) + material (Phong/Constant with a texture).
- Instance with Tx/Ty/Rz/Sx; optionally animate shader.

> For heavy TOPs/RENDER ops: set **Common ▸ Cook Type = Selective**. The switch already gates cooking (`allowCooking`) so only the active effect pays.

------

## 5) Hook it together & smoke test

1. Connect **PoseCam** → `PoseEfxSwitch/inCHOP` + `PoseEfxSwitch/inTOP`.
2. Clone `PoseEffect_Master` → `PoseEffect_Dots`; in `fxCore` build dots; wire `../fxOut`.
3. In `PoseEfxSwitch`, wire `PoseEffect_Dots/fxOut` to `out_switch` input 0.
4. Use **ActiveEffect** menu to pick “Dots”.
5. On `PoseEffect_Dots`, set `LandmarkFilter` to `all` (or `hands`) and verify `landmarkSelect/select1.channame` fills and dots render.
6. Unplug camera: `guardTOP` turns **red**, and the master pass-through shows red too (clear signal the camera is missing / effect is still pass-through).

------

## 6) FAQ

- **Where’s onStart?** Inside the switch as `exec_init.onStart() → PoseEfxSwitchExt.Initialize()`. Self-contained.
- **Do filters live on the switch?** No—**per effect** only. The switch just provides the menu items and CSV resolver.
- **Why local `landmark_names` per LandmarkSelect?** It’s tiny and cached; simplest approach. You can centralize later if needed.
- **Does the red fallback change Clone Immune?** No. Keep **only `fxCore`** Clone Immune in each concrete effect. The master’s default pass-through and the switch’s red guard don’t affect that.
- **Growing new effects?** Clone the master, set `fxCore` Clone Immune, build inside `fxCore`, wire to `fxOut`, add to `out_switch`, done.

------

You’re set to iterate quickly: the switch gives you a clean UI and cooking control, the master guarantees a consistent interface, and each effect focuses only on its `fxCore`.