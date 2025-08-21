# Build and EfxSwith COMP

this script has gotten out of date.

The LandmarkSelect Comp needs its ext and param

the ext are created using the rightClick Component Editor

v2 with chatgpt

going to be a v3 after i go back and make the SelectOnePerson COMP that strips the p#_ from all the channels, and names them id_name... actually, the 

awesome — let’s lock down the TD side so you can drop effects in, switch them cleanly, and keep inactive ones from cooking.

Below is a concise, build‑once pattern you can use across the example app. It matches your current plan (PoseCamIn → personRouter → N effects → Efx Switch → Out TOP) and the repo’s TD starter guidance (OSC→fan‑out→router→switchable effects) , plus the dev notes that call out `poseCamTox_Dev.toe`, `poseCamIn`, and `personRouter` as foundations for effects and an `efx_switch` comp next .

# 1) PoseEffect template (TOX)

## Interface contract (all PoseEffects follow this)

- **Inputs**
  - `CHOP In` (required): one person’s channels from `personRouter` (e.g. `p1_*`).
  - `TOP In` (optional): camera/NDI or background feed to composite over.
- **Outputs**
  - `TOP Out` (required): the effect’s final image (aka the TOP stream the switch will choose).
  - `CHOP Out` (optional): any diagnostics (fps, counts) if you want.
- **Pars (on the COMP)**
  - `Active` (pulse/Bool) – set by the switch; turn cooking on/off.
  - `Bypass Inactive` (Bool, default On) – if inactive, auto‑bypass the heavy subnetwork.
  - `LandmarkFilter` (Menu) – e.g. `All`, `Hands`, `Skeleton`, `Face`, `CustomCSV`.
  - `FilterCSV` (Str) – path like `data/markSelect_hands.csv` (used when `CustomCSV`).

This mirrors the “switchable effects” pattern from the starter guide and keeps effect internals trivial .

## Internal nodes (inside each PoseEffect COMP)

- `in1` (CHOP In), `in2` (TOP In)
- `landmarkSelect` (a small COMP, see §3) → feeds only the channels the effect needs.
- Your effect graph (TOPs/CHOPs/SOPs)
- `out1` (TOP Out)
- Optional `null_diag` (CHOP) for debug
- **Selective cooking**: On the PoseEffect COMP, set **Cook Type = Selective**. The switch will flip `allowCooking` so only the chosen effect runs. (TD cooks only the selected input of a Switch TOP; we still hard‑gate via `allowCooking` for safety in complex networks.)
- NOPE - this is wrong

## Extension (PoseEffectExt) — minimal on/off + filter hookup

Attach this as the COMP’s Extension (External .py file or DAT):

```python
# PoseEffectExt.py
class PoseEffectExt:
    def __init__(self, owner):
        self.owner = owner

    def SetActive(self, active: bool):
        # Hard cook gate for the whole effect
        self.owner.allowCooking = bool(active)
        # Optionally bypass an internal heavy subnetwork operator
        heavy = self.owner.op('fxCore')  # make fxCore a COMP/TOP you want bypassed
        if heavy:
            heavy.par.bypass = not active

    def ApplyFilter(self):
        mode = self.owner.par.Landmarkfilter.eval()  # menu
        table = None
        if mode in ('Hands', 'Skeleton', 'Face'):
            # use built‑in CSVs like data/markSelect_hands.csv
            name = mode.lower()
            table = self.owner.op('landmarkSelect/tableFromCSV')
            table.par.file = f"data/markSelect_{name}.csv"
        elif mode == 'Customcsv':
            table = self.owner.op('landmarkSelect/tableFromCSV')
            table.par.file = self.owner.par.Filtercsv.eval()

        sel = self.owner.op('landmarkSelect/selectCHOP')
        if table and sel:
            # rebuild channel pattern from CSV
            chans = [r[0].val for r in table.rows()[1:]]  # assumes header "chan"
            sel.par.channame = ' '.join(chans)
```

> Tip: keep `fxCore` as the sole heavy cooking branch. Lightweight plumbing (Selects, Nulls) can stay live without cost.

