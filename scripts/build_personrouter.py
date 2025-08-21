# create Person Router stub
# build_personrouter.py
# Run this ONCE inside your empty PersonRouter Base COMP.
# It creates:
# - CHOP In "in1" (pose channels from PoseCam)
# - Select CHOP "router_sel" using All/Selected params
# - Null CHOP "out1" (final Out CHOP)
# - DAT In "meta_in" (meta from PoseCam)
# - Null DAT "meta_out" (final Out DAT)
# - Custom parameters: All (toggle), Selid (int)
# Safe to re-run: it won't duplicate existing ops/params.

c = parent()  # the PersonRouter COMP

def op_get_or_create(family, name):
    o = c.op(name)
    if o: return o
    return c.create(family, name)

# --- Operators ---
in1 = op_get_or_create(chopIn, 'in1')              # CHOP In
sel = op_get_or_create(selectCHOP, 'router_sel')   # Select CHOP
out1 = op_get_or_create(nullCHOP, 'out1')          # Null CHOP -> Out

meta_in = op_get_or_create(datIn, 'meta_in')       # DAT In
meta_out = op_get_or_create(nullDAT, 'meta_out')   # Null DAT -> Out

# Wiring
sel.inputConnectors[0].connect(in1)
out1.inputConnectors[0].connect(sel)
meta_out.inputDATs = [meta_in]

# Make out nodes the COMP outputs
if not any(isinstance(o, type(out1)) and o.isOutput for o in c.children):
    out1.nodeX, out1.nodeY = 400, 0
    out1.par.display = True
    out1.par.viewer = True
    out1.viewer = True
    out1.outputCOMP = c   # marks as Out CHOP

# Mark meta_out as Out DAT
meta_out.outputCOMP = c

# --- Custom Parameters ---
page = c.appendCustomPage('Router') if not c.customPages else c.customPages[0]
if not hasattr(c.par, 'All'):
    page.appendToggle('All', label='All (else Selected)')
    c.par.All = True
if not hasattr(c.par, 'Selid'):
    page.appendInt('Selid', label='Selected ID')
    c.par.Selid = 1
    c.par.Selid.normMin = 1
    c.par.Selid.normMax = 8

# --- Select CHOP expression ---
# If All -> '*', else -> f"p{Selid}_*"
expr = "`'*' if parent().par.All else f'p{int(parent().par.Selid)}_*'`"
if sel.par.channame.eval() != expr:
    sel.par.channame = expr

# Cosmetic layout
in1.nodeX, in1.nodeY = 0, 0
sel.nodeX, sel.nodeY = 200, 0
out1.nodeX, out1.nodeY = 400, 0
meta_in.nodeX, meta_in.nodeY = 0, -200
meta_out.nodeX, meta_out.nodeY = 200, -200

# Friendly labels
out1.par.name = 'out1'        # Out CHOP name
meta_out.par.name = 'meta_out' # Out DAT name

debug = f"""
PersonRouter stub ready.
- CHOP In:  in1 (wire from PoseCam/pose_out)
- CHOP Out: out1 (all or selected p{{id}}_* channels)
- DAT In:   meta_in (wire from PoseCam meta DAT)
- DAT Out:  meta_out
- Params:   Router/All (toggle), Router/Selid (int)
"""
print(debug)
