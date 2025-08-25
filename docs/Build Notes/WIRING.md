# WIRING

this is old likely outdated documentation. initially created by ChatGPT for how to setup the PoseCamTox project.

### PoseCam COMP
1) OSC In DAT: **poseoscIn1**
2) Table DAT: **landmark_map** → File: `td/data/landmark_names.csv`
3) Script CHOP: **poseFanout** → Callbacks: `td/scripts/pose_fanout.py`
4) Null CHOP: **pose_out** (Cook Type: Selective)

---

Here’s exactly how to wire it and which parameters to set.

### Inside the PoseCam COMP

1. **OSC In DAT** → name it `poseoscIn1`.
    This receives `/p{pid}/{landmark}` (or `/pose/p{pid}/{lid}`) messages from PoseCamPC. 
2. **Table DAT** → name it `landmark_map`.
    Set **File** → `td/data/landmark_names.csv`. This is the id↔name map the script reads. 
3. **Script CHOP** → name it `poseFanout`.
   - Set **Callbacks DAT / File** → `td/scripts/pose_fanout.py`.
   - The script’s `onCook()` **reads** from `poseoscIn1` and `landmark_map` by operator name (no wire needed), then **creates CHOP channels** like `p1_wrist_l_x/y/z` plus `p{pid}_present`, `pose_n_people`, etc.   
4. **Null CHOP** → name it `pose_out`.
   - **Wire the output** of `poseFanout` → `pose_out`.
   - Set **Cook Type** = **Selective**.
   - Downstream COMPs (e.g., PersonRouter, effects) reference `PoseCam/pose_out`.  

### Visual sketch

```
[poseoscIn1] (OSC In DAT)       [landmark_map] (Table DAT, File=td/data/landmark_names.csv)
        │                                    (referenced by name from the script; no wire)
        ▼
[poseFanout] (Script CHOP, Callbacks=td/scripts/pose_fanout.py)
        │   (onCook() reads poseoscIn1 + landmark_map, emits CHOP channels)
        ▼
 [pose_out] (Null CHOP, Cook Type=Selective)
```

### Key points

- **No DAT-to-CHOP wire** is required for `poseoscIn1` or `landmark_map`; the Script CHOP **pulls them by name** (`op('poseoscIn1')`, `op('landmark_map')`) in `pose_fanout.py`. The **only physical wire** is **Script CHOP → Null CHOP**. 
- `landmark_map` must point at the CSV so ids map to names consistently (e.g., `…/wrist_l`). 

If you want, I can also add the two quick sanity bits people often forget:

- Set the Script CHOP’s **Time Slice** to match your network needs (usually off for frame-at-a-time bundles).
- Consider giving `pose_out` a short **Cue/Export prefix** to keep downstream Selects tidy (optional).

---



### PersonRouter COMP
- CHOP In: from PoseCam/pose_out
- Select CHOP: `p*_present` → CHOP Execute DAT (file: `td/scripts/active_person.py`) to write active PID into a Table DAT
- Use that PID to Select CHOP channels for the active person

### Effects
- Hands/points: Script SOP callback `td/scripts/efx_points_sop.py` with optional mask Table DAT reading `td/data/masks_hands.csv`
- Skeleton lines: Script SOP callback `td/scripts/efx_lines_sop.py` with Table DAT reading `td/data/skeleton_edges.csv`

### UI Panel
- OSC In DAT (Callbacks `td/scripts/osc_map.py`) handles /show/* control messages
