"""
LandmarkSelectExt: An extension for managing landmark channel filtering.

This extension is designed to be placed on a component that contains:
- Custom Parameters:
  - 'Landmarkfiltermenu' (Menu): Selects the active filter.
  - 'Currentfilter' (String): A read-only parameter reflecting the active filter.
  - 'Customfiltercsv' (String): Path to a landmark list csv for use when menu is Custom
  - 'Rebuildmenu' (Pulse): Triggers a rebuild of the menu.
- A 'switch1' CHOP (to bypass or engage filtering)
- A 'select1' CHOP (to select landmark channels by name)
- A 'landmark_filter' Table DAT (to hold the list of active landmark names)
- A 'LandmarkFilterMenu_csv' Table DAT (the menu source, populated from the manifest CSV)

Primary Method: LoadActiveFilter()
- Reads the 'Landmarkfiltermenu' parameter from its owner.
- If the filter is 'all' or empty, it bypasses the filter.
- Otherwise, it looks up the filter name in the 'LandmarkFilterMenu_csv' DAT to find a CSV file.
- It loads the landmark names from that CSV into the 'landmark_filter' DAT.
- It generates a channel name pattern (e.g., "p*_nose_x p*_nose_y ...") and
  configures the 'select1' CHOP.
- It activates the 'switch1' CHOP to use the filtered channel set.

Integration:
- An Execute DAT's onStart() should call owner.ext.LandmarkSelectExt.Initialize().
- A Parameter Execute DAT should monitor 'Landmarkfiltermenu' and 'Rebuildmenu'
  to call LoadActiveFilter() and RebuildMenu() respectively.
"""
import os
import csv

