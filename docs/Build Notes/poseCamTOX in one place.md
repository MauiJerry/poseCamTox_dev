# poseCamTOX in one place 

Got it — I went through your attached specs and pulled together the **exact external files** (TD Python callbacks + CSV/JSON) those COMPs expect, plus the **COMP list**. Everything below is ready to drop into your repo; the code matches the contracts in your docs and keeps all logic external to the .toe/.tox as specified.

------

# What to include (one place)

## TouchDesigner COMPs you’ll build/export

- **PoseCam.tox** — OSC In DAT + Script CHOP “fan‑out”. Uses `td/scripts/pose_fanout.py`.
- **PersonRouter.tox** — Active/All/Per‑person outputs, maskable. Uses `td/scripts/active_person.py` and CSV masks.
- **efx_switcher.tox** — hosts pluggable effects (hands/skeleton/…). Uses `td/scripts/toggle_cooking.py`.
- **ui_panel.tox** — operator UI + PoseCamPC remote + show‑control mapping. Uses `td/scripts/pe_posecam.py`, `td/scripts/osc_map.py`; optional in‑panel help markdown.

> Effects (optional examples): **efx_hands.tox**, **efx_skeleton.tox**; these use the CHOP channels emitted upstream and (for skeleton) `td/data/skeleton_edges.csv`.

------

# External code (place under `td/scripts/`)

> **Hook these via each Text DAT’s “File” parameter** (don’t embed) — that’s the pattern your docs call for.

### `td/scripts/pose_fanout.py` — OSC bundle → CHOP channels (PoseCam)

```python
# Script CHOP callbacks — PoseCam bundle → named channels
# Matches your bundle (/pose/p{pid}/{lid} [x y z [(v)]), also accepts legacy /p{pid}/{name}
# Source: consolidated from your Step-by-Step Guide (8/17/2025)

LANDMARK_NAMES = [
 'head','mp_eye_inner_l','eye_l','mp_eye_outer_l',
 'mp_eye_inner_r','eye_r','mp_eye_outer_e','mp_ear_l','mp_ear_r',
 'mp_mouth_l','mp_mouth_r','shoulder_l','shoulder_r',
 'elbow_l','elbow_r','wrist_l','wrist_r',
 'mp_pinky_l','mp_pinky_r','handtip_l','handtip_r',
 'thumb_l','thumb_r','hip_l','hip_r',
 'knee_l','knee_r','ankle_l','ankle_r',
 'mp_heel_l','mp_heel_r','foot_l','foot_r'
]
ID_TO_NAME = {i: n for i, n in enumerate(LANDMARK_NAMES)}

def _float(dat, r, name, idx):
    return float(dat[r, name].val) if name in dat.colNames else float(dat[r, idx].val)

def _parse_addr(addr):
    # Returns (pid:int, lname:str|None, lid:int|None)
    if not addr or addr[0] != '/': return (None, None, None)
    parts = addr.strip('/').split('/')
    if len(parts) == 3 and parts[0] == 'pose' and parts[1].startswith('p'):
        try: return (int(parts[1][1:]), None, int(parts[2]))
        except: return (None, None, None)
    if len(parts) == 2 and parts[0].startswith('p'):
        try: return (int(parts[0][1:]), parts[1], None)
        except: return (None, None, None)
    return (None, None, None)

def onCook(scriptOp):
    d = op('oscin1'); scriptOp.clear()
    if d is None or d.numRows <= 1:
        scriptOp.appendChan('pose_n_people')[0] = 0.0
        scriptOp.appendChan('pose_ts_ms')[0] = absTime.frame * (1000.0 / me.time.rate)
        return

    latest = {}   # (pid,lname) → (x,y,z,vis)
    present = set()

    for r in range(d.numRows - 1, 0, -1):
        addr = d[r, 'address'].val if 'address' in d.colNames else d[r, 0].val
        pid, lname, lid = _parse_addr(addr)
        if pid is None: continue
        try:
            x = _float(d, r, 'arg1', 2); y = _float(d, r, 'arg2', 3); z = _float(d, r, 'arg3', 4)
            vis = _float(d, r, 'arg4', 5) if ('arg4' in d.colNames or d.numCols > 5) else None
        except:
            continue
        if lname is None and lid is not None:
            lname = ID_TO_NAME.get(lid, f"id_{lid:02d}")
        if not lname: continue
        key = (pid, lname)
        if key not in latest:
            latest[key] = (x, y, z, vis)
            present.add(pid)

    for pid, lname in sorted(latest.keys()):
        x, y, z, vis = latest[(pid, lname)]
        scriptOp.appendChan(f"p{pid}_{lname}_x")[0] = x
        scriptOp.appendChan(f"p{pid}_{lname}_y")[0] = y
        scriptOp.appendChan(f"p{pid}_{lname}_z")[0] = z
        if vis is not None:
            scriptOp.appendChan(f"p{pid}_{lname}_v")[0] = vis

    for pid in sorted(present):
        scriptOp.appendChan(f"p{pid}_present")[0] = 1.0

    scriptOp.appendChan('pose_n_people')[0] = float(len(present))
    scriptOp.appendChan('pose_ts_ms')[0] = absTime.frame * (1000.0 / me.time.rate)
    return
```

