# Replacement Scripts 

Awesome—here are **complete, drop‑in replacements** for the four files you attached, plus a brand‑new **UI Builder** script and exactly where to put it.

These implement our 5pm decisions:

- **Parent `PoseEffect_\*` is SSOT** for `UiDisplayName` and `LandmarkFilter`.
- **Child `fxCore`** is SSOT for visual params.
- **UI discovery rule:** expose **all `Ui\*` params** in `fxCore` **plus** anything listed in `fxCore/expose_params` (single‑column).
- **Menu labels:** prefer `UiDisplayName` on the parent; fall back to pretty OP name.
- **Landmark menus:** stamped and bound per effect; `landmarkSelect` reads the parent’s params.

I kept all previous lifecycle and routing behaviors, just modernized naming/label logic and added small helpers where useful.

------

# 1) `ext/PoseEffectMasterExt.py` (replace entirely)

```python
# ext/PoseEffectMasterExt.py
# Lives on each PoseEffect_* (including the Master). Handles activation, bypass policy,
# and tells the child landmarkSelect to rebuild when needed.

class PoseEffectMasterExt:
    def __init__(self, owner):
        self.owner = owner

    # ===== Activation & lifecycle ============================================
    def SetActive(self, active: bool):
        """Called by PoseEfxSwitch when this effect becomes (in)active."""
        # 1) Gate cooking at the COMP level
        self.owner.allowCooking = bool(active)

        # 2) Update any 'Active' UI toggle (if present) to reflect state
        if hasattr(self.owner.par, 'Active'):
            want = 1 if active else 0
            if int(self.owner.par.Active.eval() or 0) != want:
                self.owner.par.Active = want

        # 3) Bypass policy for fxCore when inactive (optional)
        core = self.owner.op('fxCore')
        if core:
            bypass_inactive = False
            if hasattr(self.owner.par, 'Bypassinactive'):
                try:
                    bypass_inactive = bool(self.owner.par.Bypassinactive.eval())
                except Exception:
                    bypass_inactive = True
            core.par.bypass = (not active) and bypass_inactive

        # 4) On activation, ensure the landmark selection is fresh
        if active:
            self.ApplyFilter()

    # ===== Filter propagation (parent is SSOT) ================================
    def ApplyFilter(self):
        """Ask the child landmarkSelect to rebuild its Select CHOP pattern."""
        ls = self.owner.op('landmarkSelect')
        if ls and hasattr(ls.ext, 'LandmarkSelectExt'):
            ls.ext.LandmarkSelectExt.Rebuild()

    # ===== Services to children ===============================================
    def ResolveMenuCSV(self, key: str) -> str:
        """Delegate menu CSV lookup to the PoseEfxSwitch parent."""
        switch = self.owner.parent()
        if hasattr(switch.ext, 'PoseEfxSwitchExt'):
            return switch.ext.PoseEfxSwitchExt.ResolveMenuCSV(key)
        return ''
```

(Your previous version already had this shape; this keeps the same responsibilities and API.)

------

# 2) `ext/PoseEfxSwitchExt.py` (replace entirely)

