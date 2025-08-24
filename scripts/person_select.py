#from doctest import debug

def onCook(scriptOp):
    debug("person_select onCook")
    scriptOp.clear()

    comp = scriptOp.parent()
    pid  = int(comp.par.Selectpersonid.eval())

    # Source is the first input to this Script CHOP
    if not scriptOp.inputs or scriptOp.inputs[0] is None:
        return
    src = scriptOp.inputs[0]

    # Get channel list across TD versions
    ch_list = getattr(src, 'chans', None)
    if callable(ch_list):   # defensive: older builds sometimes expose .chans() as a method
        ch_list = ch_list()
    if ch_list is None:
        return  # nothing to do

    prefix = f"p{pid}_"

    # Keep only channels that belong to the selected person
    keep = [ch for ch in ch_list if ch.name.startswith(prefix)]

    if not keep:
        return

    # Preserve timing
    scriptOp.numSamples = src.numSamples
    scriptOp.rate       = src.rate
    scriptOp.start      = src.start

    # Create channels and copy samples
    out_names = [ch.name for ch in keep]
    scriptOp.appendChan(out_names)
    for i, ch in enumerate(keep):
        scriptOp.chan(i).vals = ch.vals

    return
