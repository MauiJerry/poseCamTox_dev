# PoseCamTox Starter Pack

This pack contains **externalized** TouchDesigner scripts and data files for the Pose2Art / PoseCam project.

Sorta: this project is under Very active development. Sometimes pushed to github, often only weekly.  Take everything you read with ton of salt as the docs are out of date and code in flux. (26aug2025)

## Contents

```
td/
  scripts/
    pose_fanout.py        # OSC DAT (poseoscIn1) → CHOP channels, uses landmark_map DAT
    active_person.py      # PersonRouter active PID selection
    toggle_cooking.py     # Only selected effect cooks
    osc_map.py            # Show-control OSC → UI parameters
    efx_points_sop.py     # Point cloud from landmark channels
    efx_lines_sop.py      # Skeleton lines from CSV edges
  data/
    landmark_names.csv    # id↔name used by pose_fanout (load with landmark_map DAT)
    masks_hands.csv       # example mask list
    masks_basicpose.csv   # example mask list
    skeleton_edges.csv    # edges for skeleton lines effect
  ui/
    osc_map.csv           # optional: data-driven OSC→param mapping
docs/
  WIRING.md               # how to wire COMPs
```

## PoseCam COMP wiring

- **OSC In DAT** named `poseoscIn1` (port = your PoseCamPC sender)
- **Table DAT** `landmark_map` → File: `td/data/landmark_names.csv`
- **Script CHOP** `poseFanout` → Callbacks: `td/scripts/pose_fanout.py`
- **Null CHOP** `pose_out` (Cook Type = Selective)

## PersonRouter (example)

- Input CHOP from `PoseCam/pose_out`
- Select `p*_present` → CHOP Execute DAT (file: `td/scripts/active_person.py`) updates `active_pid` Table DAT
- Use `active_pid` to Select CHOP channels for the chosen person

## Effects (examples)

- **Points**: Script SOP with `td/scripts/efx_points_sop.py`, CHOP In → mask Table DAT (optional)
- **Skeleton Lines**: Script SOP with `td/scripts/efx_lines_sop.py`, CHOP In → Table DAT reading `td/data/skeleton_edges.csv`

## UI Panel (show control)

- OSC In DAT (Callbacks: `td/scripts/osc_map.py`) to drive custom UI parameters from OSC
- Optional: drive from `td/ui/osc_map.csv` with a small DAT Execute if you prefer data-driven mapping
