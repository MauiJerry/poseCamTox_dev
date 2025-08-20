# -*- coding: utf-8 -*-
"""
pose_fanout.py (DAT-based, Bundle-only)
---------------------------------------
TouchDesigner Script CHOP that parses PoseCamPC **Bundle-mode** OSC rows from an
OSC In DAT and fans them out into CHOP channels.

# -*- coding: utf-8 -*-
"""
pose_fanout.py (DAT-based, Bundle-only)
---------------------------------------
TouchDesigner Script CHOP that parses PoseCamPC **Bundle-mode** OSC rows from an
OSC In DAT and fans them out into CHOP channels.

Recognized incoming OSC messages (each as its own DAT row when "Split Bundles" = ON):

  Metadata (some may be sent periodically):
    /pose/frame_count       <int>
    /pose/num_persons       <int>
    /pose/image_width       <int>
    /pose/image_height      <int>
    /pose/timestamp         <float seconds since epoch>          <-- NEW
    /pose/timestamp_str     <string "YYYY.MM.DD.HH.MM.SS.ms">    <-- NEW

  Landmarks (one per landmark in the frame):
    /pose/p{pid}/{lid}      <float x> <float y> <float z>
    (also supported) /pose/p{pid}/{name}
    (also supported) /p{pid}/{lid|name}   # short form accepted

Outputs (CHOP channels):
  - p{pid}_{name}_x, p{pid}_{name}_y, p{pid}_{name}_z
  - p{pid}_present
  - pose_n_people                     (from /pose/num_persons, fallback=len(present))
  - pose_frame_count                  (if present)
  - pose_img_w, pose_img_h            (if present)
  - pose_ts_sec, pose_ts_ms           (if /pose/timestamp present)         <-- NEW

String mirroring:
  - If a Text DAT named 'pose_ts_str' exists, /pose/timestamp_str is written there.

Landmark name lookup:
  - From a Table DAT (CSV) named 'landmark_map' with 2 columns: id, name
  - Header row optional (id,name). If missing, first row is treated as data.

OSC In DAT requirements:
  - "Split Bundles into Messages" = ON
  - "Clear on Frame" = ON (recommended)
