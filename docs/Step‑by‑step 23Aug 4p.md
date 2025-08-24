Here’s a tight, copy‑pasteable plan + code to make this work end‑to‑end.

# Step‑by‑step 23Aug 4p

## 1) Master: add `expose_params` in `PoseEffectMASTER/fxCore`

- Dive into `PoseEffectMASTER/fxCore`.
- Component Editor ▸ **Customize Component…** add two custom pars:
  - `UiDisplayName` (Str, default **Master**)
  - `UiLandmarkFilter` (Menu, default **All**)
- Add a **Table DAT** named **`expose_params`** with at least these two rows:

```
name,label,style,size,min,max,default,group
UiDisplayName,Display Name,string,1,,,,UI
UiLandmarkFilter,Landmark Filter,menu,1,,,All,Filter
```

This table (and defaults) is what EfxSwitch/UIBuilder will read to (a) name the effect in the menu and (b) seed the per‑effect filter UI. (The switch is already set up to distribute a landmark filter menu and keep child `landmarkSelect` bound to the parent PoseEffect; we’re just giving it defaults here.)  

> Why in **fxCore**: it clones with the effect and stays near the code that uses it. If you prefer, you can put the same two pars on the PoseEffect container; the UIBuilder snippet below checks `fxCore` first, then the parent.

## 2) Switch: use `UiDisplayName` when (re)building the ActiveEffect menu

Patch your `PoseEfxSwitchExt.BuildEffectsMenu()` to prefer `fxCore.par.UiDisplayName` unless it’s still “Master” (in which case derive from the OP name “PoseEffect_*”). The switch already handles menu population and syncing with **ActiveIndex**, so we’re just swapping how labels are chosen. 

### Minimal patch (inside `PoseEfxSwitchExt.py`)

```python
def _fx_display_name(self, fx):
    # Prefer fxCore.UiDisplayName; fall back to derived name
    core = fx.op('fxCore')
    val = ''
    try:
        if core and hasattr(core.par, 'Uidisplayname'):
            val = (core.par.Uidisplayname.eval() or '').strip()
    except Exception:
        val = ''
    if not val or val.lower() == 'master':
        # derive from op name: PoseEffect_Dots -> "Dots"
        base = fx.name.replace('PoseEffect_', '')
        val = base.replace('_', ' ').title()
    return val

def BuildEffectsMenu(self):
    keys, labels, ops, idxs = [], [], [], []
    # Auto‑discover PoseEffect_* children
    for i, fx in enumerate(self._effects()):
        key = fx.name  # keep key stable as exact comp name
        lab = self._fx_display_name(fx)
        keys.append(key); labels.append(lab); ops.append(fx.name); idxs.append(i)
    # stamp the menu
    self.owner.par.ActiveEffect.menuNames  = keys
    self.owner.par.ActiveEffect.menuLabels = labels
    # ...keep your existing dispatch table + sync code...
```

*(Your existing Initialize/OnActiveEffectChanged/SetActiveIndex control flow remains the same.)* The rest of the switch (landmark filter menu stamping + child bindings) is unchanged and already covered in your architecture doc. 

## 3) UIBuilder: walk effects, collect names, call switch to rebuild, and build the panel

Create `/UI/UI_Builder` (Text DAT) and use this:

