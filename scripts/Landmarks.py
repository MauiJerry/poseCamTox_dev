    # build the Landmarks Menu, Preloading CSV files
    import os, csv, glob

    def ScanAndBuildMaskMenu(self):
        """Merge data/LandmarkFilterMenu.csv with discovered data/mask*.csv,
        preload each mask to /mask_cache, and (re)build LandmarkFilterMenu_csv.
        """
        base_dir = project.folder
        data_dir = os.path.join(base_dir, 'data')

        def _abs(path_like):
            if not path_like: return ''
            return path_like if os.path.isabs(path_like) else os.path.join(base_dir, path_like)

        # rows: dicts {key,label,csv,include,order}
        rows, seen = [], set()
        def _push(key, label, csvp='', include='1', order='1000'):
            k = (key or '').strip().lower()
            if not k or k in seen: return
            seen.add(k)
            rows.append({
                'key': k,
                'label': (label or k.title()).strip(),
                'csv': (csvp or '').strip(),
                'include': str(include or '1'),
                'order': str(order or '1000')
            })

        # Always start with base rows
        _push('all', 'All', '', '1', '0')
        _push('custom', 'Custom', '', '1', '1')

        # Optional config file
        cfg = os.path.join(data_dir, 'LandmarkFilterMenu.csv')
        if os.path.isfile(cfg):
            try:
                with open(cfg, newline='', encoding='utf-8') as f:
                    for r in csv.DictReader(f):
                        key   = (r.get('key') or '').strip().lower()
                        label = (r.get('label') or '').strip()
                        csvrel= (r.get('csv') or '').strip()
                        inc   = (r.get('include') or '1').strip()
                        order = (r.get('order') or '100').strip()
                        # allow csv to be relative to data/
                        full = _abs(csvrel if os.path.isabs(csvrel) else os.path.join('data', csvrel))
                        _push(key, label, full if csvrel else '', inc, order)
            except Exception as e:
                print('[ScanAndBuildMaskMenu] config read error:', e)

        # Discover masks on disk
        disc = []
        if os.path.isdir(data_dir):
            for pat in (os.path.join(data_dir, 'mask_*.csv'),
                        os.path.join(data_dir, 'masks_*.csv')):
                disc.extend(glob.glob(pat))

        def key_from(path):
            nm = os.path.splitext(os.path.basename(path))[0]
            return nm[5:].lower() if nm.startswith('mask_') else (nm[6:].lower() if nm.startswith('masks_') else nm.lower())

        existing = {r['key'] for r in rows}
        for p in sorted(disc):
            k = key_from(p)
            if k in ('all','custom') or k in existing: continue
            _push(k, k.title().replace('_',' '), p, '1', '1000')

        # Build cache under /mask_cache and record dispatch table
        cache = self.owner.op('mask_cache') or self.owner.create(baseCOMP, 'mask_cache')
        for c in cache.children: c.destroy()
        self._mask_dispatch = {}
        for r in rows:
            k, csvp, inc = r['key'], r['csv'], r['include']
            if csvp:
                self._mask_dispatch[k] = csvp  # record regardless
            if csvp and inc != '0' and os.path.isfile(csvp):
                t = cache.create(tableDAT, f"mask_{k}")
                t.par.file = csvp
                # force immediate load (builds differ: 'reloadpulse' vs 'reload')
                rp = getattr(t.par, 'reloadpulse', None) or getattr(t.par, 'reload', None)
                if rp and hasattr(rp, 'pulse'): rp.pulse()

        # Write/refresh the LandmarkFilterMenu_csv table (pretty csv paths)
        menu = self.owner.op('LandmarkFilterMenu_csv') or self.owner.create(tableDAT, 'LandmarkFilterMenu_csv')
        menu.clear()
        menu.appendRow(['key','label','csv','include','order'])
        def sk(r):
            try: return (int(r['order']), r['label'])
            except: return (1000, r['label'])
        for r in sorted(rows, key=sk):
            csv_show = r['csv']
            if csv_show.startswith(base_dir):
                csv_show = os.path.relpath(csv_show, base_dir).replace('\\','/')
            menu.appendRow([r['key'], r['label'], csv_show, r['include'], r['order']])

        # Stamp menus to effects/child selectors using existing routine
        self.InitLandmarkMenus()

    # ===== Services for children ==============================================
    
    def ResolveMenuCSV(self, key: str) -> str:
        """Given a filter menu key (e.g., 'hands'), return default CSV path."""
        debug("db ResolveMenuCSV PoseEfxSwitchExt", key)
        k = (key or '').strip().lower()
        # NEW: prefer cache from ScanAndBuildMaskMenu
        p = self._mask_dispatch.get(k, '')
        if p: return p
        # FALLBACK: read from LandmarkFilterMenu_csv table (old behavior)
        table = self.owner.op('LandmarkFilterMenu_csv')
        if not table or table.numRows < 2:
            return ''
        heads = [c.val.lower() for c in table.row(0)]
        try:
            ki = heads.index('key'); ci = heads.index('csv')
        except ValueError:
            return ''
        for r in table.rows()[1:]:
            if r[ki].val.strip().lower() == k:
                return (r[ci].val or '').strip()
        return ''
  def ResolveMaskTable(self, key: str):
        """Return cached mask Table DAT for a given key, or None."""
        k = (key or '').strip().lower()
        return self.owner.op('mask_cache/{}'.format(f"mask_{k}"))