(Design and bundle shape are straight from your “Step‑by‑Step” doc.)

### `td/scripts/active_person.py` — choose the active person (PersonRouter)

```python
# Watches present persons and selects active PID based on PersonMode/PersonID

def onValueChange(channel, sampleIndex, val, prev):
    router = op('..')
    present = []
    for c in op('present_sel').chans:
        if c.val >= 0.5:
            # "p2_present" → pid=2
            n = c.name
            pid = int(n[1:n.find('_')])
            present.append(pid)

    pid = -1
    if present:
        mode = router.par.Personmode.eval()
        if mode == 'Specific':
            want = int(router.par.Personid.eval())
            pid = min(present, key=lambda p: abs(p - want))
        elif mode == 'Closest':
            # TODO: replace with distance metric if available downstream
            pid = min(present)
        elif mode == 'Highestscore':
            # TODO: replace with score channel if provided
            pid = max(present)

    op('active_pid')['v0'] = pid
    return
```

(Exactly the routing behavior described.)

### `td/scripts/toggle_cooking.py` — only the active effect cooks

```python
# Toggle allowCooking for effect COMPs under your Effects container

def onValueChange(par, prev):
    active = int(par.eval())
    names = ['efx_hands', 'efx_skeleton', 'efx_face']  # keep in sync with your layout
    base = op('/project1/VIEW/ui_efx/Effects')         # make this a String custom par if you prefer
    for i, name in enumerate(names):
        comp = base.op(name)
        if comp is not None:
            live_bypass = hasattr(comp.par, 'Live') and bool(comp.par.Live.eval())
            comp.allowCooking = (i == active) or live_bypass
    return
```

(From your spec; path can be parameterized.)

### `td/scripts/pe_posecam.py` — drive PoseCamPC over OSC (ui_panel)

```python
# Send OSC control to PoseCamPC when UI parameters change

def onValueChange(par, prev):
    o = op('../osc_posecam_out')
    n = par.name.lower()
    if n == 'start':       o.sendOSC('/posecam/start', [1])
    elif n == 'stop':      o.sendOSC('/posecam/stop', [0])
    elif n in ('destip','destport'):
        ip   = parent().par.Destip.eval()
        port = int(parent().par.Destport)
        o.sendOSC('/posecam/set/dest', [ip, port])
    elif n == 'mode':      o.sendOSC('/posecam/set/mode',   [par.eval()])
    elif n == 'source':    o.sendOSC('/posecam/set/source', [par.eval()])
    elif n == 'loop':      o.sendOSC('/posecam/set/loop',   [int(par.eval())])
    return
```

(Directly from your `ui_panel.tox` spec.)

