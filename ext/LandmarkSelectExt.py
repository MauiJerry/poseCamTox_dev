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
        debug(f"LandmarkSelectExt __init__ called for {ownerComp.name}" )
             
        # A re-entrancy guard to prevent feedback loops if LoadActiveFilter is called rapidly
        self._loading = False

        # --- Cache references to operators and parameters for performance and clarity ---
        self.switchChop = self.owner.op('switch1')
        self.selectChop = self.owner.op('select1')
        self.filter_tableDat = self.owner.op('landmark_filter')
        self.menu_dat = self.owner.op('LandmarkFilterMenu_csv')
        
        self.filter_par = self.owner.par.Landmarkfiltermenu
        self.current_filter_par = self.owner.par.Currentfilter
        self.csv_path_par = self.owner.par.Customfiltercsv

        self.is_valid = False
        self._validate_ops()

        debug(f"LandmarkSelectExt initialized on {ownerComp.path}")

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
            ('Landmarkfiltermenu', self.filter_par),
            ('Currentfilter', self.current_filter_par),
            ('Customfiltercsv', self.csv_path_par),
        ]

        for name, op_or_par in required:
            # The .valid attribute works for both OPs and Par objects
            if not op_or_par or not op_or_par.valid:
                if self.is_valid: # Only log the error on the first failure
                    debug(f"ERROR: LandmarkSelectExt on {self.owner.path} has an invalid reference to '{name}'. It will be disabled until fixed.")
                self.is_valid = False
                return False
        
        self.is_valid = True
        return True

    def Initialize(self):
        """
        A method to be called from an onStart() or onCreate() callback.
        Rebuilds the menu and ensures the initial filter state is loaded correctly.
        """
        debug(f"[{self.owner.name}] Initialize called")
        self.RebuildMenu()

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
            return

        if self._loading:
            return
        self._loading = True
        try:
            self._load_filter_internal()
        finally:
            self._loading = False

    def _set_pass_through_mode(self, reason=""):
        """Helper to configure the component for pass-through mode."""
        if not self.is_valid:
            return

        if reason:
            debug(f"[{self.owner.name}] {reason}, setting to pass-through.")
        
        if self.switchChop.par.index != 0:
            self.switchChop.par.index = 0
        if not self.selectChop.bypass:
            self.selectChop.bypass = True
            
        # Clear the table but keep the header for clarity
        if self.filter_tableDat.numRows > 1 or self.filter_tableDat.numCols == 0:
            self.filter_tableDat.clear()
            self.filter_tableDat.appendRow(['name'])

    def _load_filter_internal(self):
        """Internal implementation of LoadActiveFilter to be wrapped by a guard."""
        if not self.is_valid:
            return

        # --- 2. Get current filter name from the menu parameter ---
        filter_name = (self.filter_par.eval() or '').strip().lower()

        # Update the read-only Currentfilter parameter for display
        if self.current_filter_par.eval() != filter_name:
            self.current_filter_par.val = filter_name

        # --- 3. Handle pass-through case for 'all' or empty filter ---
        if not filter_name or filter_name == 'all':
            self._set_pass_through_mode(f"Filter is '{filter_name}'")
            return
        
        # --- 4. Look up CSV filename in the menu DAT ---
        csv_filename = self._find_csv_for_filter(filter_name, self.menu_dat)

        if not csv_filename:
            self._set_pass_through_mode(f"Filter key '{filter_name}' not found in {self.menu_dat.path}")
            return

        # --- 5. Read the landmark names from the specified CSV ---
        landmark_names = self._read_landmarks_from_csv(csv_filename)

        if landmark_names is None: # Indicates an error during file read
            self._set_pass_through_mode(f"Failed to read landmarks from '{csv_filename}'")
            return

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
        if self.selectChop.bypass:
            self.selectChop.bypass = False
        if self.switchChop.par.index != 1:
            self.switchChop.par.index = 1

        debug(f"[{self.owner.name}] Loaded filter '{filter_name}' with {len(landmark_names)} landmarks.")

    def RebuildMenu(self):
        """
        Rebuilds the landmark filter menu from the source CSV file.
        Reads the path from the 'Customfiltercsv' parameter, loads the CSV,
        and populates the menu source DAT ('LandmarkFilterMenu_csv').
        """
        # Re-validate on every call to protect against live-editing changes.
        if not self._validate_ops():
            return

        if not self.is_valid:
            return

        debug(f"[{self.owner.name}] RebuildMenu called")

        csv_path = self.csv_path_par.eval()
        if not csv_path:
            debug(f"WARNING: 'Customfiltercsv' parameter is empty. Cannot rebuild menu.")
            self.menu_dat.clear()
            self.menu_dat.appendRow(['key', 'label', 'csv'])
            return

        if not os.path.isabs(csv_path):
            csv_path = os.path.normpath(os.path.join(project.folder, csv_path))

        if not os.path.isfile(csv_path):
            debug(f"ERROR: Menu manifest CSV not found: {csv_path}")
            self.menu_dat.clear()
            self.menu_dat.appendRow(['key', 'label', 'csv'])
            return

        try:
            with open(csv_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                self.menu_dat.clear()
                for row in reader:
                    self.menu_dat.appendRow(row)
            debug(f"[{self.owner.name}] Rebuilt menu from {csv_path} with {self.menu_dat.numRows} entries.")
        except Exception as e:
            debug(f"ERROR: Failed to read or parse menu manifest CSV {csv_path}: {e}")
            # Clear the menu to avoid using stale data
            self.menu_dat.clear()
            self.menu_dat.appendRow(['key', 'label', 'csv'])
            return

        # After rebuilding, reload the current filter to ensure consistency.
        self.LoadActiveFilter()

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