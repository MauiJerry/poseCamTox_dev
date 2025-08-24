# ext/PoseEfxSwitchExt.py
# -----------------------------------------------------------------------------
# PoseEfxSwitchExt
# -----------------------------------------------------------------------------
# Attach this extension to the PoseEfxSwitch COMP.
#
# Responsibilities (finalized 23 Aug):
#   • Build the ActiveEffect menu labels from PoseEffect parent.par.UiDisplayName
#     (fall back to pretty OP name). Menu values remain stable keys (OP names).
#   • Keep ActiveEffect (menu) and ActiveIndex (int) in sync WITHOUT loops.
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
#   - ActiveIndex        (Int)      ← internal index (hide if you like)
#   - RebuildEffectsMenu (Pulse)    ← manual refresh
#
# Initialization:
#   - Put an Execute DAT *inside* PoseEfxSwitch with:
#       def onStart(): op('.').ext.PoseEfxSwitchExt.Initialize()
# -----------------------------------------------------------------------------

class PoseEfxSwitchExt:
    def __init__(self, owner):
        self.owner = owner
        self._syncing = False  # re-entrancy guard

    # ===== Lifecycle ==========================================================
    def Initialize(self):
        """Called by the embedded Execute DAT on project start."""
        self.InitLandmarkMenus()
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
        keys, labels = [], []
        for fx in self._effects():
            key = fx.name  # OP name is the stable key
            lab = self._label_for_effect(fx)
            keys.append(key)
            labels.append(lab)

        # Stamp the UI menu
        self.owner.par.ActiveEffect.menuNames  = keys
        self.owner.par.ActiveEffect.menuLabels = labels

        # Keep current selection valid, then push activation
        cur = (self.owner.par.ActiveEffect.eval() or '').strip()
        if cur not in keys and keys:
            self.owner.par.ActiveEffect = keys[0]
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
        if self._syncing:
            return
        self._syncing = True
        try:
            key = (self.owner.par.ActiveEffect.eval() or '').strip()
            idx = self._indexForOpName(key)
            if idx is not None and int(self.owner.par.ActiveIndex.eval() or -1) != idx:
                self.owner.par.ActiveIndex = idx
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
            fx  = self._effectAtIndex(idx)
            key = fx.name if fx else ''
            if key and (self.owner.par.ActiveEffect.eval() or '') != key:
                self.owner.par.ActiveEffect = key
            self.SetActiveIndex(idx)
        finally:
            self._syncing = False

    def SetActiveEffect(self, key: str):
        """Programmatic activation by OP name (updates both params + activation)."""
        key = (key or '').strip()
        keys = self._menuKeys()
        if not keys:
            return
        if key not in keys:
            key = keys[0]
        self.owner.par.ActiveEffect = key  # triggers OnActiveEffectChanged

    def SetActiveIndex(self, idx: int):
        """
        Activate exactly one PoseEffect_* and route out_switch to that index.
        """
        # Route output switch
        sw = self.owner.op('out_switch')
        if sw:
            sw.par.index = int(idx)

        # Gate cooking + call SetActive on each effect
        for i, fx in enumerate(self._effects()):
            is_active = (i == int(idx))
            fx.allowCooking = is_active
            core = fx.op('fxCore')
            if core:
                core.par.bypass = not is_active
            if hasattr(fx.ext, 'PoseEffectMasterExt'):
                fx.ext.PoseEffectMasterExt.SetActive(is_active)

    # ===== Services for children ==============================================
    def ResolveMenuCSV(self, key: str) -> str:
        """Given a filter menu key (e.g., 'hands'), return default CSV path."""
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
