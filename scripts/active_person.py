# td/scripts/active_person.py
# Choose the active person based on Personmode and available p*_present channels.

def onValueChange(channel, sampleIndex, val, prev):
    router = op('..')
    present = []
    src = op('present_sel')
    if not src:
        return
    for c in src.chans:
        if c.val >= 0.5:
            n = c.name  # e.g., "p2_present"
            try:
                pid = int(n[1:n.find('_')])
                present.append(pid)
            except Exception:
                pass

    pid = -1
    if present:
        mode = router.par.Personmode.eval() if hasattr(router.par, 'Personmode') else 'Specific'
        if mode == 'Specific':
            want = int(router.par.Personid.eval()) if hasattr(router.par, 'Personid') else 1
            pid = min(present, key=lambda p: abs(p - want))
        elif mode == 'Closest':
            pid = min(present)
        elif mode == 'Highestscore':
            pid = max(present)

    if op('active_pid'):
        op('active_pid')['v0'] = pid
    return
