# PoseCam Demo Top Layout

Short answer: yes—put **UI** and **ShowControl I/O** in **top‑level COMPs** alongside the processing chain. Keep only tiny helpers inside `PoseEfxSwitcher` (e.g., a `select(effectName)` method and a `get_param_registry()` that enumerates each `PoseEffect_*`’s exposed params). This keeps the switcher reusable and makes the whole demo easier to run from a single `.toe`.

Below is a concise “drop‑in” architecture and the minimal code you need to move to top‑level without rewriting everything we already built.

------

# Top‑level layout (recommended)

```
/project1
  /PoseCamIn          # OSC/NDI ingest, bundle fan-out → CHOPs
  /PersonRouter       # p1/p2/... filter → per-person CHOPs
  /EfxSwitch          # holds PoseEffect_* containers, output TOP/CHOP
  /OutCompositor      # optional background/NDI-under compositing → out TOP
  /UI                 # panels/buttons built from discovered FX + params
  /ShowControlIO      # OSC In/Out for show-control; discovery + state feedback
```

- **PoseCamIn**: already in your plan; no changes.
- **PersonRouter**: already in your plan; no changes.
- **EfxSwitch**: keep selection & crossfade/local logic here, but no OSC or UI responsibilities.
- **OutCompositor**: compositing right before out; switch/over nodes go here.
- **UI**: TD panel UI builder lives here (buttons, sliders built from FX param registry).
- **ShowControlIO**: one **OSC In DAT** (control), one **OSC Out DAT** (feedback), plus a **Text DAT** for the router script.

> This matches the “PoseCamDemo.toe” you described and preserves the clean separation of concerns.

------

# Does this change much of the code?

Only **paths** and **initialization points** change. The logic we wrote for:

- listing effects,
- selecting active FX,
- reading per‑FX exposed parameters,
- sending/receiving `/pose2art/*` messages

…stays the same. You’ll just call those methods **from `/ShowControlIO`** instead of from inside `/EfxSwitch`.

Concretely:

- Replace `op('../EfxSwitch')` style lookups with absolute or exported OP shortcuts: e.g., set an **OP shortcut** `efx = /EfxSwitch` and `ui = /UI` and reference `op.efx`, `op.ui` from scripts.
- Move the UI‑builder script into `/UI/UI_Builder` (Text DAT) and call it once on project start and whenever FX change.
- Put the OSC router into `/ShowControlIO/osc_router` (Text DAT) and set it as the **Callback DAT** on your **OSC In DAT**.

Everything else—message addresses, parameter exposure schema, etc.—is unchanged.

------

# Parameter exposure (no change to the convention)

Keep the **per‑effect** declarative table:

- Inside each `PoseEffect_*` container, add a **Table DAT** named `expose_params`:

| name     | label     | style | size | min  | max  | default | group  |
| -------- | --------- | ----- | ---- | ---- | ---- | ------- | ------ |
| Color    | Color     | rgba  | 4    | 0    | 1    | 1,1,1,1 | Look   |
| Speed    | Speed     | float | 1    | 0    | 5    | 1.0     | Motion |
| DotCount | Dot Count | int   | 1    | 0    | 500  | 150     | Render |

This lets the **UI builder** and **OSC router** discover what to show and what to accept, without you hard‑coding parameter names.

> If you already have custom parameters on the FX core, add a small helper in the FX to auto‑materialize that table (optional). Using the table is simple & robust, so I recommend sticking with it.

------

# Minimal code you can paste in

## 1) `/EfxSwitch/efx_api` — tiny API for the world to call

Add a **Text DAT** with:

```python
# /EfxSwitch/efx_api

def list_effects():
    """Return list of PoseEffect_* COMP names in /EfxSwitch."""
    return [c.name for c in parent().children if c.name.startswith('PoseEffect_')]

def active_effect():
    """Return the currently active PoseEffect_* name."""
    sw = parent().op('switch1')  # your CHOP/TOP Switch
    try:
        idx = int(sw.par.index.eval())
    except:
        idx = 0
    names = list_effects()
    return names[idx] if 0 <= idx < len(names) else (names[0] if names else '')

def select_effect(name: str):
    """Activate effect by exact name; updates switch index."""
    names = list_effects()
    if name in names:
        idx = names.index(name)
        parent().op('switch1').par.index = idx
        return True
    return False

def param_registry():
    """Yield (effect_name, [paramMeta...]) discovered from expose_params DAT."""
    out = []
    for c in parent().children:
        if not c.name.startswith('PoseEffect_'):
            continue
        meta = []
        t = c.op('expose_params')
        if t and t.numRows > 1:
            hdr = [h.val for h in t.row(0)]
            for r in t.rows()[1:]:
                row = dict(zip(hdr, [c_.val for c_ in r]))
                meta.append(row)
        out.append((c.name, meta))
    return out

def set_param(effect_name: str, param_name: str, values):
    """Set a parameter on an effect by name; supports list/tuple or scalar."""
    c = parent().op(effect_name)
    if not c:
        return False
    p = getattr(c.par, param_name, None)
    if not p:
        return False
    # coerce sizes
    if hasattr(p, 'val'):
        try:
            p.val = values if not isinstance(values, (list, tuple)) else values[0]
        except:
            return False
    else:
        # multi-value (e.g., RGBA)
        try:
            p = getattr(c.par, param_name)  # Par
            for i, v in enumerate(values):
                p[i] = v
        except:
            return False
    return True
```

