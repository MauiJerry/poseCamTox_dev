# PoseEfxSwitch/inmeta_exec py script
# Fire once to populate defaults when the node is created
def onCreate(dat):
    op('guard_meta').module.update_guard()
    return

# Fires when the watched DAT is a Table DAT and its cells/shape change
def onTableChange(dat):
    op('guard_meta').module.update_guard()
    return

# Fires when the watched DAT isn't strictly table-y, or for general updates
def onDATChange(dat):
    op('guard_meta').module.update_guard()
    return
