# PoseEfxSwitch / parexec1 (Parameter Execute DAT callbacks)

# Canvas defaults that should trigger a guarded meta rebuild (if you use one)

CANVAS_PARAMS = {'defaultcanvasw', 'defaultcanvash'} # compare lower case

# Optional pulse param name to force a manual refresh
PULSE_REFRESH_META = 'refreshmeta'
PULSE_REBUILD_MENU = 'rebuildeffectsmenu'  # if your parm is "RebuildEffectsMenu", this still matches

def onStart():
    debug('[parexec1] onStart')
    return True
    
def _norm(s): 
    return (s or '').strip().casefold()


def _update_guard():
    gm = op('guard_meta')
    if not gm:
        debug('[parexec1] Missing guard_meta Text DAT')
        return
    try:
        debug('[parexec1] guard_meta._update_guard, call module.update_guard()')
        gm.module.update_guard()
    except Exception as e:
        debug('[parexec1] guard_meta.update_guard() error:', e)

def onValueChange(name1par, prev):
    """Called when any watched parameter's value changes."""
    name_l = _norm(getattr(par, 'tupletName', '') or par.name)

    debug(f'[parexec1] onValueChange: {par.name} {name1} from {prev} to {par.eval()}')
    
    if par is None:
        return True

    
    # 1) Guarded meta refresh when canvas defaults change
    if name1 in CANVAS_PARAMS:
        _update_guard()

    # 2) Switch behaviors
    if name1 == 'activeeffect':
        op('.').ext.PoseEfxSwitchExt.OnActiveEffectChanged()
    elif name1 == 'activeindex':
        op('.').ext.PoseEfxSwitchExt.OnActiveIndexChanged()
    elif name1 == 'rebuildfefectsMenu':
        op('.').ext.PoseEfxSwitchExt.BuildEffectsMenu()
    else:
        debug(f'[parexec1] onValueChange: unhandled param {par.name} {name_l}')
    return True

def onPulse(par):
    """Called when any watched pulse parameter is pressed."""
    if par is None:
        return True
    name_l = _norm(getattr(par, 'tupletName', '') or par.name)

    debug(f'[parexec1] onPulse: {par.name} {name_l}')

    if name_l == PULSE_REFRESH_META:
        _update_guard()
        return True

    if name_l == 'rebuildeffectsmenu':
        op('.').ext.PoseEfxSwitchExt.BuildEffectsMenu()

    if par.name == 'scanlandmarkmasks':
        op('.').ext.PoseEfxSwitchExt.ScanAndBuildMaskMenu()

    return True

def onExpressionChange(par, prev):
    """If canvas defaults are expression-driven, refresh on expression change too."""
    name_l = _norm(getattr(par, 'tupletName', '') or par.name)
    
    if par and par.name in CANVAS_PARAMS:
        _update_guard()
    return True

def onExportChange(par, prev):
    if par and par.name in CANVAS_PARAMS:
        _update_guard()
    return True