> Adjust `switch1` path if your switch node has a different name. If you switch CHOPs and TOPs separately, wrap those two too.

------

## 2) `/ShowControlIO/osc_router` — OSC in → dispatch, and feedback helpers

Create a **Text DAT** and set it as the **Callbacks DAT** on your **OSC In DAT** (`oscin1`). Create an **OSC Out DAT** named `oscout1`.

```python
# /ShowControlIO/osc_router

def _efx():
    return op('^/EfxSwitch/efx_api') or op('/EfxSwitch/efx_api')

def _ui():
    return op('/UI/UI_Builder')

def _send(addr, *args):
    """Send an OSC message via oscout1."""
    out = parent().op('oscout1')
    # TouchDesigner OSC Out DAT has a python method sendOSC
    out.sendOSC(addr, list(args))

def _send_fx_list():
    names = _efx().module.list_effects()
    for n in names:
        _send('/pose2art/fx/list', n)

def _send_active():
    n = _efx().module.active_effect()
    _send('/pose2art/fx/active', n)

def _send_param_meta():
    # Flatten: (fx, name, label, style, size, min, max, default, group)
    for fx, metas in _efx().module.param_registry():
        for m in metas:
            _send('/pose2art/fx/param_meta',
                  fx, m.get('name',''), m.get('label',''), m.get('style',''),
                  int(float(m.get('size', '1'))),
                  float(m.get('min','0')), float(m.get('max','1')),
                  m.get('default',''), m.get('group',''))

def _handle_fx_param(addr, args):
    # /pose2art/fx/param/<ParamName>  [value...]
    parts = addr.strip('/').split('/')
    if len(parts) < 4:
        return
    pname = parts[3]
    # If caller specified which FX in args[0] as a string, pop it.
    # Else apply to active effect.
    if args and isinstance(args[0], str) and args[0].startswith('PoseEffect_'):
        fx = args[0]; vals = args[1:]
    else:
        fx = _efx().module.active_effect(); vals = args
    ok = _efx().module.set_param(fx, pname, vals)
    if ok:
        _send('/pose2art/fx/param_ack', fx, pname)

def _rebuild_ui():
    b = _ui()
    if b and hasattr(b.module, 'rebuild'):
        b.module.rebuild()

def onReceive(dat, rowIndex, message, bytes, timeStamp, address, args, peer):
    """
    Map incoming OSC to actions:
      /pose2art/info
      /pose2art/state
      /pose2art/fx/list
      /pose2art/fx/query
      /pose2art/fx/select <name>
      /pose2art/fx/param/<name> [values...]  (optionally first arg = FX name)
      /pose2art/person <int>
      /pose2art/bg/source <ndi|cam|solid|none>
      /pose2art/ui/rebuild
    """
    try:
        if address == '/pose2art/info':
            _send('/pose2art/info', 'Pose2Art TD demo', 'v1')
            _send_active(); _send_fx_list()

        elif address == '/pose2art/state':
            _send_active(); _send_fx_list(); _send_param_meta()

        elif address == '/pose2art/fx/list':
            _send_fx_list()

        elif address == '/pose2art/fx/query':
            _send_param_meta()

        elif address == '/pose2art/fx/select':
            if args and isinstance(args[0], str):
                if _efx().module.select_effect(args[0]):
                    _send_active()
                    _rebuild_ui()

        elif address.startswith('/pose2art/fx/param/'):
            _handle_fx_param(address, args)

        elif address == '/pose2art/person':
            # forward to PersonRouter
            pr = op('/PersonRouter')
            if args:
                pr.par.Personid = int(args[0])

        elif address == '/pose2art/bg/source':
            # forward to OutCompositor (implement par Source = ndi/cam/solid/none)
            oc = op('/OutCompositor')
            if args:
                oc.par.Source = str(args[0])

        elif address == '/pose2art/ui/rebuild':
            _rebuild_ui()

    except Exception as e:
        debug = op('debug') if parent().op('debug') else None
        if debug: debug.write(str(e))
```

