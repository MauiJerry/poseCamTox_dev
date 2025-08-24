
# OP Execute DAT callbacks
def onPreCook(OP):
    try:
        debug(f"[{OP.path}] cook begin @ frame={absTime.frame} time={absTime.seconds:.6f}s")
    except Exception:
        print(f"[{OP.path}] cook begin @ frame={absTime.frame} time={absTime.seconds:.6f}s")
    return

def onPostCook(OP):
    # OP.cookTime is the duration of the last cook in milliseconds (available at end)
    try:
        debug(f"[{OP.path}] cook end   dur={OP.cookTime:.3f} ms  frame={absTime.frame}")
    except Exception:
        print(f"[{OP.path}] cook end   dur={OP.cookTime:.3f} ms  frame={absTime.frame}")
    return
