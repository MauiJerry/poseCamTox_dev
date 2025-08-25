# PoseEffect_Master update for canvas

actions to be done 8.22.2025, after we implement the Meta channel handling from PoseCamPC

### Yes — make `PoseEffect_MASTER` own the canvas + defaults, and **bind** them both up (to `PoseEfxSwitch`) and down (into each `fxCore`)

Below is a clean, TouchDesigner‑friendly pattern you can drop in now while you still have few effects. It keeps everything resolution‑independent but lets any effect get pixel‑true sizes when a camera/NDI meta stream is present.

------

## 1) Add canvas + meta toggles on `PoseEffect_MASTER`

**Where:** open your clone master `PoseEffect_MASTER` COMP (the template all `PoseEffect_*` clone from).

**Actions (TD UI):**

1. RMB the COMP ▸ **Customize Component…** (Parameter Dialog).
2. **+** add a new page: `Canvas`.
3. Add these custom parameters:
   - `Canvasw` (Int, default `1280`)
   - `Canvash` (Int, default `720`)
   - `Usemeta` (Toggle, default `On`) – “Use incoming image_width/height when available”
   - `Keepaspect` (Toggle, default `On`)
   - `Aspect` (Float, **read‑only**) with expression: `me.par.Canvasw / me.par.Canvash if me.par.Canvash else 1`
   - (optional) `Dotsizepx` (Float, default `6`) and `Linewidthpx` (Float) — common pixel‑scale knobs many effects will share.

> Tip: mark `Aspect` “read only” by disabling “Enable” and leaving the expression.

------

## 2) Bind those defaults **up** to the parent `PoseEfxSwitch` (so the UI can expose one global set)

This gives you a single “Default Canvas” at the switcher, while still allowing per‑effect overrides by breaking the bind locally.

**On `PoseEfxSwitch`:**

1. RMB ▸ **Customize Component…**
2. Add page `Defaults`, with:
   - `Defaultcanvasw` (Int `1280`)
   - `Defaultcanvash` (Int `720`)
   - `Defaultdotsizepx` (Float)
   - `Defaultlinewidthpx` (Float)

**Create the binds (two‑way, not expressions):**

- Go back into `PoseEffect_MASTER` ▸ `Canvas` page.
- For `Canvasw`: RMB the parameter ▸ **Bind…** ▸ choose **Operator:** `../..` (your `PoseEfxSwitch`), **Parameter:** `Defaultcanvasw`, OK.
- Repeat for `Canvash` → `Defaultcanvash`, `Dotsizepx` → `Defaultdotsizepx`, etc.

Now changing the switcher defaults ripples to every effect using the clone master. You can still break a single instance’s bind if it needs a custom canvas.

------

## 3) Feed meta (image_width/height) in as a CHOP and **mux** with the fallback

Inside `PoseEffect_MASTER` create a small “meta hub” the `fxCore` can read:

**Inside `PoseEffect_MASTER`:**

1. Drop **CHOP In** `meta_in` (index 1). This will be wired from your `/PoseMeta` CHOP that carries `image_width`, `image_height` (and maybe `fps`).

2. Add **Constant CHOP** `meta_fallback` with channels:

   - `image_width` value: `parent().par.Canvasw`
   - `image_height` value: `parent().par.Canvash`

3. Add **Switch CHOP** `meta_mux`:

   - **Input 0** = `meta_fallback`

   - **Input 1** = `meta_in`

   - **Index** expression:

     ```
     1 if parent().par.Usemeta and len(op('meta_in').channels) >= 2 else 0
     ```

4. (Optional) **Math CHOP** `meta_derive` after `meta_mux` to compute `aspect_ratio` with “Combine CHOPs ▸ Expressions”:

   - Add a new channel `aspect_ratio` with expr: `ic(0,'image_width')/max(1,ic(0,'image_height'))`

Now any script/instancer inside `fxCore` can read `op('../meta_mux')['image_width'][0]` etc., and it will automatically fall back to your CanvasW/H when meta is missing or `Usemeta` is off.

------

## 4) Bind the `fxCore`’s **internal** defaults **down** from the master

Inside `PoseEffect_MASTER/fxCore` you likely have:

