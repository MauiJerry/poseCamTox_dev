# PoseEffect_Master / parexec DAT has this code
# This DAT lives inside each PoseEffect_* (via the master clone source).
# It calls the effect's extension to rebuild landmark selection or toggle cooking.

# this is currently not used. It was intended to keep landmark values in this Container consistent with
# those in the fxCore.  The binding and clone logic was wrong so we disabled cloning for now.
# and this Op's Bypass flag is on

BUSY_KEY = '_parexec_busy'

# ------------------------
# helpers
# ------------------------
def _norm_name(par):
    """Case-insensitive name for a Par (tuplet-safe)."""
    nm = getattr(par, 'tupletName', '') or par.name or ''
    return nm.strip().casefold()

def _ext():
    """Return PoseEffectMasterExt (if present), else None."""
    ex = getattr(op('.'), 'ext', None)
    if not ex:
        return None
    return getattr(ex, 'PoseEffectMasterExt', None)


def _guarded(fn):
    # Prevent re-entrancy loops
    if me.fetch(BUSY_KEY, False):
        debug("onValueChange: re-entrant call detected")
        return
    me.store(BUSY_KEY, True)
    try:
        fn()
    finally:
        me.store(BUSY_KEY, False)

# Parameters to watch (case-insensitive)
_WATCH_FILTER = {'landmarkfilter', 'landmarkfiltercsv'}
_WATCH_ACTIVE = {'active'}

# ------------------------
# per-event callbacks
# ------------------------

def onValueChange(par, prev):
    nm  = _norm_name(par)
    ext = _ext()
    if not ext:
        return True

    if nm in WATCH_FILTER:
        _guarded(lambda: ext.ApplyFilter())
    elif nm in WATCH_ACTIVE:
        # Only react to UI/switcher; SetActive() no longer writes Active back
        val = bool(par.eval())
        debug(f"onValueChange ACTIVE {val}")

        _guarded(lambda: ext.SetActive(val))
    return True

def onPulse(par):
    # Optional: add a Pulse param 'ApplyFilter' on the effect to force a rebuild
    if _norm_name(par) == 'applyfilter':
        ext = _ext()
        if ext:
            _guarded(lambda: ext.ApplyFilter())
    return True

# Leave the rest at defaults
def onValuesChanged(changes): return True
def onExpressionChange(par, val, prev): return True
def onExportChange(par, val, prev): return True
def onEnableChange(par, val, prev): return True
def onModeChange(par, val, prev): return True

def onValuesChanged_old(changes):
    """
    Called once at end of frame with all changes.
    We coalesce: if any filter-related param changed, rebuild once.
    If Active changed, toggle allowCooking through the extension.
    """
    if not changes:
        return True

    ext = _ext()
    do_rebuild = False
    active_par = None

    for c in changes:
        nm = _norm_name(c.par)
        if nm in _WATCH_FILTER:
            do_rebuild = True
        elif nm in _WATCH_ACTIVE:
            active_par = c.par  # last one wins; fine because it's a single toggle

    if active_par is not None and ext:
        try:
            ext.SetActive(bool(active_par.eval()))
        except Exception as e:
            print('[PoseEffectMaster parexec] SetActive error:', e)

    if do_rebuild and ext:
        try:
            ext.ApplyFilter()
        except Exception as e:
            print('[PoseEffectMaster parexec] ApplyFilter error:', e)

    return True

