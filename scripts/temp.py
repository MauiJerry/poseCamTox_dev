# PoseEffect_Master / parexec1  (Parameter Execute DAT script)

BUSY_KEY = '_parexec_busy'

def _norm_name(par):
    nm = getattr(par, 'tupletName', '') or par.name or ''
    return nm.strip().casefold()

def _ext():
    ex = getattr(op('.'), 'ext', None)
    return getattr(ex, 'PoseEffectMasterExt', None) if ex else None

# Which parameters we watch (case-insensitive)
WATCH_FILTER = {'landmarkfilter', 'landmarkfiltercsv'}
WATCH_ACTIVE = {'active'}

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