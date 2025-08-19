# td/scripts/efx_points_sop.py
# Build a SOP of points at selected landmark channels from incoming CHOP

def onCook(scriptOp):
    ch = op('in_chop')
    if not ch or ch.numChans == 0:
        scriptOp.clear(); return

    mask = op('mask_table') if op('mask_table') else None
    names = set([r[0].val for r in mask.rows()]) if mask else None

    scriptOp.clear()
    for cx in ch.chans:
        if not cx.name.endswith('_x'):
            continue
        base = cx.name[:-2]  # strip "_x"
        cy = ch[base + 'y'] if base + 'y' in ch else None
        cz = ch[base + 'z'] if base + 'z' in ch else None
        lname = base.split('_', 1)[1] if '_' in base else base
        if names and lname not in names:
            continue
        x = cx.eval(); y = cy.eval() if cy else 0.0; z = cz.eval() if cz else 0.0
        scriptOp.appendPoint((x, y, z))
    return
