# PoseEffectMasterExt.py
class PoseEffectMasterExt:
# Keeps PoseEffect and child landmarkSelect menus in sync from landmarkSelect/landmarkfilter_csv.
# Also rebuilds the child's Select CHOP when filter changes or effect activates.

    def __init__(self, owner):
        self.owner = owner

    # ---- lifecycle helpers ----
    def InitMenus(self):
        """
        Read keys/labels from child landmarkSelect/landmarkfilter_csv and set
        the menu entries on BOTH the parent (PoseEffect) and the child.
        If current selection is invalid, default to the first key.
        Also auto-fill LandmarkFilterCSV when the selected key has a default csv (non-custom).
        """
        lmSel = self.owner.op('landmarkSelect')
        if not lmSel:
            print("[PoseEffectExt.InitMenus] Missing child 'landmarkSelect'.")
            return
        mapTab = lmSel.op('landmarkfilter_csv')
        if not mapTab or mapTab.numRows < 2:
            print("[PoseEffectExt.InitMenus] Missing/empty 'landmarkfilter_csv'.")
            return

        # Parse mapping table
        heads = [c.val.lower() for c in mapTab.row(0)]
        key_i  = heads.index('key')  if 'key'  in heads else -1
        lab_i  = heads.index('label')if 'label'in heads else -1
        csv_i  = heads.index('csv')  if 'csv'  in heads else -1
        if key_i < 0 or lab_i < 0:
            print("[PoseEffectExt.InitMenus] mapping table must have 'key' and 'label' columns.")
            return

        keys, labels, csvs = [], [], []
        for r in mapTab.rows()[1:]:
            k = r[key_i].val.strip()
            if not k: continue
            keys.append(k)
            labels.append((r[lab_i].val or k).strip())
            csvs.append((r[csv_i].val if csv_i >= 0 else '').strip())

        if not keys:
            print("[PoseEffectExt.InitMenus] No keys found in mapping.")
            return

        # Set parent menu entries
        p_menu = self.owner.par.Landmarkfilter
        p_menu.menuNames  = keys
        p_menu.menuLabels = labels

        # Set child menu entries (for UX parity; value is bound anyway)
        c_menu = lmSel.par.Landmarkfilter
        c_menu.menuNames  = keys
        c_menu.menuLabels = labels

        # Validate current selection
        cur = p_menu.eval().strip()
        if cur not in keys:
            # choose first entry as default
            p_menu.val = keys[0]
            cur = keys[0]

        # If non-custom and a default csv exists, fill LandmarkFilterCSV once
        if cur != 'custom':
            idx = keys.index(cur)
            default_csv = csvs[idx] if idx < len(csvs) else ''
            if default_csv:
                self.owner.par.Landmarkfiltercsv = default_csv
                # child param is bound so it follows

    def SetActive(self, active: bool):
        # Gate the whole effect cooking
        self.owner.allowCooking = bool(active)
        core = self.owner.op('fxCore')
        if core:
            core.par.bypass = not active
        if active:
            # On activation, ensure menus are initialized and child is rebuilt
            self.InitMenus()
            self.ApplyFilter()

    def ApplyFilter(self):
        """
        Rebuild the child selector. If you did not bind child params,
        you can uncomment the push-down lines below.
        """
        lmSel = self.owner.op('landmarkSelect')
        if not lmSel: return

        # -- Only needed if you DID NOT bind child params: --
        # lmSel.par.Landmarkfilter    = self.owner.par.Landmarkfilter.eval()
        # lmSel.par.Landmarkfiltercsv = self.owner.par.Landmarkfiltercsv.eval()

        if hasattr(lmSel.ext, 'LandmarkSelectExt'):
            lmSel.ext.LandmarkSelectExt.Rebuild()

    # ---- event hooks you can call from Parameter/Execute DATs ----
    def OnFilterChanged(self):
        """Call when LandmarkFilter or LandmarkFilterCSV changes on the parent."""
        # If the user picked a non-custom option with a default csv, reflect it
        key = self.owner.par.Landmarkfilter.eval().strip().lower()
        if key and key != 'custom':
            # re-init menus to re-apply default csv for that key
            self.InitMenus()
        self.ApplyFilter()

    def OnMenuTableChanged(self):
        """Call when the mapping table 'landmarkfilter_csv' changes (rows edited)."""
        self.InitMenus()
        self.ApplyFilter()
