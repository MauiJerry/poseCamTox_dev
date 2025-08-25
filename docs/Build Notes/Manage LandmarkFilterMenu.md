# Manage LandmarkFilterMenu 

got it — here’s a clean pattern that keeps the **PoseEffect** and its child **LandmarkSelect** in lock-step, with a single **menu source DAT** that defines the options and their CSVs. Then I show exactly what changes in both extensions.

csv is called confg/LandmarkFilterMenu.csv

------

# 0) Shared menu source (keeps both COMPs in sync)

Create a Table DAT inside **PoseEffect** (and clone into LandmarkSelect) named **`landmarkfiltermenu_csv`**:

```
key, label, csv
all, All Landmarks,
hands, Hands, data/masks_hands.csv
basicpose, Basic Pose, data/masks_basicpose.csv
skeleton, Skeleton, data/masks_skeleton.csv
face, Face, data/masks_face.csv
custom, Custom CSV,
```

- **key**: stable token used by code (`all|hands|basicpose|skeleton|face|custom`)
- **label**: human-readable menu text
- **csv**: default CSV path for this option (blank for `all` and `custom`)

Then, when you add the **LandmarkFilter** (menu) parameter on **both** COMPs:

- In **Customize Component…** set **Menu Source DAT** to this `landmarkfiltermenu_csv` and:
  - **Menu Labels Column** = `label`
  - **Menu Names Column** = `key`
- Add a **LandmarkFilterCSV** (File) parameter on both COMPs (used only when the selected key is `custom`).

> Now both menus are driven from the same DAT, so items never drift.

not sure how this connection works.  Maybe there is an update in the Ext py that reads the dat and fills in the menu?

------

# 1) Bind child parameters to parent (no code needed)

Inside each PoseEffect instance:

- Select `landmarkSelect` → Parameters → set:
  - `LandmarkFilter` to **Bind** to `../par.Landmarkfilter`
  - `LandmarkFilterCSV` to **Bind** to `../par.Landmarkfiltercsv`

That’s it. Changing the PoseEffect’s params will *auto-propagate* into the child.

(If you prefer not to use binding, I include a tiny “push down” in `PoseEffectExt` below.)

------

# 2) LandmarkSelect internals (names that your file uses)

Inside `landmarkSelect`:

- `in1` (CHOP In)
- `landmark_names` (Table DAT) → loads `data/landmark_names.csv`
- `landmark_mask` (Table DAT) → **this is the file we switch** based on selection
- `landmarkfilter_csv` (Table DAT) → the menu mapping table (same schema as above)
- `select1` (Select CHOP) → `op = ../in1`
- `outCHOP` (Null CHOP)

> You asked to honor these exact operator names: **`landmark_names`** and **`landmarkfilter_csv`**.

------

# 3) Updated `LandmarkSelectExt.py` (reads mapping table + unprefixed channels)

Save this at `ext/LandmarkSelectExt.py`, attach via Component Editor (Class Name: `LandmarkSelectExt`). It assumes channels are **unprefixed** (e.g., `wrist_l_x`).

