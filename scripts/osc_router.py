# /scripts/osc_router.py
#
# Attach as a Text DAT inside /ShowControlIO named "osc_router"
# A DAT Execute DAT watches the OSC In DAT and calls route(dat,row)

from typing import Any

def _fxswitch():
    return op('/EfxSwitch')

def _active_fx():
    sw = _fxswitch()
    key = (sw.par.ActiveEffect.eval() or '').strip()
    return sw.op('effects/' + key) if key else None

def _active_fxcore():
    fx = _active_fx()
    return fx.op('fxCore') if fx else None

def _discover_params(core):
    """
    Discovery = Ui* parameters PLUS any in fxCore/expose_params (single column).
    Same rule as UI_Builder.
    """
    names = set()
    # A) Ui* prefix
    for p in core.customPars:
        if p.name.startswith(('Ui','UI','ui')):
            names.add(p.name)
    # B) expose_params DAT
    t = core.op('expose_params')
    if t:
        for r in t.rows():
            if r and r[0].val.strip():
                names.add(r[0].val.strip())
    return [n for n in sorted(names) if hasattr(core.par, n)]

def _send_feedback(addr: str, *args: Any):
    """Send OSC reply out ShowControlIO/osc_out1"""
    out = op('osc_out1')
    if out:
        out.sendOSC(addr, list(args))

def route(dat, row):
    """Main entrypoint called by DAT Execute on OSC In"""
    try:
        addr = row[0].val  # OSC address
        args = [c.val for c in row[1:]]
    except Exception as e:
        debug("osc_router.route bad row", e)
        return

    if addr == '/pose2art/fx/list':
        _handle_list()
    elif addr == '/pose2art/fx/query':
        _handle_query()
    elif addr.startswith('/pose2art/fx/param/'):
        _handle_param(addr, args)
    else:
        debug("osc_router: unhandled", addr, args)

def _handle_list():
    sw = _fxswitch()
    effs = [c for c in sw.op('effects').children if c.name.startswith('PoseEffect_')]
    labels = []
    for fx in effs:
        # prefer UiDisplayName, else derive from OP name
        disp = getattr(fx.par, 'Uidisplayname', None)
        if disp:
            val = (disp.eval() or '').strip()
            if val and val.lower() != 'master':
                labels.append(val)
                continue
        labels.append(fx.name.replace('PoseEffect_', '').replace('_',' ').title())
    # Send back as list of (opName,label) pairs
    for fx,label in zip(effs, labels):
        _send_feedback('/pose2art/fx/list', fx.name, label)

def _handle_query():
    core = _active_fxcore()
    if not core:
        return
    for pname in _discover_params(core):
        p = getattr(core.par, pname)
        val = p.eval()
        _send_feedback('/pose2art/fx/param', pname, str(val))

def _handle_param(addr, args):
    """OSC param set: /pose2art/fx/param/<ParamName> <val>"""
    core = _active_fxcore()
    if not core:
        return
    try:
        pname = addr.split('/')[-1]
        p = getattr(core.par, pname, None)
        if not p:
            debug("osc_router: no param", pname)
            return
        # Simple type coercion
        if p.isFloat or p.isInt:
            p.val = float(args[0])
        elif p.isRGB or p.tupletSize > 1:
            for i,v in enumerate(args):
                if i < p.tupletSize:
                    p[i] = float(v)
        else:
            p.val = str(args[0])
        # echo back
        _send_feedback('/pose2art/fx/param', pname, str(p.eval()))
    except Exception as e:
        debug("osc_router param err", e)
