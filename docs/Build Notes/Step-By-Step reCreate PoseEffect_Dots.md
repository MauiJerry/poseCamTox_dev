# Step-By-Step reCreate PoseEffect_Dots

25 Aug 2:30p

## prompt

ok big error.  I forgot to turn off "Enable Cloning" on the fxCore inside PoseEffect_Dots.  Thus all the changes i made were lost.  Lets write a step-by-step to add it back into the system.
0 Copy/Paste Master (or create new Container COMP), 0.1 rename to PoseEffect_NEWNAME
0.2 connect it to effects' inLandmarks and inMeta. only keep connetion to inTop if the fx is going to use the NDI input image.
1 turn off EnableCloning on fxCore
2 create Custom Parameters for the Effect (UiColor, UiDotSize, etc) on the new PoseEffect_ (remember actual code names with be Uicolor, Uidotsize etc.)
3 create same custom parameters on fxCore and bind them to the parent PoseEffect_ values
4 open fxCore and implement its features
4.1 create the shuffle_landmarks to convert inLandmarks to tx,ty,tz.
4.2 flip ty
4.3 put null chops after shuffle and also after flip latter is readyLandmarks
4.5 create the Geo, Mat, Camera, Render setup 
4.5.1 rename Mat for _Dots
4.6 connect Color of Mat to fxCore UiColor rgba Parameter
4.7 connect geo to Uidotsize Parameter
4.8 feed the inMeta image_width image_height to Render
4.9 render Connects to fxCore outTop
Result should show up properly at top level, and in some of the COMPS that have the Render or similar flag to display them on background.
At this point the UI controls (color, etc) are in the PoseEffect_Dots parameters editor. Dont bother with higher level UI yet.
Include other features that I've left out here if you recall them from earlier

## Response

perfect catch on cloning. here’s a clean, **click-by-click rebuild** for `PoseEffect_Dots` using your simple network (shuffle → flip-Y → instancing), with the params living at the top and bound into `fxCore`. i’ve added a few extras (selective cook, sanity checks) you’ll want.

------

### 0) create the effect shell and wire inputs

1. **Copy/Paste** your PoseEffect master (or make a new **Container COMP**).
    0.1 **Rename** → `PoseEffect_Dots` (or `PoseEffect_NEWNAME`).
    0.2 **Inputs** (inside it):
   - **CHOP In (index 0)** → name `inLandmarks` (single person).
   - **CHOP In (index 1)** → name `inMeta` (image_width/image_height from your inMeta **DAT** via DAT-to-CHOP, or leave unconnected if you’ll read the DAT directly).
   - **TOP In (index 0)** → only if this FX composites over the NDI/video frame.
   - **TOP Out** at the bottom → name `fxOut`.

------

### 1) fxCore: turn OFF cloning

1. Dive into `PoseEffect_Dots/fxCore`.
2. **Common** page → **Enable Cloning = OFF**.
    *(Optional)* On key child nodes you edit a lot, set **Clone Immune = On** (right-click → Flags) so they won’t get overwritten if you later flip cloning on at parent comps.
