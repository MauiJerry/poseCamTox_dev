# pass_debug: Script CHOP
# - Passes all input channels through unchanged
# - Emits a debug line every N cooks (configurable via inline constants)
#
# How it works:
#   • Uses Script CHOP's Python mode with a single cook(scriptOP) function
#   • Copies channel names & samples from input[0] to output
#   • Logs with debug() if available, else falls back to print()

# --- simple "settings" you can tweak ---
DEBUG_ENABLED   = True     # flip to False to silence logs
DEBUG_EVERY_N   = 30       # log every Nth cook (reduce spam)

def _log(msg: str):
    try:
        # TouchDesigner has a global debug() helper that respects /local/debug
        debug(msg)  # noqa
    except Exception:
        print(msg)

def cook(scriptOP):
    # Rate-limit bookkeeping (uses operator storage to persist across cooks)
    count = scriptOP.storage.get('cook_count', 0) + 1
    scriptOP.storage['cook_count'] = count

    # Clear any previous output
    scriptOP.clear()

    # If nothing connected, nothing to do
    if scriptOP.numInputs < 1 or scriptOP.inputs[0] is None:
        if DEBUG_ENABLED and count % DEBUG_EVERY_N == 0:
            _log("[pass_debug] no input connected")
        return

    src = scriptOP.inputs[0]

    # Prepare output sample count
    scriptOP.numSamples = src.numSamples

    # Pass-through: recreate channels with same names & values
    # (TD channels are 1-D; we just copy sample-by-sample)
    for ch in src.chans():
        out = scriptOP.appendChan(ch.name)
        # fast copy via slice assignment
        for i in range(src.numSamples):
            out[i] = ch[i]

    # Minimal preview: print first sample of first few channels
    if DEBUG_ENABLED and count % DEBUG_EVERY_N == 0:
        preview = []
        limit = min(4, src.numChans)
        for k in range(limit):
            c = src.chans()[k]
            v = c[0] if src.numSamples else None
            preview.append(f"{c.name}={v:.4f}" if isinstance(v, (int, float)) else f"{c.name}={v}")
        _log(f"[pass_debug] cook#{count} chans={src.numChans} samples={src.numSamples} | " + ", ".join(preview))

    return
