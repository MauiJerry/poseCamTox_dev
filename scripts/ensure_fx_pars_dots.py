# ensure_fx_pars_dots.py  (lives in fxCore of cloned PoseEffect_* container)
# the ensure_fx_pars operator needs to be clone immune
# basic one is linked in the original in the PoseEffect_Master
# then the clone will need to create its own ensure_fx_pars_CloneName.py 
from td import ParMode

PAGE = 'fxParm'

def _add_or_get_page(c):
    for p in c.customPages:
        if p.name == PAGE:
            return p
    return c.appendCustomPage(PAGE)

def ensure():
    mecomp = parent()  # PoseEffect_Dots (da clone)
    core = mecomp.op('fxCore') # da uncloneable
    page = _add_or_get_page(mecomp)

    def bind_float(name, src="fxCore"):
        p = getattr(mecomp.par, name, None)
        if not p:
            p = page.appendFloat(name)
        p.mode = ParMode.BIND
        p.bindExpr = "op('{}').par.{}".format(src, name)

    def bind_rgb(name, src="fxCore"):
        p = getattr(mecomp.par, name, None)
        if not p:
            p = page.appendRGB(name)
        p.mode = ParMode.BIND
        p.bindExpr = "op('{}').par.{}".format(src, name)
        
    # need bind_menu()
    
    # should read fx_pars DAT whose contents are in config/fx_pars_CloneName.py
    

    # mirror the fxCore params you care about
    bind_rgb('UiColor')
    bind_float('UiDotSize')
    
    # ...repeat for any others...
