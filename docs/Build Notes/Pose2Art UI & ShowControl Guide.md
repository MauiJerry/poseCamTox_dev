# Pose2Art UI & ShowControl Guide 

## (with `fxCore` parameter exposure)

This is a focused, step‑by‑step build guide for the **UI** and **ShowControl (OSC)** layers, assuming you already have:

- `poseCam` TOX that ingests pose OSC and outputs CHOP channels,
- a basic **EfxSwitch** container that can select one `PoseEffect_*`.

Where I first introduce a TouchDesigner (TD) technique, I explain it in detail; later references are concise.

------

### 1) Master container setup

Create/verify a **master** container (e.g., `PoseEfxSwitcher`) that centralizes UI, switching, and show control.

#### 1.1 Add master custom parameters

Right‑click the container → **Customize Component…**. Create pages and parameters:

**Page: Routing**

- `ActiveEffect` (Menu)
- `Person` (Int, default `1`)

**Page: Background**

- `BGSource` (Menu: `none ndi cam solid`)
- `BGOpacity` (Float 0–1)
- `Premultiply` (Toggle)

**Page: ShowControl**

- `CtlInPort` (Int, e.g., `7500`)
- `CtlOutIP` (Str, e.g., `127.0.0.1`)
- `CtlOutPort` (Int, e.g., `7501`)

*(Optional)* **Page: Fades**

- `Crossfade` (Float 0–1)
- `FadeTime` (Float ms)

> **Why:** Centralizing parameters on the master makes it trivial to bind UI widgets, set up OSC, and automate state.

------

### 2) UI panel (auto‑surfacing `fxCore` parameters)

We’ll show the active effect’s **exposed** parameters in a single panel. Because TD does **not** support arbitrary **per‑parameter tags**, we’ll use a robust **exposure convention**:

- **Preferred (explicit):** put a `Table DAT` named `expose_params` inside each `PoseEffect_*/fxCore` with one parameter name per row (col0 = `parName`).
- **Fallback (implicit):** expose any custom parameter whose **name starts with** `Ui`, `UI`, or `ui` (e.g., `UiColor`, `UiSpeed`).

#### 2.1 Create the UI holder

Inside `PoseEfxSwitcher`:

```
PoseEfxSwitcher/
  uiPanel/                 # container for UI
    paramsPanel (Parameter COMP)   # shows the master’s custom pages
```

- Select `paramsPanel` → set **Owner** to `..` (or leave blank; we’ll set it in code).
- (Optional) Set **Page** to `FX_Active` (we’ll create this page).

#### 2.2 Drop in the UI builder script

Create a `Text DAT` named `fx_ui_builder` inside `PoseEfxSwitcher` and paste:

```python
# fx_ui_builder.py
# Build a page 'FX_Active' on the master, binding controls to the active effect's fxCore.
# Exposure rules:
#  1) If fxCore has a Table DAT 'expose_params', use its rows (par names).
#  2) Else, expose any custom par whose name starts with Ui/UI/ui.

from td import ParMode

MASTER = parent()
PAGE_NAME = 'FX_Active'
EXPOSE_TABLE = 'expose_params'
EXPOSE_PREFIXES = ('Ui', 'UI', 'ui')

def _dbg(msg):
    log = op('LOG')
    log.appendRow(['ui', msg]) if log else print('[FxUi]', msg)

def _get_active_fxcore():
    par = getattr(MASTER.par, 'Activeeffect', None)
    if not par or not par.eval():
        return None
    eff = MASTER.op(par.eval())
    return eff.op('fxCore') if eff else None

def _clear_old_page():
    for page in list(MASTER.customPages):
        if page.name == PAGE_NAME:
            MASTER.deleteCustomPage(page)

def _resolve_exposed_pars(core):
    # 1) explicit table?
    tab = core.op(EXPOSE_TABLE)
    names = []
    if tab and tab.isDAT and tab.numRows > 0:
        names = [tab[i,0].val.strip() for i in range(tab.numRows) if tab[i,0].val.strip()]
    if names:
        pars = []
        for n in names:
            p = getattr(core.par, n, None)
            if p: pars.append(p)
        return pars

    # 2) fallback by prefix
    out = []
    for p in core.customPars:
        if any(p.name.startswith(pref) for pref in EXPOSE_PREFIXES):
            out.append(p)
    return out

def _copy_menu(src, dst):
    try:
        dst.menuNames  = list(src.menuNames)
        dst.menuLabels = list(src.menuLabels)
    except Exception:
        pass

def _add_bound_par(page, src):
    style, name = src.style, src.name
    label = src.label or name

    if style == 'Float':
        p = page.appendFloat(name)
        try: p.normMin, p.normMax = src.normMin, src.normMax
        except: pass
    elif style == 'Int':
        p = page.appendInt(name)
        try: p.normMin, p.normMax = src.normMin, src.normMax
        except: pass
    elif style == 'Toggle':
        p = page.appendToggle(name)
    elif style == 'Menu':
        p = page.appendMenu(name); _copy_menu(src, p)
    elif style in ('RGB','RGBA','Color'):
        p = page.appendRGB(name)
    elif style in ('Str','String'):
        p = page.appendStr(name)
    elif style == 'Pulse':
        p = page.appendPulse(name)
    else:
        p = page.appendFloat(name)

    p.label = label
    p.mode = ParMode.BIND
    p.bindExpr = f"op('{src.owner.path}').par.{name}"
    return p

def rebuild():
    core = _get_active_fxcore()
    _clear_old_page()

    if not core:
        _dbg('No active fxCore.')
        return

    exposed = _resolve_exposed_pars(core)
    if not exposed:
        _dbg(f'No exposed params found on {core.path}.')
        return

    page = MASTER.appendCustomPage(PAGE_NAME)
    for src in exposed:
        _add_bound_par(page, src)

    pnl = MASTER.op('uiPanel/paramsPanel')
    if pnl:
        pnl.par.owner = MASTER
        try: pnl.par.page = PAGE_NAME
        except: pass

    _dbg(f'Built {len(exposed)} controls from {core.path} into {MASTER.path}.{PAGE_NAME}')
```

