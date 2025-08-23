
# PoseEfxSwitch / parexec1 (Parameter Execute DAT callbacks)

# Canvas defaults that should trigger a guarded meta rebuild
CANVAS_PARAMS = {'Defaultcanvasw', 'Defaultcanvash'}

# Optional pulse param name to force a manual refresh
REFRESH_PULSE = 'Refreshmeta'

def _update_guard():
    gm = op('guard_meta')
    if not gm:
        debug('[parexec1] Missing guard_meta Text DAT')
        return
    try:
        gm.module.update_guard()
    except Exception as e:
        debug('[parexec1] guard_meta.update_guard() error:', e)

def onValueChange(par, prev):
    """Called when any watched parameter's value changes."""
    if par is None:
        return True

    # 1) Guarded meta refresh when canvas defaults change
    if par.name in CANVAS_PARAMS:
        _update_guard()

    # 2) Existing PoseEfxSwitch behaviors
    if par.name == 'ActiveEffect':
        op('.').ext.PoseEfxSwitchExt.OnActiveEffectChanged()
    elif par.name == 'ActiveIndex':
        op('.').ext.PoseEfxSwitchExt.OnActiveIndexChanged()
    elif par.name == 'RebuildEffectsMenu':
        # If this is a toggle/bool instead of a pulse, handle it here too
        op('.').ext.PoseEfxSwitchExt.BuildEffectsMenu()
    return True

def onPulse(par):
    """Called when any watched pulse parameter is pressed."""
    if par is None:
        return True

    # Allow a manual refresh
    if par.name == REFRESH_PULSE:
        _update_guard()

    # If RebuildEffectsMenu is a pulse param, handle it here as well
    if par.name == 'RebuildEffectsMenu':
        op('.').ext.PoseEfxSwitchExt.BuildEffectsMenu()

    return True

def onExpressionChange(par, prev):
    """If canvas defaults are expression-driven, refresh on expression change too."""
    if par and par.name in CANVAS_PARAMS:
        _update_guard()
    return True

def onExportChange(par, prev):
    # Not strictly needed for this use, but safe to keep symmetrical behavior
    if par and par.name in CANVAS_PARAMS:
        _update_guard()
    return True
