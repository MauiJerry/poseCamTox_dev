def onCreate(comp, template, master, row):
    comp.par.start_lm = row['start_lm']
    comp.par.end_lm   = row['end_lm']
    comp.par.start_r  = float(row['start_r'])
    comp.par.end_r    = float(row['end_r'])
    return
