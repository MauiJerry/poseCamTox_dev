Landmark filter rearchitect

this took a bit to get working and still isnt right as of 28 aug.  It currently works with the Default Filter param added to the LandmarkSelect Component.  The menu is not working.

back to figuring out why dots dont match with those coming thru PoseCamPC ndi.

Got it—let’s silo the Landmark Filter so only PoseEffect_Dots owns it, and strip out anything in PoseEfxSwitch and PoseEffectMaster that touches it.

What we’re doing

1. Remove/neutralize any Landmark Filter code, bindings, or expressions in:

PoseEfxSwitch (its Parameter Execute DAT and its PoseEfxSwitchExt).

PoseEffectMaster (its Parameter Execute DAT and extension).



2. Localize the Landmark Filter to PoseEffect_Dots:

PoseEffect_Dots will read a CSV file itself and populate its own menu.

No bindings to parent, no exports, no cross-component meddling.





---

A) Purge “Landmark Filter” meddling upstream

1) In the TouchDesigner UI (PoseEfxSwitch)

Select /project1/PoseEfxSwitch.

Parameters pane → look for the LandmarkFilter (or similarly named) custom parameter:

If the value field is green → it’s Bound. RMB on the field → Edit Bind… → Remove Binding.

If you see a tiny red export flag on the parameter name → RMB → Remove Export.

If the field shows a python expression (purple triangle) → RMB → Expression → Remove Expression.


Operator bindings:

Open the Parameter Execute DAT (likely parexec1) → in the script, delete any onValueChange or onPulse handlers that read or write a Landmark Filter on any child components.

Open the Text DAT for PoseEfxSwitchExt → search for “filter”, “landmark”, “menu”, “csv” and comment/remove any code that:

Reads a CSV and sets menu items/labels on other COMPs.

Writes into PoseEffect_* parameters related to LandmarkFilter.




> Quick TD tip: in Textport, op('/project1/PoseEfxSwitch').findChildren(parName='LandmarkFilter') will help you locate any lingering parameters with that name; kill bindings/exports/expressions on each.



2) In the TouchDesigner UI (PoseEffectMaster)

Select /project1/PoseEfxSwitch/effects/PoseEffectMaster (path may vary).

Repeat the unbind / unexport / remove expression steps above for any Landmark Filter parameter.

Open the Parameter Execute DAT attached to PoseEffectMaster (or its extension DAT):

Delete/disable any code that:

Receives “Landmark Filter” from parent/switcher.

Pushes “Landmark Filter” into child fxCore parameters.



In the Extensions page of PoseEffectMaster:

Open the extension script and remove functions that build or “ensure” Landmark Filter menus or values in children.

If there’s an onStart() (or similar) that sets LandmarkFilter anywhere, remove that logic.



> Goal: No upstream component should modify or feed the Landmark Filter. The parameter can still exist upstream if you want, but it must be inert: no binds, no exports, no expressions, no code touching it.




---

B) Make PoseEffect_Dots load its own Landmark Filter CSV

We’ll give PoseEffect_Dots a self-contained loader:

A Table DAT inside PoseEffect_Dots to serve as the Menu Source.

A Parameter Execute DAT (or tiny extension) to read a CSV file and fill that DAT.

A custom menu parameter whose Menu Source DAT points at that table.

A Pulse to reload, and a String parameter to choose the CSV path.


> You won’t bind anything to parent or to PoseEfxSwitch. This component is self-sufficient.



1) Prepare the CSV

Place your CSV somewhere you control, e.g.:

/project1/PoseEfxSwitch/config/LandmarkFilterMenu.csv

Format suggestion (2 columns, no header required, but headers are okay):

key,label
full,All Landmarks
upper,Upper Body
hands,Hands Only
face,Face Only

First column = internal name (what the parameter value returns).

Second column = label shown in the menu.


2) Add custom parameters on PoseEffect_Dots

Select the PoseEffect_Dots Container COMP (the parent of fxCore for dots).

RMB → Customize Component…

Page: create or reuse a page (e.g., Filter).

Add:

String parameter: FilterCSV (default: project.folder + '/PoseEfxSwitch/config/LandmarkFilterMenu.csv' or just the path you’ll use).

Pulse parameter: ReloadFilterMenu.

Menu parameter: LandmarkFilter.

Set Menu Source DAT to landmark_menu (we’ll create this DAT next).

Use first col for Names and second for Labels.





> If your TD build doesn’t support dynamic Menu Source via GUI, you can still do it—see “Hooking the menu source” note below.



3) Inside PoseEffect_Dots, create the menu source DAT

Dive into PoseEffect_Dots.

Create a Table DAT named landmark_menu.

Leave it empty for now (the loader will fill it).



4) Add the loader code

