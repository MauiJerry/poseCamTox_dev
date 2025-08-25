Got it—this is almost always a re-entrancy loop from the PoseEffect’s **Parameter Execute DAT** calling code that *writes back into parameters* the DAT is watching, or an expression cycle through `landmarkSelect`. Here’s a clean, TD-idiomatic fix.

------

### Why the loop happens (likely)

- Your **parexec** watches `Active` and also calls `SetActive()`.
- In your `PoseEffectMasterExt.SetActive()` you mirror the UI by writing `self.owner.par.Active = ...`.
- That write fires the **parexec** again → loop warning.
- A second source can be `ApplyFilter()` → `LandmarkSelectExt.Rebuild()` → changing params the parent is *expressed to* (avoid writing back to `LandmarkFilter`/`Landmarkfiltercsv`).

------

## Fix 1 — Don’t write back to `Active` from the extension

Make `Active` a **UI input only**. Let the switcher or UI toggle call `SetActive()`, but **don’t mirror it** in code.

**Replace** your `SetActive()` with this minimal version:

```python
# PoseEffectMasterExt.py (simplified, no UI mirroring)
class PoseEffectMasterExt:
    def __init__(self, owner):
        self.owner = owner

    def SetActive(self, active: bool):
        # Gate cooking at COMP level; one effect cooks at a time
        self.owner.allowCooking = bool(active)
        if active:
            # On activation, ensure the selection is fresh
            self.ApplyFilter()

    def ApplyFilter(self):
        ls = self.owner.op('landmarkSelect')
        if ls and hasattr(ls.ext, 'LandmarkSelectExt'):
            ls.ext.LandmarkSelectExt.Rebuild()
```

> If you really want the UI toggle to reflect state, bind a **read-only Indicator** param via expression instead of writing back to `Active` in Python.

------

## Fix 2 — Add a tiny re-entrancy guard to the parexec

Even with the above, guards make it bulletproof (and help if you later add more watches).

Use this **full** Parameter Execute DAT (TouchDesigner *Parameter Callbacks DAT* style, no external callbacks). Turn **on** “Value Change” and **off** “Values Changed” to keep it simple:

```python
# PoseEffect_Master / parexec1  (Parameter Execute DAT script)

BUSY_KEY = '_parexec_busy'

def _norm_name(par):
    nm = getattr(par, 'tupletName', '') or par.name or ''
    return nm.strip().casefold()

def _ext():
    ex = getattr(op('.'), 'ext', None)
    return getattr(ex, 'PoseEffectMasterExt', None) if ex else None

def _guarded(fn):
    # Prevent re-entrancy loops
    if me.fetch(BUSY_KEY, False):
        return
    me.store(BUSY_KEY, True)
    try:
        fn()
    finally:
        me.store(BUSY_KEY, False)

# Which parameters we watch (case-insensitive)
WATCH_FILTER = {'landmarkfilter', 'landmarkfiltercsv'}
WATCH_ACTIVE = {'active'}

def onValueChange(par, prev):
    nm  = _norm_name(par)
    ext = _ext()
    if not ext:
        return True

    if nm in WATCH_FILTER:
        _guarded(lambda: ext.ApplyFilter())
    elif nm in WATCH_ACTIVE:
        # Only react to UI/switcher; SetActive() no longer writes Active back
        val = bool(par.eval())
        _guarded(lambda: ext.SetActive(val))
    return True

def onPulse(par):
    # Optional: add a Pulse param 'ApplyFilter' on the effect to force a rebuild
    if _norm_name(par) == 'applyfilter':
        ext = _ext()
        if ext:
            _guarded(lambda: ext.ApplyFilter())
    return True

# Leave the rest at defaults
def onValuesChanged(changes): return True
def onExpressionChange(par, val, prev): return True
def onExportChange(par, val, prev): return True
def onEnableChange(par, val, prev): return True
def onModeChange(par, val, prev): return True
```

**TD UI toggles for this DAT:**

- ✅ Value Change
- ❌ Values Changed (turn this **off** to avoid coalesce complexity)
- ✅ On Pulse (only if you add the optional `ApplyFilter` pulse)

------

## Fix 3 — Keep LandmarkSelect write-only and one-way

In `LandmarkSelectExt.Rebuild()`:

- **Do not** write to the child’s `LandmarkFilter`/`Landmarkfiltercsv` (they should mirror parent via expressions).
- It’s fine to set:
  - `select1.par.op = '../in1'`
  - `select1.par.channame = '...'`
  - `landmark_mask.par.file = <csv>` (then pulse `reload`/`reloadpulse`)

This keeps the dataflow **parent → child**, never child → parent, which avoids dependency cycles.

------

## Fix 4 — Sanity settings that help

- On each `PoseEffect_*` COMP: **Cook Type = Selective**.
- On heavy nodes inside `fxCore`: Selective too.
- Ensure the **fxCore** doesn’t contain expressions referencing back to `landmarkSelect/select1` in a way that alters the effect’s **own** parameters. Read-only is fine.

------

## Quick test checklist

1. Open the warning bubble on `PoseEffect_Dots/parexec1`—after the changes, the cook dependency loop warning should be gone.
2. Toggle `LandmarkFilter` on the **active** effect:
   - `landmarkSelect/select1.par.channame` updates once.
   - No re-trigger storm in the Textport.
3. Toggle **Active** on an effect:
   - Only that effect cooks (`allowCooking=True`), others stop.
   - parexec doesn’t loop (because `SetActive()` no longer writes `Active`).

If you still see the loop warning, tell me the exact operators named in the loop report (TD shows the chain). I’ll pinpoint and patch the last edge.