```python
# ext/PoseEfxSwitchExt.py
# -----------------------------------------------------------------------------
# PoseEfxSwitchExt
# -----------------------------------------------------------------------------
# Attach this extension to the PoseEfxSwitch COMP.
#
# Responsibilities (finalized 23 Aug):
#   • Build the ActiveEffect menu labels from PoseEffect parent.par.UiDisplayName
#     (fall back to pretty OP name). Menu values remain stable keys (OP names).
#   • Keep ActiveEffect (menu) and ActiveIndex (int) in sync WITHOUT loops.
#   • Activate exactly one PoseEffect_*:
#       - Route out_switch.index
#       - fx.allowCooking  = True for active, False for others
#       - fxCore.bypass    = False for active, True for others
#       - fx.ext.PoseEffectMasterExt.SetActive(active)
#   • Stamp LandmarkFilter menu items into each PoseEffect and its child
#     landmarkSelect from LandmarkFilterMenu_csv (key,label,csv).
#   • Ensure each landmarkSelect reads its parent PoseEffect params via expressions.
#
# Expected nodes inside PoseEfxSwitch:
#   - LandmarkFilterMenu_csv  (Table DAT: key,label,csv)               ← REQUIRED
#   - effects/                (Base COMP container for PoseEffect_* children)
#   - out_switch              (Switch TOP)
#
# UI parameters on PoseEfxSwitch (Customize Component…):
#   - ActiveEffect       (Menu)     ← user-facing effect picker (values = OP names)
#   - ActiveIndex        (Int)      ← internal index (hide if you like)
#   - RebuildEffectsMenu (Pulse)    ← manual refresh
#
# Initialization:
#   - Put an Execute DAT *inside* PoseEfxSwitch with:
#       def onStart(): op('.').ext.PoseEfxSwitchExt.Initialize()
# -----------------------------------------------------------------------------

class PoseEfxSwitchExt:
    def __init__(self, owner):
        self.owner = owner
        self._syncing = False  # re-entrancy guard

    # ===== Lifecycle ==========================================================
    def Initialize(self):
        """Called by the embedded Execute DAT on project start."""
        self.InitLandmarkMenus()
        self.EnsureLandmarkBindings()
        self.BuildEffectsMenu()

        # Choose initial active effect: keep current if valid else first else index 0
        key = (self.owner.par.ActiveEffect.eval() or '').strip()
        keys = self._menuKeys()
        if key in keys:
            self.SetActiveEffect(key)
        elif keys:
            self.SetActiveEffect(keys[0])
        else:
            self.SetActiveIndex(0)

    # ===== Landmark filter menus (per-effect) =================================
    def InitLandmarkMenus(self):
        """Stamp LandmarkFilter menu (names/labels) onto PoseEffect and child selector."""
        table = self.owner.op('LandmarkFilterMenu_csv')
        if not table or table.numRows < 2:
            debug("[PoseEfxSwitchExt.InitLandmarkMenus] Missing/empty LandmarkFilterMenu_csv")
            return

        heads = [c.val.lower() for c in table.row(0)]
        try:
            ki = heads.index('key')
            li = heads.index('label')
            ci = heads.index('csv')
        except ValueError:
            debug("[PoseEfxSwitchExt.InitLandmarkMenus] CSV must have columns: key,label,csv")
            return

        keys, labels, csvs = [], [], []
        for r in table.rows()[1:]:
            k = r[ki].val.strip()
            if not k:
                continue
            keys.append(k)
            labels.append((r[li].val or k).strip())
            csvs.append((r[ci].val or '').strip())

        for fx in self._effects():
            # Stamp on PoseEffect parent (SSOT)
            if hasattr(fx.par, 'LandmarkFilter'):
                fx.par.LandmarkFilter.menuNames  = keys
                fx.par.LandmarkFilter.menuLabels = labels

            # Mirror menu on child landmarkSelect (value is expression-bound)
            ls = fx.op('landmarkSelect')
            if ls and hasattr(ls.par, 'LandmarkFilter'):
                ls.par.LandmarkFilter.menuNames  = keys
                ls.par.LandmarkFilter.menuLabels = labels

            # Seed default CSV if key has mapping and isn't 'custom'
            cur = (getattr(fx.par, 'LandmarkFilter', None).eval() if hasattr(fx.par, 'LandmarkFilter') else '') or ''
            if cur in keys and cur != 'custom':
                idx = keys.index(cur)
                defcsv = csvs[idx] if idx < len(csvs) else ''
                if defcsv and hasattr(fx.par, 'Landmarkfiltercsv'):
                    fx.par.Landmarkfiltercsv = defcsv

    def EnsureLandmarkBindings(self):
        """Ensure landmarkSelect reads parent PoseEffect params via expressions."""
        for fx in self._effects():
            ls = fx.op('landmarkSelect')
            if not ls:
                continue
            if hasattr(ls.par, 'LandmarkFilter') and not ls.par.LandmarkFilter.expr:
                ls.par.LandmarkFilter.expr = "op('..').par.LandmarkFilter.eval()"
            if hasattr(ls.par, 'Landmarkfiltercsv') and not ls.par.Landmarkfiltercsv.expr:
                ls.par.Landmarkfiltercsv.expr = "op('..').par.Landmarkfiltercsv.eval() or ''"

    # ===== Effect menu (ActiveEffect) =========================================
    def BuildEffectsMenu(self):
        """
        Auto-discover PoseEffect_* children and build ActiveEffect menu.
        Values = OP names (stable). Labels = parent.par.UiDisplayName if set,
        else derived from OP name ("PoseEffect_Dots2" -> "Dots 2").
        """
        keys, labels = [], []
        for fx in self._effects():
            key = fx.name  # OP name is the stable key
            lab = self._label_for_effect(fx)
            keys.append(key)
            labels.append(lab)

        # Stamp the UI menu
        self.owner.par.ActiveEffect.menuNames  = keys
        self.owner.par.ActiveEffect.menuLabels = labels

        # Keep current selection valid, then push activation
        cur = (self.owner.par.ActiveEffect.eval() or '').strip()
        if cur not in keys and keys:
            self.owner.par.ActiveEffect = keys[0]
        self.OnActiveEffectChanged()

    def _label_for_effect(self, fx):
        """Prefer PoseEffect.UiDisplayName (non-'Master'), else pretty OP name."""
        try:
            p = getattr(fx.par, 'Uidisplayname', None)
            if p:
                val = (p.eval() or '').strip()
                if val and val.lower() != 'master':
                    return val
        except Exception:
            pass
        return fx.name.replace('PoseEffect_', '').replace('_', ' ').title()

    def OnActiveEffectChanged(self):
        """Called when the ActiveEffect (menu) param changes."""
        if self._syncing:
            return
        self._syncing = True
        try:
            key = (self.owner.par.ActiveEffect.eval() or '').strip()
            idx = self._indexForOpName(key)
            if idx is not None and int(self.owner.par.ActiveIndex.eval() or -1) != idx:
                self.owner.par.ActiveIndex = idx
            self.SetActiveIndex(int(self.owner.par.ActiveIndex.eval() or 0))
        finally:
            self._syncing = False

    def OnActiveIndexChanged(self):
        """Called when the ActiveIndex (int) param changes."""
        if self._syncing:
            return
        self._syncing = True
        try:
            idx = int(self.owner.par.ActiveIndex.eval() or 0)
            fx  = self._effectAtIndex(idx)
            key = fx.name if fx else ''
            if key and (self.owner.par.ActiveEffect.eval() or '') != key:
                self.owner.par.ActiveEffect = key
            self.SetActiveIndex(idx)
        finally:
            self._syncing = False

    def SetActiveEffect(self, key: str):
        """Programmatic activation by OP name (updates both params + activation)."""
        key = (key or '').strip()
        keys = self._menuKeys()
        if not keys:
            return
        if key not in keys:
            key = keys[0]
        self.owner.par.ActiveEffect = key  # triggers OnActiveEffectChanged

    def SetActiveIndex(self, idx: int):
        """
        Activate exactly one PoseEffect_* and route out_switch to that index.
        """
        # Route output switch
        sw = self.owner.op('out_switch')
        if sw:
            sw.par.index = int(idx)

        # Gate cooking + call SetActive on each effect
        for i, fx in enumerate(self._effects()):
            is_active = (i == int(idx))
            fx.allowCooking = is_active
            core = fx.op('fxCore')
            if core:
                core.par.bypass = not is_active
            if hasattr(fx.ext, 'PoseEffectMasterExt'):
                fx.ext.PoseEffectMasterExt.SetActive(is_active)

    # ===== Services for children ==============================================
    def ResolveMenuCSV(self, key: str) -> str:
        """Given a filter menu key (e.g., 'hands'), return default CSV path."""
        key = (key or '').strip().lower()
        table = self.owner.op('LandmarkFilterMenu_csv')
        if not table or table.numRows < 2:
            return ''
        heads = [c.val.lower() for c in table.row(0)]
        try:
            ki = heads.index('key')
            ci = heads.index('csv')
        except ValueError:
            return ''
        for r in table.rows()[1:]:
            if r[ki].val.strip().lower() == key:
                return (r[ci].val or '').strip()
        return ''

    # ===== Helpers =============================================================
    def _effects(self):
        """Return all PoseEffect_* COMPs under ./effects."""
        eff = self.owner.op('effects')
        if not eff:
            return []
        return [c for c in eff.children if c.isCOMP and c.name.startswith('PoseEffect_')]

    def _menuKeys(self):
        """Return menu values (OP names)."""
        return list(self.owner.par.ActiveEffect.menuNames or [])

    def _effectAtIndex(self, idx: int):
        effs = self._effects()
        if 0 <= idx < len(effs):
            return effs[idx]
        return None

    def _indexForOpName(self, name: str):
        effs = self._effects()
        for i, fx in enumerate(effs):
            if fx.name == name:
                return i
        return None
```