In PoseEffect_Dots, create a Text DAT named filter_menu_loader and paste this:


# filter_menu_loader
import os, csv

def load_filter_menu(compOwner=None):
    """
    Load the CSV pointed to by ownerComp.par.Filtercsv, fill landmark_menu DAT (2 columns: name, label).
    This does not bind or export anywhere else. Self-contained to PoseEffect_Dots.
    """
    owner = compOwner or parent()  # parent() == PoseEffect_Dots if this DAT is placed directly inside it
    try:
        # Resolve path
        raw_path = owner.par.Filtercsv.eval()
        csv_path = raw_path

        # Allow project.folder prefix use (optional)
        if raw_path.startswith('project.folder'):
            # If user typed "project.folder + '/…/file.csv'"
            # safer to evaluate in TD expressions; here keep simple:
            csv_path = eval(raw_path, {'project': project})  # noqa
    
        csv_path = os.path.normpath(csv_path)
    
        if not os.path.isfile(csv_path):
            debug(f"[PoseEffect_Dots] Landmark CSV not found: {csv_path}")
            _write_table(owner.op('landmark_menu'), [['full','All Landmarks']])
            return
    
        rows = []
        with open(csv_path, 'r', newline='', encoding='utf-8') as f:
            rdr = csv.reader(f)
            header = next(rdr, None)
            # Accept with/without header
            if header and len(header) >= 2 and header[0].lower() in ('key','name') and header[1].lower()=='label':
                # header present, use rows after it
                pass
            else:
                # no header; use the row we just read as data if it has >=2 cols
                if header and len(header) >= 2:
                    rows.append([header[0], header[1]])
    
            for r in rdr:
                if len(r) >= 2 and r[0] and r[1]:
                    rows.append([r[0], r[1]])
    
        if not rows:
            debug("[PoseEffect_Dots] CSV empty or invalid; writing default menu.")
            rows = [['full','All Landmarks']]
    
        _write_table(owner.op('landmark_menu'), rows)
        debug(f"[PoseEffect_Dots] Loaded {len(rows)} filter entries from CSV.")
    
    except Exception as e:
        debug(f"[PoseEffect_Dots] Error loading filter CSV: {e}")
        _write_table(owner.op('landmark_menu'), [['full','All Landmarks']])

def _write_table(tableDAT, rows):
    tableDAT.clear()
    for r in rows:
        tableDAT.appendRow(r)

5) Wire it to start-up and a reload pulse

Create a Parameter Execute DAT inside PoseEffect_Dots named parexec_filter.

Parameters:

Active: On

Parameters: set to FilterCSV ReloadFilterMenu (or leave empty to listen to all and branch in code).

Value Change: On

Pulse: On

File: point it to a synced file if you like; or paste callback code directly:




# parexec_filter callbacks
def onStart():
    # Load menu on component start
    mod.filter_menu_loader.load_filter_menu(ownerComp)
    return

def onPulse(par):
    if par.name == 'ReloadFilterMenu':
        mod.filter_menu_loader.load_filter_menu(ownerComp)
    return

def onValueChange(par, prev):
    if par.name == 'FilterCSV':
        mod.filter_menu_loader.load_filter_menu(ownerComp)
    return

Now PoseEffect_Dots:

Reads FilterCSV.

Populates its own landmark_menu DAT.

The LandmarkFilter menu uses that DAT as its source.

You can Pulse ReloadFilterMenu to re-read the CSV at runtime.



---

C) TouchDesigner “how to click it” cheatsheet

Remove a binding: RMB the parameter field → Edit Bind… → Remove.

Remove an export: RMB the parameter name (has red flag) → Remove Export.

Remove an expression: RMB parameter field → Expression → Delete (or clear the expression).

Point a menu to a DAT:

Customize Component → your Menu parameter → Menu Source DAT → pick landmark_menu.

Ensure “First column are Names”, “Second column are Labels” is set (default behavior in recent builds).



> If your TD build doesn’t expose “Menu Source DAT” reliably for custom parameters, an alternative is to leave the parameter as a String and add a Dropdown Widget (UI) that takes its items/labels from landmark_menu, then writes the selection into the String parameter. But in most 2023+ builds, Menu Source DAT works fine.




---

D) Sanity checks

Textport:

op('/project1/PoseEfxSwitch').par.LandmarkFilter should no longer be bound/exported/expressed anywhere.

op('/project1/PoseEfxSwitch').findChildren(parName='LandmarkFilter') to ensure only your Dots comp uses it (or that others exist but are inert).


Inside PoseEffect_Dots:

par.FilterCSV points where you expect.

landmark_menu fills after start; if not, try Pulse ReloadFilterMenu.


No cooking loops:

Your parexec_filter only writes to a DAT—safe, no CHOP feedback.