> If your TD build doesn’t expose `sendOSC` on OSC Out DAT, swap to a **CHOP/DAT bridge**: append rows to a Table DAT and wire it into the OSC Out DAT (set `Format` = Table).

------

## 3) `/UI/UI_Builder` — build the panel from the registry

Create a **Base COMP** `/UI` and inside it a **Text DAT** `UI_Builder`:

```python
# /UI/UI_Builder

def container():
    return parent()  # /UI

def clear_ui():
    for c in container().children:
        if c.isPanel:
            c.destroy()

def rebuild():
    clear_ui()
    efx_api = op('/EfxSwitch/efx_api').module
    # Top bar: FX dropdown + select button
    fxnames = efx_api.list_effects()
    drop = container().create(comboCOMP, 'fxCombo')
    drop.par.Menu = '\n'.join(fxnames)
    drop.par.Alignorder = 1
    btn = container().create(buttonCOMP, 'fxSelect')
    btn.par.Alignorder = 2
    btn.par.label = 'Select'
    # Bind select click
    def onClick(panelValue):
        name = drop.par.selectedlabel.eval()
        if name:
            efx_api.select_effect(name)
            op('/ShowControlIO/osc_router').module._send('/pose2art/fx/active', name)
            rebuild()  # refresh parameter panel for new FX
        return
    btn.click = onClick

    # Active FX label
    lab = container().create(textTOP, 'fxLabel')
    lab.par.alignorder = 0
    lab.par.text = 'Active: ' + efx_api.active_effect()

    # Params grid
    y = 80
    for fx, metas in efx_api.param_registry():
        if fx != efx_api.active_effect():
            continue
        for m in metas:
            pname = m.get('name',''); label = m.get('label', pname)
            style = m.get('style','float'); size = int(float(m.get('size','1')))
            vmin = float(m.get('min','0')); vmax = float(m.get('max','1'))
            default = m.get('default','')
            # Label
            t = container().create(textTOP, f"lbl_{pname}")
            t.par.text = label
            t.par.t = y
            # Control
            if style in ('float','int'):
                s = container().create(sliderCOMP, f"sl_{pname}")
                s.par.t = y + 20
                s.par.min = vmin; s.par.max = vmax
                # Set from current Par if available
                fxop = op('/EfxSwitch').op(efx_api.active_effect())
                par = getattr(fxop.par, pname, None)
                if par:
                    try: s.par.value0 = float(par.eval())
                    except: pass
                # on value change → set param
                def make_cb(nm):
                    def _cb(v):
                        efx_api.set_param(efx_api.active_effect(), nm, [float(v)])
                        op('/ShowControlIO/osc_router').module._send(f"/pose2art/fx/param_ack", efx_api.active_effect(), nm)
                        return
                    return _cb
                s.panel.value = make_cb(pname)

            elif style == 'rgba':
                # 4 sliders stacked
                comps = []
                for i, axis in enumerate('rgba'):
                    ss = container().create(sliderCOMP, f"sl_{pname}_{axis}")
                    ss.par.t = y + 20 + i*26
                    ss.par.min = vmin; ss.par.max = vmax
                    comps.append(ss)
                fxop = op('/EfxSwitch').op(efx_api.active_effect())
                par = getattr(fxop.par, pname, None)
                if par:
                    for i in range(min(4, len(par))):
                        comps[i].par.value0 = float(par[i])
                def make_cb4(nm):
                    def _cb(_):
                        vals = [float(c.par.value0) for c in comps]
                        efx_api.set_param(efx_api.active_effect(), nm, vals)
                        op('/ShowControlIO/osc_router').module._send(f"/pose2art/fx/param_ack", efx_api.active_effect(), nm)
                        return
                    return _cb
                for c in comps: c.panel.value = make_cb4(pname)
                y += 3*26  # extra height for stacked sliders

            y += 50

    # Simple layout
    for p in container().children:
        if p.isPanel:
            p.par.align = 'top'
            p.par.w = 320
```

- Trigger a first build on startup by adding a **Startup Script** (or run `op('/UI/UI_Builder').module.rebuild()` once).
- This is deliberately minimal; style it however you like.

------

# Wiring tips

- Set **OP Shortcuts** on `/project1`:
  - `efx` → `/EfxSwitch`
  - `ui` → `/UI`
  - `io` → `/ShowControlIO`
- In `/ShowControlIO`:
  - `oscin1`: set **Callbacks DAT** to `osc_router`.
  - `oscout1`: set IP/Port to the **external show controller** (or loopback to your Tk app).