#### 2.3 Rebuild when the active effect changes

Add a **Parameter Execute DAT** named `fx_ui_events` (on `PoseEfxSwitcher`), with:

```python
# fx_ui_events.py
def onValueChange(par, prev):
    if par.name.lower() == 'activeeffect':
        op('fx_ui_builder').rebuild()
    return
```

> **Authoring flow per effect:** in `PoseEffect_*/fxCore`, either:
>
> - create `expose_params` (Table DAT) listing `Color`, `Speed`, `Size`, etc., **or**
> - rename the parameters to start with `Ui` (e.g., `UiColor`, `UiSpeed`, `UiSize`).

------

### 3) Populate `ActiveEffect` menu automatically

Add a small script to scan children named `PoseEffect_*` and fill the master’s `ActiveEffect` menu.

Create `Text DAT` `effect_menu_builder`:

```python
# effect_menu_builder.py
MASTER = parent()

def _pretty(name:str)->str:
    s = name.replace('PoseEffect_', '').replace('_',' ')
    # CamelCase splitter
    out=[]; token=''
    for ch in s:
        if token and ch.isupper() and not token[-1].isupper():
            out.append(token); token=ch
        else:
            token+=ch
    if token: out.append(token)
    return ' '.join(out).title()

def rebuild_menu():
    par = getattr(MASTER.par, 'Activeeffect', None)
    if not par or not par.isMenu: return

    effs = [c for c in MASTER.children if c.name.startswith('PoseEffect_')]
    effs.sort(key=lambda c: c.name.lower())

    items = [c.name for c in effs]
    labels = [_pretty(n) for n in items]

    current = par.eval() if par.eval() in items else (items[0] if items else '')
    par.menuItems  = items
    par.menuNames  = labels
    par.menuLabels = labels
    if current: par.val = current
```

Call `rebuild_menu()` on project start (Execute DAT `onStart()`) and any time you add/remove effects.

------

### 4) ShowControl (OSC) — listener, feedback, discovery

We’ll add a **separate control port** (not the pose stream), implement a clean namespace, and provide **discovery** + **state feedback**.

#### 4.1 Add the IO operators

Inside `PoseEfxSwitcher`:

- **`oscCtlIn`** (OSC In DAT) — set port to your `CtlInPort` value.
- **`oscCtlOut`** (OSC Out DAT) — set network address to `CtlOutIP:CtlOutPort`.

Because ports/ips on operators aren’t parameter‑bindable, set them on start with a small **Execute DAT** `ctl_ports_on_start`:

```python
# ctl_ports_on_start.py
def onStart():
    m = parent()
    op('oscCtlIn').par.port = int(m.par.Ctlinport.eval())
    out = op('oscCtlOut')
    out.par.address = m.par.Ctloutip.eval()
    out.par.port    = int(m.par.Ctloutport.eval())
    return
```

#### 4.2 Dispatcher for incoming control (Callbacks DAT)

Create a `Text DAT` `osc_dispatch` and assign it to **oscCtlIn → Callbacks DAT**:

