# Build Landmark Select - 21Aug

Landmark select is part of PoseEffect__Master template.

> Your upstream **Rename CHOP** removed the `p*_` prefix, so channel names look like `wrist_l_x`, `elbow_r_y`, etc. This guide updates the `landmarkSelect` sub-COMP to assume **single-person, unprefixed** channels.

------

#### What LandmarkSelect does (updated)

- Reads **CSV masks** from `/data` (`landmark_names.csv`, `masks_hands.csv`, `masks_basicpose.csv`, optional `masks_face.csv`, or your custom CSV).
- Expands **landmark names** to **channel names**: (this is done b4 PoseEffect)
   `wrist_l_x wrist_l_y wrist_l_z` (no `p*_` prefix).
- Accepts masks [arameter that specify **explicit channels** via a `chan` column (used verbatim).
- Writes the final space-separated list to the **Select CHOP**’s `channame`.

------

### 1) Create the `landmarkSelect` sub-COMP

**Inside your PoseEffect (e.g., `PoseEffect_MASTER`):**

- Add a **Base COMP** named `landmarkSelect`.

note: table_names is actually landmark_names, same as over in PoseCamIn TOX, loading the same data

**Inside `landmarkSelect`, add:** 

- `in1` — **CHOP In** (connect from PoseEffect’s `in1`)
- `landmark_names` — **Table DAT** → `par.file = data/landmark_names.csv`
- `table_mask` — **Table DAT** (file will switch based on filter mode)
- `select1` — **Select CHOP**
  - `par.op = ../in1`
  - leave `par.channame` empty (extension will set it)
- `outCHOP` — **Null CHOP** (from `select1`)

------

### 2) Add LandmarkSelect parameters 

Right-click `landmarkSelect` → **Customize Component…** → Parameters → Page **SELECT**:

- `Filtermode` (Menu): `All Hands BasicPose CustomCSV`
   *(add `Face` later if you ship a CSV ; BasicPose might be Major_Marks?, add Skeleton as special case = paired up, or just in order)*
- `Filtercsv` (File Path): used only when `Filtermode = CustomCSV`

------

### 3) Attach the Extension via **Component Editor**

1. Right-click `landmarkSelect` → **Component Editor…** → **Extensions**.
2. Enter **Class Name**: `LandmarkSelectExt` → **Add**.
   - A Text DAT (e.g., `landmarkSelect/LandmarkSelectExt`) is created.
3. Select that DAT and set **File** to: `ext/LandmarkSelectExt.py`
    *(or paste the code directly into the DAT).*
4. Enable **Re-Init Extensions on Start**. Close.

------

### 4) Drop-in extension code (verbose & updated for no prefix)

Save this as `ext/LandmarkSelectExt.py` and point the Extension DAT to it.

Chat likes to name things like Tables using the pattern table_ (eg table_names, table_mask). Better naming would be  more explicit - eg landmark_names landmark_filter

***this doc's code is for REFERENCE. refer to actual file for updates, do them there.***



```python
# ext/LandmarkSelectExt.py
# -----------------------------------------------------------------------------
# LandmarkSelectExt (no person prefix version)
# -----------------------------------------------------------------------------
# Purpose
#   Build a Select CHOP channel list from /data CSV masks assuming single-person,
#   unprefixed channels like:
#       wrist_l_x, wrist_l_y, elbow_r_x, ...
#
# Inputs inside `landmarkSelect` COMP:
#   - in1 (CHOP In): upstream pose channels (unprefixed)
#   - table_names (Table DAT): data/landmark_names.csv  -> column 'name'
#   - table_mask  (Table DAT): path set by Filtermode/Filtercsv
#   - select1     (Select CHOP): targets ../in1; `channame` set here
#   - outCHOP     (Null CHOP): Select output pass-through
#
# Parameters on `landmarkSelect`:
#   - Filtermode (Menu): All | Hands | BasicPose | CustomCSV   [Face optional]
#   - Filtercsv  (File): used only when Filtermode = CustomCSV
#
# CSV schemas:
#   - landmark_names.csv  -> header includes 'name'
#   - masks_*.csv/custom  -> either 'name' (landmark names) OR 'chan' (explicit)
#       * if 'name', expand to: <name>_x <name>_y <name>_z
#       * if 'chan', use verbatim (wildcards allowed)
#
# Notes:
#   - Including _z is harmless if absent; Select CHOP ignores non-existent names.
#   - We log to a local 'log' Text DAT if present, else to the textport.
# -----------------------------------------------------------------------------

class LandmarkSelectExt:
    """Extension for `landmarkSelect`COMP that (re)builds Select CHOP channel patterns."""

    def __init__(self, owner):
        self.owner = owner

    # ---------------- Public API ----------------
    def Rebuild(self):
        """
        Compute and apply the Select CHOP's `channame` based on Filtermode/CSV.

        Steps:
          1) Decide which mask CSV to use (switch table_mask.par.file).
          2) Build channel list:
             - All       -> read names from `table_names`, expand to name_x/y/z
             - Hands/…   -> read rows from `table_mask`:
                             * 'chan' -> use verbatim
                             * 'name' -> expand to name_x/y/z
             - CustomCSV -> same as above, using Filtercsv file
          3) De-duplicate (order preserving) and set select1.par.channame.
        """
        selectCHOP = self.owner.op('select1')
        if not selectCHOP:
            self._log("[Rebuild] Missing 'select1' Select CHOP.")
            return

        tmask = self.owner.op('table_mask')
        if not tmask:
            self._log("[Rebuild] Missing 'table_mask' Table DAT.")
            return

        mode_raw = (self.owner.par.Filtermode.eval() or '').strip()
        mode = mode_raw.lower()

        # 1) Choose mask CSV path - some built in
        csv_path = None
        if mode == 'hands':
            csv_path = 'data/masks_hands.csv'
        elif mode == 'basicpose':
            csv_path = 'data/masks_basicpose.csv'
        elif mode == 'face':
            csv_path = 'data/masks_face.csv'  # only if you ship this file
        elif mode == 'customcsv':
            csv_path = (self.owner.par.Filtercsv.eval() or '').strip()
            if not csv_path:
                self._log("[Rebuild] CustomCSV selected but Filtercsv is empty.")
        elif mode == 'all' or mode == '':
            csv_path = ''  # not used in All
        else:
            self._log(f"[Rebuild] Unknown Filtermode '{mode_raw}', defaulting to All.")
            csv_path = ''

        # Apply selected path (blank is fine for 'All')
        tmask.par.file = csv_path

        # 2) Build pattern list
        channels = []
        if mode == 'all' or mode == '':
            for nm in self._read_names():
                channels += self._expand(nm)
        else:
            for kind, val in self._read_mask_items():
                if kind == 'chan':
                    channels.append(val)      # verbatim; wildcards ok
                else:  # 'name'
                    channels += self._expand(val)

        # 3) De-duplicate & apply
        final = _dedup(channels)
        selectCHOP.par.op = '../in1'          # ensure correct input target
        selectCHOP.par.channame = ' '.join(final)

        self._log(f"[Rebuild] mode='{mode_raw}', patterns={len(final)}")

    # ---------------- Internals -----------------
    # table_names is landmark_names DAT same as
    # in poseCamIn comp, loads from same csv.
    def _read_names(self):
        """Return list of landmark names from `table_names` (reads 'name' column)."""
        tnames = self.owner.op('table_names')
        if not tnames:
            self._log("[_read_names] Missing 'table_names' Table DAT.")
            return []
        rows = _rows_as_dicts(tnames)
        out = []
        for r in rows:
            nm = (r.get('name') or r.get('landmark') or '').strip()
            if nm:
                out.append(nm)
        if not out:
            self._log("[_read_names] No names found.")
        return out

    def _read_mask_items(self):
        """
        Return list of ('chan', value) or ('name', value) from `table_mask`.
        Accepts either column (case-insensitive). Rows may mix both.
        """
        tmask = self.owner.op('table_mask')
        if not tmask:
            self._log("[_read_mask_items] Missing 'table_mask' Table DAT.")
            return []
        rows = _rows_as_dicts(tmask)
        out = []
        for r in rows:
            ch = (r.get('chan') or '').strip()
            nm = (r.get('name') or '').strip()
            if ch:
                out.append(('chan', ch))
            elif nm:
                out.append(('name', nm))
        return out

    def _expand(self, name):
        """
        Expand a landmark base name into axis channels (no prefix):
          'wrist_l' -> ['wrist_l_x','wrist_l_y','wrist_l_z']
        """
        base = f"{name}_"
        return [base + 'x', base + 'y', base + 'z']

    def _log(self, msg):
        """Write to local 'log' DAT if present, else print to textport."""
        logdat = self.owner.op('log')
        try:
            if logdat and hasattr(logdat, 'write'):
                logdat.write(str(msg) + '\n')
            else:
                print(str(msg))
        except Exception:
            pass


# ---------------- Module helpers ----------------
def _rows_as_dicts(tab):
    """Convert a Table DAT to list[dict] using row 0 as headers (case-insensitive)."""
    try:
        if tab.numRows <= 1 or tab.numCols <= 0:
            return []
        heads = [c.val.lower() for c in tab.row(0)]
        rows = []
        for r in tab.rows()[1:]:
            d = {}
            for i in range(min(len(heads), len(r))):
                d[heads[i]] = r[i].val
            rows.append(d)
        return rows
    except Exception:
        return []

def _dedup(seq):
    """De-duplicate while preserving order."""
    seen, out = set(), []
    for x in seq:
        if x and x not in seen:
            seen.add(x); out.append(x)
    return out
```

------

### 5) Typical wiring (unchanged)

```
PoseEffect/
  in1 (CHOP In)  ──▶ landmarkSelect/ … ─▶ outCHOP ──▶ fxCore (CHOP input)
  in2 (TOP In)   ───────────────────────────────────▶ fxCore (TOP input)
```

to get it built right...

From your effect’s activation or UI change, call:

```python
op('PoseEffect_*').op('landmarkSelect').ext.LandmarkSelectExt.Rebuild()
```

------

### 6) Heads-up: update any code that assumed `p*_`

If you copied the earlier **Skeleton pair-eval** Script CHOP that did things like `f"p{pid}_{a}_x"`, change those lookups to **unprefixed** names:

```python
ax = src.get(f"{a}_x"); ay = src.get(f"{a}_y")
bx = src.get(f"{b}_x"); by = src.get(f"{b}_y")
```

That’s it—`landmarkSelect` now cleanly targets your single-person, unprefixed channel set.

yes, that is a Rename CHOP just before the  PoseEfxSwitch (parent of this tox)