- A **Render TOP** (orthographic)
- A **Constant CHOP** that seeds sizes/params
- A **Script CHOP/TOP** or instancing path that converts UV→NDC and sizes things

**Do:**

- In the **Render TOP** ▸ **Common ▸ Resolution = Specify** and set:

  - **W**: `int(op('../meta_mux')['image_width'][0])`
  - **H**: `int(op('../meta_mux')['image_height'][0])`

- In the **Constant CHOP** that provides defaults (e.g., `fx_defaults`), for channels like `dotsize_ndc` compute from pixels using meta height:

  - `dotsize_ndc` value expression:

    ```
    parent().par.Dotsizepx * (2.0 / max(1, op('../meta_mux')['image_height'][0]))
    ```

  - Do similar for `linewidth_ndc`.

This keeps **positions in UV (0–1)** but converts to **NDC** and **pixel‑true sizes** per effect using current meta.

------

## 5) Make parameter exposure easy for the UI Builder

If you’re using an `expose_params` DAT/table in each effect:

- Add rows for `Canvasw`, `Canvash`, `Usemeta`, `Dotsizepx`, etc.
   That lets the auto‑UI (and OSC) discover and control them. Because they are **bound** to `PoseEfxSwitch` defaults, the ShowControl surface can tweak them globally, and any effect can still be overridden by breaking the bind.

------

## 6) Cloning details so this propagates cleanly

- Ensure all your `PoseEffect_*` instances have **Clone** = `PoseEffect_MASTER` and **Enable Cloning** checked.
- For operators inside that must retain local tweaks (e.g., a texture unique to an effect), set **Clone Immune = On** on those operators only.
- When you finish the master changes, **RMB `PoseEffect_MASTER` ▸ Reinit Network** to push the update through clones.

------

## 7) Aspect ratio — do we need an explicit channel?

Not strictly. If you carry **both** `image_width` and `image_height`, each effect can compute `aspect = w/h` on the fly. Having a precomputed `aspect_ratio` in the meta CHOP is a small convenience, not a requirement. I’d **keep meta as CHOP** (numeric, occasionally changing). Use a DAT for registries and menus; use CHOP for live numeric plumbing.

------

## 8) Optional: small helper extension to auto‑wire meta

If you routinely drop new `PoseEffect_*` into `/PoseEfxSwitch/effects`, add an extension on `PoseEffect_MASTER` that runs on create and auto‑connects the effect’s `meta_in` to a fixed path like `/PoseMeta/pose_meta_out` if present:

```python
# PoseEffect_MASTER/poseeffect_master_ext.py
class PoseEffectMasterExt:
    def __init__(self, ownerComp):
        self.owner = ownerComp

    def OnCreate(self):
        try:
            meta_src = op('/PoseMeta/pose_meta_out')
            meta_in  = self.owner.op('meta_in')
            if meta_src and meta_in and len(meta_in.inputs) == 0:
                meta_in.connect(meta_src)
        except Exception as e:
            debug(f'PoseEffectMasterExt.OnCreate: {e}')
```

Bind this to **Extensions** on the master (Promote off). Now new clones “just work.”

------

## 9) Summary of the data flow

- **Landmarks:** stay UV (0–1) into every effect.
- **Meta (W/H):** tiny CHOP, muxed with `CanvasW/H` on the master.
- **Sizing math:** per‑effect inside `fxCore` (UV→NDC, px→NDC scale).
- **Global control:** `PoseEfxSwitch.DefaultCanvasW/H` etc., **bound** to each effect via the master.
- **Local override:** break a bind on an effect instance if needed.

If you want, I can draft the exact custom‑parameter JSON block (for TD’s `par` template import) and a minimal `PoseEffect_MASTER` network diagram so you can paste and go.

---

# **JSON + NetworkDiagram**

Awesome—here’s a tight, drop‑in JSON spec plus a TD network diagram that wires “Canvas & Meta defaults” in **PoseEffect_MASTER**, exposes them up to **EfxSwitch**, and down to each **fxCore** via bound parameters.

# JSON spec (single source of truth)

Use this as `poseeffect_master_spec.json`. It defines what the master owns, what’s exposed to the UI/EfxSwitch, and how child fxCores consume it.