"""

import re
import logging

# ---------------- Configuration -------------------------------------------------
OSC_IN_DAT_NAME   = 'poseoscIn1'   # OSC In DAT name (relative to this COMP)
ID_MAP_DAT_NAME   = 'landmark_map' # Table DAT (2 cols: id, name)
TS_STR_DAT_NAME   = 'pose_ts_str'  # Optional Text DAT to mirror /pose/timestamp_str

# Optional per-frame logging of the received rows
LOG_BUNDLES = False                # set True to log each frame’s rows
LOG_FILE    = 'pose_fanout.log'    # written to TD project folder

# If a Text DAT named 'pose_log' exists beside this script, logs mirror there too
LOG_TEXT_DAT_NAME = 'pose_log'
# -------------------------------------------------------------------------------

# Accept both numeric-id and name variants, with/without '/pose' prefix
_RE_NUM = re.compile(r"^/(?:pose/)?p(?P<pid>\d+)/(?P<lid>\d+)$")
_RE_NAM = re.compile(r"^/(?:pose/)?p(?P<pid>\d+)/(?P<lname>[A-Za-z0-9_]+)$")

# ---------------- Utilities -----------------------------------------------------

def _here():
    return me.parent() if hasattr(me, 'parent') else None

def _op_lookup(name_or_path):
    comp = _here()
    if not name_or_path:
        return None
    if name_or_path.startswith('/'):
        return op(name_or_path)
    if comp:
        o = comp.op(name_or_path)
        if o: return o
    return op(name_or_path)

def _col_idx_any(dat, names, default):
    """Return index of the first existing named column; else default."""
    for nm in names:
        try:
            c = dat.col(nm)
            return c.index
        except Exception:
            pass
    return default

def _resolve_cols(dat):
    """
    Tolerant column detection:
      - Address: "OSC address" or "address" (fallback col 0)
      - Args: start at 'arg0' or 'arg1' (fallback col 1)
    """
    addr = _col_idx_any(dat, ['OSC address', 'address', 'Address'], 0)
    a0   = _col_idx_any(dat, ['arg0', 'arg1', 'Arg0', 'Arg1'], 1)
    return {
        'addr': addr,
        'a1':   a0,
        'a2':   a0 + 1,
        'a3':   a0 + 2,
        'a4':   a0 + 3,
    }

def _first_row_is_header(dat, addr_idx):
    if dat.numRows < 1:
        return False
    try:
        val = dat[0, addr_idx].val.strip().lower()
        return val in ('osc address', 'address')
    except Exception:
        return False

def _safe_float(cell):
    try:
        return float(cell.val)
    except Exception:
        try:
            return float(cell)
        except Exception:
            return None

def _cell_str(cell):
    """Return string value from a DAT cell (no quoting), or ''."""
    try:
        s = cell.val
        # Strip surrounding quotes if sender included them
        if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
            return s[1:-1]
        return s
    except Exception:
        return ''

def _build_id_to_name_map():
    """
    Build {id:int -> name:str} from Table DAT ID_MAP_DAT_NAME.
    Two columns expected: id, name. Header row optional.
    """
    m = {}
    d = _op_lookup(ID_MAP_DAT_NAME)
    if not d or d.numCols < 2:
        return m
    first = d[0, 0].val.strip().lower()
    start = 1 if first in ('id', '#', 'index') else 0
    for r in range(start, d.numRows):
        try:
            lid = int(float(d[r, 0].val))
            name = d[r, 1].val.strip()
            if name:
                m[lid] = name
        except Exception:
            continue
    return m

def _append_scalar(scriptOp, name, val):
    ch = scriptOp.appendChan(name)
    ch[0] = float(val)

def _get_logger():
    log = logging.getLogger('pose_fanout')
    if not log.handlers:
        handler = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')
        fmt = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        handler.setFormatter(fmt)
        log.addHandler(handler)
        log.setLevel(logging.DEBUG)
    return log

def _log_to_text_dat(lines):
    td_log = _op_lookup(LOG_TEXT_DAT_NAME)
    if td_log and hasattr(td_log, 'text'):
        td_log.text = '\n'.join(lines)

def _set_text_dat(name, text):
    td_dat = _op_lookup(name)
    if td_dat and hasattr(td_dat, 'text'):
        td_dat.text = text

# ---------------- TouchDesigner Callback ---------------------------------------

def onCook(scriptOp):
    """
    Main fan-out: read OSC rows from the OSC In DAT and publish channels.
    Also mirrors the human-readable timestamp string (if present) into a
    Text DAT named TS_STR_DAT_NAME.
    """
    scriptOp.clear()

    osc_dat = _op_lookup(OSC_IN_DAT_NAME)
    if not osc_dat or osc_dat.numRows <= 0:
        _append_scalar(scriptOp, 'pose_n_people', 0.0)
        return

    COL = _resolve_cols(osc_dat)
    start_row = 1 if _first_row_is_header(osc_dat, COL['addr']) else 0

    id_map = _build_id_to_name_map()

    latest = {}        # (pid, lname) -> (x,y,z)
    present = set()
    frame_count = None
    num_persons = None
    img_w = None
    img_h = None
    ts_sec = None          # <-- NEW
    ts_str = None          # <-- NEW

    # Optional logging: capture a readable snapshot of this frame’s rows
    if LOG_BUNDLES:
        logger = _get_logger()
        snap_lines = ['--- pose_fanout frame ---']

    for r in range(start_row, osc_dat.numRows):
        addr_cell = osc_dat[r, COL['addr']]
        addr = addr_cell.val if addr_cell is not None else ''
        if not addr:
            continue

        a1 = osc_dat[r, COL['a1']] if COL['a1'] < osc_dat.numCols else None
        a2 = osc_dat[r, COL['a2']] if COL['a2'] < osc_dat.numCols else None
        a3 = osc_dat[r, COL['a3']] if COL['a3'] < osc_dat.numCols else None

        if LOG_BUNDLES:
            args_preview = []
            for cidx in (COL['a1'], COL['a2'], COL['a3'], COL['a4']):
                if cidx < osc_dat.numCols:
                    v = osc_dat[r, cidx].val
                    if v != '':
                        args_preview.append(v)
            line = f"{addr}  {' '.join(args_preview)}"
            logger.debug(line)
            snap_lines.append(line)

        # ---- Metadata ----
        if addr == '/pose/frame_count':
            v = _safe_float(a1);  frame_count = int(v) if v is not None else frame_count
            continue
        if addr == '/pose/num_persons':
            v = _safe_float(a1);  num_persons = int(v) if v is not None else num_persons
            continue
        if addr == '/pose/image_width':
            v = _safe_float(a1);  img_w = int(v) if v is not None else img_w
            continue
        if addr == '/pose/image_height':
            v = _safe_float(a1);  img_h = int(v) if v is not None else img_h
            continue
        if addr == '/pose/timestamp':                 # <-- NEW numeric timestamp
            v = _safe_float(a1)
            if v is not None:
                ts_sec = float(v)
            continue
        if addr == '/pose/timestamp_str':             # <-- NEW string timestamp
            ts_str = _cell_str(a1)
            continue

        # ---- Landmarks (numeric-id form) ----
        m = _RE_NUM.match(addr)
        if m:
            try:
                pid = int(m.group('pid'))
                lid = int(m.group('lid'))
                x = _safe_float(a1); y = _safe_float(a2); z = _safe_float(a3)
                if x is None or y is None or z is None:
                    continue
                lname = id_map.get(lid, f'id_{lid:02d}')
                latest[(pid, lname)] = (x, y, z)
                present.add(pid)
                continue
            except Exception:
                pass

        # ---- Landmarks (named form) ----
        m = _RE_NAM.match(addr)
        if m:
            try:
                pid = int(m.group('pid'))
                lname = m.group('lname')
                x = _safe_float(a1); y = _safe_float(a2); z = _safe_float(a3)
                if x is None or y is None or z is None:
                    continue
                latest[(pid, lname)] = (x, y, z)
                present.add(pid)
                continue
            except Exception:
                pass

        # Everything else ignored (incl. legacy)

    # ---- Emit channels ----
    # Per-landmark components (sorted for stable ordering)
    for (pid, lname), (x, y, z) in sorted(latest.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        _append_scalar(scriptOp, f'p{pid}_{lname}_x', x)
        _append_scalar(scriptOp, f'p{pid}_{lname}_y', y)
        _append_scalar(scriptOp, f'p{pid}_{lname}_z', z)

    # Presence and counts
    for pid in sorted(present):
        _append_scalar(scriptOp, f'p{pid}_present', 1.0)

    if num_persons is None:
        num_persons = len(present)
    _append_scalar(scriptOp, 'pose_n_people', float(num_persons))

    # Optional meta
    if frame_count is not None: _append_scalar(scriptOp, 'pose_frame_count', float(frame_count))
    if img_w is not None:       _append_scalar(scriptOp, 'pose_img_w', float(img_w))
    if img_h is not None:       _append_scalar(scriptOp, 'pose_img_h', float(img_h))

    # NEW: timestamps
    if ts_sec is not None:
        _append_scalar(scriptOp, 'pose_ts_sec', ts_sec)
        _append_scalar(scriptOp, 'pose_ts_ms',  ts_sec * 1000.0)

    if ts_str:
        _set_text_dat(TS_STR_DAT_NAME, ts_str)  # mirror into Text DAT if present

    # Mirror log to a Text DAT if present
    if LOG_BUNDLES:
        _log_to_text_dat(snap_lines)

    return
 incoming OSC messages (each as its own DAT row when "Split Bundles" = ON):

  Metadata (some may be sent periodically):
    /pose/frame_count    <int>
    /pose/num_persons    <int>
    /pose/image_width    <int>
    /pose/image_height   <int>

  Landmarks (one per landmark in the frame):
    /pose/p{pid}/{lid}   <float x> <float y> <float z>
    (also supported) /pose/p{pid}/{name}
    (also supported) /p{pid}/{lid|name}   # short form accepted

Outputs (CHOP channels):
  - p{pid}_{name}_x, p{pid}_{name}_y, p{pid}_{name}_z
  - p{pid}_present
  - pose_n_people   (from /pose/num_persons, fallback=len(present))
  - pose_frame_count (if present)
  - pose_img_w, pose_img_h (if present)

Landmark name lookup:
  - From a Table DAT (CSV) named 'landmark_map' with 2 columns: id, name
  - Header row optional (id,name). If missing, first row is treated as data.

OSC In DAT requirements:
  - "Split Bundles into Messages" = ON
  - "Clear on Frame" = ON (recommended)

Author: Pose2Art
"""