# 2) Efx Switch component

A small manager COMP that owns N PoseEffects and a master Switch TOP.

## Inputs/Outputs

- **CHOP In**: the routed person channels from `personRouter` (one person) — aligns with the plan in your notes and starter guide .
- **TOP In (optional)**: background/camera feed to all effects.
- **TOP Out**: the selected effect’s `TOP Out`.

## Internal wiring

- `in1` (CHOP) → fan to each `PoseEffectX/in1`
- `in2` (TOP)  → fan to each `PoseEffectX/in2`
- Each PoseEffect outputs a TOP to `switch1` inputs (index 0…N‑1)
- `switch1` → `out1` (TOP)

Set `switch1` → **Index** bound to a custom parameter `ActiveIndex` (0…N‑1). Switch TOP will only cook the selected input; combined with each effect’s `allowCooking` gate, off‑effects stay cold.

## Parameters on EfxSwitch

- `ActiveIndex` (Int)
- `EnableUI` (Bool, optional)
- For convenience, an enum menu `ActiveName` (Dots, Skeleton, HandEmitters, TexSkel) that drives `ActiveIndex`.

## Extension (EfxSwitchExt)

Attach this to the EfxSwitch COMP:

```python
# EfxSwitchExt.py
class EfxSwitchExt:
    def __init__(self, owner):
        self.owner = owner
        # collect effect COMPs once
        self.effects = [c for c in owner.findChildren(type=COMP, depth=1) if c.tags and 'PoseEffect' in c.tags]

    def _sync_active(self):
        idx = int(self.owner.par.Activeindex)
        for i, fx in enumerate(self.effects):
            try:
                fx.par.Active.pulse() if i == idx else None
                fxext = fx.ext.PoseEffectExt
                fxext.SetActive(i == idx)
                fxext.ApplyFilter()  # optional: re-apply filter on activate
            except Exception as e:
                debug = self.owner.op('debug')
                if debug: debug.write(f"{fx.name}: {e}")

    def OnActiveIndexChange(self):
        self._sync_active()
```

Wire the `ActiveIndex` parameter’s value change callback to call `OnActiveIndexChange()`.

# 3) LandmarkSelect template (reusable sub‑COMP)

Two interchangeable styles, per your request:

### A) “Channel group filters (shared)” style

- A **Table DAT** with a single column `chan` listing fully‑qualified channel names (e.g., `p1_handtip_l_x`, `p1_handtip_r_y`, …).
- A **Select CHOP** reading from the PoseEffect’s `in1`, with `channame` expression built from the DAT (space‑separated list).
- Pros: dead simple and fast.
- Cons: you edit the list inside the toe unless you externalize.

### B) CSV‑driven (preferred for replication)

- Put named CSVs under **`/data`**, e.g.:
  - `data/markSelect_hands.csv`
  - `data/markSelect_skeleton.csv`
  - `data/markSelect_face.csv`
- **Format** (header + rows):

```
chan
p1_handtip_l_x
p1_handtip_l_y
p1_handtip_r_x
p1_handtip_r_y
```

- Sub‑COMP contents:
  - `tableFromCSV` (Table DAT) → `par.file` points to CSV.
  - `buildPattern` (Text DAT) — optional utility that converts rows to a pattern string.
  - `selectCHOP` (Select CHOP) with:
    - `op` → the upstream `in1` (PoseEffect’s CHOP In)
    - `channame` → Python: `' '.join([r[0].val for r in op('tableFromCSV').rows()[1:]])`

Your upstream OSC/ID naming (using Mediapipe’s 33 names) ensures these channel names exist; the repo’s detector mapping shows the canonical names like `handtip_l`, `thumb_r`, `shoulder_l`, etc., which is what you’ll see after your fan‑out step in TD .

# 4) Wiring it all together (step‑by‑step)

1. **Place the building blocks**

- Drop **`poseCamIn`** (your OSC→channels COMP) and **`personRouter`** (selects p1 / all) — these two already exist per your notes .
- Add **`efx_switch`** (this new manager COMP).
- Inside `efx_switch`, drop four **PoseEffect** instances (tag each with `PoseEffect`):
   `efx_dots`, `efx_skeleton`, `efx_handemit`, `efx_texskel`.