- In `/OutCompositor`: add a **TOP Switch** or **Composite TOP** fed from
  - `EfxSwitch` output TOP,
  - and optionally `NDI In TOP` or `Video Device In TOP`, plus a bypassable branch.

------

# Address space (unchanged)

We’ll keep the same OSC addresses we’ve been using:

- **Queries/feedback**
  - `/pose2art/info`
  - `/pose2art/state`
  - `/pose2art/fx/list` (TD → controller: multiple messages, one per FX name)
  - `/pose2art/fx/active` (TD → controller)
  - `/pose2art/fx/param_meta` (TD → controller: `(fx,name,label,style,size,min,max,default,group)`)
- **Control**
  - `/pose2art/fx/select <name>`
  - `/pose2art/fx/param/<ParamName> [<FXName?>] <values...>`
    - if `FXName` omitted, applies to active FX
  - `/pose2art/person <int>`
  - `/pose2art/bg/source <ndi|cam|solid|none>`
  - `/pose2art/ui/rebuild`

This allows a **bidirectional** controller (your Tk tester or a lighting console) to *discover* capabilities and mirror UI state.

------

# Why this split works well

- **Reusability**: `EfxSwitch` remains a clean, embeddable module for any project.
- **Maintainability**: all show‑control logic and networking are centralized in `/ShowControlIO`.
- **Operator‑friendly**: `/UI` can be themed/expanded without touching switcher internals.
- **Scales**: adding a new `PoseEffect_*` only requires dropping it under `/EfxSwitch` and defining its `expose_params` table—UI & OSC discovery pick it up automatically.

If you want, I can also supply a tiny `/OutCompositor` preset (ndi/cam/solid/none) and a template `expose_params` DAT you can copy into each FX.

---

Yes—Totally. TouchDesigner lets you run **multiple OSC In DATs** at the same time, each bound to a different UDP port. That’s a clean way to keep high‑rate pose data separate from human‑scale show‑control.

### Recommended setup

- **/PoseCamIn/osc_pose (OSC In DAT)** → Port `7400` (or your poseCam sender port)
  - High‑frequency pose bundles → feed a Script CHOP that fans out channels.
- **/ShowControlIO/osc_ctl (OSC In DAT)** → Port `7500` (or whatever you picked for control)
  - Low‑rate control messages → callbacks that drive UI/EfxSwitch/etc.

### How to wire it (step‑by‑step)

1. Drop two OSC In DATs anywhere (I like putting them in their functional COMPs):

   - `PoseCamIn/osc_pose` → set **Network Port** = `7400`. Leave **Network Address** blank to listen on all interfaces.
   - `ShowControlIO/osc_ctl` → set **Network Port** = `7500`.

2. For `osc_pose`:

   - Leave **Callbacks DAT** empty (you’ll read the DAT rows from your Script CHOP that does the fan‑out).

3. For `osc_ctl`:

   - Set **Callbacks DAT** = your show‑control router script (e.g., `/ShowControlIO/osc_router` from earlier).

4. (Optional) Put an **Execute DAT (onStart)** in `/ShowControlIO` to programmatically set ports from top‑level params:

   ```python
   # /ShowControlIO/ctl_ports_on_start
   def onStart():
       m = op('/ShowControlIO')
       op('osc_ctl').par.port = int(op('/').par.Ctlinport.eval())  # if you keep a top-level param
       out = op('oscout1')
       out.par.address = op('/').par.Ctloutip.eval()
       out.par.port    = int(op('/').par.Ctloutport.eval())
       return
   ```

### Good practices

- **One socket per port per process:** only one operator (in one TD instance) can bind a given UDP port. If you see “port in use,” change the port or stop the other listener.
- **Different traffic profiles:** keeping pose (hundreds of msgs/sec) on its own port prevents control latency and makes debugging easier.
- **Callbacks isolation:** give `osc_ctl` its own callbacks DAT so you never parse high‑rate pose rows in Python callbacks by accident.
- **Address filtering:** if you ever *must* use one port, you can still split by OSC address prefix (`/pose/...` vs `/pose2art/...`), but it’s less robust.
- **CHOP vs DAT:** use **OSC In DAT** for structured messages and routing to Python; use **OSC In CHOP** only when you need continuous numeric channels published directly by the sender (not typical for your bundled pose).

### Minimal sanity check

- Start TD, confirm both `osc_pose` and `osc_ctl` show green “Active.”
- From your Tk tester:
  - Send `/pose2art/info` to `127.0.0.1:7500` → see log/feedback.
- From PoseCamPC:
  - Send pose bundles to `127.0.0.1:7400` → confirm your Script CHOP channels update.
- If either DAT is dark red: wrong port or firewall/permission issue.

That’s it—two OSC In DATs is the standard way to do exactly what you want.