### `td/scripts/osc_map.py` — show‑control (OSC) → UI parameters (ui_panel)

```python
# Map show-control OSC to ui_panel custom parameters

def onReceiveOSC(dat, rowIndex, message, bytes, timeStamp, address, args, peer):
    ui = parent()
    if address == '/show/efx/select':
        ui.par.Activeeffect = int(args[0])
    elif address == '/show/efx/next':
        ui.par.Activeeffect = int(ui.par.Activeeffect) + 1
    elif address == '/show/fader':
        ui.par.Fader = float(args[0])
    elif address == '/show/person/id':
        ui.par.Personid = int(args[0])
    elif address == '/show/mask':
        ui.par.Mask = str(args[0])
    elif address == '/show/posecam/start':
        ui.par.Start.pulse()
    elif address == '/show/posecam/stop':
        ui.par.Stop.pulse()
    elif address == '/show/blackout':
        ui.par.Blackout = int(args[0])
    return
```

(Again, straight from your spec.)

### (Optional) `td/scripts/efx_points_sop.py` — points from CHOP (hands/dots)

```python
# Build a SOP of points at selected landmark channels from incoming CHOP

def onCook(scriptOp):
    ch = op('in_chop')
    if not ch or ch.numChans == 0:
        scriptOp.clear(); return

    # Expect channels like p1_*_x/y/z; pick a mask from a DAT if present
    mask = op('mask_table') if op('mask_table') else None
    names = set([r[0].val for r in mask.rows()]) if mask else None

    scriptOp.clear()
    pts = []
    for cx in ch.chans:
        if not cx.name.endswith('_x'): continue
        base = cx.name[:-2]  # strip "_x"
        cy = ch[base + 'y'] if base + 'y' in ch else None
        cz = ch[base + 'z'] if base + 'z' in ch else None
        lname = base.split('_', 1)[1] if '_' in base else base
        if names and lname not in names: continue
        x = cx.eval(); y = cy.eval() if cy else 0.0; z = cz.eval() if cz else 0.0
        pts.append((x, y, z))

    for p in pts:
        scriptOp.appendPoint(p)
    return
```

(Thin utility to visualize landmarks as points — pairs well with `masks_hands.csv` from your structure.)

### (Optional) `td/scripts/efx_lines_sop.py` — skeleton lines from CSV edges

```python
# Create poly lines between landmark pairs defined in td/data/skeleton_edges.csv

def onCook(scriptOp):
    ch = op('in_chop'); edges = op('skeleton_edges')
    scriptOp.clear()
    if not ch or not edges or edges.numRows < 2:
        return

    # Build a quick name → (x,y,z) lookup for person 1
    get = lambda a: ch[a].eval() if a in ch else None
    pos = {}
    for c in ch.chans:
        if c.name.startswith('p1_') and (c.name.endswith('_x') or c.name.endswith('_y') or c.name.endswith('_z')):
            base = c.name[:-2]
            if base not in pos:
                x = get(base + 'x'); y = get(base + 'y'); z = get(base + 'z')
                if x is not None and y is not None and z is not None:
                    pos[base.replace('p1_', '')] = (x, y, z)

    # Edges CSV has headers: a,b (landmark names)
    for r in range(1, edges.numRows):
        a = edges[r, 'a'].val; b = edges[r, 'b'].val
        pa = pos.get(a); pb = pos.get(b)
        if not pa or not pb: continue
        i0 = scriptOp.appendPoint(pa); i1 = scriptOp.appendPoint(pb)
        prim = scriptOp.appendPoly(2, closed=False, addPoints=False)
        prim[0].point = i0; prim[1].point = i1
    return
```

------

# External data files (place under `td/data/`)

### `td/data/masks_hands.csv`

```csv
name
handtip_l
handtip_r
thumb_l
thumb_r
mp_pinky_l
mp_pinky_r
wrist_l
wrist_r
```

(Referenced in your TD data lists for masks.)

### `td/data/masks_basicpose.csv`

