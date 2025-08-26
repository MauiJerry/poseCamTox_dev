# me - this DAT
# 
# frame - the current frame
# state - True if the timeline is paused
# 
# Make sure the corresponding toggle is enabled in the Execute DAT.

def onStart():
    component_op = op('.')

    # Wait for the extension to be ready.
    if component_op.extensionsReady:
        component_op.ext.PoseEffectMasterExt.OnStart()
    else:
        # Fallback or a warning if not ready in time.
        debug("Warning: Extensions were not ready during onStart.")

    #op('.').ext.PoseEffectMasterExt.OnStart()
    return

d