```json
{
  "component": "PoseEffect_MASTER",
  "version": "1.0",
  "defaults": {
    "canvas": {
      "width": 1280,
      "height": 720,
      "origin": "UV_0_1",          // UV_0_1 or NDC_-1_1
      "aspect_policy": "fit",       // fit | fill | stretch (advice for downstream)
      "pixel_density_hint": 1.0     // for FX that care about px semantics
    },
    "pose": {
      "landmark_set": "MediaPipe33",// matches sender
      "z_is": "confidence"          // confidence | depth
    }
  },
  "meta_stream": {
    "channels": [
      "image_width",
      "image_height",
      "frame_count",
      "num_persons",
      "timestamp",
      "timestamp_str"
    ],
    "source": "PoseCamPC/OSC bundle",
    "update_rate_hz": 30
  },
  "expose_to_parent": [
    // Bound up to EfxSwitch (so UI/ShowControl can read & set once)
    {"name": "CanvasW", "type": "int", "min": 64, "max": 8192, "default": 1280},
    {"name": "CanvasH", "type": "int", "min": 36, "max": 8192, "default": 720},
    {"name": "Origin",  "type": "menu", "items": ["UV_0_1","NDC_-1_1"], "default": "UV_0_1"},
    {"name": "LandmarkSet", "type": "menu", "items": ["MediaPipe33","COCO17"], "default": "MediaPipe33"},
    {"name": "DebugView", "type": "toggle", "default": false}
  ],
  "expose_to_fxCore": [
    // Bound down into each fxCore (readonly there—comes from master)
    {"name": "CanvasW", "bind": "../CanvasW"},
    {"name": "CanvasH", "bind": "../CanvasH"},
    {"name": "Origin",  "bind": "../Origin"},
    {"name": "LandmarkSet", "bind": "../LandmarkSet"},
    {"name": "DebugView", "bind": "../DebugView"}
  ],
  "fxCore_meta_input": {
    "optional_chop_in_1": ["image_width", "image_height"],
    "fallback_to": ["../CanvasW","../CanvasH"]
  },
  "osc_showcontrol": {
    "inbound": [
      "/pose2art/fx/param/CanvasW <int>",
      "/pose2art/fx/param/CanvasH <int>",
      "/pose2art/fx/param/Origin <string>",
      "/pose2art/fx/param/LandmarkSet <string>",
      "/pose2art/fx/param/DebugView <0|1>"
    ],
    "feedback": [
      "/pose2art/fx/param/CanvasW <int>",
      "/pose2art/fx/param/CanvasH <int>",
      "/pose2art/fx/param/Origin <string>",
      "/pose2art/fx/param/LandmarkSet <string>",
      "/pose2art/fx/param/DebugView <0|1>"
    ]
  }
}
```

Why this layout?

- We keep **landmarks in 0‑1 UV** by default and guarantee **pixel‑aware** output by also carrying **CanvasW/H** everywhere (either live meta or master fallback).
- fxCores get a consistent **meta_in** CHOP (optional) and otherwise read the **master’s CanvasW/H** parameters; their Script CHOPs convert UV→NDC and compute pixel sizing from CanvasH.
- EfxSwitch & ShowControl can treat **CanvasW/H/Origin** as global knobs, surfaced once.

# TD network diagram (w/ binding points)

This is the wiring that makes the JSON real. You can build it directly in TD.

