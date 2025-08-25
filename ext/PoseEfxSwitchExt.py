# ext/PoseEfxSwitchExt.py
# -----------------------------------------------------------------------------
# PoseEfxSwitchExt
# -----------------------------------------------------------------------------
# Attach this extension to the PoseEfxSwitch COMP.
#
# Responsibilities (finalized 23 Aug):
#   • Build the ActiveEffect menu labels from PoseEffect parent.par.UiDisplayName
#     (fall back to pretty OP name). Menu values remain stable keys (OP names).
#   • Keep ActiveEffect (menu) and Activeindex (int) in sync WITHOUT loops.
#   • Activate exactly one PoseEffect_*:
#       - Route out_switch.index
#       - fx.allowCooking  = True for active, False for others
#       - fxCore.bypass    = False for active, True for others
#       - fx.ext.PoseEffectMasterExt.SetActive(active)
#   • Stamp LandmarkFilter menu items into each PoseEffect and its child
#     landmarkSelect from LandmarkFilterMenu_csv (key,label,csv).
#   • Ensure each landmarkSelect reads its parent PoseEffect params via expressions.
#
# Expected nodes inside PoseEfxSwitch:
#   - LandmarkFilterMenu_csv  (Table DAT: key,label,csv)               ← REQUIRED
#   - effects/                (Base COMP container for PoseEffect_* children)
#   - out_switch              (Switch TOP)
#
# UI parameters on PoseEfxSwitch (Customize Component…):
#   - ActiveEffect       (Menu)     ← user-facing effect picker (values = OP names)
#   - Activeindex        (Int)      ← internal index (hide if you like)
#   - RebuildEffectsMenu (Pulse)    ← manual refresh
#
# Initialization:
#   - Put an Execute DAT *inside* PoseEfxSwitch with:
#       def onStart(): op('.').ext.PoseEfxSwitchExt.Initialize()
# -----------------------------------------------------------------------------

import os, csv, glob

