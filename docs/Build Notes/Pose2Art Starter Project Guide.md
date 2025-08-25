Here’s a clean **step-by-step developer guide** that summarizes the **latest Pose2Art plan and codebase** and sets it up as a reusable **TouchDesigner starter project (toe/tox)**.

------

# Pose2Art Starter Project Guide

This guide is for an **experienced software developer new to TouchDesigner (TD)**.
 It shows how to integrate PoseCam’s **OSC bundles** into TD, fan them out to channels, and route them into multiple **switchable effects**.

We’ll use **externalized Python files and annotations** so the TD project is self-documenting and extendable.

------

## 1. System Overview

- **PoseCam (Python side)**
  - Runs `pose_PC_MediaPipe.py` or `pose_PC_MediaPipe_ndi.py`.
  - Captures webcam/video frames, extracts pose landmarks via **MediaPipe**.
  - Sends OSC messages (bundles or singles) to TD.
  - Optional: streams original video over **NDI**.
- **TouchDesigner (TD side)**
  - **OSC In DAT** receives bundles (multi-person, multi-landmark).
  - **Script CHOP** parses and “fans out” messages into per-landmark channels.
  - **Person Router COMP** manages multi-person selection.
  - **Switch CHOP** routes active skeleton stream into an effect.
  - **Effect stubs (TOX)** process skeletons (hands, emitters, skeleton lines, etc.).

------

## 2. OSC Message Format

From `pose_PC_MediaPipe_ndi.py`:

```text
/p1/head    [x, y, z]
/p1/hand_l  [x, y, z]
/p1/hand_r  [x, y, z]
...
/p2/head    [x, y, z]
```

- Prefix = person (`p1`, `p2`, …).
- Landmark names come from `pose_id_to_name`.
- Arguments = `(u, v, z)` → normalized screen coords + confidence.

------

## 3. TD Architecture

```
[OSC In DAT]
     ↓
[Script CHOP: oscFanOut.py]
     ↓
[Person Router COMP]
     ↓
[Switch CHOP]
 ┌───────────┬───────────┬────────────┐
[efx_hand] [efx_skel] [efx_fluid] ...
```

------

## 4. Hybrid Parsing: Script CHOP

Instead of 100s of `Select DAT`s, we use **one Script CHOP** to fan out OSC rows into channels.

**oscFanOut.py (externalized Python, with inline comments):**

```python
# oscFanOut.py
# Fan out OSC In DAT messages into CHOP channels
# Each channel is named person_landmark_axis (e.g., p1_head_x)

def cook(scriptOP):
    # Clear existing channels
    scriptOP.clear()

    # Reference to the OSC In DAT in the same COMP
    oscDAT = op('osc_in_dat')

    for row in oscDAT.rows()[1:]:  # skip header row
        address = row[0].val   # OSC address (e.g., "/p1/head")
        args = row[2:]         # type tags + values

        parts = address.strip('/').split('/')
        if len(parts) < 2: 
            continue
        person, landmark = parts[0], parts[1]

        # Expect args [x, y, z]
        if len(args) >= 3:
            x, y, z = [float(a.val) for a in args[:3]]

            # Create channels dynamically
            scriptOP.appendChan(f"{person}_{landmark}_x")[0] = x
            scriptOP.appendChan(f"{person}_{landmark}_y")[0] = y
            scriptOP.appendChan(f"{person}_{landmark}_z")[0] = z
```

👉 Save this as **oscFanOut.py** alongside the `.toe`.
 👉 Attach it in the Script CHOP.

------

## 5. Person Router

A **custom COMP** that:

- Accepts channels like `p1_*`, `p2_*`.
- Exposes a **parameter (PersonID)**.
- Internally uses a **Select CHOP** or small Script CHOP to filter.
- Outputs only that person’s channels.

This makes effects simpler: they always receive **one skeleton**.

------

## 6. Effect Stubs

Each effect is packaged as a **TOX component**.
 Stub examples:

- **efx_hands.tox** → just draws hand positions.
- **efx_skeleton.tox** → connects landmarks with lines.
- **efx_emitters.tox** → particle emitters from hand tips.

Each takes the same CHOP input.
 A **Switch CHOP** chooses which effect is cooked.
 Unselected effects have **Cook Type = Selective** (saves GPU).

------

## 7. Annotations Inside TD

For clarity:

- Place **Text DATs** describing each COMP.
- Use **Annotation COMPs** at key points.
- Keep Python code external (`oscFanOut.py`, `personRouter.py`).

------

## 8. Folder Layout

```
Pose2Art_TD/
 ├─ Pose2Art.toe        # main starter TD project
 ├─ scripts/
 │   ├─ oscFanOut.py
 │   └─ personRouter.py
 ├─ effects/
 │   ├─ efx_hands.tox
 │   ├─ efx_skeleton.tox
 │   └─ efx_emitters.tox
 ├─ docs/
 │   └─ DeveloperGuide.md
```

------

## 9. Next Steps

1. Create the **starter toe** with OSC In DAT + Script CHOP fanout.
2. Add the **Person Router COMP**.
3. Add **Switch CHOP + effect stubs**.
4. Test with `pose_PC_MediaPipe_ndi.py` sending bundles.
5. Expand effects as needed (hand emitters, skeleton viz, etc.).

------

✅ This guide + code is enough for you (or a new dev) to **spin up a working Pose2Art TD project** that’s modular, annotated, and extendable.

------

Do you want me to go ahead and **generate the downloadable `Pose2Art_TD_starter.zip`** now, with:

- `.toe` project,
- externalized `oscFanOut.py` + `personRouter.py`,
- 3 stub `.tox` effects,
- annotation DATs?