---

E) Minimal usage pattern in Dots code

Wherever your dots logic needs to react to the selected filter:

selected = op('..').par.Landmarkfilter.eval()  # from inside fxCore, '..' goes up to PoseEffect_Dots
# Use 'selected' to decide which landmarks to include

No parents involved.


---

If you want, send me the exact operator paths you’re using for the Dots comp and your preferred CSV location, and I’ll tailor the default FilterCSV expression and the onStart code to your project tree so you don’t have to click through path pickers.
... CSV and menu in data folder

Perfect

erfect—since your CSVs live under /data, let’s wire PoseEffect_Dots to (a) read a filter list manifest CSV from /data and (b) load the selected filter’s CSV (also in /data) into the menu—no bindings to EfxSwitch/Master.

What you’ll have after this

PoseEffect_Dots owns two tables:

filter_list — the manifest of available filters (key, label, csv).

landmark_menu — the live 2-col name/label table used by the LandmarkFilter menu.


Two parameters on PoseEffect_Dots:

FilterListCSV — path to the manifest CSV (in /data).

ActiveFilter — menu populated from filter_list (choose which filter CSV to load).


One pulse:

ReloadFilterList — re-reads the manifest and repopulates ActiveFilter.


On ActiveFilter change, the corresponding per-filter CSV in /data is loaded into landmark_menu.



---

TouchDesigner click-path & parameters (on PoseEffect_Dots container)

1. Customize Component… (RMB on PoseEffect_Dots)



Page: Filter

Add String: FilterListCSV
Default value:

project.folder + '/data/landmark_filters_manifest.csv'

> Use your actual filename; this is the manifest (list) CSV.



Add Pulse: ReloadFilterList

Add Menu: ActiveFilter

Menu Source DAT: filter_list

Names: column 0 (keys)

Labels: column 1 (labels)


Add Menu: LandmarkFilter

Menu Source DAT: landmark_menu

Names: column 0

Labels: column 1



> Result: ActiveFilter chooses which filter CSV to load; LandmarkFilter shows the entries from that CSV.




---

Inside PoseEffect_Dots (create these DATs)

Table DAT: filter_list (leave empty; script fills it)

Table DAT: landmark_menu (leave empty; script fills it)

Text DAT: filter_menu_loader — paste code below

Parameter Execute DAT: parexec_filter — paste callbacks below



---

CSV formats in /data/

Manifest CSV (e.g., landmark_filters_manifest.csv) — 3 columns (header allowed):

key,label,csv
full,All Landmarks,landmarks_full.csv
upper,Upper Body,landmarks_upper.csv
hands,Hands Only,landmarks_hands.csv
face,Face Only,landmarks_face.csv

csv is a filename or relative path under /data. (You can also put absolute paths if you want.)


Per-filter CSVs (e.g., landmarks_face.csv) — 2 columns (header optional):

key,label
nose,Nose
left_eye,Left Eye
right_eye,Right Eye
...



---

filter_menu_loader (Text DAT) — drop-in code

# filter_menu_loader
import os, csv

def _norm(path):
    try:
        return os.path.normpath(path)
    except Exception:
        return path

def _write_rows(tableDAT, rows):
    tableDAT.clear()
    for r in rows:
        tableDAT.appendRow(r)

def _project_data_path():
    # Absolute path to the /data folder next to your .toe (adjust if your layout differs)
    return os.path.join(project.folder, 'data')

def load_filter_list(owner=None):
    """
    Load the manifest CSV into filter_list (cols: key, label, csv) and
    repopulate the ActiveFilter menu source.
    """
    comp = owner or parent()
    manifest_path_raw = comp.par.Filterlistcsv.eval()
    # If user supplied just a filename, search in /data
    if not os.path.isabs(manifest_path_raw):
        manifest_path = os.path.join(_project_data_path(), manifest_path_raw)
    else:
        manifest_path = manifest_path_raw
    manifest_path = _norm(manifest_path)

    rows = []
    try:
        with open(manifest_path, 'r', newline='', encoding='utf-8') as f:
            rdr = csv.reader(f)
            header = next(rdr, None)
            has_header = False
            if header and len(header) >= 3:
                h0 = (header[0] or '').strip().lower()
                h1 = (header[1] or '').strip().lower()
                h2 = (header[2] or '').strip().lower()
                has_header = (h0 in ('key','name') and h1 == 'label' and h2 == 'csv')
            else:
                header = None
    
            if not has_header and header and len(header) >= 3:
                rows.append([header[0], header[1], header[2]])
    
            for r in rdr:
                if len(r) >= 3 and r[0] and r[1] and r[2]:
                    rows.append([r[0].strip(), r[1].strip(), r[2].strip()])
    except Exception as e:
        debug(f"[PoseEffect_Dots] Manifest read error: {e}")
    
    if not rows:
        debug("[PoseEffect_Dots] Manifest empty/invalid. Seeding one default entry.")
        rows = [['full','All Landmarks','landmarks_full.csv']]
    
    _write_rows(comp.op('filter_list'), rows)
    debug(f"[PoseEffect_Dots] Loaded {len(rows)} filter list entries.")

