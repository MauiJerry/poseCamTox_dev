"""
LandmarkSelect_parexec.py

Callbacks for a Parameter Execute DAT on the LandmarkSelect component.
This script acts as a simple trigger, delegating all logic to the
LandmarkSelectExt extension.
"""

def onStart(info):
    """
    Called by TouchDesigner when the component starts.
    Tells the extension to run its initialization logic.
    does not seem to be called
    """
    debug("LandmarkSelect_parexec onStart called")
    # 'parent()' is the component this DAT is inside of.
    try:
        parent().ext.LandmarkSelectExt.Initialize()
    except AttributeError:
        debug(f"ERROR: Could not find LandmarkSelectExt on {parent().path}. Has it been created/attached?")
    return

def onValueChange(par, prev):
    """
    Called by TouchDesigner when a parameter on the owner component changes.
    """
    debug(f"LandmarkSelect_parexec onValueChange called for {par.name}")
    if par.name == 'Landmarkfiltermenu':
        newFilterKey = par.eval()
        parent().par.Currentfilter.val= newFilterKey
        parent().ext.LandmarkSelectExt.LoadActiveFilter()
    if par.name == 'Customfiltercsv':
        try:
            # Tell the extension to load the newly selected mask.
            parent().ext.LandmarkSelectExt.SetCustomCSV()
        except AttributeError:
            debug(f"ERROR: Could not find LandmarkSelectExt on {parent().path}. Has it been created/attached?")
    return

def onPulse(par):
    """
    Called by TouchDesigner when a pulse parameter is activated.
    """
    debug(f"LandmarkSelect_parexec onPulse called for {par.name}")
    # We only care about the 'RebuildMenu' pulse parameter.
    if par.name == 'RebuildMenu':
        try:
            # Tell the extension to rebuild its menu. This is useful if the
            # underlying data files (like the menu manifest) have changed.
            parent().ext.LandmarkSelectExt.RebuildMenu()
        except AttributeError:
            debug(f"ERROR: Could not find LandmarkSelectExt or RebuildMenu method on {parent().path}.")
    return

