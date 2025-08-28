# ext/PoseEffectMasterExt.py
# Lives on each PoseEffect_* (including the Master). Handles activation, bypass policy,
# and tells the child landmarkSelect to rebuild when needed.

class PoseEffectMasterExt:
    def __init__(self, owner):
        self.owner = owner
        debug(f"PoseEffectMasterExt __init__ called for {owner.name}" ) 
        self.Initialize()

    def onExtensionReady(self):
        """
        This method is called by TouchDesigner when the extension is ready.
        """
        debug(f"[{self.owner.name}] Landmark electExt.py onExtensionReady complete")
        self.Initialize()
        debug("LandmarkSelect Extension now ready")

    def Initialize(self):
        debug(f"PoseEffectMasterExt Initialize called for {self.owner.name}" )
        self.OnStart()
        return

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
        debug("PoseEffect Ext ApplyFilter called" )
        #ls = self.owner.op('landmarkselect')
        landmarkSelectOp = self.owner.op('landmarkSelect')
        if landmarkSelectOp and hasattr(landmarkSelectOp.ext, 'LandmarkSelectExt'):
            debug("PoseEffectMasterExt tell my landmarkSelect to Rebuild()")
            landmarkSelectOp.ext.LandmarkSelectExt.Rebuild()
        else:
            debug(f"ERROR LandmarkSelect not found or missing ext: {landmarkSelectOp}")

    def OnStart(self):
        debug(f"PoseEffectMasterExt OnStart()  called {self.owner.name}, init landmarkselect" )
        # do things when the clone starts.
        # insure the landmarkSelect component is setup
        landmarkSelectOp = self.owner.op('landmarkselect')
        if landmarkSelectOp and hasattr(landmarkSelectOp.ext, 'LandmarkSelectExt'):
            debug("onStart, call landmarSelectExt.Initialize")
            landmarkSelectOp.ext.LandmarkSelectExt.Initialize()
            debug("onStart, returned landmarSelectExt.Initialize")
        else:
            debug(f"ERROR LandmarkSelect not found or missing ext")  
            