```csv
name
head
shoulder_l
shoulder_r
hip_l
hip_r
knee_l
knee_r
ankle_l
ankle_r
```

(“Basic Pose” example mask as suggested in the step‑by‑step.)

### `td/data/skeleton_edges.csv`

```csv
a,b
shoulder_l,shoulder_r
shoulder_l,elbow_l
elbow_l,wrist_l
shoulder_r,elbow_r
elbow_r,wrist_r
hip_l,hip_r
hip_l,knee_l
knee_l,ankle_l
hip_r,knee_r
knee_r,ankle_r
shoulder_l,hip_l
shoulder_r,hip_r
```

(Used by `efx_lines_sop.py` / skeleton effect.)

### `td/data/landmark_names.csv`

```csv
id,name
0,head
1,mp_eye_inner_l
2,eye_l
3,mp_eye_outer_l
4,mp_eye_inner_r
5,eye_r
6,mp_eye_outer_e
7,mp_ear_l
8,mp_ear_r
9,mp_mouth_l
10,mp_mouth_r
11,shoulder_l
12,shoulder_r
13,elbow_l
14,elbow_r
15,wrist_l
16,wrist_r
17,mp_pinky_l
18,mp_pinky_r
19,handtip_l
20,handtip_r
21,thumb_l
22,thumb_r
23,hip_l
24,hip_r
25,knee_l
26,knee_r
27,ankle_l
28,ankle_r
29,mp_heel_l
30,mp_heel_r
31,foot_l
32,foot_r
```

(Exactly the list used by your Python senders; handy for lookups in TD.)

### (Optional) `td/ui/osc_map.csv`

```csv
address,param
/show/efx/select,Activeeffect
/show/fader,Fader
/show/person/id,Personid
/show/mask,Mask
/show/blackout,Blackout
/show/posecam/start,Start
/show/posecam/stop,Stop
```

(If you ever want a data‑driven mapping instead of hard‑coded `osc_map.py`.)

### (Optional) `docs/UI_README.md`

Short in‑panel help your spec calls out; point a Text TOP at this.

------

# Wiring quick notes (so the COMPs find these files)

- **PoseCam.tox**
  - `oscin1` (OSC In DAT) → `poseFanout` (Script CHOP, File=`td/scripts/pose_fanout.py`) → `pose_out` (Null CHOP, Cook Type=Selective).
- **PersonRouter.tox**
  - `in1` (CHOP In) from PoseCam/pose_out → `present_sel` (Select `p*_present`) → **CHOP Execute DAT** (File=`td/scripts/active_person.py`) updating `active_pid` → `active_sel` (Select `p{pid}_*`). Optional Replicator for per‑person outs.
- **efx_switcher.tox**
  - Holds `efx_hands`, `efx_skeleton`, … + Switch TOP/CHOP. Param Exec DAT (File=`td/scripts/toggle_cooking.py`) watching UI’s ActiveEffect.
- **ui_panel.tox**
  - Custom pars per your spec; `osc_posecam_out` (OSC Out DAT) bound to DestIP/DestPort; Param Exec DAT (File=`td/scripts/pe_posecam.py`); `map_osc_in` (OSC In DAT, Callbacks=`td/scripts/osc_map.py`).

------

# Why these files / addresses

- The **OSC contract** (`/pose/p{pid}/{lid}` with `[x y z (v)]`) + legacy named variant is the “high‑level contract” in your repo structure plan; the fan‑out script adheres to that so the same PoseCamPC can drive all COMPs.
- `ui_panel.tox`’s PoseCamPC control endpoints match your spec (`/posecam/start`, `/posecam/set/*`, etc.).

------

If you want, I can also spit these out as real files in a `td/` folder you can download as a ready-made starter pack; but the code above is everything your **PoseCam**, **Fanout**, **PersonRouter**, **UI**, and sample **EFX** need, including the external CSVs your docs call for.

---

### Update accepted. Here’s the exact code + files you asked for