class PoseEfxSwitchExt:
    def __init__(self, owner):
        debug("db init PoseEfxSwitchExt")
        self.owner = owner
        self._syncing = False  # re-entrancy guard
        self._mask_dispatch = {}   # NEW: key -> absolute csv path

    # ===== Lifecycle ==========================================================
    def Initialize(self):
        """Called by the embedded Execute DAT on project start."""
        debug("db Initialize PoseEfxSwitchExt")
        tab = self.owner.op('LandmarkFilterMenu_csv')
        if not tab or tab.numRows < 2: self.ScanAndBuildMaskMenu()
        else: self.InitLandmarkMenus()

        self.EnsureLandmarkBindings()
        self.BuildEffectsMenu()

        # Choose initial active effect: keep current if valid else first else index 0
        key = (self.owner.par.ActiveEffect.eval() or '').strip()
        keys = self._menuKeys()
        if key in keys:
            self.SetActiveEffect(key)
        elif keys:
            self.SetActiveEffect(keys[0])
        else:
            self.SetActiveIndex(0)

    # ===== Landmark filter menus (per-effect) =================================
    def InitLandmarkMenus(self):
        """Stamp LandmarkFilter menu (names/labels) onto PoseEffect and child selector."""
        debug("db InitLandmarkMenus PoseEfxSwitchExt")
        table = self.owner.op('LandmarkFilterMenu_csv')
        if not table or table.numRows < 2:
            debug("[PoseEfxSwitchExt.InitLandmarkMenus] Missing/empty LandmarkFilterMenu_csv")
            return

        heads = [c.val.lower() for c in table.row(0)]
        try:
            ki = heads.index('key')
            li = heads.index('label')
            ci = heads.index('csv')
        except ValueError:
            debug("[PoseEfxSwitchExt.InitLandmarkMenus] CSV must have columns: key,label,csv")
            return

        keys, labels, csvs = [], [], []
        for r in table.rows()[1:]:
            k = r[ki].val.strip()
            if not k:
                continue
            keys.append(k)
            labels.append((r[li].val or k).strip())
            csvs.append((r[ci].val or '').strip())

        for fx in self._effects():
            # Stamp on PoseEffect parent (SSOT)
            if hasattr(fx.par, 'LandmarkFilter'):
                fx.par.LandmarkFilter.menuNames  = keys
                fx.par.LandmarkFilter.menuLabels = labels

            # Mirror menu on child landmarkSelect (value is expression-bound)
            ls = fx.op('landmarkSelect')
            if ls and hasattr(ls.par, 'LandmarkFilter'):
                ls.par.LandmarkFilter.menuNames  = keys
                ls.par.LandmarkFilter.menuLabels = labels

            # Seed default CSV if key has mapping and isn't 'custom'
            cur = (getattr(fx.par, 'LandmarkFilter', None).eval() if hasattr(fx.par, 'LandmarkFilter') else '') or ''
            if cur in keys and cur != 'custom':
                idx = keys.index(cur)
                defcsv = csvs[idx] if idx < len(csvs) else ''
                if defcsv and hasattr(fx.par, 'Landmarkfiltercsv'):
                    fx.par.Landmarkfiltercsv = defcsv

    def EnsureLandmarkBindings(self):
        """Ensure landmarkSelect reads parent PoseEffect params via expressions."""
        debug("db EnsureLandmarkBindings PoseEfxSwitchExt")
        
        for fx in self._effects():
            ls = fx.op('landmarkSelect')
            if not ls:
                continue
            if hasattr(ls.par, 'LandmarkFilter') and not ls.par.LandmarkFilter.expr:
                ls.par.LandmarkFilter.expr = "op('..').par.LandmarkFilter.eval()"
            if hasattr(ls.par, 'Landmarkfiltercsv') and not ls.par.Landmarkfiltercsv.expr:
                ls.par.Landmarkfiltercsv.expr = "op('..').par.Landmarkfiltercsv.eval() or ''"

    # ===== Effect menu (ActiveEffect) =========================================
    def BuildEffectsMenu(self):
        """
        Auto-discover PoseEffect_* children and build ActiveEffect menu.
        Values = OP names (stable). Labels = parent.par.UiDisplayName if set,
        else derived from OP name ("PoseEffect_Dots2" -> "Dots 2").
        """
        debug("db BuildEffectsMenu PoseEfxSwitchExt")
        keys, labels = [], []
        for fx in self._effects():
            key = fx.name  # OP name is the stable key
            lab = self._label_for_effect(fx)
            keys.append(key)
            labels.append(lab)

        # Stamp the UI menu
        self.owner.par.Activeeffect.menuNames  = keys
        self.owner.par.Activeeffect.menuLabels = labels

        # Keep current selection valid, then push activation
        cur = (self.owner.par.Activeeffect.eval() or '').strip()
        if cur not in keys and keys:
            self.owner.par.Activeeffect = keys[0]
        self.OnActiveEffectChanged()

    def _label_for_effect(self, fx):
        """Prefer PoseEffect.UiDisplayName (non-'Master'), else pretty OP name."""
        try:
            p = getattr(fx.par, 'Uidisplayname', None)
            if p:
                val = (p.eval() or '').strip()
                if val and val.lower() != 'master':
                    return val
        except Exception:
            pass
        return fx.name.replace('PoseEffect_', '').replace('_', ' ').title()

    def OnActiveEffectChanged(self):
        """Called when the ActiveEffect (menu) param changes."""
        debug("db OnActiveEffectChanged PoseEfxSwitchExt")
        if self._syncing:
            return
        self._syncing = True
        try:
            key = (self.owner.par.Activeeffect.eval() or '').strip()
            idx = self._indexForOpName(key)
            if idx is not None and int(self.owner.par.Activeindex.eval() or -1) != idx:
                self.owner.par.Activeindex = idx
            self.SetActiveIndex(int(self.owner.par.Activeindex.eval() or 0))
        finally:
            self._syncing = False

    def OnActiveIndexChanged(self):
        """Called when the ActiveIndex (int) param changes."""
        debug("db OnActiveIndexChanged PoseEfxSwitchExt")
        if self._syncing:
            return
        self._syncing = True
        try:
            idx = int(self.owner.par.Activeindex.eval() or 0)
            fx  = self._effectAtIndex(idx)
            key = fx.name if fx else ''
            if key and (self.owner.par.Activeeffect.eval() or '') != key:
                self.owner.par.ActiveEffect = key
            self.SetActiveIndex(idx)
        finally:
            self._syncing = False

    def SetActiveEffect(self, key: str):
        """Programmatic activation by OP name (updates both params + activation)."""
        debug("db SetActiveEffect PoseEfxSwitchExt", key)
        key = (key or '').strip()
        keys = self._menuKeys()
        if not keys:
            return
        if key not in keys:
            key = keys[0]
        self.owner.par.Activeeffect = key  # triggers OnActiveEffectChanged

    def SetActiveIndex(self, idx: int):
        """
        Activate exactly one PoseEffect_* and route out_switch to that index.
        """
        debug("db SetActiveIndex PoseEfxSwitchExt", idx)
        # Route output switch
        sw = self.owner.op('out_switch')
        if sw:
            sw.par.index = int(idx)

        # Gate cooking + call SetActive on each effect (PoseEffect_ )
        for i, fx in enumerate(self._effects()):
            is_active = (i == int(idx))
            fx.allowCooking = is_active
            if hasattr(fx.ext, 'PoseEffectMasterExt'):
                fx.ext.PoseEffectMasterExt.SetActive(is_active)

    # build the Landmarks Menu, Preloading CSV files
    import os, csv, glob

    def ScanAndBuildMaskMenu(self):
        """Merge data/LandmarkFilterMenu.csv with discovered data/mask*.csv,
        preload each mask to /mask_cache, and (re)build LandmarkFilterMenu_csv.
        """
        base_dir = project.folder
        data_dir = os.path.join(base_dir, 'data')

        def _abs(path_like):
            if not path_like: return ''
            return path_like if os.path.isabs(path_like) else os.path.join(base_dir, path_like)

        # rows: dicts {key,label,csv,include,order}
        rows, seen = [], set()
        def _push(key, label, csvp='', include='1', order='1000'):
            k = (key or '').strip().lower()
            if not k or k in seen: return
            seen.add(k)
            rows.append({
                'key': k,
                'label': (label or k.title()).strip(),
                'csv': (csvp or '').strip(),
                'include': str(include or '1'),
                'order': str(order or '1000')
            })

        # Always start with base rows
        _push('all', 'All', '', '1', '0')
        _push('custom', 'Custom', '', '1', '1')

        # Optional config file
        cfg = os.path.join(data_dir, 'LandmarkFilterMenu.csv')
        if os.path.isfile(cfg):
            try:
                with open(cfg, newline='', encoding='utf-8') as f:
                    for r in csv.DictReader(f):
                        key   = (r.get('key') or '').strip().lower()
                        label = (r.get('label') or '').strip()
                        csvrel= (r.get('csv') or '').strip()
                        inc   = (r.get('include') or '1').strip()
                        order = (r.get('order') or '100').strip()
                        # allow csv to be relative to data/
                        full = _abs(csvrel if os.path.isabs(csvrel) else os.path.join('data', csvrel))
                        _push(key, label, full if csvrel else '', inc, order)
            except Exception as e:
                print('[ScanAndBuildMaskMenu] config read error:', e)

        # Discover masks on disk
        disc = []
        if os.path.isdir(data_dir):
            for pat in (os.path.join(data_dir, 'mask_*.csv'),
                        os.path.join(data_dir, 'masks_*.csv')):
                disc.extend(glob.glob(pat))

        def key_from(path):
            nm = os.path.splitext(os.path.basename(path))[0]
            return nm[5:].lower() if nm.startswith('mask_') else (nm[6:].lower() if nm.startswith('masks_') else nm.lower())

        existing = {r['key'] for r in rows}
        for p in sorted(disc):
            k = key_from(p)
            if k in ('all','custom') or k in existing: continue
            _push(k, k.title().replace('_',' '), p, '1', '1000')

        # Build cache under /mask_cache and record dispatch table
        cache = self.owner.op('mask_cache') or self.owner.create(baseCOMP, 'mask_cache')
        for c in cache.children: c.destroy()
        self._mask_dispatch = {}
        for r in rows:
            k, csvp, inc = r['key'], r['csv'], r['include']
            if csvp:
                self._mask_dispatch[k] = csvp  # record regardless
            if csvp and inc != '0' and os.path.isfile(csvp):
                t = cache.create(tableDAT, f"mask_{k}")
                t.par.file = csvp
                # force immediate load (builds differ: 'reloadpulse' vs 'reload')
                rp = getattr(t.par, 'reloadpulse', None) or getattr(t.par, 'reload', None)
                if rp and hasattr(rp, 'pulse'): rp.pulse()

        # Write/refresh the LandmarkFilterMenu_csv table (pretty csv paths)
        menu = self.owner.op('LandmarkFilterMenu_csv') or self.owner.create(tableDAT, 'LandmarkFilterMenu_csv')
        menu.clear()
        menu.appendRow(['key','label','csv','include','order'])
        def sk(r):
            try: return (int(r['order']), r['label'])
            except: return (1000, r['label'])
        for r in sorted(rows, key=sk):
            csv_show = r['csv']
            if csv_show.startswith(base_dir):
                csv_show = os.path.relpath(csv_show, base_dir).replace('\\','/')
            menu.appendRow([r['key'], r['label'], csv_show, r['include'], r['order']])

        # Stamp menus to effects/child selectors using existing routine
        self.InitLandmarkMenus()

    # ===== Services for children ==============================================
    
    def ResolveMenuCSV(self, key: str) -> str:
        """Given a filter menu key (e.g., 'hands'), return default CSV path."""
        debug("db ResolveMenuCSV PoseEfxSwitchExt", key)
        k = (key or '').strip().lower()
        # NEW: prefer cache from ScanAndBuildMaskMenu
        p = self._mask_dispatch.get(k, '')
        if p: return p
        # FALLBACK: read from LandmarkFilterMenu_csv table (old behavior)
        table = self.owner.op('LandmarkFilterMenu_csv')
        if not table or table.numRows < 2:
            return ''
        heads = [c.val.lower() for c in table.row(0)]
        try:
            ki = heads.index('key'); ci = heads.index('csv')
        except ValueError:
            return ''
        for r in table.rows()[1:]:
            if r[ki].val.strip().lower() == k:
                return (r[ci].val or '').strip()
        return ''

    # ===== Helpers =============================================================
    def ResolveMaskTable(self, key: str):
        """Return cached mask Table DAT for a given key, or None."""
        k = (key or '').strip().lower()
        return self.owner.op('mask_cache/{}'.format(f"mask_{k}"))


    def _effects(self):
        """Return all PoseEffect_* COMPs under ./effects."""
        eff = self.owner.op('effects')
        if not eff:
            return []
        return [c for c in eff.children if c.isCOMP and c.name.startswith('PoseEffect_')]

    def _menuKeys(self):
        """Return menu values (OP names)."""
        return list(self.owner.par.ActiveEffect.menuNames or [])

    def _effectAtIndex(self, idx: int):
        effs = self._effects()
        if 0 <= idx < len(effs):
            return effs[idx]
        return None

    def _indexForOpName(self, name: str):
        effs = self._effects()
        for i, fx in enumerate(effs):
            if fx.name == name:
                return i
        return None
