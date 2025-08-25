# ext/PoseEffectMasterExt.py
# Lives on each PoseEffect_* (including the Master). Handles activation, bypass policy,
# and tells the child landmarkSelect to rebuild when needed.

def _debug(owner, msg):
    # won't crash if there's no logger; prints component path for clarity
    try:
        log = owner.op('log')
        (log.write if hasattr(log, 'write') else print)(f"[{owner.path}] {msg}\n")
    except Exception:
        print(f"[{owner.path}] {msg}")

class PoseEffectMasterExt:
    def __init__(self, owner):
        self.owner = owner

    def OnStart(self):
        _debug(self.owner, "OnStart()")
        # Ensure child bindings exist (so LandmarkSelect params show grey/expr‑driven)
        self._ensure_landmark_bindings()
        # Do one filter apply to populate select1.channame right away
        self.ApplyFilter()

    def _ensure_landmark_bindings(self):
        ls = self.owner.op('landmarkSelect')
        if not ls:
            _debug(self.owner, "No landmarkSelect child found.")
            return
        try:
            if not ls.par.LandmarkFilter.expr:
                ls.par.LandmarkFilter.expr = "op('..').par.LandmarkFilter.eval()"
            if not ls.par.Landmarkfiltercsv.expr:
                ls.par.Landmarkfiltercsv.expr = "op('..').par.Landmarkfiltercsv.eval() or ''"
        except Exception as e:
            _debug(self.owner, f"_ensure_landmark_bindings: {e}")


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
        ls = self.owner.op('landmarkselect')
        if ls and hasattr(ls.ext, 'LandmarkSelectExt'):
            ls.ext.LandmarkSelectExt.Rebuild()
        else:
            debug(f" LandmarkSelect not found or missing ext: {ls}")

    def ResolveMenuCSV(self, key: str) -> str:
        """Delegate menu CSV lookup to the PoseEfxSwitch parent."""
        debug(f"{self.name} ResolveMenuCSV called" )
        switch = self.owner.parent()
        if hasattr(switch.ext, 'PoseEfxSwitchExt'):
            return switch.ext.PoseEfxSwitchExt.ResolveMenuCSV(key)
        return ''
