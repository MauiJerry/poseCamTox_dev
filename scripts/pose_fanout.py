# -*- coding: utf-8 -*-
"""
pose_fanout.py (DAT-based, Bundle-only)
---------------------------------------
aug 20 12:58
TouchDesigner Script CHOP that parses PoseCamPC **Bundle-mode** OSC rows from an
OSC In DAT (poseoscIn1) and fans them out into CHOP channels.

Recognized incoming OSC messages:
  Metadata: (saved to channel and poseMetaDAT)
    /pose/frame_count       <int>
    /pose/num_persons       <int>
    /pose/image_width       <int>
    /pose/image_height      <int>
    /pose/timestamp         <float seconds since epoch>
    /pose/timestamp_str     <string "YYYY.MM.DD.HH.MM.SS.ms"> (strings dont go into chop)

  Landmarks:
    /pose/p{pid}/{lid}      <float x> <float y> <float z>
    /pose/p{pid}/{name}
    /p{pid}/{lid|name}      (short form accepted)

Outputs (CHOP channels):
  - p{pid}_{name}_x, p{pid}_{name}_y, p{pid}_{name}_z
  - p{pid}_present
  - pose_n_people
  - pose_frame_count
  - pose_img_w, pose_img_h
  - pose_ts_sec, pose_ts_ms
  
  PoseMetaDAT


String mirroring:
  - If a Text DAT named 'pose_ts_str' exists, /pose/timestamp_str is written there.

OSC In DAT requirements:
  - "Split Bundles into Messages" = ON
  - "Clear on Frame" = ON
"""

import re
# import logging

OSC_IN_DAT_NAME      = 'poseoscIn1'
ID_MAP_DAT_NAME      = 'landmark_map'
TS_STR_DAT_NAME      = 'pose_ts_str'
POSE_META_DAT_NAME   = 'poseMetaDAT'   # NEW  (Table DAT with header: key,value)

LOG_BUNDLES          = False
LOG_FILE             = 'pose_fanout.log'
LOG_TEXT_DAT_NAME    = 'pose_log'

_RE_NUM = re.compile(r"^/(?:pose/)?p(?P<pid>\d+)/(?P<lid>\d+)$")
_RE_NAM = re.compile(r"^/(?:pose/)?p(?P<pid>\d+)/(?P<lname>[A-Za-z0-9_]+)$")

# --- TouchDesigner compatibility helpers (method vs property) ----------------
def _upsert_meta(key, value):  
    """
    Upsert key->value into the poseMetaDAT table, writing only when changed.
    Initializes the header if the table was empty or wrong shape.
    """
    t = _op_lookup(POSE_META_DAT_NAME)
    if not t:
        return False
    # Ensure header exists and is correct
    if _nrows(t) == 0 or _ncols(t) < 2 or (t[0,0].val.strip().lower() != 'key'):
        t.clear()
        t.appendRow(['key', 'value'])

    sval = str(value)
    # find existing row
    row_index = None
    for r in range(1, _nrows(t)):
        if t[r, 0].val == key:
            row_index = r
            break
    if row_index is None:
        t.appendRow([key, sval])
        return True
    else:
        if t[row_index, 1].val != sval:
            t[row_index, 1].val = sval
            return True
    return False # nothing changed

def _get_val(attr):
    """Return attr() if callable, else attr (for TD versions where numRows/numCols
    are methods vs. properties)."""
    try:
        return attr() if callable(attr) else attr
    except Exception:
        return attr  # best-effort

def _nrows(dat):
    return _get_val(dat.numRows) if hasattr(dat, 'numRows') else 0

def _ncols(dat):
    return _get_val(dat.numCols) if hasattr(dat, 'numCols') else 0

# --- OP/COMP helpers ---------------------------------------------------------
def _here():
    return me.parent() if hasattr(me, 'parent') else None

def _op_lookup(name_or_path):
    comp = _here()
    if not name_or_path:
        return None
    if isinstance(name_or_path, str) and name_or_path.startswith('/'):
        return op(name_or_path)
    if comp:
        o = comp.op(name_or_path)
        if o:
            return o
    return op(name_or_path)

# --- Misc helpers ------------------------------------------------------------
def _first_row_is_header(dat, addr_idx_guess=0):
    """Detect if row 0 looks like a header (e.g., 'OSC address', 'address')."""
    if _nrows(dat) < 1:
        return False
    try:
        headers = []
        for c in range(_ncols(dat)):
            cell = dat[0, c]
            v = getattr(cell, 'val', '') if cell is not None else ''
            headers.append((v or '').strip().lower())
        return any(h in ('osc address', 'address') for h in headers)
    except Exception:
        return False

