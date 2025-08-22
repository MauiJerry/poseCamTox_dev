# ext/PoseEfxSwitchExt.py
# -----------------------------------------------------------------------------
# PoseEfxSwitchExt
# -----------------------------------------------------------------------------
# Attach this extension to your PoseEfxSwitch COMP.
#
# Responsibilities:
#   • Build the ActiveEffect (menu) from PoseEffectsMenu_csv (if present),
#     otherwise auto-discover PoseEffect_* children under ./effects.
#   • Keep ActiveEffect (menu) and ActiveIndex (int) in sync WITHOUT loops.
#   • Activate exactly one PoseEffect_*:
#       - Route out_switch.index
#       - Set fx.allowCooking True for active, False for others
#       - Toggle fxCore.bypass (False when active, True when not)
#       - Call each effect’s PoseEffectMasterExt.SetActive(active)
#   • Stamp LandmarkFilter menu items (names/labels) into each PoseEffect
#     and its child landmarkSelect from LandmarkFilterMenu_csv.
#   • Ensure each landmarkSelect reads its parent PoseEffect params via expressions:
#       LandmarkFilter  = op('..').par.LandmarkFilter.eval()
#       Landmarkfiltercsv = op('..').par.Landmarkfiltercsv.eval() or ''
#
# Expected nodes inside PoseEfxSwitch:
#   - LandmarkFilterMenu_csv   (Table DAT: key,label,csv)  ← REQUIRED
#   - PoseEffectsMenu_csv      (Table DAT: key,label,opName,index) ← OPTIONAL
#   - effects/                 (Base COMP container for PoseEffect_* children)
#   - out_switch               (Switch TOP)
#
# UI parameters on PoseEfxSwitch (Customize Component…):
#   - ActiveEffect    (Menu)     ← user-facing
#   - ActiveIndex     (Int)      ← internal (can be hidden)
#   - RebuildEffectsMenu (Pulse) ← optional refresh button
#
# Initialization:
#   - Place an Execute DAT inside PoseEfxSwitch with:
#       def onStart(): op('.').ext.PoseEfxSwitchExt.Initialize()
#
# Notes:
#   - Filters (LandmarkFilter/Landmarkfiltercsv) are per-effect, not on this switch.
#   - The switch’s LandmarkFilterMenu_csv is the single source of truth for filter menus.
#   - When wiring outputs, ensure each PoseEffect_*/fxOut is connected to out_switch
#     at the index you expect (especially if you rely on an explicit 'index' column).
# -----------------------------------------------------------------------------