```python
# ext/LandmarkSelectExt.py
# -----------------------------------------------------------------------------
# LandmarkSelectExt
# -----------------------------------------------------------------------------
# Purpose
#   Read the parent-specified selection (LandmarkFilter + LandmarkFilterCSV),
#   look up the default CSV in the local 'landmarkfilter_csv' table,
#   set 'landmark_mask.par.file' accordingly, and build the Select CHOP pattern.
#
# Inputs (inside 'landmarkSelect'):
#   - landmark_names (Table DAT)     : data/landmark_names.csv with column 'name'
#   - landmark_mask  (Table DAT)     : the chosen mask CSV (name/chan columns)
#   - landmarkfilter_csv (Table DAT) : mapping table (key,label,csv)
#   - select1 (Select CHOP)          : targets ../in1
#
# Parameters (bound from parent PoseEffect):
#   - LandmarkFilter    (menu tokens match 'key' column, e.g., 'hands')
#   - LandmarkFilterCSV (file path; used only when key == 'custom')
#
# Channels are assumed UNPREFIXED (e.g., 'wrist_l_x').
# -----------------------------------------------------------------------------

class LandmarkSelectExt:
    def __init__(self, owner):
        self.owner = owner

    # ---------- public ----------
    def Rebuild(self):
        """
        Apply the selected filter:
          1) Resolve key -> csv using 'landmarkfiltermenu_csv' table.
          2) Set 'landmark_mask.par.file' to that csv (or to LandmarkFilterCSV if key=='custom').
          3) Build channel list from either:
             - ALL: expand every 'name' in landmark_names to name_x/y/z
             - MASK: read landmark_mask rows (support 'name' or 'chan')
          4) De-dup and write to select1.par.channame.
        """
        filt_key = (self.owner.par.Landmarkfilter.eval() or '').strip().lower()
        custom_csv = (self.owner.par.Landmarkfiltercsv.eval() or '').strip()

        sel = self.owner.op('select1')
        if not sel:
            self._log("Missing 'select1'.")
            return

        mask = self.owner.op('landmark_mask')
        if not mask:
            self._log("Missing 'landmark_mask'.")
            return

        # 1) resolve key -> default csv from mapping table
        default_csv = self._lookup_csv_for_key(filt_key)

        # 2) choose final mask file path
        if filt_key in ('', 'all'):
            mask.par.file = ''  # not used
        elif filt_key == 'custom':
            if custom_csv:
                mask.par.file = custom_csv
            else:
                self._log("Custom selected but LandmarkFilterCSV is empty.")
                mask.par.file = ''
        else:
            mask.par.file = default_csv or ''

        # 3) build channels
        if filt_key in ('', 'all'):
            names = self._read_names()
            chans = _flatten([_expand_unprefixed(n) for n in names])
        else:
            entries = self._read_mask_items()
            chans = []
            for kind, val in entries:
                if kind == 'chan':
                    chans.append(val)           # verbatim; wildcards ok
                else:
                    chans += _expand_unprefixed(val)

        # 4) de-dup and apply
        final = _dedup(chans)
        sel.par.op = '../in1'
        sel.par.channame = ' '.join(final)
        self._log(f"Rebuilt: key='{filt_key}', patterns={len(final)}, mask='{mask.par.file.eval()}'")

    # ---------- helpers ----------
    def _lookup_csv_for_key(self, key):
        """Find default csv for a given key in 'landmarkfilter_csv' (key,label,csv)."""
        tbl = self.owner.op('landmarkfilter_csv')
        if not tbl or tbl.numRows < 2:
            return ''
        # normalize headers (expect: key,label,csv)
        heads = [c.val.lower() for c in tbl.row(0)]
        key_idx = heads.index('key')   if 'key'  in heads else -1
        csv_idx = heads.index('csv')   if 'csv'  in heads else -1
        if key_idx < 0 or csv_idx < 0:
            return ''
        for r in tbl.rows()[1:]:
            if r[key_idx].val.strip().lower() == key:
                return r[csv_idx].val.strip()
        return ''

    def _read_names(self):
        """Return list of landmark names from 'landmark_names' (expects column 'name')."""
        t = self.owner.op('landmark_names')
        if not t or t.numRows < 2:
            return []
        heads = [c.val.lower() for c in t.row(0)]
        if 'name' not in heads:
            return []
        name_idx = heads.index('name')
        return [r[name_idx].val.strip() for r in t.rows()[1:] if r[name_idx].val.strip()]

    def _read_mask_items(self):
        """
        Return list[('chan', str) | ('name', str)] from 'landmark_mask'.
        Accepts either column; rows may mix.
        """
        t = self.owner.op('landmark_mask')
        if not t or t.numRows < 2:
            return []
        heads = [c.val.lower() for c in t.row(0)]
        name_i = heads.index('name') if 'name' in heads else -1
        chan_i = heads.index('chan') if 'chan' in heads else -1
        out = []
        for r in t.rows()[1:]:
            if chan_i >= 0 and r[chan_i].val.strip():
                out.append(('chan', r[chan_i].val.strip()))
            elif name_i >= 0 and r[name_i].val.strip():
                out.append(('name', r[name_i].val.strip()))
        return out

    def _log(self, msg):
        logdat = self.owner.op('log')
        try:
            if logdat and hasattr(logdat, 'write'):
                logdat.write(str(msg) + '\n')
            else:
                print(str(msg))
        except Exception:
            pass


# ---------- module helpers ----------
def _expand_unprefixed(name):
    """'wrist_l' -> ['wrist_l_x','wrist_l_y','wrist_l_z']"""
    base = f"{name}_"
    return [base + 'x', base + 'y', base + 'z']

def _dedup(seq):
    seen, out = set(), []
    for s in seq:
        if s and s not in seen:
            seen.add(s); out.append(s)
    return out

def _flatten(list_of_lists):
    out = []
    for sub in list_of_lists:
        out.extend(sub)
    return out
```

**Why this works**

- The **LandmarkFilter** menu token is the single source of truth (`key`).
- The **mapping DAT** provides the default CSV path for that token.
- `custom` uses the **LandmarkFilterCSV** file parameter.
- `all` expands from `landmark_names` (ignores mask file).
- No `p*_` prefixes anywhere.

------

# 4) Updated PoseEffect extension (push-down + rebuild)

If you use **parameter binding** on the child, your PoseEffect extension only needs to call `Rebuild()` when values change or the effect activates:

```python
# ext/PoseEffectExt.py  (or PoseEffectMasterExt.py if you prefer)
class PoseEffectExt:
    def __init__(self, owner):
        self.owner = owner

    def SetActive(self, active: bool):
        # Gate the whole effect
        self.owner.allowCooking = bool(active)
        # Optional: bypass heavy core when inactive
        core = self.owner.op('fxCore')
        if core:
            core.par.bypass = not active
        # On activate, rebuild the child selector once
        if active:
            self.ApplyFilter()

    def ApplyFilter(self):
        """
        If the child params are *bound*, we just ask the child to rebuild.
        If you skipped binding, uncomment the two lines that push values down.
        """
        sel = self.owner.op('landmarkSelect')
        if not sel: return

        # (Only needed if you do *not* bind the child's parameters)
        # sel.par.Landmarkfilter    = self.owner.par.Landmarkfilter.eval()
        # sel.par.Landmarkfiltercsv = self.owner.par.Landmarkfiltercsv.eval()

        if hasattr(sel.ext, 'LandmarkSelectExt'):
            sel.ext.LandmarkSelectExt.Rebuild()
```

Hook this up from a **Parameter Execute DAT** on the PoseEffect so that when either `LandmarkFilter` or `LandmarkFilterCSV` changes, it runs `ext.PoseEffectExt.ApplyFilter()`.

------

## Quick checklist

-  Both COMPs have `LandmarkFilter` (menu) and `LandmarkFilterCSV` (file).
-  Both menus use the **same** `landmarkfilter_csv` DAT as Menu Source.
-  In `landmarkSelect`, bind its two params to the parent PoseEffect.
-  `LandmarkSelectExt.py` uses: `landmark_names`, `landmark_mask`, `landmarkfilter_csv`.
-  Channels are **unprefixed** everywhere.
-  `PoseEffectExt` calls child `Rebuild()` on activate and when params change.

If you want, I can also draft a tiny **Parameter Execute DAT** body for both COMPs so the rebuild triggers are already wired.