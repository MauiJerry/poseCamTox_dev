# router_core.py
# Stateless helpers + state container stored on the COMP

import re
import time

ADDR_RE = re.compile(r"^/p(?P<pid>\d+)/(?P<name>[A-Za-z0-9_:-]+)$")
FRAME_KEYS = {"/image-width": "image_width",
              "/image-height": "image_height",
              "/numLandmarks": "num_landmarks"}

def _now_ms():
    return int(time.time() * 1000)

def get_cfg(comp):
    """Read parameters + landmark table into a simple dict."""
    # custom pars (create these on the COMP UI)
    cfg = {
        "min_conf": float(comp.par.Minconfidence.eval() if hasattr(comp.par,'Minconfidence') else 0.35),
        "timeout_ms": int(comp.par.Timeoutms.eval() if hasattr(comp.par,'Timeoutms') else 500),
        "max_persons": int(comp.par.Maxpersons.eval() if hasattr(comp.par,'Maxpersons') else 6),
        "primary_mode": (comp.par.Primaryselection.eval() if hasattr(comp.par,'Primaryselection') else "Auto-Closest"),
        "fixed_pid": int(comp.par.Fixedpersonid.eval() if hasattr(comp.par,'Fixedpersonid') else 1),
        "enable_smoothing": bool(comp.par.Enablesmoothing.eval() if hasattr(comp.par,'Enablesmoothing') else False),
    }

    # landmarks table
    lm_dat = comp.op('landmarksDAT')
    lm_list = []
    if lm_dat:
        # expect header: index,name,alt_names,enabled
        for r in range(1, lm_dat.numRows):
            enabled = str(lm_dat[r,3]) in ("1","true","True")
            if enabled:
                idx = int(lm_dat[r,0])
                name = str(lm_dat[r,1]).strip()
                alt  = str(lm_dat[r,2]).strip()
                alts = [a.strip() for a in alt.split(",") if a.strip()] if alt else []
                lm_list.append((idx, name, alts))
        # sort by index
        lm_list.sort(key=lambda t: t[0])
    cfg["landmarks"] = lm_list
    cfg["landmark_names"] = [name for _,name,_ in lm_list]
    cfg["name_map"] = _build_name_map(lm_list)
    return cfg

def _build_name_map(lm_list):
    name_map = {}
    for _, name, alts in lm_list:
        name_map[name.lower()] = name
        for a in alts:
            name_map[a.lower()] = name
    return name_map

def get_state(comp):
    """Return state dict stored on the COMP (create if missing)."""
    st = comp.fetch('state', None)
    if st is None:
        st = {
            "persons": {},  # pid -> { name->(u,v,conf), last_seen, avg_conf, count, bbox }
            "frame": {"image_width": 0, "image_height": 0, "num_landmarks": 0, "timestamp_ms": 0},
            "dirty": False,
            "primary_pid": None,
        }
        comp.store('state', st)
    return st

def log(comp, msg):
    t = comp.op('routerLog')
    if t:
        t.write("{} | {}".format(time.strftime("%H:%M:%S"), msg))
        # keep last ~200 lines
        lines = t.text.splitlines()
        if len(lines) > 200:
            t.text = "\n".join(lines[-200:])

def update_from_dat_row(comp, addr, args):
    """Process one OSC-style row: address string + args list of floats/ints."""
    st = get_state(comp)
    cfg = get_cfg(comp)
    now = _now_ms()

    # frame keys
    if addr in FRAME_KEYS:
        key = FRAME_KEYS[addr]
        st["frame"][key] = int(args[0]) if args else 0
        st["frame"]["timestamp_ms"] = now
        st["dirty"] = True
        return

    m = ADDR_RE.match(addr or "")
    if not m:
        return

    pid = int(m.group("pid"))
    raw_name = m.group("name")
    # squeeze names like "handtip_l:u" to base and ignore axis suffix if present
    base = raw_name.split(":")[0].lower()
    name = cfg["name_map"].get(base)
    if not name:
        # unrecognized landmark, optionally log
        return

    # prefer 3-arg [u, v, conf] flavor
    if not args or len(args) < 3:
        return
    u, v, conf = float(args[0]), float(args[1]), float(args[2])

    # clamp conf from rough Mediapipe z/conf to [0..1] if desired (optional)
    # Here we map z in [-5..5] -> conf in [0..1], else keep if already 0..1
    if conf < 0.0 or conf > 1.0:
        conf = max(0.0, min(1.0, (conf + 5.0) / 10.0))

    persons = st["persons"]
    p = persons.get(pid)
    if p is None:
        p = {
            "lm": {},  # name -> (u,v,conf)
            "last_seen": now,
            "avg_conf": 0.0,
            "count": 0,
            "bbox": [1.0, 1.0, 0.0, 0.0],  # minU,minV,maxU,maxV
        }
        persons[pid] = p

    p["lm"][name] = (u, v, conf)
    p["last_seen"] = now
    p["count"] += 1
    # incremental average
    p["avg_conf"] = ((p["avg_conf"] * (p["count"] - 1)) + conf) / max(1, p["count"])
    # bbox
    b = p["bbox"]
    b[0] = min(b[0], u); b[1] = min(b[1], v)
    b[2] = max(b[2], u); b[3] = max(b[3], v)

    st["dirty"] = True

def _diag(bbox):
    du = max(0.0, bbox[2] - bbox[0])
    dv = max(0.0, bbox[3] - bbox[1])
    return (du**2 + dv**2) ** 0.5

def _choose_primary(comp, cfg, st):
    persons = st["persons"]
    if not persons:
        st["primary_pid"] = None
        return

    mode = cfg["primary_mode"]
    if mode == "Fixed Person ID":
        pid = cfg["fixed_pid"]
        if pid in persons:
            st["primary_pid"] = pid
            return
        # fall through to auto if fixed isn't present

    # Build candidates
    cand = []
    for pid, p in persons.items():
        cand.append((pid, p["avg_conf"], _diag(p["bbox"])))
    # Highest conf wins; for "Auto-Closest" we invert diag
    if mode == "Auto-Closest":
        # smallest diagonal
        cand.sort(key=lambda t: (t[2], -t[1]))
    else:
        # Auto-HighestConf
        cand.sort(key=lambda t: (-t[1], t[2]))
    st["primary_pid"] = cand[0][0]

def gc_and_select(comp):
    """Drop timed out persons, choose primary, and update Persons_OUT/FrameInfo_OUT/Landmarks_OUT."""
    st = get_state(comp)
    cfg = get_cfg(comp)
    now = _now_ms()

    # GC
    to_del = []
    for pid, p in st["persons"].items():
        if now - p["last_seen"] > cfg["timeout_ms"]:
            to_del.append(pid)
    for pid in to_del:
        del st["persons"][pid]

    _choose_primary(comp, cfg, st)

    # write Persons_OUT
    persons_dat = comp.op('personsStateDAT')
    if persons_dat:
        persons_dat.clear()
        persons_dat.appendRow(["person_id","last_seen_ms","age_ms","avg_conf","points","diag","primary_rank"])
        # rank: 1 for primary, else blank
        for pid, p in sorted(st["persons"].items()):
            diag = _diag(p["bbox"])
            rank = 1 if pid == st["primary_pid"] else ""
            persons_dat.appendRow([pid, p["last_seen"], now - p["last_seen"], round(p["avg_conf"],3),
                                   len(p["lm"]), round(diag,4), rank])

    # write FrameInfo_OUT
    fi = st["]()