```python
# osc_dispatch.py
MASTER = parent()

def _out(addr, *args):
    op('oscCtlOut').sendOSC(addr, list(args))

def _active_fxcore():
    pe = getattr(MASTER.par,'Activeeffect',None)
    eff = MASTER.op(pe.eval()) if pe and pe.eval() else None
    return eff.op('fxCore') if eff else None

def _select_effect(name:str):
    if hasattr(MASTER.par,'Activeeffect'):
        MASTER.par.Activeeffect = name
        _out('/pose2art/fx/active', name)

def _set_person(n:int):
    if hasattr(MASTER.par,'Person'):
        MASTER.par.Person = int(n)
        _out('/pose2art/person', int(n))

def _set_param(name:str, vals):
    core = _active_fxcore()
    if not core: return
    p = getattr(core.par, name, None)
    if not p:
        # try case-insensitive tuplet lookup
        low = name.lower()
        for q in core.pars():
            if q.tupletName.lower()==low: p=q; break
    if not p: return

    # Coerce by type
    try:
        if p.tupletSize>1:
            p.vals = [float(v) for v in vals[:p.tupletSize]]
        elif p.isNumber: p.val = float(vals[0])
        elif p.isToggle or p.isMomentary: p.val = 1 if float(vals[0])>0.5 else 0
        elif p.isMenu: p.val = str(vals[0])
        else: p.val = str(vals[0])
    except: return

    _out(f'/pose2art/fx/param/{p.tupletName}', *p.evalVals)

def _list_effects():
    names = [c.name for c in MASTER.children if c.name.startswith('PoseEffect_')]
    _out('/pose2art/fx/list', *names)

def _param_meta():
    core = _active_fxcore()
    if not core: return
    # replicate UI exposure rules
    tab = core.op('expose_params')
    names = [tab[i,0].val.strip() for i in range(tab.numRows)] if tab and tab.numRows else None
    for p in core.customPars:
        inc = (names and p.name in names) or (not names and p.name.startswith(('Ui','UI','ui')))
        if not inc: continue
        size = getattr(p,'tupletSize',1)
        mi   = getattr(p,'normMin', '')
        ma   = getattr(p,'normMax', '')
        _out('/pose2art/fx/param_meta', p.name, p.label or p.name, p.style, size, mi, ma)

def _state_dump():
    pe = getattr(MASTER.par,'Activeeffect',None)
    pn = getattr(MASTER.par,'Person',None)
    _out('/pose2art/state', 'active', pe.eval() if pe else '', 'person', int(pn.eval()) if pn else 0)

def onReceiveOSC(dat, rowIndex, message, bytes, ts, address, args, peer):
    a = address.strip('/').split('/')
    try:
        if a[0] != 'pose2art': return
        if len(a)==1 or a[1]=='info':
            _out('/pose2art/info', 'Pose2Art TD', 'v0.1'); return
        if a[1]=='fx':
            if a[2]=='list':    _list_effects()
            elif a[2]=='select': _select_effect(str(args[0]))
            elif a[2]=='param':  _set_param(str(a[3]), args)
            elif a[2]=='query':  _param_meta()
        elif a[1]=='person':    _set_person(int(args[0]))
        elif a[1]=='query':     _param_meta()
        elif a[1]=='state':     _state_dump()
    except Exception as e:
        log = op('LOG'); (log.appendRow if log else print)(['osc', f'ERR {e}'])
    return
```

**Supported inbound control (examples):**

- `/pose2art/info`
- `/pose2art/fx/list`
- `/pose2art/fx/select "PoseEffect_Dot"`
- `/pose2art/fx/param/UiSpeed 0.8`
- `/pose2art/fx/query`
- `/pose2art/person 1`
- `/pose2art/state`

> **Tip:** Keep parameter **names stable** across effects (`UiColor`, `UiSpeed`, …) to simplify upstream programming. Discovery (`/pose2art/fx/query`) removes guesswork.

#### 4.3 Feedback on changes (Parameter Execute)

Create `fx_ui_feedback` (Parameter Execute DAT) on the master:

```python
# fx_ui_feedback.py
def onValueChange(par, prev):
    # Echo master state changes
    if par.name.lower() == 'activeeffect':
        op('oscCtlOut').sendOSC('/pose2art/fx/active', [par.eval()])

    if par.name.lower() == 'person':
        op('oscCtlOut').sendOSC('/pose2art/person', [int(par.eval())])

    # Echo FX_Active page parameter changes (bound to fxCore)
    if par.page and par.page.name == 'FX_Active':
        vals = par.evalVals
        op('oscCtlOut').sendOSC(f"/pose2art/fx/param/{par.name}", list(vals))
    return
```

