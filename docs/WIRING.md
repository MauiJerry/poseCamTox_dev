# WIRING

### PoseCam COMP
1) OSC In DAT: **poseoscIn1**
2) Table DAT: **landmark_map** → File: `td/data/landmark_names.csv`
3) Script CHOP: **poseFanout** → Callbacks: `td/scripts/pose_fanout.py`
4) Null CHOP: **pose_out** (Cook Type: Selective)

### PersonRouter COMP
- CHOP In: from PoseCam/pose_out
- Select CHOP: `p*_present` → CHOP Execute DAT (file: `td/scripts/active_person.py`) to write active PID into a Table DAT
- Use that PID to Select CHOP channels for the active person

### Effects
- Hands/points: Script SOP callback `td/scripts/efx_points_sop.py` with optional mask Table DAT reading `td/data/masks_hands.csv`
- Skeleton lines: Script SOP callback `td/scripts/efx_lines_sop.py` with Table DAT reading `td/data/skeleton_edges.csv`

### UI Panel
- OSC In DAT (Callbacks `td/scripts/osc_map.py`) handles /show/* control messages
