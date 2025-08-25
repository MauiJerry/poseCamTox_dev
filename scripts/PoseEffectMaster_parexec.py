# PoseEffect_Master / parexec  (TouchDesigner Parameter Execute DAT script)
# This DAT lives inside each PoseEffect_* (via the master clone source).
# It calls the effect's extension to rebuild landmark selection or toggle cooking.

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

# Parameters to watch (case-insensitive)
_WATCH_FILTER = {'landmarkfilter', 'landmarkfiltercsv'}
_WATCH_ACTIVE = {'active'}

# ------------------------
# per-event callbacks
# ------------------------

def onValueChange(par, prev):
    """
    Fires for each parameter as it changes.
    We keep this light-weight and let onValuesChanged() coalesce multiple changes.
    """
    # If you prefer immediate rebuild for single changes, you can uncomment:
    # if _norm_name(par) in _WATCH_FILTER:
    #     ext = _ext()
    #     if ext: ext.ApplyFilter()
    return True

def onValuesChanged(changes):
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

def onPulse(par):
    """
    Optional: if you add a Pulse parameter named 'ApplyFilter' on PoseEffect_Master,
    this lets you force a rebuild from the UI.
    """
    nm = _norm_name(par)
    if nm in ('applyfilter',):
        ext = _ext()
        if ext:
            try:
                ext.ApplyFilter()
            except Exception as e:
                print('[PoseEffectMaster parexec] ApplyFilter (pulse) error:', e)
    return True

def onExpressionChange(par, val, prev):
    # No special handling needed; keep default True.
    return True

def onExportChange(par, val, prev):
    # No special handling needed; keep default True.
    return True

def onEnableChange(par, val, prev):
    # No special handling needed; keep default True.
    return True

def onModeChange(par, val, prev):
    # No special handling needed; keep default True.
    return True
