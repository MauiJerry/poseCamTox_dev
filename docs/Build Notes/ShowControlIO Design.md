# ShowControlIO Design

Exactly 👍

Here’s the clean design pattern for **ShowControlIO**:

------

## 1. Where `osc_router.py` lives

- Keep all your extension scripts together in the **`/scripts` folder** (same place as `PoseEfxSwitchExt.py`, `PoseEffectMasterExt.py`, etc.).
- Name it **`osc_router.py`** (or `ShowControlIORouter.py` if you want to match the COMP name).

That way you have **one canonical scripts folder**, version-controlled, and TD COMPs just “mount” those as extensions.

------

## 2. The ShowControlIO COMP

At the **top level** of your `.toe` (next to `PoseCamIn`, `PersonRouter`, `EfxSwitch`, `UI`):

- Create a **Base COMP** named `ShowControlIO`.
- Inside it, drop:
  - an **OSC In DAT** (listening on your show-control port, e.g. 9001),
  - an **OSC Out DAT** (feedback/echo back to controller),
  - a **Text DAT** named `osc_router` with the code below.
- Hook the **OSC In DAT → DAT Execute DAT**; in the callback, call `op('osc_router').module.route(dat, row)`.

------

## 3. osc_router.py (full module)

```python
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
```

------

## 4. Usage

From a controller you can send:

- `/pose2art/fx/list` → returns each effect’s `(opName, displayLabel)`.
- `/pose2art/fx/query` → returns all active fxCore’s exposed params and their values.
- `/pose2art/fx/param/ColorType random` → sets `ColorType=random` on active fxCore, echoes back.

------

✅ So yes:

- Put `osc_router.py` in the **same scripts folder** as the rest.
- Create a new **ShowControlIO COMP** at the top level.
- Inside it, add an **OSC In/Out**, a **Text DAT** named `osc_router` with that code, and a **DAT Execute** to call `route()`.

Do you want me to also stub the **DAT Execute** code (like you had for `poseEfxSwitch_exec_init.py`) so you can paste it straight in?