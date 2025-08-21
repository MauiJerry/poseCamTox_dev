PersonRouterCOMP README.md

### PersonRouter COMP — summary & implementation plan

**Goal:** take incoming OSC pose streams (one or more people) and publish clean, routable CHOP/DAT outputs per person (plus a selected “Primary”) for downstream effects. It also normalizes names, tracks activity/timeout, and exposes simple show‑control parameters.

------

### What it ingests / what it emits

- **Inputs**
  - **DAT In**: `poseInDAT` — rows of OSC messages from `poseoscIn1` (e.g., `/p1/handtip_l <u v conf>`, `/image-height`, `/numLandmarks`).
  - (Optional) **OSC In DAT**: `oscInDAT` inside for self‑contained testing; disabled by default.
- **Outputs**
  - **CHOP**: `Primary_OUT` — channels for a single chosen person (u, v, conf per landmark).
  - **CHOP**: `All_OUT` — channels for all active persons, namespaced by person (e.g., `p1:shoulder_l:u`).
  - **DAT**: `Persons_OUT` — table of current persons with last_seen, avg_conf, bbox, selection rank.
  - **DAT**: `FrameInfo_OUT` — image size, numLandmarks, timestamp.
  - **DAT**: `Landmarks_OUT` — normalized landmark list the router is using (joined from the name map).

------

### Custom parameters (on the COMP)

1. **Input**
   - **Source** (Menu): `External DAT` | `Internal OSC` (default External)
   - **DAT Path** (Str): `/project1/poseCamIn/poseoscIn1` (default)
   - **Address Prefix** (Str): `/p` (default)
2. **Routing**
   - **Mode** (Menu): `Primary Only` | `Primary + All` | `All Persons` (default `Primary + All`)
   - **Primary Selection** (Menu): `Auto-Closest` | `Auto-HighestConf` | `Fixed Person ID` (default `Auto-Closest`)
   - **Fixed Person ID** (Int): 1
   - **Max Persons** (Int): 6
   - **Min Confidence** (Float): 0.35
   - **Timeout (ms)** (Int): 500 (person removed if no updates)
3. **Smoothing**
   - **Enable Smoothing** (Toggle): off
   - **Lag (samples)** (Int): 5
4. **Landmark Map**
   - **Map DAT** (Str): `./config/landmarks_map.csv`
   - **Use Mediapipe 33** (Toggle): on (else use 17 set)
5. **Debug**
   - **Log Level** (Menu): `WARN|INFO|DEBUG` (default INFO)
   - **Show Missing Landmarks** (Toggle)

------

### Internal network (operators and wiring)

```
PersonRouter (base COMP)
├─ Input
│  ├─ In DAT         (poseInDAT)   <-- externally wired from poseoscIn1
│  └─ OSC In DAT     (oscInDAT)    <-- optional test input (Source=Internal)
│
├─ Config
│  ├─ Table DAT      (landmarksDAT)  loads ./config/landmarks_map.csv
│  └─ DAT Execute    (onLandmarksDAT) to trigger reindex on file reload
│
├─ Parse & State
│  ├─ Script DAT     (router_core.py)      # state, parsing, selection
│  ├─ DAT Execute    (onPoseDAT)           # reacts to new pose rows
│  └─ Table DAT      (personsStateDAT)     # person_id, last_seen, avg_conf, bbox
│
├─ Build CHOPs
│  ├─ Script CHOP    (allPersons_CHOP)     # creates channels for all persons
│  ├─ Filter CHOP    (smooth_ALL)          # optional smoothing gate
│  ├─ Select CHOP    (primary_SELECT)      # extracts current primary’s channels
│  ├─ Null CHOP      (All_OUT)             # exported output
│  └─ Null CHOP      (Primary_OUT)         # exported output
│
├─ Info & Debug
│  ├─ Text DAT       (routerLog)           # rolling logs
│  ├─ Table DAT      (frameInfoDAT)        # width,height,numLandmarks,timestamp
│  └─ Table DAT      (landmarks_OUT)       # resolved ordered landmark names
│
└─ Exports
   ├─ Out DAT        (Persons_OUT)
   ├─ Out DAT        (FrameInfo_OUT)
   └─ Out DAT        (Landmarks_OUT)
```

**Signals & flow**

- `onPoseDAT` watches the selected input DAT (`poseInDAT` or `oscInDAT`) for new rows.
- It calls functions in `router_core.py` to parse the OSC address/value(s), update person state, and stash latest landmark values in a per‑person cache (dict).
- `allPersons_CHOP.onCook` reads the cache and builds channels dynamically each cook:
  - **Channel naming:**
    - All persons: `p{pid}:{landmark}:{u|v|conf}` (e.g., `p1:shoulder_l:u`)
    - Primary (via Select): same base names without the `pN:` prefix (e.g., `shoulder_l:u`) for convenience.
- Optional smoothing (Filter CHOP) is inserted only when **Enable Smoothing** is on (driven by parameter pulse/script switch).

------

### Landmark map & external files

