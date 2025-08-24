# PoseEfxSwitch / parexec1 (Parameter Execute DAT callbacks)

# Canvas defaults that should trigger a guarded meta rebuild (if you use one)

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
    
    debug(f'[parexec1] onValueChange: {par.name} from {prev} to {par.eval()}')
    
    if par is None:
        return True

    # 1) Guarded meta refresh when canvas defaults change
    if par.name in CANVAS_PARAMS:
        _update_guard()

    # 2) Switch behaviors
    if par.name == 'ActiveEffect':
        op('.').ext.PoseEfxSwitchExt.OnActiveEffectChanged()
    elif par.name == 'ActiveIndex':
        op('.').ext.PoseEfxSwitchExt.OnActiveIndexChanged()
    elif par.name == 'RebuildEffectsMenu':
        op('.').ext.PoseEfxSwitchExt.BuildEffectsMenu()
    return True

def onPulse(par):
    """Called when any watched pulse parameter is pressed."""
    if par is None:
        return True

    debug(f'[parexec1] onPulse: {par.name}')
    
    if par.name == REFRESH_PULSE:
        _update_guard()

    if par.name == 'RebuildEffectsMenu':
        op('.').ext.PoseEfxSwitchExt.BuildEffectsMenu()

    return True

def onExpressionChange(par, prev):
    """If canvas defaults are expression-driven, refresh on expression change too."""
    if par and par.name in CANVAS_PARAMS:
        _update_guard()
    return True

def onExportChange(par, prev):
    if par and par.name in CANVAS_PARAMS:
        _update_guard()
    return True
