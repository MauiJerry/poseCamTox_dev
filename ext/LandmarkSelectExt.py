"""
LandmarkSelectExt: An extension for managing landmark channel filtering.

This extension is designed to be placed on a component that contains:
- A 'switch1' CHOP (to bypass or engage filtering)
- A 'select1' CHOP (to select landmark channels by name)
- A 'landmark_mask' Table DAT (to hold the list of active landmark names)

It works in conjunction with a master 'landmark filter menu' DAT, which is a
manifest of available filters (e.g., 'full', 'upper_body') and the CSV
files associated with them.

Primary Method: LoadMask()
- Reads a 'Mask' parameter from its owner.
- If the mask is 'all' or empty, it bypasses the filter.
- Otherwise, it looks up the mask name in the menu DAT to find a CSV file.
- It loads the landmark names from that CSV into the 'landmark_mask' DAT.
- It generates a channel name pattern (e.g., "p*_nose_x p*_nose_y ...") and
  configures the 'select1' CHOP.
- It activates the 'switch1' CHOP to use the filtered channel set.

Integration:
- An Execute DAT's onStart() should call self.owner.ext.LandmarkSelectExt.Initialize().
- A Parameter Execute DAT should monitor the owner's 'Mask' parameter and call
  self.owner.ext.LandmarkSelectExt.LoadMask() on change.
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
        # A re-entrancy guard to prevent feedback loops if LoadMask is called rapidly
        self._loading = False
        debug(f"LandmarkSelectExt initialized on {ownerComp.path}")

    def Initialize(self):
        """
        A method to be called from an onStart() or onCreate() callback.
        Ensures the initial mask state is loaded correctly.
        """
        debug(f"[{self.owner.name}] Initialize called")
        self.LoadMask()

    def LoadMask(self):
        """
        Loads the landmark mask based on the owner's 'Mask' parameter.

        This is the main entry point for updating the filter. It finds the
        correct landmark list, populates the local mask table, and sets up
        the CHOP network to filter the incoming pose data.
        """
        debug(f"[{self.owner.name}] LoadMask called")
        if self._loading:
            return
        self._loading = True
        try:
            self._load_mask_internal()
        finally:
            self._loading = False

    def _load_mask_internal(self):
        """Internal implementation of LoadMask to be wrapped by a guard."""
        owner = self.owner

        # --- 1. Locate required operators and parameters ---
        try:
            switchChop = owner.op('switch1')  # The CHOP that switches between pass-through and filtered
            selectChop = owner.op('select1') # The CHOP that selects landmark channels by name
            mask_tableDat = owner.op('landmark_mask')
            menu_dat = owner.op('LandmarkFilterMenu_csv')
            # The parameter pointing to the master menu DAT
            mask_par = owner.par.Mask
        except Exception as e:
            debug(f"ERROR: LandmarkSelectExt could not find a required OP or parameter on {owner.path}: {e}")
            return

        if not all([switchChop, selectChop, mask_tableDat, menu_dat, mask_par]):
            debug(f"ERROR: LandmarkSelectExt on {owner.path} is missing required operators.")
            return

        # --- 2. Get current mask name ---
        mask_name = (mask_par.eval() or '').strip().lower()

        # --- 3. Handle pass-through case for 'all' or empty mask ---
        if not mask_name or mask_name == 'all':
            debug(f"[{owner.name}] Mask is '{mask_name}', setting to pass-through.")
            if switchChop.par.index != 0:
                switchChop.par.index = 0
            if not selectChop.bypass:
                selectChop.bypass = True
            # Clear the table but keep the header for clarity
            if mask_tableDat.numRows > 1 or mask_tableDat.numCols == 0:
                mask_tableDat.clear()
                mask_tableDat.appendRow(['name'])
            return
        # not all, so load the mask table
        
        # --- 4. Look up CSV filename in the menu DAT ---
        csv_filename = self._find_csv_for_mask(mask_name, menu_dat)

        if not csv_filename:
            debug(f"WARNING: Mask key '{mask_name}' not found in {menu_dat.path}. Falling back to pass-through.")
            # go back to pass-through
            if switchChop.par.index != 0:
                switchChop.par.index = 0
            if not selectChop.bypass:
                selectChop.bypass = True
            return

        # --- 5. Read the landmark names from the specified CSV ---
        landmark_names = self._read_landmarks_from_csv(csv_filename)

        if landmark_names is None: # Indicates an error during file read
            debug(f"WARNING: Failed to read landmarks from '{csv_filename}'. Falling back to pass-through.")
            if switchChop.par.index != 0:
                switchChop.par.index = 0
            if not selectChop.bypass:
                selectChop.bypass = True
            return

        # --- 6. Populate the local 'landmark_mask' Table DAT ---
        # note the DAT is just for reference. The Select CHOP uses patterns.
        mask_tableDat.clear()
        mask_tableDat.appendRow(['name'])
        for name in landmark_names:
            mask_tableDat.appendRow([name])

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
        if selectChop.par.channames.eval() != pattern:
            selectChop.par.channames = pattern

        # --- 8. Activate the filter path in the CHOP network ---
        if selectChop.bypass:
            selectChop.bypass = False
        if switchChop.par.index != 1:
            switchChop.par.index = 1

        debug(f"[{owner.name}] Loaded mask '{mask_name}' with {len(landmark_names)} landmarks.")

    def _find_csv_for_mask(self, mask_name, menu_dat):
        """Looks up a mask key in the menu DAT and returns the csv filename."""
        # Assumes menu_dat has columns: key, label, csv
        for i in range(menu_dat.numRows):
            key_cell = menu_dat[i, 0]
            if key_cell is not None and key_cell.val.strip().lower() == mask_name:
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

        landmark_names = []
        try:
            with open(csv_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                # Check for a header row (e.g., 'key', 'name') and skip it
                if header and header[0].strip().lower() in ('key', 'name'):
                    pass
                # If it wasn't a header, treat it as the first data row
                elif header and header[0].strip():
                    landmark_names.append(header[0].strip())

                # Read the first column of all subsequent rows
                for row in reader:
                    if row and row[0].strip():
                        landmark_names.append(row[0].strip())
            return landmark_names
        except Exception as e:
            debug(f"ERROR: Failed to read or parse landmark CSV {csv_path}: {e}")
            return None