class PoseEfxSwitchExt:
    def __init__(self, owner):
        self.owner = owner
        # Re-entrancy guard to prevent ActiveEffect<->ActiveIndex ping-pong
        self._syncing = False

    # ===== Lifecycle ==========================================================
    def Initialize(self):
        """Called by the embedded Execute DAT on project start."""
        self.InitLandmarkMenus()
        self.EnsureLandmarkBindings()
        self.BuildEffectsMenu()

        # Choose initial active effect (by key if present, else first, else index 0)
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
        """
        Stamp LandmarkFilter menu (names/labels) onto each PoseEffect and its
        child landmarkSelect from LandmarkFilterMenu_csv (key,label,csv).
        If an effect currently selects a non-custom key with a CSV mapping,
        seed its Landmarkfiltercsv file param with that default path.
        """
        table = self.owner.op('LandmarkFilterMenu_csv')
        if not table or table.numRows < 2:
            print("[PoseEfxSwitchExt.InitLandmarkMenus] Missing/empty LandmarkFilterMenu_csv")
            return

        heads = [c.val.lower() for c in table.row(0)]
        try:
            ki = heads.index('key')
            li = heads.index('label')
            ci = heads.index('csv')
        except ValueError:
            print("[PoseEfxSwitchExt.InitLandmarkMenus] CSV must have columns: key,label,csv")
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
            # Stamp menu items on PoseEffect param UI
            fx.par.LandmarkFilter.menuNames  = keys
            fx.par.LandmarkFilter.menuLabels = labels

            # Mirror same items on the child selector (value follows via expression)
            ls = fx.op('landmarkSelect')
            if ls:
                ls.par.LandmarkFilter.menuNames  = keys
                ls.par.LandmarkFilter.menuLabels = labels

            # If current key has a default csv (and is not 'custom'), seed file param
            cur = (fx.par.LandmarkFilter.eval() or '').strip()
            if cur in keys and cur != 'custom':
                idx = keys.index(cur)
                defcsv = csvs[idx] if idx < len(csvs) else ''
                if defcsv:
                    fx.par.Landmarkfiltercsv = defcsv

    def EnsureLandmarkBindings(self):
        """
        Ensure each landmarkSelect reads its parent PoseEffect parameters via expressions.
        (We do NOT bind effect params to the switch; filters are per-effect.)
        """
        for fx in self._effects():
            ls = fx.op('landmarkSelect')
            if not ls:
                continue
            if not ls.par.LandmarkFilter.expr:
                ls.par.LandmarkFilter.expr = "op('..').par.LandmarkFilter.eval()"
            if not ls.par.Landmarkfiltercsv.expr:
                ls.par.Landmarkfiltercsv.expr = "op('..').par.Landmarkfiltercsv.eval() or ''"

    # ===== Effect menu (ActiveEffect) =========================================
    def BuildEffectsMenu(self):
        """
        Populate ActiveEffect (menu) from PoseEffectsMenu_csv if present; otherwise
        auto-discover PoseEffect_* children under ./effects. Also (re)build a local
        EffectDispatch_csv mapping table with columns: key,label,op,index.
        """
        keys, labels, ops, idxs = [], [], [], []
        cfg = self.owner.op('PoseEffectsMenu_csv')

        def add_row(k, lab, opName, ix):
            if not k:
                return
            keys.append(k)
            labels.append(lab or k)
            ops.append(opName or '')
            try:
                idxs.append(int(ix))
            except Exception:
                idxs.append(len(idxs))  # fallback sequential index

        if cfg and cfg.numRows > 1:
            heads = [c.val.lower() for c in cfg.row(0)]
            ki = heads.index('key')    if 'key'    in heads else -1
            li = heads.index('label')  if 'label'  in heads else -1
            oi = heads.index('opname') if 'opname' in heads else -1
            ii = heads.index('index')  if 'index'  in heads else -1
            rows = cfg.rows()[1:]
            # Sort by provided 'index' if present and valid
            try:
                if ii >= 0:
                    rows = sorted(rows, key=lambda r: int(r[ii].val))
            except Exception:
                pass
            for r in rows:
                k   = r[ki].val.strip() if ki >= 0 else ''
                lab = (r[li].val or '').strip() if li >= 0 else ''
                opn = (r[oi].val or '').strip() if oi >= 0 else ''
                ix  = r[ii].val.strip() if ii >= 0 else ''
                add_row(k, lab, opn, ix)
        else:
            # Auto-discover PoseEffect_* children
            for i, fx in enumerate(self._effects()):
                name = fx.name
                key  = name.replace('PoseEffect_', '').lower()
                lab  = key.title().replace('_', ' ')
                add_row(key, lab, name, i)

        # Stamp the UI menu
        self.owner.par.ActiveEffect.menuNames  = keys
        self.owner.par.ActiveEffect.menuLabels = labels

        # Build/update local dispatch table (handy for debugging/inspection)
        disp = self._ensureDispatchTable()
        disp.clear()
        disp.appendRow(['key', 'label', 'op', 'index'])
        for i in range(len(keys)):
            disp.appendRow([keys[i], labels[i], ops[i], idxs[i]])

        # Keep current selection valid, then push activation
        cur = (self.owner.par.ActiveEffect.eval() or '').strip()
        if cur not in keys and keys:
            self.owner.par.ActiveEffect = keys[0]
        self.OnActiveEffectChanged()

    def OnActiveEffectChanged(self):
        """Called when the ActiveEffect (menu) param changes."""
        if self._syncing:
            return
        self._syncing = True
        try:
            key = (self.owner.par.ActiveEffect.eval() or '').strip()
            idx = self._indexForKey(key)
            # Only set ActiveIndex if it actually differs (prevents loops)
            if idx is not None and int(self.owner.par.ActiveIndex.eval() or -1) != idx:
                self.owner.par.ActiveIndex = idx
            # Activate (idempotent if unchanged)
            self.SetActiveIndex(int(self.owner.par.ActiveIndex.eval() or 0))
        finally:
            self._syncing = False

    def OnActiveIndexChanged(self):
        """Called when the ActiveIndex (int) param changes."""
        if self._syncing:
            return
        self._syncing = True
        try:
            idx = int(self.owner.par.ActiveIndex.eval() or 0)
            key = self._keyForIndex(idx) or ''
            # Only set ActiveEffect if it actually differs (prevents loops)
            if key and (self.owner.par.ActiveEffect.eval() or '') != key:
                self.owner.par.ActiveEffect = key
            # Activate (idempotent if unchanged)
            self.SetActiveIndex(idx)
        finally:
            self._syncing = False

    def SetActiveEffect(self, key: str):
        """Programmatic activation by menu key (updates both params + activation)."""
        key = (key or '').strip()
        keys = self._menuKeys()
        if not keys:
            return
        if key not in keys:
            key = keys[0]
        # Setting the menu triggers OnActiveEffectChanged(), which syncs the index.
        self.owner.par.ActiveEffect = key

    def SetActiveIndex(self, idx: int):
        """
        Activate exactly one PoseEffect_* and route out_switch to that index.
        Uses the dispatch table to find the opName for the selected index so
        we gate cooking by the correct COMP even if child order differs.
        """
        # Route output switch
        sw = self.owner.op('out_switch')
        if sw:
            sw.par.index = int(idx)

        # Which opName is active according to dispatch?
        active_name = self._opNameForIndex(idx)

        # Gate cooking and call SetActive(active)
        effects = self._effects()
        for fx in effects:
            is_active = (fx.name == active_name) if active_name else (effects.index(fx) == idx)
            fx.allowCooking = is_active
            core = fx.op('fxCore')
            if core:
                core.par.bypass = not is_active
            if hasattr(fx.ext, 'PoseEffectMasterExt'):
                fx.ext.PoseEffectMasterExt.SetActive(is_active)

    # ===== Services for children (csv resolve) =================================
    def ResolveMenuCSV(self, key: str) -> str:
        """
        Given a filter menu key (e.g., 'hands', 'basicpose'), return the default
        CSV path from LandmarkFilterMenu_csv. Returns '' if not found.
        """
        key = (key or '').strip().lower()
        table = self.owner.op('LandmarkFilterMenu_csv')
        if not table or table.numRows < 2:
            return ''
        heads = [c.val.lower() for c in table.row(0)]
        try:
            ki = heads.index('key')
            ci = heads.index('csv')
        except ValueError:
            return ''
        for r in table.rows()[1:]:
            if r[ki].val.strip().lower() == key:
                return (r[ci].val or '').strip()
        return ''

    # ===== Helpers =============================================================
    def _effects(self):
        """Return all PoseEffect_* COMPs under ./effects."""
        eff = self.owner.op('effects')
        if not eff:
            return []
        # Only COMPs whose name starts with PoseEffect_
        return [c for c in eff.children if c.isCOMP and c.name.startswith('PoseEffect_')]

    def _ensureDispatchTable(self):
        """Create or return the local EffectDispatch_csv table."""
        disp = self.owner.op('EffectDispatch_csv')
        if not disp:
            # TD build variations: try class token first, then fallback to string type
            try:
                disp = self.owner.create(tableDAT, 'EffectDispatch_csv')  # type: ignore  # noqa
            except Exception:
                disp = self.owner.create('tableDAT', 'EffectDispatch_csv')
        return disp

    def _menuKeys(self):
        """Return the list of menu keys currently set on ActiveEffect."""
        # menuNames may be a tuple-like object; coerce to list
        names = self.owner.par.ActiveEffect.menuNames or []
        return list(names)

    def _indexForKey(self, key):
        """Lookup numeric index for a given effect key using EffectDispatch_csv."""
        disp = self.owner.op('EffectDispatch_csv')
        if not disp or disp.numRows < 2:
            return None
        heads = [c.val.lower() for c in disp.row(0)]
        try:
            ki = heads.index('key')
            ii = heads.index('index')
        except ValueError:
            return None
        for r in disp.rows()[1:]:
            if r[ki].val == key:
                try:
                    return int(r[ii].val)
                except Exception:
                    return None
        return None

    def _keyForIndex(self, idx):
        """Lookup effect key string for a given numeric index."""
        disp = self.owner.op('EffectDispatch_csv')
        if not disp or disp.numRows < 2:
            return ''
        heads = [c.val.lower() for c in disp.row(0)]
        try:
            ki = heads.index('key')
            ii = heads.index('index')
        except ValueError:
            return ''
        for r in disp.rows()[1:]:
            try:
                if int(r[ii].val) == int(idx):
                    return r[ki].val
            except Exception:
                pass
        return ''

    def _opNameForIndex(self, idx):
        """Lookup the child COMP name (opName) for a given numeric index."""
        disp = self.owner.op('EffectDispatch_csv')
        if not disp or disp.numRows < 2:
            return ''
        heads = [c.val.lower() for c in disp.row(0)]
        try:
            oi = heads.index('op')
            ii = heads.index('index')
        except ValueError:
            return ''
        for r in disp.rows()[1:]:
            try:
                if int(r[ii].val) == int(idx):
                    return r[oi].val
            except Exception:
                pass
        return ''