```python
# /UI/UI_Builder

def _switch():
    return op('/PoseEfxSwitch') if op('/PoseEfxSwitch') else op('/EfxSwitch')

def _list_effects():
    eff = _switch().op('effects')
    return [c for c in eff.children if c.isCOMP and c.name.startswith('PoseEffect_')]

def _display_name(fx):
    # 1) fxCore.UiDisplayName; 2) parent.UiDisplayName; 3) derived from name
    core = fx.op('fxCore')
    for owner in (core, fx):
        if owner and hasattr(owner.par, 'Uidisplayname'):
            val = (owner.par.Uidisplayname.eval() or '').strip()
            if val and val.lower() != 'master':
                return val
    return fx.name.replace('PoseEffect_', '').replace('_', ' ').title()

def rebuild():
    sw = _switch()

    # ensure switch menu is fresh (works whether you exposed a pulse or call method)
    if hasattr(sw.par, 'RebuildeffectsMenu'):
        sw.par.RebuildeffectsMenu.pulse()
    elif hasattr(sw.ext, 'PoseEfxSwitchExt'):
        ext = sw.ext.PoseEfxSwitchExt
        if hasattr(ext, 'RebuiltEffectsMenu'):
            ext.RebuiltEffectsMenu()
        else:
            ext.BuildEffectsMenu()

    # clear existing UI panels under /UI
    for c in parent().children:
        if c.isPanel: c.destroy()

    # build a simple dropdown of all PoseEffect_* using display names
    names = [(fx.name, _display_name(fx)) for fx in _list_effects()]
    combo = parent().create(comboCOMP, 'fx_menu')
    combo.par.Menu = '\n'.join([lab for _, lab in names])

    # Select button: map chosen label -> comp name and set ActiveEffect on switch
    btn = parent().create(buttonCOMP, 'select')
    btn.par.label = 'Activate'

    def _onClick(_):
        label = combo.par.selectedlabel.eval()
        # lookup comp name by label
        compname = next((n for n, lab in names if lab == label), '')
        if compname:
            sw.par.ActiveEffect = compname  # switch already keeps index in sync
    btn.click = _onClick

    # Build "active FX" parameter panel by reading fxCore/expose_params
    act = sw.par.ActiveEffect.eval() or (names[0][0] if names else '')
    fx  = sw.op('effects/' + act) if act else None
    if not fx: return
    core = fx.op('fxCore') or fx
    expo = core.op('expose_params')
    rows = []
    if expo and expo.numRows > 1:
        hdr = [c.val.lower() for c in expo.row(0)]
        for r in expo.rows()[1:]:
            d = {hdr[i]: r[i].val for i in range(min(len(hdr), len(r)))}
            rows.append(d)

    y = 60
    for meta in rows:
        pname = meta.get('name','')
        label = meta.get('label', pname)
        style = (meta.get('style','float') or '').lower()
        # label
        t = parent().create(textTOP, f"lbl_{pname}")
        t.par.text = label
        t.par.t = y

        # control (float/int/menu/string/rgba minimal handling)
        owner = core if hasattr(core.par, pname) else fx
        if style in ('float','int'):
            s = parent().create(sliderCOMP, f"sl_{pname}")
            s.par.t = y + 20
            # bind to the parameter so changes reflect down & UI stays live
            s.par.value0.expr = f"op('{owner.path}').par.{pname}"
            # push back on drag
            def make_cb(nm, ow):
                def _cb(v):
                    getattr(ow.par, nm).val = float(v)
                    return
                return _cb
            s.panel.value = make_cb(pname, owner)
            y += 50

        elif style in ('rgba','rgb'):
            # simple 3/4 sliders
            count = 4 if style == 'rgba' else 3
            for i in range(count):
                ss = parent().create(sliderCOMP, f"sl_{pname}_{i}")
                ss.par.t = y + 20 + i*26
                ss.par.value0.expr = f"op('{owner.path}').par.{pname}[{i}]"
                def make_cb_i(nm, ow, idx):
                    def _cb(v):
                        par = getattr(ow.par, nm)
                        par[idx] = float(v); return
                    return _cb
                ss.panel.value = make_cb_i(pname, owner, i)
            y += 26*count + 20

        elif style == 'menu':
            dd = parent().create(comboCOMP, f"dd_{pname}")
            dd.par.t = y + 20
            # read menu labels if present, else fall back to current menu entries
            labels = getattr(owner.par, pname).menuLabels or getattr(owner.par, pname).menuNames or []
            dd.par.Menu = '\n'.join(labels)
            def _onSel(_):
                # set by name, not index, so bindings elsewhere keep working
                key = getattr(owner.par, pname).menuNames[dd.par.selectedindex.eval()]
                getattr(owner.par, pname).val = key
                return
            dd.click = _onSel
            y += 60

        else:  # string
            fld = parent().create(fieldCOMP, f"txt_{pname}")
            fld.par.t = y + 20
            fld.par.text.expr = f"op('{owner.path}').par.{pname}"
            def _onChg(v):
                getattr(owner.par, pname).val = str(v)
            fld.panel.value = _onChg
            y += 50
```