import re
import logging

# ---------------- Configuration -------------------------------------------------
OSC_IN_DAT_NAME = 'poseoscIn1'     # OSC In DAT name (relative to this COMP)
ID_MAP_DAT_NAME = 'landmark_map'   # Table DAT (2 cols: id, name)

# Optional per-frame logging of the received rows
LOG_BUNDLES = False                # set True to log each frame’s rows
LOG_FILE    = 'pose_fanout.log'    # written to TD project folder

# If a Text DAT named 'pose_log' exists beside this script, logs mirror there too
LOG_TEXT_DAT_NAME = 'pose_log'
# -------------------------------------------------------------------------------

# Accept both numeric-id and name variants, with/without '/pose' prefix
_RE_NUM = re.compile(r"^/(?:pose/)?p(?P<pid>\d+)/(?P<lid>\d+)$")
_RE_NAM = re.compile(r"^/(?:pose/)?p(?P<pid>\d+)/(?P<lname>[A-Za-z0-9_]+)$")

# ---------------- Utilities -----------------------------------------------------

def _here():
    return me.parent() if hasattr(me, 'parent') else None

def _op_lookup(name_or_path):
    comp = _here()
    if not name_or_path:
        return None
    if name_or_path.startswith('/'):
        return op(name_or_path)
    if comp:
        o = comp.op(name_or_path)
        if o: return o
    return op(name_or_path)