def load_active_filter(owner=None):
    """
    Using ActiveFilter key, resolve CSV from filter_list and load it into landmark_menu.
    """
    comp = owner or parent()
    key = comp.par.Activefilter.eval().strip()
    table = comp.op('filter_list')
    if table.numRows <= 0 or table.numCols < 3:
        debug("[PoseEffect_Dots] filter_list is empty or malformed; try ReloadFilterList.")
        _write_rows(comp.op('landmark_menu'), [['full', 'All Landmarks']])
        return

    # Build a map key -> csv
    csv_map = {}
    for i in range(table.numRows):
        row = table.row(i)
        if len(row) >= 3:
            k = row[0].val.strip()
            c = row[2].val.strip()
            if k:
                csv_map[k] = c
    
    csv_name = csv_map.get(key)
    if not csv_name:
        # Fallback to first entry
        first = table.row(0)
        csv_name = first[2].val.strip()
        comp.par.Activefilter = first[0].val.strip()
        debug(f"[PoseEffect_Dots] ActiveFilter '{key}' not found. Fell back to '{comp.par.Activefilter.eval()}'")
    
    # Resolve CSV path in /data if relative
    if not os.path.isabs(csv_name):
        csv_path = os.path.join(_project_data_path(), csv_name)
    else:
        csv_path = csv_name
    csv_path = _norm(csv_path)
    
    # Read per-filter CSV -> landmark_menu (2 cols)
    rows = []
    try:
        with open(csv_path, 'r', newline='', encoding='utf-8') as f:
            rdr = csv.reader(f)
            header = next(rdr, None)
            has_header = False
            if header and len(header) >= 2:
                h0 = (header[0] or '').strip().lower()
                h1 = (header[1] or '').strip().lower()
                has_header = (h0 in ('key','name') and h1 == 'label')
            else:
                header = None
    
            if not has_header and header and len(header) >= 2:
                rows.append([header[0], header[1]])
    
            for r in rdr:
                if len(r) >= 2 and r[0] and r[1]:
                    rows.append([r[0].strip(), r[1].strip()])
    except Exception as e:
        debug(f"[PoseEffect_Dots] Filter CSV read error ({csv_path}): {e}")
    
    if not rows:
        debug("[PoseEffect_Dots] Filter CSV empty/invalid; writing default.")
        rows = [['full','All Landmarks']]
    
    _write_rows(comp.op('landmark_menu'), rows)
    debug(f"[PoseEffect_Dots] Loaded {len(rows)} landmark entries from {os.path.basename(csv_path)}")


---

parexec_filter (Parameter Execute DAT) — callbacks

Set Active=On, Value Change=On, Pulse=On. You can leave Parameters empty (we branch by name).

def onStart():
    mod.filter_menu_loader.load_filter_list(ownerComp)
    mod.filter_menu_loader.load_active_filter(ownerComp)
    return

def onPulse(par):
    if par.name == 'ReloadFilterList':
        mod.filter_menu_loader.load_filter_list(ownerComp)
        # Keep current ActiveFilter if still present; otherwise loader will fall back.
        mod.filter_menu_loader.load_active_filter(ownerComp)
    return

def onValueChange(par, prev):
    # When user changes which filter to use, reload the per-filter CSV
    if par.name == 'ActiveFilter':
        mod.filter_menu_loader.load_active_filter(ownerComp)
    elif par.name == 'FilterListCSV':
        # Manifest path changed; reload list & active
        mod.filter_menu_loader.load_filter_list(ownerComp)
        mod.filter_menu_loader.load_active_filter(ownerComp)
    return


---

Using the selection in your fxCore

From inside fxCore Script CHOPs or DATs (one level down), reference:

selected_filter = op('..').par.Activefilter.eval()     # which filter set is active
landmark_choice = op('..').par.Landmarkfilter.eval()   # which landmark entry is selected

ActiveFilter picks which per-filter CSV to load.

LandmarkFilter is the actual per-landmark choice used by your effect.



---

TD cleanup reminder (so nothing “mucks” with it)

On PoseEfxSwitch and PoseEffectMaster:
remove any bindings/exports/expressions touching ActiveFilter, LandmarkFilter, or CSV paths.

Keep all filter logic isolated in PoseEffect_Dots.


If you drop me the exact filenames in /data, I’ll plug them into the defaults so you don’t have to type paths.