You said: **use `poseoscIn1`** (not `oscin1`) and **load the landmark id↔name map from a separate DAT that reads a CSV** under `/config` or `/data`. Below is a drop‑in `pose_fanout.py` that does exactly that, followed by the CSV and the TD wiring notes.

------

### `td/scripts/pose_fanout.py` (uses `poseoscIn1` + external landmark map DAT)

> Place this on a **Script CHOP** in your PoseCam COMP. It expects:
>
> - an **OSC In DAT** named `poseoscIn1`
> - a **Table DAT** named `landmark_map` with headers `id,name` and its **File** parameter pointing to your CSV (e.g., `./data/landmark_names.csv` or `./config/landmark_names.csv`)
>    These patterns (externalizing code/data) are straight from your specs.  

```python
# td/scripts/pose_fanout.py
# Fan-out PoseCam OSC bundle rows → CHOP channels, using an external landmark map DAT.
# Requirements inside the PoseCam COMP:
#   - OSC In DAT named: poseoscIn1
#   - Table DAT named: landmark_map   (headers: id,name; File -> ./data/landmark_names.csv or ./config/landmark_names.csv)

def _resolve_landmark_map():
    """Return two dicts: id->name, name->id from the landmark_map Table DAT."""
    m = op('landmark_map')
    id2name, name2id = {}, {}
    if m is None or m.numRows < 2:
        # Final fallback: create an empty mapping; channels will use id_XX for unknowns.
        return id2name, name2id

    # Try header names; if absent, assume two columns
    try:
        id_col = m.col('id').index
        name_col = m.col('name').index
    except Exception:
        id_col, name_col = 0, 1

    for r in range(1, m.numRows):
        try:
            lid = int(m[r, id_col].val)
            lname = m[r, name_col].val.strip()
            if lname:
                id2name[lid] = lname
                name2id[lname] = lid
        except Exception:
            continue
    return id2name, name2id

def _float(dat, r, name, idx):
    # Read arg as float via named or positional column
    return float(dat[r, name].val) if name in dat.colNames else float(dat[r, idx].val)

def _parse_addr(addr):
    """
    Return (pid:int, lname:str|None, lid:int|None).
    Supports:
      /pose/p{pid}/{lid}         (bundle numeric ids)
      /p{pid}/{landmark_name}    (legacy named)
    """
    if not addr or addr[0] != '/':
        return (None, None, None)
    parts = addr.strip('/').split('/')
    # bundle: /pose/p2/17
    if len(parts) == 3 and parts[0] == 'pose' and parts[1].startswith('p'):
        try:
            return (int(parts[1][1:]), None, int(parts[2]))
        except Exception:
            return (None, None, None)
    # legacy: /p2/wrist_l
    if len(parts) == 2 and parts[0].startswith('p'):
        try:
            return (int(parts[0][1:]), parts[1], None)
        except Exception:
            return (None, None, None)
    return (None, None, None)

def onCook(scriptOp):
    d = op('poseoscIn1')  # ← your requested name
    scriptOp.clear()

    if d is None or d.numRows <= 1:
        scriptOp.appendChan('pose_n_people')[0] = 0.0
        scriptOp.appendChan('pose_ts_ms')[0] = absTime.frame * (1000.0 / me.time.rate)
        return

    # Load id<->name mapping from external Table DAT
    ID_TO_NAME, NAME_TO_ID = _resolve_landmark_map()

    latest = {}      # (pid,lname) -> (x,y,z,vis)
    present = set()  # {pid}

    # newest→oldest; keep the latest message per (pid,lname)
    for r in range(d.numRows - 1, 0, -1):
        addr = d[r, 'address'].val if 'address' in d.colNames else d[r, 0].val
        pid, lname, lid = _parse_addr(addr)
        if pid is None:
            continue
        try:
            x = _float(d, r, 'arg1', 2)
            y = _float(d, r, 'arg2', 3)
            z = _float(d, r, 'arg3', 4)
            vis = _float(d, r, 'arg4', 5) if ('arg4' in d.colNames or d.numCols > 5) else None
        except Exception:
            continue

        # Normalize name
        if lname is None and lid is not None:
            lname = ID_TO_NAME.get(lid, f"id_{lid:02d}")
        elif lname is not None and lid is None:
            # If a name is provided, we can optionally sanity-map back to id
            lid = NAME_TO_ID.get(lname, None)

        if not lname:
            continue

        key = (pid, lname)
        if key not in latest:
            latest[key] = (x, y, z, vis)
            present.add(pid)

    # Publish channels
    for pid, lname in sorted(latest.keys()):
        x, y, z, vis = latest[(pid, lname)]
        scriptOp.appendChan(f"p{pid}_{lname}_x")[0] = x
        scriptOp.appendChan(f"p{pid}_{lname}_y")[0] = y
        scriptOp.appendChan(f"p{pid}_{lname}_z")[0] = z
        if vis is not None:
            scriptOp.appendChan(f"p{pid}_{lname}_v")[0] = vis

    for pid in sorted(present):
        scriptOp.appendChan(f"p{pid}_present")[0] = 1.0

    scriptOp.appendChan('pose_n_people')[0] = float(len(present))
    scriptOp.appendChan('pose_ts_ms')[0] = absTime.frame * (1000.0 / me.time.rate)
    return
```

