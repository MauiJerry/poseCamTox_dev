# ext/LandmarkSelectExt.py
# Builds Select CHOP channame based on parent's filter settings and menu resolution.

class LandmarkSelectExt:
    def __init__(self, owner):
        debug("db init landmarkSelectExt")
        self.owner = owner

    def Rebuild(self):
        par = self.owner.par
        key = (par.LandmarkFilter.eval() or '').strip().lower()
        custom_csv = (par.Landmarkfiltercsv.eval() or '').strip()

        sel = self.owner.op('select1')
        if not sel:
            print('LandmarkSelect: missing select1')
            return

        # All/blank → pass-through
        if key in ('', 'all'):
            sel.par.op = '../in1'
            sel.par.channame = ''  # blank selects everything
            return

        # Get source mask table
        src = None
        if key == 'custom' and custom_csv:
            # Use file directly (Table DAT will auto-reload on file change)
            m = self.owner.op('landmark_mask')
            if m:
                m.par.file = custom_csv
                src = m
        else:
            # Ask parent effect → switch for cached table
            pfx = self.owner.parent()
            if hasattr(pfx.ext, 'PoseEffectMasterExt'):
                src = pfx.ext.PoseEffectMasterExt.ResolveMaskTable(key)
            # Fallback to switch-provided csv path if cache missing
            if not src and hasattr(pfx.ext, 'PoseEffectMasterExt'):
                csv_path = pfx.ext.PoseEffectMasterExt.ResolveMenuCSV(key)
                m = self.owner.op('landmark_mask')
                if m:
                    m.par.file = csv_path
                    src = m

        # Build channel name list
        chan_list = self._channels_from_table(src) if src else ''
        sel.par.op = '../in1'
        sel.par.channame = chan_list

# helpers
    # helpers
    def _channels_from_table(self, tab):
        if not tab or tab.numRows <= 1:
            return ''
        heads = [c.val.lower() for c in tab.row(0)]
        out = []
        if 'chan' in heads:
            ci = heads.index('chan')
            for r in tab.rows()[1:]:
                v = r[ci].val.strip()
                if v: out.append(v)
        elif 'name' in heads:
            ni = heads.index('name')
            for r in tab.rows()[1:]:
                nm = r[ni].val.strip()
                if nm:
                    b = nm + '_'
                    out.extend([b+'x', b+'y', b+'z'])
        # de-dup keep order
        seen, uniq = set(), []
        for c in out:
            if c and c not in seen:
                seen.add(c); uniq.append(c)
        return ' '.join(uniq)
    
    def _log(self, msg):
        logdat = self.owner.op('log')
        try:
            if logdat and hasattr(logdat, 'write'): logdat.write(str(msg)+'\n')
            else: print(str(msg))
        except Exception: pass

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