def _col_idx_any(dat, names, default):
    """
    Return index of the first existing named column; else default.
    Handles oscinDAT and Table DAT.
    """
    for nm in names:
        try:
            c = dat.col(nm)
            return c.index
        except Exception:
            pass
    return default

def _resolve_cols(dat):
    """
    Tolerant column detection:
      - Address: "OSC address" or "address" (fallback col 0)
      - Args: start at 'arg0' or 'arg1' (fallback col 1)
    """
    addr = _col_idx_any(dat, ['OSC address', 'address', 'Address'], 0)
    a0   = _col_idx_any(dat, ['arg0', 'arg1', 'Arg0', 'Arg1'], 1)
    return {
        'addr': addr,
        'a1':   a0,
        'a2':   a0 + 1,
        'a3':   a0 + 2,
        'a4':   a0 + 3,
    }

def _first_row_is_header(dat, addr_idx):
    if dat.numRows < 1:
        return False
    try:
        val = dat[0, addr_idx].val.strip().lower()
        return val in ('osc address', 'address')
    except Exception:
        return False

def _safe_float(cell):
    try:
        return float(cell.val)
    except Exception:
        try:
            return float(cell)
        except Exception:
            return None

def _build_id_to_name_map():
    """
    Build {id:int -> name:str} from Table DAT ID_MAP_DAT_NAME.
    Two columns expected: id, name. Header row optional.
    """
    m = {}
    d = _op_lookup(ID_MAP_DAT_NAME)
    if not d or d.numCols < 2:
        return m
    first = d[0, 0].val.strip().lower()
    start = 1 if first in ('id', '#', 'index') else 0
    for r in range(start, d.numRows):
        try:
            lid = int(float(d[r, 0].val))
            name = d[r, 1].val.strip()
            if name:
                m[lid] = name
        except Exception:
            continue
    return m

def _append_scalar(scriptOp, name, val):
    ch = scriptOp.appendChan(name)
    ch[0] = float(val)

def _get_logger():
    log = logging.getLogger('pose_fanout')
    if not log.handlers:
        handler = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')
        fmt = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        handler.setFormatter(fmt)
        log.addHandler(handler)
        log.setLevel(logging.DEBUG)
    return log

def _log_to_text_dat(lines):
    td_log = _op_lookup(LOG_TEXT_DAT_NAME)
    if td_log and hasattr(td_log, 'text'):
        td_log.text = '\n'.join(lines)

# ---------------- TouchDesigner Callback ---------------------------------------

