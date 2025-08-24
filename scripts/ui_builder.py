# /UI/UI_Builder.py
# Build an FX_Active page on the master (/EfxSwitch), binding to active fxCore params.
# Exposure rules:
#   1) explicit Table DAT 'expose_params' on fxCore
#   2) OR implicit Ui*/UI*/ui* prefix

EXPOSE_TABLE = 'expose_params'
EXPOSE_PREFIXES = ('Ui','UI','ui')

def _fxswitch():
    return op('/EfxSwitch')

def _active_fxcore():
    par = getattr(_fxswitch().par, 'Activeeffect', None)
    if not par or not par.eval():
        return None
    eff = _fxswitch().op(par.eval())
    return eff.op('fxCore') if eff else None

def discover_params(core):
    out = []
    # 1) explicit table
    tab = core.op(EXPOSE_TABLE)
    if tab and tab.isDAT and tab.numRows > 0:
        for r in tab.rows():
            name = r[0].val.strip()
            if not name: continue
            p = getattr(core.par, name, None)
            if p: out.append(p)
        return out
    # 2) implicit Ui* prefix
    for p in core.customPars:
        if any(p.name.startswith(pref) for pref in EXPOSE_PREFIXES):
            out.append(p)
    return out

def rebuild():
    master = _fxswitch()
    core = _active_fxcore()
    if not core: 
        debug('No active fxCore'); return
    # delete old FX_Active page
    for page in list(master.customPages):
        if page.name == 'FX_Active':
            master.deleteCustomPage(page)
    pars = discover_params(core)
    if not pars:
        debug(f'No exposed params on {core.path}'); return
    page = master.appendCustomPage('FX_Active')
    for src in pars:
        dst = page.append(src.style, src.name)
        dst.label = src.label or src.name
        dst.mode = ParMode.BIND
        dst.bindExpr = f"op('{src.owner.path}').par.{src.name}"
    debug(f'Built {len(pars)} controls from {core.path}')