> **Why:** Commercial controllers expect **bidirectional** behavior—when a local change happens, the device **reports back** so UIs stay in sync.

------

### 5) Effect authoring: expose controls

Inside each `PoseEffect_*/fxCore`:

**Option A (explicit):**

- Add a `Table DAT` named `expose_params` with one parameter name per row, e.g.:

```
Color
Size
Speed
Mode
```

**Option B (implicit):**

- Rename parameters to start with `Ui`, e.g. `UiColor`, `UiSize`, `UiSpeed`.

**Recommended styles:**

- `UiColor` → **RGB**
- `UiSize`  → **Float** (set norm min/max for slider range)
- `UiSpeed` → **Float**
- `UiMode`  → **Menu** (set names/labels)

Run:

- `op('effect_menu_builder').rebuild_menu()`
- `op('fx_ui_builder').rebuild()`

Your `uiPanel/paramsPanel` should now show `FX_Active` controls bound to the `fxCore`.

------

### 6) Hook the EfxSwitch and BG compositing (reference)

- Bind `ActiveEffect` to your switch‑logic (Switch TOP/COMP or selective cook).
- Composite underlay before `Out TOP`:
  - `Level TOP` (enable **Pre‑Multiply RGB by Alpha**),
  - `Over TOP` (Input1 = effect output; Input2 = NDI/Cam per `BGSource`),
  - `Out TOP`.

------

### 7) Quick end‑to‑end test plan

1. **Menu:** `effect_menu_builder.rebuild_menu()` populates `ActiveEffect`. Pick `PoseEffect_Dot`.
2. **Expose:** In `PoseEffect_Dot/fxCore`, add `expose_params` with `UiColor`, `UiSize`.
3. **UI:** `fx_ui_builder.rebuild()` → `FX_Active` page appears; tweak values and confirm they change inside `fxCore`.
4. **OSC in:** Send `/pose2art/fx/param/UiSize 30` → size changes; verify feedback `/pose2art/fx/param/UiSize 30` is emitted.
5. **Discovery:** Send `/pose2art/fx/query` → controller receives a stream of `/pose2art/fx/param_meta …` records.
6. **Switch:** Send `/pose2art/fx/select "PoseEffect_Skeleton"` → UI rebuilds; new params appear; feedback sends `/fx/active`.

------

### 8) Troubleshooting & tips

- **Ports won’t change:** use the `onStart` script to set `oscCtlIn` / `oscCtlOut` from master parameters.
- **No controls in UI:** ensure `fxCore` exists; either create `expose_params` **or** prefix parameters with `Ui`.
- **Menus don’t mirror:** set menu items/labels on the `fxCore` parameter; the builder copies them.
- **Frozen dissolves:** prefer **fade‑through‑black** or **snapshot dissolve** to avoid dual‑cooking.
- **Performance:** set inactive effects to **Cook Type = Selective**; keep “heavy” operators inside the active effect only.

------

### 9) Minimal “starter” expose table and parameters (copy block)

1. In `PoseEffect_Dot/fxCore` → **Customize Component**:

- Add `UiColor` (RGB), `UiSize` (Float with min=1, max=50), `UiSpeed` (Float with min=0, max=5)

1. Add `Table DAT` `expose_params` with:

```
UiColor
UiSize
UiSpeed
```

1. On master, run:

```python
op('effect_menu_builder').rebuild_menu()
op('fx_ui_builder').rebuild()
```

------

### 10) OSC reference (inbound to TD)

- `/pose2art/info`
- `/pose2art/state`
- `/pose2art/fx/list`
- `/pose2art/fx/select <string>`
- `/pose2art/fx/param/<name> <vals...>`
- `/pose2art/fx/query`  *(param metadata of active effect)*
- `/pose2art/person <int>`

**Outbound feedback (from TD):**

- `/pose2art/info <name> <version>`
- `/pose2art/state active <name> person <int>`
- `/pose2art/fx/list <names…>`
- `/pose2art/fx/active <name>`
- `/pose2art/fx/param/<name> <vals…>`
- `/pose2art/fx/param_meta <name> <label> <style> <size> <min> <max>`

------

This guide gives you a repeatable **UI and ShowControl** layer that behaves like a pro media device: **discoverable**, **bidirectional**, and **modular**. Drop in new `PoseEffect_*` TOXs, declare what’s exposed via `expose_params` **or** `Ui*` prefix, and the master will surface them to both **local UI** and **OSC controllers** automatically.