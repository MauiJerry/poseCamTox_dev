# Step‑by‑step 23Aug 5p

This version bakes in our final decisions:

- **SSOT (Single Source of Truth):**
  - **PoseEffect (parent)** owns identity/routing: `UiDisplayName`, `LandmarkFilter` (+ CSV if used).
  - **fxCore (child)** owns renderer knobs: `ColorType`, `Color`, `DotSize`, etc.
- **Discovery rule for the UI:** **Expose everything that**
  1. **starts with `Ui`** in `fxCore`, **plus**
  2. anything listed (one‑column) in `fxCore/expose_params`.
      This lets devs “promote” non‑Ui parameters by just listing their names.

------

## 0) What goes where (quick map)

- **PoseEffect_MASTER (parent)**
  - `UiDisplayName` (Str; default “Master”).
  - `LandmarkFilter` (Menu; default “All”).
- **fxCore (child)**
  - Visual params (SSOT): `ColorType` (menu: solid|random), `Color` (RGB), `DotSize` (float).
  - `UiLandmarkFilter` (Menu) **proxy bound to** parent `LandmarkFilter` so the FX panel can show it without duplicating truth.
  - `expose_params` (Table DAT, single column) to list **non‑Ui** params you want in the panel (e.g., `ColorType`, `Color`, `DotSize`).
  - (Optional) you can also use `Ui*` names instead of the table; discovery takes the **union** of both.

> The previous draft already described the general layout and cloning flow; we’re keeping that, just changing discovery/ownership rules.  

------

## 1) PoseEffectMASTER: add parent params and fxCore proxy

1. **Add to the parent (`PoseEffectMASTER`)**

   - `UiDisplayName` (Str) → default `Master`.
   - `LandmarkFilter` (Menu) → default `All`.

2. **Inside `PoseEffectMASTER/fxCore`**

   - Create `UiLandmarkFilter` (Menu) and **bind** it to the parent:

     - **Value bind:** `op('..').par.LandmarkFilter`
     - **Menu names/labels (optional binds):**
        `op('..').par.LandmarkFilter.menuNames` / `.menuLabels`

   - Create a **Table DAT** named `expose_params` (one column, one name per row). For the master template, it’s fine to start with:

     ```
     UiLandmarkFilter
     ```

   (Clones will extend this with effect‑specific knobs.)

------

## 2) PoseEfxSwitch: build the menu using `UiDisplayName` (parent)

Update your switch extension to **label** menu items with `UiDisplayName` (fall back to prettified OP name if still “Master”). Keys remain the **exact COMP names** so automation is stable. 

```python
# /PoseEfxSwitch/ext/PoseEfxSwitchExt.py

def _label_for_effect(self, fx):
    # Prefer parent.UiDisplayName; fallback to derived OP name
    try:
        p = getattr(fx.par, 'Uidisplayname', None)
        if p:
            val = (p.eval() or '').strip()
            if val and val.lower() != 'master':
                return val
    except: pass
    return fx.name.replace('PoseEffect_', '').replace('_', ' ').title()

def BuildEffectsMenu(self):
    effs  = [c for c in self.owner.op('effects').children
             if c.isCOMP and c.name.startswith('PoseEffect_')]
    items = [e.name for e in effs]               # stable keys
    labels= [self._label_for_effect(e) for e in effs]
    par = self.owner.par.Activeeffect
    par.menuItems  = items
    par.menuNames  = labels
    par.menuLabels = labels
```

> Rebuild via the “Rebuild Effects Menu” pulse as before. 

------

## 3) UI Builder: discovery = `Ui*` **union** `expose_params`

Revise your builder so the FX panel is created from the **active effect’s** `fxCore` using the hybrid rule. The panel should bind directly to the **real** parameters (SSOT), so changes reflect down immediately. The previous 4p draft already shows the “rebuild + panel build” flow; only `discover_params()` changes. 

