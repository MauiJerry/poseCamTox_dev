# Pose Fanout Script CHOP README

Convert PoseCamPC **OSC bundles** into a tidy set of CHOP channels usable across your network.

## Summary

- **Input**: OSC In DAT rows (one row per OSC message, with Split Bundles **ON**).
- **Output**: A single CHOP stream with:
  - Per‑landmark channels: `p{pid}_{name}_{x|y|z}`
  - Person flags: `p{pid}_present`
  - Frame meta: `pose_n_people`, `pose_frame_count`, `pose_img_w`, `pose_img_h`
- **Lookup**: Uses a Table DAT `landmark_map` (id→name) to convert landmark IDs to names.

The OSC bundle format matches PoseCamPC’s “Bundle mode”: it sends
`/pose/frame_count`, `/pose/num_persons`, `/pose/image_width`, `/pose/image_height`,
and per‑landmark messages like `/pose/p1/17 [x y z]`. :contentReference[oaicite:0]{index=0} :contentReference[oaicite:1]{index=1}

---

## Inputs

- **OSC In DAT** (default name: `poseoscIn1`)
  - **Port**: matches your PoseCamPC sender
  - **Split Bundles into Messages**: **On**
  - **Clear on Frame**: **On** (recommended)
  - Optional **Address Filter**: `/pose/*`

- **Table DAT** (default name: `landmark_map`)
  - CSV/table with two columns:
    - `id` (0–32)
    - `name` (e.g., `wrist_l`)
  - First row can be a header (`id,name`).

---

## Outputs (Channels)

- **Per‑landmark** (for each person `pid` and landmark `name`):
  - `p{pid}_{name}_x`
  - `p{pid}_{name}_y`
  - `p{pid}_{name}_z`

- **Presence / counts**:
  - `p{pid}_present` — 1 if any landmark for pid seen this cook
  - `pose_n_people` — from `/pose/num_persons`, fallback to number of `present` PIDs

- **Optional metadata** (if messages are present in the bundle):
  - `pose_frame_count`  ← `/pose/frame_count`
  - `pose_img_w`        ← `/pose/image_width`
  - `pose_img_h`        ← `/pose/image_height`

**Note**: PoseCamPC’s bundle format and cadence are defined in its detector layer; see `AbstractPoseDetector.send_landmarks_via_osc()` and the MediaPipe implementation. :contentReference[oaicite:2]{index=2} :contentReference[oaicite:3]{index=3}

---

## Usage

1. **Inside your PoseCam COMP**
   - Create an **OSC In DAT** named `poseoscIn1`.
     - Enable **Split Bundles** and **Clear on Frame**.
   - Create a **Table DAT** named `landmark_map` and set `File` to your CSV with `id,name`.
   - Create a **Script CHOP** named `poseFanout` and set **Callbacks DAT / File** to `td/scripts/pose_fanout.py`.
   - Create a **Null CHOP** named `pose_out`, wire it from `poseFanout`, set **Cook Type = Selective**.

2. **Downstream**
   - `Select CHOP` e.g. `p1_wrist_l_x`, `p1_present`, `pose_n_people`.
   - Use `pose_frame_count` to drive frame-synced logic if you want.
   - Use `pose_img_w/h` for UI scaling.
   - Expect to use the PersonRouterCHOP as next in line

---

## Parameters & Customization

Edit these constants at the top of `pose_fanout.py`:

```python
OSC_IN_DAT_NAME = 'poseoscIn1'
ID_MAP_DAT_NAME = 'landmark_map'