def _resolve_cols(dat):
    """
    Robust column resolver that does NOT rely on dat.col() always existing.
    It scans the first row as a header to find 'OSC address'/'address' and 'arg0'/'arg1'.
    If no header is present, it falls back to reasonable defaults:
      [message, bundle-timestamp, OSC address, arg0, arg1, ...]
    """
    ncols = _ncols(dat)
    nrows = _nrows(dat)

    addr_idx = 2 if ncols >= 3 else 0
    a0_idx   = 3 if ncols >= 4 else 1

    if nrows > 0 and ncols > 0:
        headers = []
        for c in range(ncols):
            cell = dat[0, c]
            v = getattr(cell, 'val', '') if cell is not None else ''
            headers.append((v or '').strip().lower())

        # find address column
        for i, h in enumerate(headers):
            if h in ('osc address', 'address'):
                addr_idx = i
                break

        # find first arg column (arg0 preferred, else arg1)
        arg_first = None
        for i, h in enumerate(headers):
            if h in ('arg0', 'arg 0'):
                arg_first = i
                break
        if arg_first is None:
            for i, h in enumerate(headers):
                if h in ('arg1', 'arg 1'):
                    arg_first = i
                    break

        if arg_first is not None:
            a0_idx = arg_first
        else:
            # no explicit arg header; assume args start right after address
            a0_idx = addr_idx + 1

    # explicit integer indices (avoid method objects)
    return {
        'addr': int(addr_idx),
        'a1':   int(a0_idx),
        'a2':   int(a0_idx + 1),
        'a3':   int(a0_idx + 2),
        'a4':   int(a0_idx + 3),
    }

def _safe_float(cell):
    try:
        return float(cell.val)
    except Exception:
        try:
            return float(cell)
        except Exception:
            return None

def _cell_str(cell):
    try:
        s = cell.val
        if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
            return s[1:-1]
        return s
    except Exception:
        return ''

def _build_id_to_name_map():
    m = {}
    d = _op_lookup(ID_MAP_DAT_NAME)
    if not d or _ncols(d) < 2:
        return m
    first = (d[0, 0].val or '').strip().lower() if _nrows(d) > 0 else ''
    start = 1 if first in ('id', '#', 'index') else 0
    for r in range(start, _nrows(d)):
        try:
            lid = int(float(d[r, 0].val))
            name = (d[r, 1].val or '').strip()
            if name:
                m[lid] = name
        except Exception:
            continue
    return m

def _append_scalar(scriptOp, name, val):
    ch = scriptOp.appendChan(name)
    ch[0] = float(val)

# def _get_logger():
#     # This sets up a file logger, which is not visible in the Textport.
#     # For Textport output, use print() or debug().
#     log = logging.getLogger('pose_fanout')
#     if not log.handlers:
#         h = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')
#         fmt = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
#         h.setFormatter(fmt)
#         log.addHandler(h)
#         log.setLevel(logging.DEBUG)
#     return log

def _log_to_text_dat(lines):
    td_log = _op_lookup(LOG_TEXT_DAT_NAME)
    if td_log and hasattr(td_log, 'text'):
        td_log.text = '\n'.join(lines)

def _set_text_dat(name, text):
    td = _op_lookup(name)
    if td and hasattr(td, 'text'):
        td.text = text