class LandmarkSelectExt:
    """
    Manages landmark filtering by loading masks and configuring CHOPs.
    """
    def __init__(self, ownerComp):
        """
        Initializes the extension.

        Args:
            ownerComp (COMP): The component this extension is attached to.
        """
        self.owner = ownerComp   
        debug(f"LandmarkSelectExt __init__ called for {self.owner.name}" )
             
        # A re-entrancy guard to prevent feedback loops if LoadActiveFilter is called rapidly
        self._loading = False

        # --- Cache references to operators and parameters for performance and clarity ---
        self.switchChop = self.owner.op('switch1')
        self.selectChop = self.owner.op('select1')
        self.filter_tableDat = self.owner.op('landmark_filter')
        self.menu_dat = self.owner.op('LandmarkFilterMenu_csv')

        # During initialization, owner.pars() can sometimes fail to find custom parameters.
        # A direct lookup in owner.customPars is more reliable.
        self.filtermenu_par = self._lookup_custom_parameter('Landmarkfiltermenu')
        self.current_filter_par = self._lookup_custom_parameter('Currentfilter')
        self.customfiltercsv_par = self._lookup_custom_parameter('Customfiltercsv')
        self.defaultfilter_par = self._lookup_custom_parameter('Defaultfilter')

        print(f"list custom parameters of {self.owner.name}")
        for p in self.owner.customPars:
            print(f"{p.name} = {p.eval()}")
            
        self.is_valid = False
        self._validate_ops()
        
        self.onExtensionReady()

        debug(f"LandmarkSelectExt __init__ complete on {ownerComp.path}")

    def _lookup_custom_parameter(self, name):
        """
        Searches owner's custom parameters for a parameter by name.
        This is a robust alternative to owner.pars() during initialization.
        
        Args:
            name (str): The name of the custom parameter to find.
        """
        for p in self.owner.customPars:
            if p.name == name:
                debug(f"Found custom parameter '{name}' on {self.owner.path}")
                return p
        debug(f"ERROR: Custom parameter '{name}' not found on {self.owner.path}")   
        return None

    def _validate_ops(self):
        """
        Checks if all cached operator and parameter references are still valid.
        This makes the component robust against live-editing changes like renaming.
        Updates self.is_valid and returns the new state.
        """
        required = [
            ('switch1', self.switchChop),
            ('select1', self.selectChop),
            ('landmark_filter', self.filter_tableDat),
            ('LandmarkFilterMenu_csv', self.menu_dat),
            ('Landmarkfiltermenu', self.filtermenu_par),
            ('Currentfilter', self.current_filter_par),
            ('Customfiltercsv', self.customfiltercsv_par),
            ('Defaultfilter', self.defaultfilter_par),
        ]
        # debug(f"_validate_ops called required is {required}" )

        for name, op_or_par in required:
            # Use an explicit 'is None' check for robustness. This is clearer than
            # an implicit boolean check and avoids ambiguity with "falsy" objects.
            if op_or_par is None:
                debug(f"ERROR: LandmarkSelectExt on {self.owner.path} could not find '{name}' (reference is None).")
                self.is_valid = False
                return False
            # If the reference exists, check if the underlying object is still valid.
            if not op_or_par.valid:
                debug(f"ERROR: LandmarkSelectExt on {self.owner.path} '{name}' is not valid")
                self.is_valid = False
                return False
        self.is_valid = True
        debug("_validate_ops ok")
        return True

    def onExtensionReady(self):
        """
        This method is called by TouchDesigner when the extension is ready.
        """
        debug(f"[{self.owner.name}] onExtensionReady: Initializing...")
        self.Initialize()
        debug(f"[{self.owner.name}] onExtensionReady complete.")


    def Initialize(self):
        """
        A method to be called from an onStart() or onCreate() callback.
        Rebuilds the menu and ensures the initial filter state is loaded correctly.
        """
        debug(f"[{self.owner.name}] Initialize called")
        self.RebuildMenu()
        debug(f"[{self.owner.name}] Initialize complete")

    def LoadActiveFilter(self):
        """
        Loads the landmark filter csv based on the owner's 'Landmarkfiltermenu' parameter.

        This is the main entry point for updating the filter. It finds the
        correct landmark list, populates the local mask table, and sets up
        the CHOP network to filter the incoming pose data.
        """
        debug(f"[{self.owner.name}] LoadActiveFilter called")

        # Re-validate on every call to protect against live-editing changes.
        if not self._validate_ops():
            debug(f"ERROR [{self.owner.name}]  LoadActiveFilter failed validation")
            return

        if self._loading:
            debug(f"Info [{self.owner.name}]  LoadActiveFilter already loading")
            return
        
        self._loading = True
        try:
            self._load_filter_internal()
        finally:
            self._loading = False
        debug(f"[{self.owner.name}] LoadActiveFilter complete")

    def _set_pass_through_mode(self, passthrough, reason=""):
        """
        Helper to configure the component for pass-through or active filtering.

        Args:
            passthrough (bool): If True, sets to pass-through. If False, enables filtering.
            reason (str, optional): A description of why the mode is changing.
        """
        if not self.is_valid:
            debug(f"[{self.owner.name}] _set_pass_through_mode not is_valid")   
            return

        if reason:
            debug(f"[{self.owner.name}] {reason}")
        
        if passthrough:
            debug(f"[{self.owner.name}] Setting pass-through mode.")
            if self.switchChop.par.index != 0: self.switchChop.par.index = 0
            if not self.selectChop.bypass: self.selectChop.bypass = True
            if self.filter_tableDat.numRows > 1 or self.filter_tableDat.numCols == 0:
                self.filter_tableDat.clear()
                self.filter_tableDat.appendRow(['name'])
        else: # Active filtering mode
            debug(f"[{self.owner.name}] Setting active filter mode.")
            if self.selectChop.bypass: self.selectChop.bypass = False
            if self.switchChop.par.index != 1: self.switchChop.par.index = 1

    def _load_filter_internal(self):
        """Internal implementation of LoadActiveFilter to be wrapped by a guard."""
        if not self.is_valid:
            debug(f"[{self.owner.name}] LoadActiveFilter not is_valid")
            return 0

        # --- 1. Debug menu contents as requested ---
        debug(f"Filter Menu Parameter '{self.filtermenu_par.name}' contents:")
        debug(f"  - Menu Names: {self.filtermenu_par.menuNames}")
        debug(f"  - Menu Labels: {self.filtermenu_par.menuLabels}")
        debug(f"  - Current Value: {self.filtermenu_par.eval()}")

        # --- 2. Determine the active filter name, using 'Defaultfilter' as an override ---
        default_filter_override = (self.defaultfilter_par.eval() or '').strip().lower()
        
        if default_filter_override and default_filter_override != 'all':
            filter_name = default_filter_override
            debug(f"Using override filter from 'Defaultfilter' parameter: '{filter_name}'")
        else:
            filter_name = (self.filtermenu_par.eval() or '').strip().lower()
            debug(f"Using filter from 'Landmarkfiltermenu' parameter: '{filter_name}'")

        # Update the read-only Currentfilter parameter for display
        if self.current_filter_par.eval() != filter_name:
            self.current_filter_par.val = filter_name

        # --- 3. Handle pass-through case for 'all' or empty filter ---
        if not filter_name or filter_name == 'all':
            self._set_pass_through_mode(True, reason=f"Filter is '{filter_name}'")
            debug(f"[{self.owner.name}] load filter is ALL, should set passthru")
            return 1

        # --- 4. Look up CSV filename in the menu DAT ---
        csv_filename = self._find_csv_for_filter(filter_name, self.menu_dat)

        if not csv_filename:
            self._set_pass_through_mode(True, reason=f"Filter key '{filter_name}' not found in {self.menu_dat.path}")
            return 1

        # --- 5. Read the landmark names from the specified CSV ---
        landmark_names = self._read_landmarks_from_csv(csv_filename)

        if landmark_names is None: # Indicates an error during file read
            self._set_pass_through_mode(True, reason=f"Failed to read landmarks from '{csv_filename}'")
            return 1

        # --- 6. Populate the local 'landmark_filter' Table DAT ---
        # note the DAT is just for reference. The Select CHOP uses patterns.
        self.filter_tableDat.clear()
        self.filter_tableDat.appendRow(['name'])
        for name in landmark_names:
            self.filter_tableDat.appendRow([name])

        # --- 7. Configure the 'select1' CHOP with channel patterns ---
        # A Select CHOP uses channel name patterns, not a DAT reference.
        # We generate this pattern from the loaded landmark names.
        expanded_names = []
        for name in landmark_names:
            # The 'p*' wildcard will match any person ID (p1, p2, etc.)
            base = f"p*_{name}"
            expanded_names.extend([f"{base}_x", f"{base}_y", f"{base}_z"])

        pattern = ' '.join(expanded_names)

        # a space-separated list of channel names pushed into the select CHOP
        if self.selectChop.par.channames.eval() != pattern:
            self.selectChop.par.channames = pattern

        # --- 8. Activate the filter path in the CHOP network ---
        self._set_pass_through_mode(False, reason=f"Loaded filter '{filter_name}'")
        debug(f"[{self.owner.name}] Loaded filter '{filter_name}' with {len(landmark_names)} landmarks.")

    def RebuildMenu(self):
        """
        Rebuilds the landmark filter menu from a fixed source CSV file.
        It loads 'data/landmarkFilterMenu.csv', populates the menu source DAT,
        and checks for a 'custom' entry to update the 'Customfiltercsv' parameter.
        """
        debug(f"[{self.owner.name}] RebuildMenu called")

        # Re-validate on every call to protect against live-editing changes.
        if not self._validate_ops():
            debug(f"[{self.owner.name}] RebuildMenu validate failed")
            return 0

        # The path is now fixed to 'data/landmarkFilterMenu.csv'.
        manifest_filename = 'data/landmarkFilterMenu.csv'
        csv_path = os.path.normpath(os.path.join(project.folder, manifest_filename))

        # Clear the menu DAT to ensure a clean state, but add a header for clarity on failure.
        self.menu_dat.clear()
        self.menu_dat.appendRow(['key', 'label', 'csv'])

        if not os.path.isfile(csv_path):
            debug(f"ERROR: Menu manifest CSV not found: {csv_path}")
            return 0

        try:
            with open(csv_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                # Clear the DAT again to remove the placeholder header before populating.
                self.menu_dat.clear()
                for row in reader:
                    self.menu_dat.appendRow(row)
            debug(f"[{self.owner.name}] Rebuilt menu from {csv_path} with {self.menu_dat.numRows} entries.")

            # After loading, check for a 'custom' entry and update the parameter.
            self._update_custom_csv_par_from_menu()

        except Exception as e:
            debug(f"ERROR: Failed to read or parse menu manifest CSV {csv_path}: {e}")
            # Ensure menu is in a safe, empty state with a header.
            self.menu_dat.clear()
            self.menu_dat.appendRow(['key', 'label', 'csv'])
            return 0

        # After rebuilding, reload the current filter to ensure consistency.
        v = self.LoadActiveFilter()
        return 1

    def _update_custom_csv_par_from_menu(self):
        """
        Scans the menu DAT for a 'custom' entry and updates the Customfiltercsv
        parameter with the path specified in that entry's 'csv' column.
        """
        if not self.is_valid:
            return

        for i in range(self.menu_dat.numRows):
            key_cell = self.menu_dat[i, 0]
            # Check for 'custom' key in the first column
            if key_cell and key_cell.val.strip().lower() == 'custom':
                # Check for a non-empty path in the third column
                csv_cell = self.menu_dat[i, 2]
                if csv_cell and csv_cell.val.strip():
                    custom_path = csv_cell.val.strip()
                    # Update the parameter only if the value has changed
                    if self.customfiltercsv_par.eval() != custom_path:
                        self.customfiltercsv_par.val = custom_path
                        debug(f"Updated 'Customfiltercsv' parameter to: {custom_path}")
                return # Found the custom row, no need to continue

    def _find_csv_for_filter(self, filter_name, menu_dat):
        """Looks up a filter key in the menu DAT and returns the csv filename."""
        # Assumes menu_dat has columns: key, label, csv
        for i in range(menu_dat.numRows):
            key_cell = menu_dat[i, 0]
            if key_cell is not None and key_cell.val.strip().lower() == filter_name:
                csv_cell = menu_dat[i, 2]
                if csv_cell is not None:
                    return csv_cell.val.strip()
        return None

    def _read_landmarks_from_csv(self, csv_filename):
        """Reads the first column from a CSV file in the /data folder."""
        # Construct path relative to project's /data folder
        csv_path = os.path.normpath(os.path.join(project.folder, 'data', csv_filename))

        if not os.path.isfile(csv_path):
            debug(f"ERROR: Landmark CSV file not found: {csv_path}")
            return None

        try:
            with open(csv_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                # Read all non-empty rows from the CSV
                all_rows = [row for row in reader if row and row[0].strip()]
                if not all_rows:
                    return [] # Handle empty or effectively empty files

                # Check if the first row is a header and should be skipped
                first_cell = all_rows[0][0].strip().lower()
                if first_cell in ('key', 'name', 'landmark'):
                    data_rows = all_rows[1:]
                else:
                    data_rows = all_rows
                
                # Extract the first column from the data rows
                return [row[0].strip() for row in data_rows]
        except Exception as e:
            debug(f"ERROR: Failed to read or parse landmark CSV {csv_path}: {e}")
            return None