This replacement simplifies your previous dispatch‑table complexity and aligns the menu to **OP names as stable keys** with **UiDisplayName** for labels. It preserves your init, routing, and landmark menu stamping flows.

------

# 3) `poseEfxSwitch_exec_init.py` (replace entirely)

```python
# poseEfxSwitch_exec_init.py
def onStart():
    op('.').ext.PoseEfxSwitchExt.Initialize()
    return
```

(Same entrypoint, kept as‑is.)

------

# 4) `poseEfxSwitch_paramExec.py` (replace entirely)

```python
# PoseEfxSwitch / parexec1 (Parameter Execute DAT callbacks)

# Canvas defaults that should trigger a guarded meta rebuild (if you use one)
CANVAS_PARAMS = {'Defaultcanvasw', 'Defaultcanvash'}

# Optional pulse param name to force a manual refresh
REFRESH_PULSE = 'Refreshmeta'

def _update_guard():
    gm = op('guard_meta')
    if not gm:
        debug('[parexec1] Missing guard_meta Text DAT')
        return
    try:
        gm.module.update_guard()
    except Exception as e:
        debug('[parexec1] guard_meta.update_guard() error:', e)

def onValueChange(par, prev):
    """Called when any watched parameter's value changes."""
    if par is None:
        return True

    # 1) Guarded meta refresh when canvas defaults change
    if par.name in CANVAS_PARAMS:
        _update_guard()

    # 2) Switch behaviors
    if par.name == 'ActiveEffect':
        op('.').ext.PoseEfxSwitchExt.OnActiveEffectChanged()
    elif par.name == 'ActiveIndex':
        op('.').ext.PoseEfxSwitchExt.OnActiveIndexChanged()
    elif par.name == 'RebuildEffectsMenu':
        op('.').ext.PoseEfxSwitchExt.BuildEffectsMenu()
    return True

def onPulse(par):
    """Called when any watched pulse parameter is pressed."""
    if par is None:
        return True

    if par.name == REFRESH_PULSE:
        _update_guard()

    if par.name == 'RebuildEffectsMenu':
        op('.').ext.PoseEfxSwitchExt.BuildEffectsMenu()

    return True

def onExpressionChange(par, prev):
    """If canvas defaults are expression-driven, refresh on expression change too."""
    if par and par.name in CANVAS_PARAMS:
        _update_guard()
    return True

def onExportChange(par, prev):
    if par and par.name in CANVAS_PARAMS:
        _update_guard()
    return True
```

