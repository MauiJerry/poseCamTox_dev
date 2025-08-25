# me - this DAT
# 
# frame - the current frame
# state - True if the timeline is paused
# 
# Make sure the corresponding toggle is enabled in the Execute DAT.

def onStart():
    op('.').ext.PoseEffectMasterExt.OnStart()
    return

def onCreate():
    op('.').ext.PoseEffectMasterExt.OnStart()
    return
