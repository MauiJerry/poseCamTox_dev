# Person_Router  construction

note - had to change the option 1 parameters for search and replace.  p1_*  and *(0)

havent touched the python one. rename is faster.

### Rebuild `Person_Router` (keep only `pose/p1_*`, drop `p1_`)

Below are two solid ways to do it in TouchDesigner: a no-code CHOP network (fastest + simplest) and a tiny Script CHOP (if you prefer code). Pick one; both produce channels like `pose/nose_tx` from inputs like `pose/p1_nose_tx`.

------

### Option A — Pure CHOPs (recommended)

1. **Make the COMP**

   - Create a **Container COMP** named `person_router`.
   - On its **Inputs/Outputs** page: set **Node Output** to your final CHOP (we’ll name it `OUT` below).

2. **Wire the CHOP network inside `person_router`**

   - **in1 (In CHOP)**: leave unconnected here; on the parent network you’ll wire it from `poseCamIn` (the CHOP that carries all pose channels).
   - **select1 (Select CHOP)**:
     - **CHOP** parameter: `in1`
     - **Channel Names** (pattern): `p1_*`
       - This selects only channels for person 1.
   - **rename1 (Rename CHOP)**:
     - **Method**: `Replace String` (or `From/To` depending on your build)
     - **From**: `p1_`*
     - **To**: `*(0)`
       - This strips `p1_` while preserving the `pose/` namespace.
   - **out1 (Null CHOP)**:
     - Name it `OUT` (good practice for component output).
     - Set **Cook Type** to `Selective` (optional), **Upload CPU to GPU** off.

   Wire: `in1 → select1 → rename1 → OUT`.

3. **Use it**

   - Back in the parent network, connect your `poseCamIn` CHOP output to `person_router/in1`.
   - Downstream effects can read `person_router`’s output (or directly reference `person_router/OUT`).

**Result:** Input `pose/p1_nose_tx` → Output `pose/nose_tx`. All non-p1 channels are dropped.

------

### Option B — Script CHOP (filter + rename in Python)

Use this if you want the logic in code (e.g., to later parameterize `p#` selection). Inside `person_router`:

1. **Add a Script CHOP** named `router`.
   - **CHOP Input**: wire `in1` into `router`.
   - **Callbacks DAT**: create a new Text DAT `person_router_callbacks` with the code below and point Script CHOP to it.
2. **Callbacks code (`person_router_callbacks`)**

```python
# TouchDesigner Script CHOP callbacks
# Place in /person_router/person_router_callbacks and point Script CHOP to it.

def onSetupParameters(scriptOp):
    return

def onCook(scriptOp):
    """
    Input channels are expected to include names like 'pose/p1_<landmark>'.
    We output only those, renamed to 'pose/<landmark>'.
    """
    if not scriptOp.inputs:
        scriptOp.clear()
        return

    src = scriptOp.inputs[0]

    # Match source timing
    scriptOp.clear()
    scriptOp.numSamples = src.numSamples
    scriptOp.rate = src.rate

    prefix = 'pose/p1_'
    keep = []

    for ch in src.channels:
        name = ch.name
        if name.startswith(prefix):
            out_name = 'pose/' + name[len(prefix):]  # strip 'p1_' only
            new_ch = scriptOp.appendChan(out_name)
            # fast copy of all samples
            new_ch.vals = ch.vals
            keep.append(out_name)

    # Optional: if no matching channels, still cook cleanly
    # (scriptOp already cleared; doing nothing is fine)
    return
```

1. **Output**
   - Set the COMP’s **Node Output** to `router` (or put a `Null CHOP` named `OUT` after it and set that as the output).

------

### Editor notes & gotchas (TD specifics)

- **Selecting by pattern:** In the **Select CHOP**, the **Channel Names** field accepts wildcards like `pose/p1_*`. You can add multiple patterns separated by spaces or newlines.
- **Renaming by replacement:** In the **Rename CHOP**, choose **Replace String** (or **From/To**) and use:
  - **From:** `pose/p1_`
  - **To:** `pose/`
- **Component output:** On the `person_router` COMP, open **Common → Node Output** and pick `OUT` so other COMPs can just wire from `person_router` itself.
- **Debugging:** Middle-click on CHOP nodes to view channel counts & names. Use a **Trail CHOP** or **Textport** (`Alt+t`) to confirm names after rename.
- **Performance:** The CHOP version is GPU-friendly and zero-copy; prefer it unless you need dynamic logic (e.g., routing `p2_`, `p3_` via a parameter).

------

### (Optional) Make the person id configurable

If you later want `pX_` instead of hard-coded `p1_`:

- **CHOP approach:** Add a **Custom Parameter** to `person_router` called `Personid` (Menu or Int). Then drive:
  - **Select CHOP → Channel Names**: `f'pose/p{me.par.Personid}_*'`
    - Do this with a **Python expression**: enable the expression toggle and enter:
       `f"pose/p{parent().par.Personid}_*"`
  - **Rename CHOP → From**: expression
     `f"pose/p{parent().par.Personid}_"`
- **Script approach:** Replace `prefix = 'pose/p1_'` with:
   `prefix = f"pose/p{int(parent().par.Personid)}_"`

(You’ll first add that custom parameter via **COMP → Parameter Dialog → Custom → Edit… → Add Int**.)

------

If you want, I can also add the `Personid` custom parameter and hand you the exact expressions bound in each operator so you can just paste them in.