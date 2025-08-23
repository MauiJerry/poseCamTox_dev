# Pose2Art Demo Arch w Show Control

Here’s a **full consolidated architecture + build guide** for the **Pose2Art demo**, combining everything we’ve discussed and the details from your project notes. I’ve written this in a professional, step-by-step format for an experienced developer who’s new to TouchDesigner, with expanded first descriptions of TD techniques and later shorthand for reference.

------

# Pose2Art Demo: Architecture and Show Control Integration

## 1. System Architecture

**PoseCamPC (Python side):**

- Runs `poseCamPC.py` with a detector (`mediapipe_detector.py`, or later OpenPose/AlphaPose).
- Captures video (webcam, file, or NDI in future).
- Sends **OSC messages**:
  - Legacy (per-landmark names, human-readable).
  - Bundled (compact, ID-based).
- Optional NDI stream of raw video.
- Tkinter GUI (`tk_gui.py`) for selecting input/output.

**TouchDesigner (TD side):**

- **OSC In DAT** receives bundled OSC (multi-person, multi-landmark).
- **Script CHOP** (`oscFanOut.py`) parses bundle → fans out to channels.
- **Person Router COMP** filters one person’s skeleton.
- **PoseEfxSwitcher COMP** switches between effect TOXes.
- **ShowControl UI** panel:
  - Displays available effects.
  - Exposes tagged custom parameters from each effect.
  - Reports/receives OSC commands for bidirectional show control.

------

## 2. OSC Integration in TD

1. **OSC In DAT**
   - Place `OSC In DAT`.
   - Set **Network Port** (e.g. `7001` for poseCamPC).
   - Toggle “Active” → messages appear as rows.
2. **Fanout Script CHOP**
   - Add a **Script CHOP**.
   - Point to `oscFanOut.py`:

```python
# scripts/oscFanOut.py
def cook(scriptOP):
    scriptOP.clear()
    oscDAT = op('osc_in_dat')
    for row in oscDAT.rows()[1:]:
        address = row[0].val
        args = row[2:]
        parts = address.strip('/').split('/')
        if len(parts) < 2: continue
        person, landmark = parts
        if len(args) >= 3:
            x, y, z = [float(a.val) for a in args[:3]]
            for axis, val in zip("xyz", (x,y,z)):
                scriptOP.appendChan(f"{person}_{landmark}_{axis}")[0] = val
```

1. **Person Router**
   - Wrap in a custom COMP.
   - Expose a parameter: `PersonID`.
   - Internally: Select CHOP (`p1_*`, `p2_*`), or script filter.

------

## 3. Effect Containers & Switching

1. Each effect = one `.tox`.
   - Example: `efx_dot.tox`, `efx_skeleton.tox`, `efx_particles.tox`.
   - Input: skeleton CHOP.
   - Output: TOP (rendered effect).
2. **PoseEfxSwitcher COMP**
   - Holds all effect COMPs.
   - Switch TOP (or COMP Switch) chooses active effect.
   - Disabled COMPs set to **Cook Type = Selective** (saves GPU).

------

## 4. Exposing Effect Parameters

- Inside each `fxCore` COMP, **tag parameters** with `expose`.
- Example: a Speed parameter (float), tagged `expose`.

**UI Builder Script:**

```python
# scripts/buildShowUI.py
def build_show_ui(container):
    # Clear old controls
    for c in container.findChildren(type=COMP, depth=1):
        c.destroy()

    y = 0
    for fx in op('PoseEfxSwitcher').findChildren(depth=1, type=COMP):
        for par in fx.pars():
            if 'expose' in par.tags:
                ctrl = container.create(op('ui/slider'), f"{fx.name}_{par.name}")
                ctrl.par.link = par
                ctrl.nodeY = y; y -= 100
```

- Run once on project load.
- Auto-generates a UI panel with sliders/menus tied to exposed parameters.

------

## 5. Compositing NDI Video

- Place **NDI In TOP** (from camera).
- Composite under effects:
  - Use **Composite TOP** or **Over TOP** before final Out TOP.
- Toggle background passthrough with a simple UI button.

------

## 6. Landmark Smoothing

- Apply filtering to noisy pose CHOPs.
- Options:
  - **Lag CHOP**: exponential smoothing.
  - **Filter CHOP**: low-pass average.
  - **Trail CHOP**: history-based smoothing.
- Insert before effects input.

------

## 7. Show Control (OSC)

### Receiving OSC (external control)

- Place a second **OSC In DAT** (e.g. port `7002`).
- Script interprets:
  - `/pose2art/switch 2` → switch to effect 2.
  - `/pose2art/param fx1_color 0.5` → set parameter.

### Sending OSC (status updates)

- Add **OSC Out DAT** (port back to controller).
- Script reports:
  - Active effect ID/name.
  - Current exposed parameters.
  - Supported OSC addresses (`/pose2art/info`).

### Discovery / Introspection

- On startup, script scans exposed parameters.
- Builds a JSON or OSC bundle of “capabilities.”
- Sends upstream: effect list, param names, OSC addresses.

**Industry practice:**
 This mimics **sACN/ArtNet personality reporting** and **MIDI mapping introspection** (Ableton, Resolume). Upstream show control knows what commands are supported dynamically.

------

## 8. Developer Workflow

1. Run `poseCamPC.py` (Python).
   - Check OSC bundles arriving in TD.
2. Open `Pose2Art_Dev.toe`.
   - Confirm `oscFanOut.py` channels appear.
3. Route skeleton → Person Router → Efx Switcher.
4. Add `.tox` effects in `/effects`.
5. Tag parameters → regenerate UI with `buildShowUI.py`.
6. Connect OSC In/Out for bidirectional show control.

------

## 9. Folder Layout (TD project)

```
Pose2Art_TD/
 ├─ Pose2Art_Dev.toe
 ├─ scripts/
 │   ├─ oscFanOut.py
 │   ├─ buildShowUI.py
 │   └─ oscShowControl.py
 ├─ effects/
 │   ├─ efx_dot.tox
 │   ├─ efx_skeleton.tox
 │   └─ efx_particles.tox
 ├─ ui/
 │   ├─ slider. tox
 │   └─ menu.tox
 ├─ docs/
 │   └─ DeveloperGuide.md
```

------

✅ This document covers **architecture, TD techniques, effect switching, parameter exposure, OSC show control, and compositing**. With it, you can rebuild the Pose2Art demo into a modular, show-ready tool.

------

Would you like me to **generate a ready-to-import `.tox` package** (PoseEfxSwitcher + auto-UI + OSC control scripts), or keep this as a design doc for you to implement step-by-step inside TouchDesigner?