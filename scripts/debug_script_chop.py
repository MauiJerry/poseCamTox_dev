# debug script for Script CHOP that emits debug msg
# scriptOp - the OP which is cooking

# --- simple "settings" you can tweak ---

DEBUG_ENABLED   = True     # flip to False to silence logs
DEBUG_EVERY_N   = 30       # log every Nth cook (reduce spam)

def _log(msg: str):
    try:
        # TouchDesigner has a global debug() helper that respects /local/debug
        debug(msg)  # noqa
    except Exception:
        print(msg)

# press 'Setup Parameters' in the OP to call this function to re-create the parameters.
def onSetupParameters(scriptOp):
	page = scriptOp.appendCustomPage('Custom')
	p = page.appendFloat('Valuea', label='Value A')
	p = page.appendFloat('Valueb', label='Value B')
	return

# called whenever custom pulse parameter is pushed
def onPulse(par):
	return

def cook(scriptOP):
    # Rate-limit bookkeeping (uses operator storage to persist across cooks)
    count = scriptOP.storage.get('cook_count', 0) + 1
    scriptOP.storage['cook_count'] = count
    print(f"[pass_debug] cook#{count}")

    # Clear previous output
    scriptOP.clear()

    # Use len(inputs) instead of scriptOP.numInputs
    if len(scriptOP.inputs) == 0 or scriptOP.inputs[0] is None:
        if DEBUG_ENABLED and count % DEBUG_EVERY_N == 0:
            _log("[pass_debug] no input connected")
        return

    src = scriptOP.inputs[0]

    # Prepare output sample count
    scriptOP.numSamples = src.numSamples

    # Pass-through: recreate channels with same names & values
    for ch in src.chans():
        out = scriptOP.appendChan(ch.name)
        # copy samples
        for i in range(src.numSamples):
            out[i] = ch[i]

    # Optional preview (safe & quiet by default)
    if DEBUG_ENABLED and count % DEBUG_EVERY_N == 0:
        try:
            preview = []
            limit = min(4, src.numChans)
            # cache chans() so we don't call it repeatedly
            chans = src.chans()
            for k in range(limit):
                c = chans[k]
                v = c[0] if src.numSamples else None
                if isinstance(v, (int, float)):
                    preview.append(f"{c.name}={v:.4f}")
                else:
                    preview.append(f"{c.name}={v}")
            _log(f"[pass_debug] chans={src.numChans} samples={src.numSamples} | " + ", ".join(preview))
        except Exception as e:
            _log(f"[pass_debug] preview error: {e}")