1. **Connect**

- `personRouter/out1 (CHOP)` → `efx_switch/in1`
- (Optional) your camera/NDI TOP → `efx_switch/in2`

1. **Fan inputs to all effects**

- Inside `efx_switch`, wire `in1` to each `efx_*/in1`, and `in2` to each `efx_*/in2`.

1. **Select output**

- Each `efx_*` provides a `TOP out1` → wire all to `switch1` inputs in order.
- `switch1` → `out1` (this is your **Out TOP**).

1. **Selective cooking**

- On each `efx_*` COMP: **Cook Type = Selective**.
- In `EfxSwitchExt.OnActiveIndexChange`, call `PoseEffectExt.SetActive(i == idx)`. This toggles `allowCooking` so only the selected effect runs.

1. **Filters**

- In each `efx_*`, keep a `landmarkSelect` sub‑COMP (CSV driven).
- Add a COMP menu param `LandmarkFilter` (All/Hands/Skeleton/Face/CustomCSV) and a `FilterCSV` path param.
- `PoseEffectExt.ApplyFilter()` sets `tableFromCSV.par.file` and rebuilds `selectCHOP.par.channame` accordingly.

# 5) First four PoseEffects (implementation tips)

All four consume the same filtered CHOP and (optionally) composite over the TOP input.

1. **Dots**
   - `landmarkSelect` → `null_land` → `Trail/Analyze` (optional) → `CHOP to SOP` (Points) → `Instancing` or `Point Sprite` → `Composite TOP` over `in2`.
   - Filter: `All` or a CSV listing the landmarks you want dotted.
2. **Simple Skeleton** (you already have lines logic in `osc_tubularTrim.toe`)
   - Use a fixed **Table DAT** of landmark index pairs for bones, then Build Lines (SOPs) or `Line MAT`/`Wireframe` in TOP space.
   - Filter: `Skeleton` CSV includes just the joints you’ll connect.
3. **Hand Emitters**
   - Filter: `Hands` CSV (hand tips + possibly thumbs).
   - `Select` → get `p1_handtip_l_*`, `p1_handtip_r_*` → map UV to pixel space → feed two emitter positions into your fluid/particle tox.
   - Composite result over `in2`.
4. **Texture Mapped Skeleton**
   - Use the skeleton line set as UV rails or map textures onto rectangles driven by limb vectors (shoulder→elbow, elbow→wrist).
   - Filter: `Skeleton` CSV.
   - This is heavier — make sure `fxCore` is what you bypass when inactive.

# 6) Packaging as TOX

- Make **PoseEffect.tox** (the template) with the interface, parameters, and extension but minimal visuals.
- Each concrete effect is a **Clone** of PoseEffect with its own `fxCore` inside.
- Make **EfxSwitch.tox** that expects:
  - `CHOP In` = personRouter output,
  - `TOP In` = background,
  - `TOP Out` = final composited image.

# 7) CSVs to ship in `/data`

- `markSelect_all.csv` (all channels)
- `markSelect_hands.csv`
- `markSelect_skeleton.csv`
- `markSelect_face.csv`
   Each with header `chan` and rows of channel names (e.g., `p1_handtip_l_x`). This aligns with the OSC/landmark naming coming from your detector map (`handtip_l`, `thumb_r`, `shoulder_l`, etc.) .

# 8) Why this works with your pipeline

- The architecture matches the repo’s recommended TD flow (bundle→OSC DAT→fan‑out→router→switchable effects) and keeps effects hot‑swappable and self‑contained .
- It plugs directly into the `poseCamTox_Dev.toe` work you noted (existing `poseCamIn` and `personRouter`, next up “efx_switch”) .

------

If you want, I can also draft the tiny TD **callbacks DATs** (parm change → call `EfxSwitchExt.OnActiveIndexChange`) and a **ready‑to‑paste CSV starter set** for `hands/skeleton/face`.