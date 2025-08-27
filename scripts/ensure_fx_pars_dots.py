"""
This script is intended to be run from within an 'fxCore' component inside a
clonable 'PoseEffect' component (e.g., PoseEffect_Dots).

Its primary purpose is to dynamically create custom parameters on the parent
'PoseEffect' component and bind them to the corresponding parameters on the
'fxCore'. This exposes the core controls on the parent's UI, making the
effect configurable without needing to dive into its network.

This approach supports TouchDesigner's cloning workflow. When a 'PoseEffect'
is cloned, the new clone will run this script to generate its own set of
parameters, bound to its own internal 'fxCore', ensuring each clone is
independently controllable.
"""
# The original comments provide valuable context about clone immunity:
# ensure_fx_pars_dots.py  (lives in fxCore of PoseEffect_Dots )
# the ensure_fx_pars operator needs to be clone immune
# basic one is linked in the original in the PoseEffect_Master
# then the clone will need to create its own ensure_fx_pars_CloneName.py
# while we are not using clone at this time, prepare for future
from td import ParMode

# The name of the custom parameter page that will hold
# bound params on the parent component (PoseEffect_).
PAGE = 'fxParm'

def _add_or_get_page(c):
    """
    Finds a custom parameter page by name on a component, or creates it if not found.

    Args:
        c (COMP): The component to add the page to.

    Returns:
        Page: The existing or newly created custom parameter page.
    """
    for p in c.customPages:
        if p.name == PAGE:
            return p
    return c.appendCustomPage(PAGE)

def ensure():
    """
    Main function to ensure parameters are created and bound.
    but at present we are not binding the parent.
    """
    debug("ensure_fx_pars_dots.py: ensure() called")
    # 'parent()' is the 'PoseEffect_Dots' component (the clone).
    # should check if it is named PoseEffects_ ... later
    parent_PoseEffect = parent()
    
    # 'fxCore' is the non-clonable core component inside the parent.
    # which should be this container
    core = parent_PoseEffect.op('fxCore')
    page = _add_or_get_page(parent_PoseEffect)

    def bind_float(name, src="fxCore"):
        p = getattr(parent_PoseEffect.par, name, None)
        if not p:
            p = page.appendFloat(name)
        p.mode = ParMode.BIND
        # Set the bind expression to link to the source parameter on the fxCore COMP.
        p.bindExpr = "op('{}').par.{}".format(src, name)

    def bind_rgb(name, src="fxCore"):
        """Ensures an RGB parameter exists on the parent and binds it to the source."""
        p = getattr(parent_PoseEffect.par, name, None)
        if not p:
            p = page.appendRGB(name)
        p.mode = ParMode.BIND
        p.bindExpr = "op('{}').par.{}".format(src, name)

    # TODO: Implement a bind_menu function.
    # This would be similar to the above, but use page.appendMenu().
    # Note that binding a menu's value is straightforward, but syncing the
    # menu items (names and labels) requires binding the menuSource properties.
    def bind_menu(name, src="fxCore"):
        """
        Ensures a Menu parameter exists on the parent and binds its value.
        Note: This only binds the selected value, not the list of menu options.
        """
        p = getattr(parent_PoseEffect.par, name, None)
        if not p:
            p = page.appendMenu(name)
        p.mode = ParMode.BIND
        p.bindExpr = "op('{}').par.{}".format(src, name)

    # TODO: This process could be data-driven.
    # Instead of hard-coding calls, read a definition table (e.g., a DAT)
    # that lists parameter names and types (float, rgb, menu, etc.).
    # The script would then loop through the table and call the appropriate
    # bind_* function for each entry.
    # e.g., should read fx_pars DAT whose contents are in config/fx_pars_CloneName.py


    # --- Parameter Mirroring ---
    # Call the helper functions to create and bind each parameter you want to expose.
    # These parameters must already exist on the 'fxCore' component.

    # Expose the UI color parameter.
    # bind_rgb('UiColor')
    # Expose the dot size parameter.
    # bind_float('UiDotSize')
    # bind_menu('UiLandmarkSelectMenu)

    # ...repeat for any other parameters on fxCore you want to control from the parent...
