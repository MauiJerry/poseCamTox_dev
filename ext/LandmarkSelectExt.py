# ext/LandmarkSelectExt.py
# Builds Select CHOP channame based on parent's filter settings and menu resolution.

class LandmarkSelectExt:
    def __init__(self, owner):
        self.owner = owner

    def Rebuild(self):
        key = (self.owner.par.LandmarkFilter.eval() or '').strip().lower()
        custom_csv = (self.owner.par.Landmarkfiltercsv.eval() or '').strip()

        posefx = self.owner.parent()
        default_csv = ''
        if hasattr(posefx.ext, 'PoseEffectMasterExt'):
            default_csv = posefx.ext.PoseEffectMasterExt.ResolveMenuCSV(key)

        sel  = self.owner.op('select1')
        mask = self.owner.op('landmark_mask')
        names= self.owner.op('landmark_names')
        if not sel or not mask or not names:
            self._log("Missing select1/landmark_mask/landmark_names.")
            return

        # choose mask file
        if key in ('', 'all'):
            mask.par.file = ''
        elif key == 'custom':
            mask.par.file = custom_csv
        else:
            mask.par.file = default_csv or ''

        # build channels
        if key in ('', 'all'):
            nlist = _col_as_list(names, 'name')
            chans = _flatten([_xyz(n) for n in nlist])
        else:
            rows = _rows_as_dicts(mask)
            chans = []
            for r in rows:
                ch = (r.get('chan') or '').strip()
                nm = (r.get('name') or '').strip()
                if ch: chans.append(ch)
                elif nm: chans += _xyz(nm)

        # apply
        sel.par.op = '../in1'
        sel.par.channame = ' '.join(_dedup(chans))
        self._log(f"Rebuild key='{key}', file='{mask.par.file.eval()}', count={len(chans)}")

    def _log(self, msg):
        logdat = self.owner.op('log')
        try:
            if logdat and hasattr(logdat, 'write'): logdat.write(str(msg)+'\n')
            else: print(str(msg))
        except Exception: pass

# helpers
def _rows_as_dicts(tab):
    try:
        if tab.numRows <= 1 or tab.numCols <= 0: return []
        heads = [c.val.lower() for c in tab.row(0)]
        out = []
        for r in tab.rows()[1:]:
            d = {}
            for i in range(min(len(heads), len(r))):
                d[heads[i]] = r[i].val
            out.append(d)
        return out
    except Exception:
        return []

def _col_as_list(tab, colname):
    try:
        if tab.numRows <= 1 or tab.numCols <= 0: return []
        heads = [c.val.lower() for c in tab.row(0)]
        if colname.lower() not in heads: return []
        ci = heads.index(colname.lower())
        return [r[ci].val.strip() for r in tab.rows()[1:] if r[ci].val.strip()]
    except Exception:
        return []

def _xyz(name):
    b=f"{name}_"; return [b+'x', b+'y', b+'z']

def _dedup(seq):
    seen,out=set(),[]
    for s in seq:
        if s and s not in seen:
            seen.add(s); out.append(s)
    return out

def _flatten(xxs):
    out=[]; [out.extend(x) for x in xxs]; return out