- That script:
  - Calls the switch to **rebuild** its menu first.
  - Gathers **PoseEffect_*** under `/EfxSwitch/effects`.
  - Uses `UiDisplayName` unless it’s still “Master”, then derives from OP name (`PoseEffect_Dots` → “Dots”).
  - Builds controls by reading **fxCore/expose_params** and **binding** them to the actual parameters so changes reflect down.

*(Your earlier docs show the same discovery flow and that UI should be rebuilt after effect/param changes.)*  

## 4) Create **Dots** by cloning Master and exposing its params

- Under `/EfxSwitch/effects`:
  1. **Clone** `PoseEffectMASTER` → `PoseEffect_Dots`.
  2. Dive into `PoseEffect_Dots` and set **`fxCore` Clone Immune = On** (only `fxCore` is immune; everything else inherits from Master). 
  3. Inside `fxCore`:
     - Add custom pars:
       - `ColorType` (Menu: `Solid|Random`, default `Solid`)
       - `Color` (RGB)
       - `DotSize` (Float)
       - `LandmarkFilter` (Menu, default `All`) or keep it on the parent PoseEffect if you’re already using the switch’s stamped menus.
     - Add/extend **`expose_params`** to include the new controls:

```
name,label,style,size,min,max,default,group
UiDisplayName,Display Name,string,1,,,,UI
UiLandmarkFilter,Landmark Filter,menu,1,,,All,Filter
ColorType,Color Type,menu,1,,,Solid,Look
Color,Color,rgba,4,0,1,1,1,1,1,Look
DotSize,Dot Size,float,1,1,64,8,Render
 - Build the dots network (instanced rectangles) and add the **Script CHOP** `landmark_to_instances` (use your file `fxCore_Dots_landmark_to_instances.py`, same shape as the drop‑in we documented: outputs `tx,ty,scale,r,g,b,a`). :contentReference[oaicite:7]{index=7} :contentReference[oaicite:8]{index=8}
 - Wire **Geometry COMP** with instancing:
   - Instance OP = the Script CHOP
   - Tx/ Ty = `tx/ty`; Uniform Scale = `scale`
   - Render with **Constant MAT** (blending ON). :contentReference[oaicite:9]{index=9}
```

- Back at `/UI`, run `op('/UI/UI_Builder').module.rebuild()`; you’ll see “Dots” in the menu and sliders for Color/DotSize, etc.

> Pixel‑accurate size: the Script CHOP converts pixels to NDC (`scale = DotSize / CanvasH` with ortho cam width=2), so dot size stays consistent with resolution. 

------

## Notes / conventions (recap)

- The **switch** still owns effect selection and keeps ActiveEffect ↔ ActiveIndex in sync; we’re only changing how the **labels** are chosen (via `UiDisplayName`). 
- Landmark filter menus remain **per‑effect**, stamped by the switch and bound into each effect’s `landmarkSelect`. (Your Master/Docs already describe this and the “rebuild” behavior.) 
- If a clone **doesn’t override** `UiDisplayName` (still “Master”), the menu label is auto‑derived from its OP name (“PoseEffect_Dots” → “Dots”). That gives you sensible names like “Dots 1/2/3” for multiple instances.

If you want, I can hand you a ready‑to‑paste `PoseEfxSwitchExt.py` with the `_fx_display_name()` helper folded in, or tweak the UIBuilder to show parameter **groups** as collapsible sections.

---

# a few additional prompts

