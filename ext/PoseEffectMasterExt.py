# ext/PoseEffectMasterExt.py
# Lives on each PoseEffect_* (including the Master). Handles activation, bypass policy,
# and tells the child landmarkSelect to rebuild when needed.

class PoseEffectMasterExt:
    def __init__(self, owner):
        self.owner = owner

    # ===== Activation & lifecycle ============================================
    def SetActive(self, active: bool):
        """Called by PoseEfxSwitch when this effect becomes (in)active."""
        # 1) Gate cooking at the COMP level
        self.owner.allowCooking = bool(active)

        # 2) Update any 'Active' UI toggle (if present) to reflect state
        if hasattr(self.owner.par, 'Active'):
            want = 1 if active else 0
            if int(self.owner.par.Active.eval() or 0) != want:
                self.owner.par.Active = want

        # 3) Bypass policy for fxCore when inactive (optional)
        core = self.owner.op('fxCore')
        if core:
            bypass_inactive = False
            if hasattr(self.owner.par, 'Bypassinactive'):
                try:
                    bypass_inactive = bool(self.owner.par.Bypassinactive.eval())
                except Exception:
                    bypass_inactive = True
            core.par.bypass = (not active) and bypass_inactive

        # 4) On activation, ensure the landmark selection is fresh
        if active:
            self.ApplyFilter()

    # ===== Filter propagation (parent is SSOT) ================================
    def ApplyFilter(self):
        """Ask the child landmarkSelect to rebuild its Select CHOP pattern."""
        ls = self.owner.op('landmarkSelect')
        if ls and hasattr(ls.ext, 'LandmarkSelectExt'):
            ls.ext.LandmarkSelectExt.Rebuild()

    # ===== Services to children ===============================================
    def ResolveMenuCSV(self, key: str) -> str:
        """Delegate menu CSV lookup to the PoseEfxSwitch parent."""
        switch = self.owner.parent()
        if hasattr(switch.ext, 'PoseEfxSwitchExt'):
            return switch.ext.PoseEfxSwitchExt.ResolveMenuCSV(key)
        return ''