(This keeps your behavior intact.)

------

# 5) New: create the **UI Builder** and drop this script

**Where to create it**

- Make a base COMP `/UI` (or pick an existing UI container).

- Inside `/UI`, create a **Text DAT** named **`UI_Builder`**.

- Paste the following script. You can call it from the Textport with:

  ```
  op('/UI/UI_Builder').module.rebuild()
  ```

- It builds a simple control panel directly under `/UI` using TD components (labels, sliders, combos). Edit as needed.

**What this does**

- Rebuilds the switch menu first (so it reflects current effects).
- Builds the **FX panel for the active effect**, using our discovery rule:
  - **All `Ui\*` params in `fxCore`**
  - **PLUS** anything listed in **`fxCore/expose_params`** (single column of names)

```python
# /UI/UI_Builder

def _switch():
    return op('/PoseEfxSwitch') if op('/PoseEfxSwitch') else op('/EfxSwitch')

def _active_fx():
    sw = _switch()
    name = sw.par.ActiveEffect.eval()
    return sw.op('effects/' + name) if name else None

def _discover_params(fx):
    """
    Discovery = (A) Ui* params on fxCore UNION (B) names listed in fxCore/expose_params.
    Returns a sorted list of parameter names that exist on fxCore.
    """
    core = fx.op('fxCore') or fx
    names = set()

    # (A) Ui* params
    for p in core.customPars:
        if p.name.startswith('Ui'):
            names.add(p.name)

    # (B) expose_params DAT (single-column)
    t = core.op('expose_params')
    if t:
        for r in t.rows():
            if r and r[0].val.strip():
                names.add(r[0].val.strip())

    # Only keep ones that actually exist
    keep = [n for n in names if hasattr(core.par, n)]
    keep.sort()
    return keep

def _pretty_label(name):
    return name.replace('Ui', '').replace('_',' ').title()

def _clear_ui():
    for c in parent().children:
        if c.isPanel:
            c.destroy()

def rebuild():
    sw = _switch()

    # 1) Rebuild the switch's menu first
    if hasattr(sw.par, 'RebuildeffectsMenu'):
        sw.par.RebuildeffectsMenu.pulse()
    elif hasattr(sw.ext, 'PoseEfxSwitchExt'):
        sw.ext.PoseEfxSwitchExt.BuildEffectsMenu()

    # 2) Build a simple header with the ActiveEffect menu (labels come from switch)
    _clear_ui()
    y = 10
    lbl = parent().create(textTOP, 'lbl_fx')
    lbl.par.text = 'Active Effect'
    lbl.par.t = y

    dd = parent().create(comboCOMP, 'dd_fx')
    dd.par.t = y + 24
    names = sw.par.ActiveEffect.menuLabels or sw.par.ActiveEffect.menuNames or []
    dd.par.Menu = '\n'.join(names)

    def _onSelect(_=None):
        # Translate selected label -> OP name by index
        idx = dd.par.selectedindex.eval()
        items = sw.par.ActiveEffect.menuNames or []
        if 0 <= idx < len(items):
            sw.par.ActiveEffect = items[idx]
            _build_fx_panel()  # refresh the panel for newly active FX
    dd.click = _onSelect
    y += 70

    # 3) Build the panel for the current active effect
    _build_fx_panel(start_y=y)

def _build_fx_panel(start_y=80):
    """(Re)build the controls for the active effect under /UI."""
    fx = _active_fx()
    if not fx:
        return
    core = fx.op('fxCore') or fx

    # Remove old controls (but keep header/menu)
    for c in parent().children:
        if c.isPanel and c.name.startswith(('lbl_', 'dd_')) is False:
            c.destroy()

    y = start_y
    for pname in _discover_params(fx):
        p = getattr(core.par, pname)
        # Label
        lbl = parent().create(textTOP, f"lbl_{pname}")
        lbl.par.text = _pretty_label(pname)
        lbl.par.t = y

        if p.isMenu:
            dd = parent().create(comboCOMP, f"dd_{pname}")
            dd.par.t = y + 24
            dd.par.Menu = '\n'.join(p.menuLabels or p.menuNames or [])
            def _onSel(_pn=pname, _owner=core):
                _par = getattr(_owner.par, _pn)
                key = _par.menuNames[dd.par.selectedindex.eval()]
                _par.val = key
            dd.click = _onSel
            y += 64

        elif p.isRGB or p.tupletSize in (3,4):
            # RGB/RGBA tuple
            for i in range(p.tupletSize):
                sl = parent().create(sliderCOMP, f"sl_{pname}_{i}")
                sl.par.t = y + 24 + i*26
                sl.par.value0.expr = f"op('{core.path}').par.{pname}[{i}]"
                def _cb(v, _idx=i, _pn=pname, _owner=core):
                    par = getattr(_owner.par, _pn)
                    par[_idx] = float(v)
                sl.panel.value = _cb
            y += 26 * p.tupletSize + 28

        elif p.isFloat or p.isInt:
            sl = parent().create(sliderCOMP, f"sl_{pname}")
            sl.par.t = y + 24
            sl.par.value0.expr = f"op('{core.path}').par.{pname}"
            def _cb(v, _pn=pname, _owner=core):
                getattr(_owner.par, _pn).val = float(v)
            sl.panel.value = _cb
            y += 64

        else:
            # Fallback: string field
            fld = parent().create(fieldCOMP, f"txt_{pname}")
            fld.par.t = y + 24
            fld.par.text.expr = f"op('{core.path}').par.{pname}"
            def _onChg(v, _pn=pname, _owner=core):
                getattr(_owner.par, _pn).val = str(v)
            fld.panel.value = _onChg
            y += 64
```

