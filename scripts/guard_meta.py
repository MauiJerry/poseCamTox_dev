# PoseEfxSwitch/guard_meta
TARGET_OP = 'guardedMeta'

def _comp():
    # This Text DAT sits inside PoseEfxSwitch
    return parent()

def _op(name):
    o = _comp().op(name)
    if not o:
        debug('Missing op:', name)
    return o

def _ensure_header(t):
    if t.numRows == 0 or t.numCols < 2 or t[0,0].val.strip().lower() != 'key':
        t.clear()
        t.appendRow(['key','value'])

def _upsert(t, key, value):
    """
    Insert or update key->value in Table DAT `t`.
    Only changes value if different (to avoid unnecessary recooks).
    """
    _ensure_header(t)
    sval = str(value)
    for r in range(1, t.numRows):
        if t[r,0].val == key:
            if t[r,1].val != sval:
                t[r,1].val = sval
                #debug("guard_meta upsert Updated:", key, "->", sval)
                return True
            else :
                return False
    t.appendRow([key, sval])
    #debug("guard_meta Inserted:", key, "->", sval)

def _read_upstream(d):
    """Return dict from a 2-col key/value table (header tolerant)."""
    res = {}
    if not d or d.numRows < 2:
        return res
    # Find header columns
    headers = [d[0,c].val.strip().lower() for c in range(d.numCols)]
    try:
        kci = headers.index('key')
    except ValueError:
        kci = 0
    try:
        vci = headers.index('value')
    except ValueError:
        vci = 1 if d.numCols > 1 else 0

    for r in range(1, d.numRows):
        k = d[r, kci].val
        v = d[r, vci].val if d.numCols > vci else ''
        if k:
            res[k] = v
    return res

def _to_int(v, fallback=None):
    try:
        return int(float(v))
    except Exception:
        return fallback

def _safe_aspect(w, h):
    w = _to_int(w, None)
    h = _to_int(h, None)
    if not w or not h:
        return 1.0
    try:
        return round(float(w) / float(h), 6)
    except Exception:
        return 1.0

def update_guard():
    """Merge upstream meta with defaults; ensure image_width, image_height, aspect."""
    #debug('db update_guard() called')
    comp = _comp()
    targetOp = _op(TARGET_OP)
    sourceOp = _op('inMeta')
    if not targetOp:
        return

    upstream = _read_upstream(sourceOp)

    # 1) Determine width/height: prefer upstream, else defaults.
    dw = comp.par.Defaultcanvasw.eval() if hasattr(comp.par, 'Defaultcanvasw') else 1280
    dh = comp.par.Defaultcanvash.eval() if hasattr(comp.par, 'Defaultcanvash') else 720

    w = upstream.get('image_width', dw)
    h = upstream.get('image_height', dh)

    # 2) Upsert required keys first (using resolved w/h).
    _upsert(targetOp, 'image_width', _to_int(w, dw))
    _upsert(targetOp, 'image_height', _to_int(h, dh))

    # 3) Aspect: prefer upstream if valid, else compute from resolved w/h.
    up_aspect = upstream.get('aspect', None)
    try:
        aspect_val = float(up_aspect) if up_aspect is not None else _safe_aspect(w, h)
    except Exception:
        aspect_val = _safe_aspect(w, h)
    _upsert(targetOp, 'aspect', aspect_val)

    # 4) Mirror all other upstream keys (but don't overwrite the three we just set).
    for k, v in upstream.items():
        if k in ('image_width', 'image_height', 'aspect'):
            continue
        _upsert(targetOp, k, v)

    # Done. 'guarded_meta' now holds required keys even with no upstream.
