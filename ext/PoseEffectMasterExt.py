# ext/PoseEffectMasterExt.py
# Lives on each PoseEffect_* (including the Master). Handles activation, bypass policy,
# and tells the child landmarkSelect to rebuild when needed.

class PoseEffectMasterExt:
    def __init__(self, owner):
        self.owner = owner

    def SetActive(self, active: bool):
        """Called by PoseEfxSwitch when this effect becomes (in)active."""
        debug(f"SetActive({active}) called" )
        # 1) Gate cooking at the COMP level
        self.owner.allowCooking = bool(active)

        # 2) Update the 'Active' UI toggle (if present) so the panel reflects state
        if hasattr(self.owner.par, 'Active'):
            # Avoid triggering loops: only set if value changed
            want = 1 if active else 0
            if int(self.owner.par.Active.eval() or 0) != want:
                self.owner.par.Active = want

        # skip 3) bypass/cooking on internal fxCore
        
        # 4) On activation, ensure the landmark selection is fresh
        if active:
            self.ApplyFilter()

    def ApplyFilter(self):
        """Ask the child landmarkSelect to rebuild its Select CHOP pattern."""
        debug("ApplyFilter called" )
        #ls = self.owner.op('landmarkSelect')
        ls = op('landmarkSelect')
        if ls and hasattr(ls.ext, 'LandmarkSelectExt'):
            ls.ext.LandmarkSelectExt.Rebuild()
        else:
            debug(f"{op('.').name} LandmarkSelect not found or missing ext: {ls}")

    def ResolveMenuCSV(self, key: str) -> str:
        """Delegate menu CSV lookup to the PoseEfxSwitch parent."""
        debug(f"{self.name} ResolveMenuCSV called" )
        switch = self.owner.parent()
        if hasattr(switch.ext, 'PoseEfxSwitchExt'):
            return switch.ext.PoseEfxSwitchExt.ResolveMenuCSV(key)
        return ''


    def OnStart(self):
        debug("OnStart called, wtf we supposed to do here?" )
        # do things when the clone starts.
        # most importantly, be sure the fx_params are taken care of
        #self.owner.op('fxCore').op('ensure_fx_pars').ensure()
        
