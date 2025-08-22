# ext/PoseEffectMasterExt.py
# Lives on each PoseEffect_* (including the Master). Gates cooking and coordinates child rebuilds.

class PoseEffectMasterExt:
    def __init__(self, owner):
        self.owner = owner

    def SetActive(self, active: bool):
        self.owner.allowCooking = bool(active)
        core = self.owner.op('fxCore')
        if core: core.par.bypass = not active
        if active:
            self.ApplyFilter()

    def ApplyFilter(self):
        ls = self.owner.op('landmarkSelect')
        if ls and hasattr(ls.ext, 'LandmarkSelectExt'):
            ls.ext.LandmarkSelectExt.Rebuild()

    def ResolveMenuCSV(self, key: str) -> str:
        # Ask the PoseEfxSwitch parent to resolve csv for 'key'
        switch = self.owner.parent()
        if hasattr(switch.ext, 'PoseEfxSwitchExt'):
            return switch.ext.PoseEfxSwitchExt.ResolveMenuCSV(key)
        return ''