3. Turn on Immune Flag:
   on the fxCore (viewed in _Dots) the op's frame has 4 or so icons on left edge (just inside input connectors.) The 2nd one down is the [Immune Flag](https://derivative.ca/UserGuide/Immune_Flag).
   - [![ImmuneFlagOffIcon.png](https://docs.derivative.ca/images/9/91/ImmuneFlagOffIcon.png)](https://docs.derivative.ca/images/9/91/ImmuneFlagOffIcon.png) Off
   - [![ImmuneFlagOnIcon.png](https://docs.derivative.ca/images/2/28/ImmuneFlagOnIcon.png)](https://docs.derivative.ca/images/2/28/ImmuneFlagOnIcon.png) On - This node is made immune.

------

### 2) top-level custom parameters (the ones you’ll edit)

on **PoseEffect_Dots** (the parent) → **Customize Component…**

- Page **Look**:
  - `UiColor` (RGBA) — default 1,1,1,1
  - `UiDotsize` (Float) — default 8 (px), range 1–64
  - *(optional)* `UiOpacity` (0–1), `UiColormode` (Menu: `Fixed|RandomPerLandmark`)

> note: TD exposes these in python as `.par.Uicolor`, `.par.Uidotsize`, etc. (only the first letter stays uppercase).

------

### 3) mirror the same params on `fxCore` and **bind**

on **PoseEffect_Dots/fxCore** → **Customize Component…**

- Add **the same names**: `UiColor`, `UiDotsize` (and any optional ones).
- For each, set **Mode = Bind** and **Bind Expression** to parent:
  - `UiColor` → `op('..').par.Uicolor`
  - `UiDotsize` → `op('..').par.Uidotsize`
  - (same idea for `UiOpacity`, `UiColormode`)

now anything inside `fxCore` uses `fxCore.par.Uicolor`/`Uidotsize` and they stay in sync with the top.

------

### 4) build the CHOP prep (shuffle → flip-Y → readyLandmarks)

inside **fxCore**:
 4.0 **CHOP In** (index 0) → rename `skeleton_in`.
 4.1 **Shuffle / Reorder** to get three channels named **`tx, ty, tz`**:

- If your incoming CHOP is per-landmark triples already, use **Rename CHOP** to set the three aggregate channels to `tx ty tz`.
- If your input is a long list of `*_x/*_y/*_z` channels, use your existing **BAS shuffle_landmarks** network that outputs 3 channels.
- Put a **Null CHOP** after it → name `after_shuffle`.

4.2 **Flip Y only** (keep UV 0..1, just make Y-up):

- **Math CHOP** after `after_shuffle` → scope only `ty`
  - **From Range** ON: `0 → 1`
  - **To Range**: `1 → 0` (reversed to flip)
  - (or: **Multiply = −1**, **Post-Add = 1**)
- Put a **Null CHOP** after it → name `readyLandmarks`.
   *(this is what you’ll instance from)*

> if you decide to convert to NDC later, drop a second Math/Expression CHOP to do `tx: 0..1→−1..1` and `ty: 0..1→1..−1`, then set camera width=2. for now we’re keeping UV 0..1 with Y-up.

------

### 5) instancing + material + camera + render

5.1 **Dot geometry**

- **Rectangle SOP** → name `dot_rect` (unit quad).

- **Geometry COMP** → name `dot_geo`.

  - **Instance** page:

    - **Instancing = On**

    - **Instance OP** = `readyLandmarks`

    - **Translate X** = `tx`

    - **Translate Y** = `ty`

    - **Uniform Scale**:

      - if you’re staying in **UV 0..1**: use a tiny normalized size (easiest: convert to NDC instead; see variant below).

      - **recommended (pixel-true)**: convert to **NDC** (as noted above) and use:

        ```
        op('..').par.Uidotsize * 2 / float(op('inMetaDAT')['image_height','value'])
        ```

        (replace `inMetaDAT` with your actual Table DAT path; if you have a CHOP meta, use `[0]` indexing on its channel.)

5.2 **Constant MAT** → name `mat_Dots`

- **Common / Blending**: **Enable** (Over or Add).
- **Color**:
  - simplest: set MAT **RGBA** fields to `op('..').par.Uicolorr/g/b/a`.
  - or do per-instance color later (map `r,g,b,a` channels on `dot_geo ▸ Instance`).

5.3 **Camera COMP** → name `cam`

- If you **converted to NDC**: **Orthographic**, **Width = 2**.
- If you **stayed in UV**: set **Orthographic**, **Width = 1**. (Y-up is already handled by your flip.)
  - You may need to offset if your quad isn’t centered—unit rectangles default around origin.

5.4 **Render TOP** → name `render1`

- **Resolution** → **Custom**:

  - **Width** expr:

    ```
    int(op('inMetaDAT')['image_width','value'])
    ```

  - **Height** expr:

    ```
    int(op('inMetaDAT')['image_height','value'])
    ```

  - (or read from `inMeta` CHOP: `int(op('inMeta')['image_width'][0])` etc.)

- Set **Camera**=`cam`, **Geometry**=`dot_geo`, **Material**=`mat_Dots`.

5.5 **Out TOP** in `fxCore` → connect from `render1` → name `outTop`.

------

### 6) wire up to the effect output

back in **PoseEffect_Dots**:

- connect `fxCore/outTop` to the component’s **TOP Out** (`fxOut`).
- wire `PoseEffect_Dots/fxOut` into your **PoseEfxSwitch** (next free input of the switcher).
- set **Selective Cook** on non-active effects (COMP ▸ Common ▸ Selective Cook = On) so only the active one cooks.

------

### 7) connect color & size controls

- test **color** by changing `PoseEffect_Dots.par.Uicolor`.
- test **size** by changing `PoseEffect_Dots.par.Uidotsize`.
- if dots don’t appear sized as expected:
  - verify your **camera mode** (UV width=1, NDC width=2).
  - confirm the **Uniform Scale** expression resolves a real number (open parameter viewer, check for red text).
  - if reading meta from a **DAT**, ensure table row labels are exactly `image_width`/`image_height` and column is `value`.

------

### 8) (optional) extras you might want back

- **UiColormode / random color**: add `UiColormode` (Fixed|RandomPerLandmark) and a small **Script CHOP** to emit `r,g,b,a` per instance, mapped on `dot_geo ▸ Instance`.

- **expose_params** table inside `fxCore` with:

  ```
  Uicolor
  Uidotsize
  Uiopacity
  Uicolormode
  ```

  (only when you’re ready to rehook the higher-level UI/OSC.)

- **Parameter Execute DAT** on `fxCore` to respond to pulse controls (e.g., “Reroll Colors”).

------

### quick sanity checklist

-  `fxCore` **Enable Cloning** = **OFF**.
-  parent has `UiColor`, `UiDotsize`; child bound to them.
-  `readyLandmarks` outputs `tx, ty, tz` with **ty flipped** (0..1 up).
-  `dot_geo` Instancing reads `tx/ty` and a sensible **Uniform Scale**.
-  `mat_Dots` blending ON; color tied to `Uicolor` (or instance color).
-  **Camera** matches your coord choice (UV width=1 **or** NDC width=2).
-  **Render** resolution driven by `inMeta` values; **outTop** hooked.
-  effect input wired into **PoseEfxSwitch** and selectable.

if you tell me whether you want to **stay UV** or **switch to NDC** for this forever, i’ll give you the exact Uniform Scale expression and camera values for that path only (and remove the other branch so nothing drifts later).