------

## Where to put the `UiDisplayName` and `UiLandmarkFilter` parameters

- On each **PoseEffect_* (parent)**: add `UiDisplayName` (Str, default “Master”) and `LandmarkFilter` (Menu, default “All”).
- Inside each **fxCore (child)**: add `UiLandmarkFilter` (Menu) **bound** to `op('..').par.LandmarkFilter`, and include it either as a `Ui*` param or list it in `fxCore/expose_params` so it shows in the FX panel.

The **UI Builder** above will then surface:

- every `Ui*` in `fxCore` (e.g., `UiLandmarkFilter` if you keep it `Ui*`), **plus**
- any **non‑Ui** names you list in `fxCore/expose_params` (e.g., `ColorType`, `Color`, `DotSize` if you don’t want to rename them).

------

## Sanity checklist

- Switch menu values are **OP names**; labels use **`UiDisplayName`** when present. (This replaces the prior “key/label/index” csv/param scheme and is simpler.)
- Landmark menus are stamped from `LandmarkFilterMenu_csv` onto each effect and mirrored on `landmarkSelect`.
- `PoseEffectMasterExt` still gates cooking, toggles `Active`, and triggers `ApplyFilter()` on activation.
- The UI Builder exists now at `/UI/UI_Builder` and builds a minimal but fully bound FX panel.

If you want, I can also hand you a tiny **starter `expose_params`** for Dots (`ColorType`, `Color`, `DotSize`, `UiLandmarkFilter`) and the **`fx_dots_landmark_to_instances.py`** again with the in‑Meta DAT reads—just say the word.