What if I copy that effect so there are two Dots with different starting params named in menu with default name.  I should be able to copy PoseEffect_Dots and make PoseEffect_Dots2, change its default options and wire it into the inputs.  

## RESPONSE

Yep—copying Dots to make a second, differently‑configured Dots effect is totally supported. Here’s the clean, TD‑editor way to do it so both show up in the switcher menu and each keeps its own defaults.

# Step‑by‑step: make “PoseEffect_Dots2”, wire it, and get it in the menu

1. Duplicate the effect
    In `/PoseEfxSwitch/effects`:

- Select `PoseEffect_Dots` → **Copy** → **Paste**.
- Rename the new COMP to `PoseEffect_Dots2`.
   (Effects are instantiated as clones of `PoseEffectMASTER`, so a straight duplicate keeps the same contract and folder layout. )

1. Connect its output to the switch

- On `PoseEfxSwitch`, wire `PoseEffect_Dots2/fxOut` into the **next free input** on the output switch (e.g., `out_switch` or `outTop` input fan‑in). The master container’s outputs are standardized for this purpose (see Master README: child effects route their render to `fxOut`). 

1. Rebuild the menu so the new item appears

- On `PoseEfxSwitch`, click **Rebuild Effects Menu** (custom parameter). This repopulates the **Active Effect** menu from all `PoseEffect_*` children under `/effects`. (You’ll see the new item—by default it uses the OP name.) 

1. Give Dots2 its own starting defaults (so it’s visually different)
    Inside `/PoseEfxSwitch/effects/PoseEffect_Dots2/fxCore`:

- Right‑click → **Customize Component…** and set the default values you want for:

  - `UiColor` (RGB),
  - `UiDotSize` (Float),
  - `UiOpacity` (Float),
  - `UiColorMode` (Menu: Fixed | RandomPerLandmark).

- Make sure those params are **exposed** so the UI/ShowControl layer can surface them. Easiest path: create a `Table DAT` called `expose_params` with one name per row:

  ```
  UiColor
  UiDotSize
  UiOpacity
  UiColorMode
  Origin
  CanvasW
  CanvasH
  ```

  (The UI builder looks for that table—or any `Ui*`‑prefixed custom pars—to auto‑show controls.)   

1. (Optional) Different landmark subset per copy
    If you want Dots2 to render a different subset (e.g., hands only), set its `LandmarkFilter` or CSV in the effect (per‑effect filtering lives on each PoseEffect clone; the switcher just hosts and menus them). Then select Dots2 in **Active Effect** to verify its channels and look. (Effect instances keep their own params; only the active one cooks.)
2. Sanity‑check the Dots plumbing (only once per clone)
    If you built Dots from the design doc, confirm the standard `fxCore` wiring is intact:

- `CHOP In (0): skeleton_in`, optional `CHOP In (1): meta_in`
- `Script CHOP: landmark_to_instances` → instances (`tx, ty, scale, r, g, b, a`)
- `Geometry COMP` instancing the quad; `Render TOP` → `out_color` → `../fxOut`
   This is the drop‑in layout your clone should already have. 

------

## What you’ll see in the UI / menu

- After step 3, **Active Effect** will list both (e.g., `PoseEffect_Dots` and `PoseEffect_Dots2`). Pick either to make it live. (That menu is owned by the switcher and rebuilt from the children.) 
- Each effect’s **exposed** `fxCore` parameters (ColorType/Mode, Color, DotSize, etc.) appear in your FX panel because of the `expose_params` table (or `Ui*` naming).  

### Notes

- Defaults vs current values: for a per‑instance “personality”, set the **custom parameter defaults** on `PoseEffect_Dots2/fxCore`. If you only change current values, they’ll work—but defaults are what you want if you later duplicate again.
- If you later want friendlier labels in the menu, you can keep using OP names (simple), or introduce a small mapping table/labeling scheme in your switcher. The quick path today is the OP name (what you asked for).

That’s it—copy, rename, wire, rebuild menu, and set defaults. You’ll end up with two independent Dots entries, each with its own look and its own UI controls.