```python
# /UI/UI_Builder (core bits)

def _switch():
    return op('/PoseEfxSwitch') if op('/PoseEfxSwitch') else op('/EfxSwitch')

def _active_fx():
    sw = _switch()
    name = sw.par.ActiveEffect.eval()
    return sw.op('effects/' + name) if name else None

def discover_params(fx):
    """Return list of parameter NAMES to expose for this PoseEffect_*."""
    core = fx.op('fxCore') or fx
    names = set()

    # A) All Ui* params on fxCore
    for p in core.customPars:
        if p.name.startswith('Ui'):
            names.add(p.name)

    # B) Any listed in fxCore/expose_params (single col)
    t = core.op('expose_params')
    if t:
        for r in t.rows():
            if r and r[0].val.strip():
                names.add(r[0].val.strip())

    return [n for n in sorted(names) if hasattr(core.par, n)]

def rebuild():
    sw = _switch()
    # Rebuild the switch menu first
    if hasattr(sw.par, 'RebuildeffectsMenu'):
        sw.par.RebuildeffectsMenu.pulse()
    elif hasattr(sw.ext, 'PoseEfxSwitchExt'):
        getattr(sw.ext.PoseEfxSwitchExt, 'BuildEffectsMenu')()

    # Build panel for the active effect
    fx  = _active_fx()
    if not fx: return
    core = fx.op('fxCore') or fx

    for c in parent().children:
        if c.isPanel: c.destroy()

    y = 10
    for pname in discover_params(fx):
        lbl = parent().create(textTOP, f"lbl_{pname}")
        lbl.par.text = pname; lbl.par.t = y

        p = getattr(core.par, pname)
        if p.isMenu:
            dd = parent().create(comboCOMP, f"dd_{pname}")
            dd.par.t = y + 20
            dd.par.Menu = '\n'.join(p.menuLabels or p.menuNames or [])
            def _onSel(_pname=pname, _owner=core):
                _par = getattr(_owner.par, _pname)
                key = _par.menuNames[dd.par.selectedindex.eval()]
                _par.val = key
            dd.click = _onSel
            y += 60
        elif p.isRGB or p.tupletSize in (3,4):
            for i in range(p.tupletSize):
                s = parent().create(sliderCOMP, f"sl_{pname}_{i}")
                s.par.t = y + 20 + i*26
                s.par.value0.expr = f"op('{core.path}').par.{pname}[{i}]"
                def _cb(v, _idx=i, _pname=pname, _owner=core):
                    par = getattr(_owner.par, _pname)
                    par[_idx] = float(v)
                s.panel.value = _cb
            y += 26*p.tupletSize + 20
        else:
            s = parent().create(sliderCOMP, f"sl_{pname}")
            s.par.t = y + 20
            s.par.value0.expr = f"op('{core.path}').par.{pname}"
            def _cb(v, _pname=pname, _owner=core):
                getattr(_owner.par, _pname).val = float(v)
            s.panel.value = _cb
            y += 50
```

------

## 4) Create **Dots** by cloning Master, add its params, and expose them

1. Under `/PoseEfxSwitch/effects`: **clone** `PoseEffectMASTER` → `PoseEffect_Dots`.
    Set **`fxCore` Clone Immune = On** (common pattern so each effect can diverge). 

2. Inside `PoseEffect_Dots/fxCore` add **visual** params (SSOT):

   - `ColorType` (Menu: `Solid|Random`, default `Solid`)
   - `Color` (RGB)
   - `DotSize` (Float)
   - Keep `UiLandmarkFilter` (Menu) **bound** to parent `LandmarkFilter` as in Step 1.

3. **Expose** those non‑Ui names via `expose_params` (single column, one per row):

   ```
   ColorType
   Color
   DotSize
   UiLandmarkFilter
   ```

   (Hybrid rule → these are now visible alongside any `Ui*` you might add later.)

4. Add your **Script CHOP** `landmark_to_instances` (the DAT‑meta version you have) that outputs `tx, ty, scale, r, g, b, a`, then instance a quad and render to `fxOut`. The previous design wiring remains the same (instancing + ortho cam width=2 for pixel sizing).  

5. Back at the switcher: **Rebuild Effects Menu**; pick “Dots” and confirm the FX panel shows `ColorType`, `Color`, `DotSize`, and the `UiLandmarkFilter` proxy. 

------

## 5) Duplicating Dots (e.g., `PoseEffect_Dots2`)

- Copy `PoseEffect_Dots` → rename to `PoseEffect_Dots2`, wire `fxOut` into the next free input, **Rebuild Effects Menu**. Both appear in the Active Effect menu.
- Set different **defaults** inside `PoseEffect_Dots2/fxCore` (`Color`, `DotSize`, `ColorType`) so each copy has a distinct personality. 

------

## 6) Sanity checklist

- Parent owns **`UiDisplayName`** and **`LandmarkFilter`**; `fxCore/UiLandmarkFilter` is a **bound proxy** for panel exposure.
- FX panel shows **`Ui\*` params PLUS** anything in **`fxCore/expose_params`** (single‑column names).
- Menu labels prefer `UiDisplayName` (parent), else pretty OP name.
- Dots Script CHOP still sizes in **pixels** given `image_height` from guarded meta (DAT) and ortho width=2.  

------

If you want, I can also paste a compact `fx_dots_landmark_to_instances.py` with the DAT `inMeta` lookup you’re using, but the wiring from the existing design remains valid.