```
/project1
 ├─ /PoseCamIn
 │    ├─ osc_pose   (OSC In DAT, pose bundles)
 │    ├─ fanout     (Script CHOP → channels: p1_head_x, ...)
 │    └─ metaDAT    (Select DAT → image_width/height rows)
 │
 ├─ /PersonRouter
 │    └─ out_skel   (single-person CHOP: head_x, head_y, head_z, ...)
 │
 ├─ /EfxSwitch
 │    ├─ inCHOP     (CHOP In  → from /PersonRouter/out_skel)
 │    ├─ inTOP      (TOP In   → optional camera/NDI)
 │    ├─ guardTOP   (Switch TOP → camera or red fallback)
 │    ├─ effects/
 │    │    ├─ PoseEffect_MASTER
 │    │    │    ├─ CanvasW/H, Origin, LandmarkSet, DebugView  [custom pars; THIS IS THE SOURCE]
 │    │    │    ├─ landmarkSelect (Base)      [filter → unprefixed *_x/y/z]
 │    │    │    ├─ fxCore (Base)              [CLONE IMMUNE]
 │    │    │    │    ├─ CHOP In (0) skeleton_in  ← ../landmarkSelect/outCHOP
 │    │    │    │    ├─ CHOP In (1) meta_in      ← /PoseCamIn/metaDAT (optional)
 │    │    │    │    ├─ meta_fallback (Constant CHOP: image_width/height = ../CanvasW/H)
 │    │    │    │    ├─ meta_mux (Switch CHOP: meta_in or fallback)
 │    │    │    │    ├─ landmark_to_instances (Script CHOP; UV→NDC, pixel scale)
 │    │    │    │    └─ out_color (TOP Out → pass-through by default)
 │    │    └─ PoseEffect_* (clones of MASTER; only fxCore differs)
 │    ├─ out_switch (Switch TOP ← PoseEffect_*/fxOut)
 │    └─ outTOP (TOP Out)
 │
 ├─ /UI
 │    └─ auto-panel bound to EfxSwitch+FX params
 │
 └─ /ShowControlIO
      ├─ osc_ctl (OSC In DAT; control)
      └─ osc_out (OSC Out DAT; feedback)
```

Key binding actions (TD editor steps)

1. In **PoseEffect_MASTER** (the clone source):

- Right‑click → **Customize Component…**; add custom pars: `CanvasW (Int)`, `CanvasH (Int)`, `Origin (Menu: UV_0_1|NDC_-1_1)`, `LandmarkSet (Menu)`, `DebugView (Toggle)`. Set defaults 1280×720 / UV_0_1.
- In `fxCore/meta_fallback` (Constant CHOP), add channels `image_width=$PAR("../CanvasW")` and `image_height=$PAR("../CanvasH")`. The `meta_mux` Switch chooses **meta_in** if connected, else fallback.
- In `fxCore/landmark_to_instances` Script CHOP, use CanvasH to convert “DotSize px → NDC scale” (already in the drop‑in code).

1. Bind **down** into each fxCore:

- For each `fxCore`, bind its local parameters back to the master:
  - `CanvasW.bindExpr = "op('..').par.CanvasW"`
  - `CanvasH.bindExpr = "op('..').par.CanvasH"`
  - `Origin.bindExpr  = "op('..').par.Origin"`
  - `LandmarkSet.bindExpr = "op('..').par.LandmarkSet"`
  - `DebugView.bindExpr = "op('..').par.DebugView"`
     This ensures all effects share the same canvas framing.

1. Surface **up** to **EfxSwitch/UI/ShowControl**:

- Add the same pars (`CanvasW/H`, `Origin`, etc.) on **EfxSwitch** if you want them on the switch; set those as **owners** for your **Parameter COMP** panel, or mirror them via a tiny extension that reads/writes the master’s values. The existing UI/OSC builder patterns auto‑expose any pars you include in the `expose_params` table (recommended).

1. fxCore input contract:

- **CHOP In (0)** = **single person** from PersonRouter (unprefixed names: `head_x`…).
- **CHOP In (1)** = **meta** (`image_width`, `image_height`) (optional). Script CHOP falls back to CanvasW/H.

1. UI & OSC discovery:

- Put a small `expose_params` table in each **fxCore** listing `Origin`, `CanvasW`, `CanvasH`, plus effect‑specific `Ui*` params. The provided **UI/OSC router** will pick them up and mirror to controllers.

# Notes on aspect ratio & scaling decisions

- Keep **landmarks in UV 0–1**; compute **pixel sizes** inside fxCore from **CanvasH**, so dot/line widths feel correct regardless of output res. This avoids double‑scaling and keeps math simple.
- If you later composite over a non‑matching background, scale the **final effect output** in the compositor (or use the `aspect_policy` hint) instead of re‑mapping the skeleton each time.

------

If you want, I can also generate a tiny `expose_params` starter table for `PoseEffect_MASTER/fxCore` (CanvasW/H/Origin/LandmarkSet/DebugView) and the **Script CHOP** block pre‑filled with the UV→NDC + pixel‑scale math used in Dots—it’s already compatible with this wiring.