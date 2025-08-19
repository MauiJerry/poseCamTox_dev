# td/scripts/toggle_cooking.py
# Toggle allowCooking so only the selected effect cooks (plus any with Live bypass).

def onValueChange(par, prev):
    active = int(par.eval())
    # You can expose these as custom String parameters if you prefer
    names = ['efx_hands', 'efx_skeleton']
    base = op('Effects') or op('/project1/VIEW/ui_efx/Effects')
    if not base:
        return
    for i, name in enumerate(names):
        comp = base.op(name)
        if comp is not None:
            live_bypass = hasattr(comp.par, 'Live') and bool(comp.par.Live.eval())
            comp.allowCooking = (i == active) or live_bypass
    return
