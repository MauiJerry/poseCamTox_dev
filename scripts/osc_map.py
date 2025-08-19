# td/scripts/osc_map.py
# Map show-control OSC messages to ui_panel custom parameters.

def onReceiveOSC(dat, rowIndex, message, bytes, timeStamp, address, args, peer):
    ui = parent()
    try:
        if address == '/show/efx/select':
            ui.par.Activeeffect = int(args[0])
        elif address == '/show/efx/next':
            ui.par.Activeeffect = int(ui.par.Activeeffect) + 1
        elif address == '/show/fader':
            ui.par.Fader = float(args[0])
        elif address == '/show/person/id':
            ui.par.Personid = int(args[0])
        elif address == '/show/mask':
            ui.par.Mask = str(args[0])
        elif address == '/show/posecam/start':
            ui.par.Start.pulse()
        elif address == '/show/posecam/stop':
            ui.par.Stop.pulse()
        elif address == '/show/blackout':
            ui.par.Blackout = int(args[0])
    except Exception:
        pass
    return