- **`./config/landmarks_map.csv`** (editable):

  ```
  index,name,alt_names,enabled
  0,head,mp_head,1
  1,mp_eye_inner_l,,1
  2,eye_l,,1
  ...
  31,foot_l,,1
  32,foot_r,,1
  ```

  - `index` is the canonical order used in outputs.
  - `name` must match what the sender uses (your python uses names like `handtip_l`, `shoulder_r`, etc.).
  - `alt_names` is a comma list the parser accepts as synonyms.
  - `enabled` lets you mask out unwanted points without code changes.

- (Optional) `./config/person_router_defaults.json` if you prefer saving parameter presets.

------

### Address formats supported

- **Per your sender(s)**:
  - Combined value message (preferred):
     `/p{pid}/{landmark} [u v conf]`
     Example from your code: `/p1/handtip_l 0.52 0.33 -0.12`
  - Frame info (optional):
     `/image-width N` `/image-height N` `/numLandmarks N`
- The parser is robust to minor variants (e.g., landmarks with `:` separators) by using the map’s `alt_names`.

------

### Selection & activity logic

- **Active persons** are tracked in memory with fields:
  - `last_seen_ms`, `avg_conf`, `num_points_seen`, `bbox_uv` (minU,minV,maxU,maxV), `streak`
- **Timeout** removes stale persons if `now - last_seen > Timeout`.
- **Primary selection** (evaluated each cook):
  - `Auto-Closest`: chooses person with the smallest screen‑space bbox diagonal (approx “closest”).
  - `Auto-HighestConf`: highest `avg_conf`.
  - `Fixed Person ID`: exact `pN`, if active; else fallback to next best per mode.

`personsStateDAT` mirrors this for UI/inspection.

------

### Script details (high level)

#### `onPoseDAT` (DAT Execute)

- **onTableChange / onRowChange**:
  - For each new row: parse address/value(s).
  - If `/image-*` or `/numLandmarks`, update `frameInfoDAT`.
  - If `/pN/landmark`, normalize `landmark` via `landmarksDAT` (name or alt_names), clamp/validate values.
  - Update person cache and `personsStateDAT` (last_seen, conf, bbox).
  - Mark a “dirty” flag (so Script CHOP knows to rebuild channels next cook).

#### `allPersons_CHOP` (Script CHOP)

- **onCook**:
  - Read the cache snapshot.
  - Drop timed‑out persons.
  - Build channel list:
    - For each active person up to **Max Persons**, for each **enabled** landmark:
      - Create/add `p{pid}:{name}:u`, `:v`, `:conf`.
  - If **Mode** contains Primary:
    - Compute primary by the selected policy and write to a python dict attribute for `primary_SELECT` to point at.
- Keep per‑channel values stable between frames when not updated (last value hold), unless a person times out (channels zeroed or removed—configurable; default: zero).

------

### Tables emitted

- **Persons_OUT** columns:
  - `person_id,last_seen_ms,age_ms,avg_conf,points,diag,primary_rank`
- **FrameInfo_OUT** columns:
  - `image_width,image_height,num_landmarks,timestamp_ms,fps_est`
- **Landmarks_OUT** columns:
  - `index,name,enabled`

------

### Minimal parsing rules (so it “just works” with your sender)

- Accept `/p\d+/(?P<name>[A-Za-z0-9_:-]+)` with 3 float args.
- Strip any `:u/:v/:tz` suffix and prefer the 3‑tuple flavor; if 1‑axis or split‑axis messages ever appear, fold them into the same store (kept for future‑proofing).
- Treat Mediapipe `lm.z` (confidence‑like) as `conf` directly, clamped to `[-5..+5] → [0..1]` (simple remap; adjustable if you prefer raw).

------

### UI/monitoring tips (inside the COMP)

- **routerLog**: last 200 lines with timestamped INFO/DEBUG lines.
- **State panel** (optional Panel COMP or Info CHOP) showing selected Primary, active count, FPS.
- **Bypass toggle** to freeze outputs (useful for show control).

------

### Testing checklist

1. Point `DAT Path` at your live `poseoscIn1` DAT. Confirm `FrameInfo_OUT` fills.
2. Confirm rows like `/p1/handtip_l` are parsed; `Persons_OUT` shows `p1`.
3. Enable **Mode=Primary + All**; verify `All_OUT` has `p1:*` channels and `Primary_OUT` has the unprefixed set.
4. Toggle **Enable Smoothing** and verify values become less jittery.
5. Simulate timeouts by pausing sender; person should drop after **Timeout (ms)**.
6. Swap the landmark CSV to a reduced set (e.g., only torso/arms) and confirm channel list shrinks accordingly.

------

### Notes tailored to your current sender code

- Your Python senders (e.g., `pose_PC_MediaPipe_loop.py`) already emit `/p1/{point_name} [u v z]` and `/image-*` messages, which this router expects.
- The landmark names in your code (`handtip_l`, `shoulder_l`, etc.) should be mirrored in `landmarks_map.csv`. Add `alt_names` if any legacy names differ.
- If later you push hand/face sub‑landmarks, you can extend the CSV with those; the router will pick them up without script changes.

------