def onCook(scriptOp):
    """
    Main fan-out: read OSC rows from the OSC In DAT and publish channels.
    """
    scriptOp.clear()

    osc_dat = _op_lookup(OSC_IN_DAT_NAME)
    if not osc_dat or osc_dat.numRows <= 0:
        _append_scalar(scriptOp, 'pose_n_people', 0.0)
        return

    COL = _resolve_cols(osc_dat)
    start_row = 1 if _first_row_is_header(osc_dat, COL['addr']) else 0

    id_map = _build_id_to_name_map()
    # Optional reverse map (name->name) if named addresses arrive
    # Not strictly needed; we will just use the provided name if already a string.
    latest = {}        # (pid, lname) -> (x,y,z)
    present = set()
    frame_count = None
    num_persons = None
    img_w = None
    img_h = None

    # Optional logging: capture a readable snapshot of this frame’s rows
    if LOG_BUNDLES:
        logger = _get_logger()
        snap_lines = ['--- pose_fanout frame ---']

    for r in range(start_row, osc_dat.numRows):
        addr_cell = osc_dat[r, COL['addr']]
        addr = addr_cell.val if addr_cell is not None else ''
        if not addr:
            continue

        a1 = osc_dat[r, COL['a1']] if COL['a1'] < osc_dat.numCols else None
        a2 = osc_dat[r, COL['a2']] if COL['a2'] < osc_dat.numCols else None
        a3 = osc_dat[r, COL['a3']] if COL['a3'] < osc_dat.numCols else None

        if LOG_BUNDLES:
            # Build a compact row dump: address and first few args
            args_preview = []
            for cidx in (COL['a1'], COL['a2'], COL['a3'], COL['a4']):
                if cidx < osc_dat.numCols:
                    val = osc_dat[r, cidx].val
                    if val != '':
                        args_preview.append(val)
            line = f"{addr}  {' '.join(args_preview)}"
            logger.debug(line)
            snap_lines.append(line)

        # ---- Metadata ----
        if addr == '/pose/frame_count':
            v = _safe_float(a1);  frame_count = int(v) if v is not None else frame_count
            continue
        if addr == '/pose/num_persons':
            v = _safe_float(a1);  num_persons = int(v) if v is not None else num_persons
            continue
        if addr == '/pose/image_width':
            v = _safe_float(a1);  img_w = int(v) if v is not None else img_w
            continue
        if addr == '/pose/image_height':
            v = _safe_float(a1);  img_h = int(v) if v is not None else img_h
            continue

        # ---- Landmarks (numeric-id form) ----
        m = _RE_NUM.match(addr)
        if m:
            try:
                pid = int(m.group('pid'))
                lid = int(m.group('lid'))
                x = _safe_float(a1); y = _safe_float(a2); z = _safe_float(a3)
                if x is None or y is None or z is None:
                    continue
                lname = id_map.get(lid, f'id_{lid:02d}')
                latest[(pid, lname)] = (x, y, z)
                present.add(pid)
                continue
            except Exception:
                pass

        # ---- Landmarks (named form) ----
        m = _RE_NAM.match(addr)
        if m:
            try:
                pid = int(m.group('pid'))
                lname = m.group('lname')
                x = _safe_float(a1); y = _safe_float(a2); z = _safe_float(a3)
                if x is None or y is None or z is None:
                    continue
                latest[(pid, lname)] = (x, y, z)
                present.add(pid)
                continue
            except Exception:
                pass

        # Everything else ignored (incl. legacy)

    # ---- Emit channels ----
    # Per-landmark components (sorted for stable ordering)
    for (pid, lname), (x, y, z) in sorted(latest.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        _append_scalar(scriptOp, f'p{pid}_{lname}_x', x)
        _append_scalar(scriptOp, f'p{pid}_{lname}_y', y)
        _append_scalar(scriptOp, f'p{pid}_{lname}_z', z)

    # Presence and counts
    for pid in sorted(present):
        _append_scalar(scriptOp, f'p{pid}_present', 1.0)

    if num_persons is None:
        num_persons = len(present)
    _append_scalar(scriptOp, 'pose_n_people', float(num_persons))

    # Optional meta
    if frame_count is not None: _append_scalar(scriptOp, 'pose_frame_count', float(frame_count))
    if img_w is not None:       _append_scalar(scriptOp, 'pose_img_w', float(img_w))
    if img_h is not None:       _append_scalar(scriptOp, 'pose_img_h', float(img_h))

    # Mirror log to a Text DAT if present
    if LOG_BUNDLES:
        _log_to_text_dat(snap_lines)

    return