Why this structure:

- **Externalized code & data**: matches your TD practice for maintainability and reuse.  
- **Bundle + legacy addressing** both supported per your contract. 

------

### `td/data/landmark_names.csv` (external file the `landmark_map` DAT loads)

Save this as `./data/landmark_names.csv` (or `./config/landmark_names.csv`) and set the **File** parameter of the `landmark_map` Table DAT to point at it. The Step‑by‑Step and design docs show this exact nameset for MediaPipe Pose (33 points).  

```csv
id,name
0,head
1,mp_eye_inner_l
2,eye_l
3,mp_eye_outer_l
4,mp_eye_inner_r
5,eye_r
6,mp_eye_outer_e
7,mp_ear_l
8,mp_ear_r
9,mp_mouth_l
10,mp_mouth_r
11,shoulder_l
12,shoulder_r
13,elbow_l
14,elbow_r
15,wrist_l
16,wrist_r
17,mp_pinky_l
18,mp_pinky_r
19,handtip_l
20,handtip_r
21,thumb_l
22,thumb_r
23,hip_l
24,hip_r
25,knee_l
26,knee_r
27,ankle_l
28,ankle_r
29,mp_heel_l
30,mp_heel_r
31,foot_l
32,foot_r
```

------

### TouchDesigner wiring (minimal, using your naming)

1. **Inside `PoseCam` COMP**

- **OSC In DAT** named `poseoscIn1` (port = PoseCamPC’s send port).
- **Table DAT** named `landmark_map` with **File** → `./data/landmark_names.csv` (or `./config/...`).
- **Script CHOP** named e.g. `poseFanout` with **Callbacks** → `td/scripts/pose_fanout.py`.
- **Null CHOP** `pose_out` (Cook Type = Selective).
   This aligns with your guide and repo structure notes.  

1. **Downstream** (unchanged by this rename):

- `PersonRouter` consumes `pose_out`, supports Specific/Closest/HighestScore per your docs. 
- `ui_panel` drives router & PoseCamPC control, all scripts externalized. 

------

### Where to put the files (one place)

```
poseTDtox/
├─ td/
│  ├─ scripts/
│  │  └─ pose_fanout.py
│  ├─ data/
│  │  └─ landmark_names.csv
│  └─ tox/
│     └─ PoseCam.tox
└─ docs/
   └─ TD_README.md
```

(Folder layout follows the plan & “external files via File parameter” pattern.)  

------

If you also want the **PersonRouter** mask CSVs (hands/basic) and the skeleton edges CSV wired to effects, I can drop those here next, but the change you requested—**rename to `poseoscIn1`** + **landmark map loaded from a DAT reading a CSV**—is fully implemented above.