# --- Main --------------------------------------------------------------------
def onCook(scriptOp):
    # debug("pose_fanout onCook")
    scriptOp.clear()
    osc_dat = _op_lookup(OSC_IN_DAT_NAME)
    count_chanAdds = 0
    count_metaAdds = 0
    if not osc_dat or _nrows(osc_dat) <= 0:
        _append_scalar(scriptOp, 'pose_n_people', 0.0)
        return

    COL = _resolve_cols(osc_dat)
    start_row = 1 if _first_row_is_header(osc_dat, COL['addr']) else 0

    id_map = _build_id_to_name_map()

    latest = {}
    present = set()

    frame_count = None
    num_persons = None
    img_w = None
    img_h = None
    ts_sec = None
    ts_str = None

    if LOG_BUNDLES:
        # logger = _get_logger()
        snap = ['--- pose_fanout frame (debug print) ---']

    nrows = _nrows(osc_dat)
    ncols = _ncols(osc_dat)

    for r in range(start_row, nrows):
        # address
        addr_cell = osc_dat[r, COL['addr']] if COL['addr'] < ncols else None
        addr = getattr(addr_cell, 'val', '') if addr_cell is not None else ''
        if not addr:
            continue

        # args (guard each index)
        a1 = osc_dat[r, COL['a1']] if COL['a1'] < ncols else None
        a2 = osc_dat[r, COL['a2']] if COL['a2'] < ncols else None
        a3 = osc_dat[r, COL['a3']] if COL['a3'] < ncols else None
        a4 = osc_dat[r, COL['a4']] if COL['a4'] < ncols else None

        if LOG_BUNDLES:
            arg_vals = []
            for c in (COL['a1'], COL['a2'], COL['a3'], COL['a4']):
                if c < ncols:
                    v = osc_dat[r, c]
                    vv = getattr(v, 'val', '') if v is not None else ''
                    if vv != '':
                        arg_vals.append(vv)
            line = f"{addr}  {' '.join(arg_vals)}"
            # logger.debug(line)
            #print(line) # For Textport debugging
            snap.append(line)

        # -- grab metadata to local variables
        if addr == '/pose/frame_count':
            v = _safe_float(a1); frame_count = int(v) if v is not None else frame_count; continue
        if addr == '/pose/num_persons':
            v = _safe_float(a1); num_persons = int(v) if v is not None else num_persons; continue
        if addr == '/pose/image_width':
            v = _safe_float(a1); img_w = int(v) if v is not None else img_w; continue
        if addr == '/pose/image_height':
            v = _safe_float(a1); img_h = int(v) if v is not None else img_h; continue
        if addr == '/pose/timestamp':
            v = _safe_float(a1); ts_sec = float(v) if v is not None else ts_sec; continue
        if addr == '/pose/timestamp_str':
            ts_str = _cell_str(a1); continue

        # -- landmarks by numeric id
        m = _RE_NUM.match(addr)
        if m:
            try:
                pid = int(m.group('pid')); lid = int(m.group('lid'))
                x = _safe_float(a1); y = _safe_float(a2); z = _safe_float(a3)
                if None in (x, y, z):
                    continue
                lname = id_map.get(lid, f'id_{lid:02d}')
                latest[(pid, lname)] = (x, y, z)
                present.add(pid)
                continue
            except Exception:
                pass

        # -- landmarks by name
        m = _RE_NAM.match(addr)
        if m:
            try:
                pid = int(m.group('pid')); lname = m.group('lname')
                x = _safe_float(a1); y = _safe_float(a2); z = _safe_float(a3)
                if None in (x, y, z):
                    continue
                latest[(pid, lname)] = (x, y, z)
                present.add(pid)
                continue
            except Exception:
                pass

    # output landmark channels, sorted by name
    for (pid, lname), (x, y, z) in sorted(latest.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        _append_scalar(scriptOp, f'p{pid}_{lname}_x', x)
        _append_scalar(scriptOp, f'p{pid}_{lname}_y', y)
        _append_scalar(scriptOp, f'p{pid}_{lname}_z', z)
        count_chanAdds += 3


    # presence flags
    for pid in sorted(present):
        _append_scalar(scriptOp, f'p{pid}_present', 1.0)
        count_metaAdds += 1

    # counts & metadata  prefix with m_ so as not to muck with later wild card p* 
    if num_persons is None:
        num_persons = len(present)
    else :
        num_persons = 0
    _append_scalar(scriptOp, 'm_n_people', float(num_persons))
    count_metaAdds += 1

    if frame_count is not None:
        _append_scalar(scriptOp, 'm_frame_count', float(frame_count))
        count_metaAdds += 1

    if img_w is not None:
        _append_scalar(scriptOp, 'm_img_w', float(img_w))
        count_metaAdds += 1

    if img_h is not None:
        _append_scalar(scriptOp, 'm_img_h', float(img_h))
        count_metaAdds += 1

    if ts_sec is not None:
        _append_scalar(scriptOp, 'm_ts_sec', ts_sec)
        _append_scalar(scriptOp, 'm_ts_ms', ts_sec * 1000.0)
        count_metaAdds += 2
        
    if ts_str:
        _set_text_dat(TS_STR_DAT_NAME, ts_str)
        
    # --- NEW: mirror slow-changing items into poseMetaDAT (key/value table) ---
    # Only updates when value actually changes (cheap for TD’s cook graph)
    meta_updated = False
    if img_w is not None:
        meta_updated = _upsert_meta('image_width', int(img_w)) or meta_updated
    if img_h is not None:
        meta_updated = _upsert_meta('image_height', int(img_h)) or meta_updated
    if num_persons is not None:
        meta_updated = _upsert_meta('num_persons', int(num_persons)) or meta_updated
    if ts_str:
        meta_updated = _upsert_meta('timestamp_str', ts_str) or meta_updated
    # Optional: if you want a coarse numeric timestamp that updates ~1 Hz:
    if frame_count is not None and meta_updated: 
        _upsert_meta('frame_count', int(frame_count)) 

    # If any of the primary metadata changed, also record the frame_count
    # at which the change occurred.
    if meta_updated and frame_count is not None:
        _upsert_meta('frame_count', int(frame_count))

    #debug(f"pose_fanout: Channel adds: {count_chanAdds}, Meta adds: {count_metaAdds}")
    
    if LOG_BUNDLES:

        _log_to_text_dat(snap)
    return
