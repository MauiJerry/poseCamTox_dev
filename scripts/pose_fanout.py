# td/scripts/pose_fanout.py
# Fan-out PoseCam OSC bundle rows → CHOP channels, using an external landmark map DAT.
# Requirements inside the PoseCam COMP:
#   - OSC In DAT named: poseoscIn1
#   - Table DAT named: landmark_map   (headers: id,name; File -> ./td/data/landmark_names.csv or ./td/config/landmark_names.csv)

def _resolve_landmark_map():
    """Return two dicts: id->name, name->id from the landmark_map Table DAT."""
    m = op('landmark_map')
    id2name, name2id = {}, {}
    if m is None or m.numRows < 2:
        return id2name, name2id

    # Try header names; if absent, assume two columns
    try:
        id_col = m.col('id').index
        name_col = m.col('name').index
    except Exception:
        id_col, name_col = 0, 1

    for r in range(1, m.numRows):
        try:
            lid = int(m[r, id_col].val)
            lname = m[r, name_col].val.strip()
            if lname:
                id2name[lid] = lname
                name2id[lname] = lid
        except Exception:
            continue
    return id2name, name2id

def _float(dat, r, name, idx):
    # Read arg as float via named or positional column
    return float(dat[r, name].val) if name in dat.colNames else float(dat[r, idx].val)

def _parse_addr(addr):
    """Return (pid:int, lname:str|None, lid:int|None).
    Supports:
      /pose/p{pid}/{lid}         (bundle numeric ids)
      /p{pid}/{landmark_name}    (legacy named)
    """
    if not addr or addr[0] != '/':
        return (None, None, None)
    parts = addr.strip('/').split('/')
    # bundle: /pose/p2/17
    if len(parts) == 3 and parts[0] == 'pose' and parts[1].startswith('p'):
        try:
            return (int(parts[1][1:]), None, int(parts[2]))
        except Exception:
            return (None, None, None)
    # legacy: /p2/wrist_l
    if len(parts) == 2 and parts[0].startswith('p'):
        try:
            return (int(parts[0][1:]), parts[1], None)
        except Exception:
            return (None, None, None)
    return (None, None, None)

def onCook(scriptOp):
    d = op('poseoscIn1')  # ← OSC In DAT name as requested
    scriptOp.clear()

    if d is None or d.numRows <= 1:
        scriptOp.appendChan('pose_n_people')[0] = 0.0
        scriptOp.appendChan('pose_ts_ms')[0] = absTime.frame * (1000.0 / me.time.rate)
        return

    # Load id<->name mapping from external Table DAT
    ID_TO_NAME, NAME_TO_ID = _resolve_landmark_map()

    latest = {}      # (pid,lname) -> (x,y,z,vis)
    present = set()  # {pid}

    # newest→oldest; keep the latest message per (pid,lname)
    for r in range(d.numRows - 1, 0, -1):
        addr = d[r, 'address'].val if 'address' in d.colNames else d[r, 0].val
        pid, lname, lid = _parse_addr(addr)
        if pid is None:
            continue
        try:
            x = _float(d, r, 'arg1', 2)
            y = _float(d, r, 'arg2', 3)
            z = _float(d, r, 'arg3', 4)
            vis = _float(d, r, 'arg4', 5) if ('arg4' in d.colNames or d.numCols > 5) else None
        except Exception:
            continue

        # Normalize name
        if lname is None and lid is not None:
            lname = ID_TO_NAME.get(lid, f"id_{lid:02d}")
        elif lname is not None and lid is None:
            # If a name is provided, we can optionally sanity-map back to id
            lid = NAME_TO_ID.get(lname, None)

        if not lname:
            continue

        key = (pid, lname)
        if key not in latest:
            latest[key] = (x, y, z, vis)
            present.add(pid)

    # Publish channels
    for pid, lname in sorted(latest.keys()):
        x, y, z, vis = latest[(pid, lname)]
        scriptOp.appendChan(f"p{pid}_{lname}_x")[0] = x
        scriptOp.appendChan(f"p{pid}_{lname}_y")[0] = y
        scriptOp.appendChan(f"p{pid}_{lname}_z")[0] = z
        if vis is not None:
            scriptOp.appendChan(f"p{pid}_{lname}_v")[0] = vis

    for pid in sorted(present):
        scriptOp.appendChan(f"p{pid}_present")[0] = 1.0

    scriptOp.appendChan('pose_n_people')[0] = float(len(present))
    scriptOp.appendChan('pose_ts_ms')[0] = absTime.frame * (1000.0 / me.time.rate)
    return
