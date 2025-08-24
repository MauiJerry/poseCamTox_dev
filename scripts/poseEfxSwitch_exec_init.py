# poseEfxSwitch_exec_init
def onStart():
    debug("poseEfxSwitch onStart")
    op('.').ext.PoseEfxSwitchExt.Initialize()
    return