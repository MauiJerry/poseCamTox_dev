# landmarkSelect landmarkFilterMenu_csv DAT extension
# 
# This extension is attached to a Table DAT and is responsible for populating it
# with data from a CSV file on project start or component creation. It also
# populates the parent component's menu parameter.

import os
import csv

def rebuildMaskMenu(table_dat):
	"""
	Populates the parent's 'landmarkMaskMenu' parameter from this DAT's contents.
	It assumes the parent COMP has a 'landmarkMaskMenu' menu parameter.
	"""
	parent_comp = table_dat.parent()
	if not parent_comp:
		debug(f"ERROR: {table_dat.path} has no parent to update.")
		return

	try:
		# The menu parameter on the parent component (e.g., LandmarkSelect)
		menu_par = parent_comp.par.landmarkMaskMenu
	except Exception:
		debug(f"ERROR: Parameter 'landmarkMaskMenu' not found on parent {parent_comp.path}.")
		return

	# The table DAT (owner of this extension) is the source of truth.
	# First row is header, so we read from row 1 onwards.
	keys = [table_dat[r, 0].val for r in range(1, table_dat.numRows)]
	labels = [table_dat[r, 1].val for r in range(1, table_dat.numRows)]

	# Manually insert the 'all' option at the beginning of the menu.
	# This is a special value handled by the LandmarkSelectExt for pass-through.
	keys.insert(0, 'all')
	labels.insert(0, 'All (Pass-through)')
	# might be duplicating all, as the dat will containe thats
	menu_par.menuNames = keys
	menu_par.menuLabels = labels
	
	# Ensure the current value is still valid
	if menu_par.eval() not in keys:
		menu_par.val = keys[0]

	debug(f"Rebuilt landmarkMaskMenu on {parent_comp.path} with {len(keys)} items.")

def _loadLandmarkMenuCSV(table_dat):
	"""
	Clears the target Table DAT and populates it from a CSV file.
	After loading, it calls a function to rebuild the parent's UI menu.

	- The CSV is expected at: project.folder/data/landmarkFilterMenu.csv
	- The CSV should have 3 columns: key, label, csv
	- The target DAT will be populated with a header and the CSV data.
	"""
	def _process_and_add_row(row_data):
		"""Helper to process a CSV row, add it to the DAT, and handle special keys."""
		if len(row_data) < 3:
			return
		key, label, csv_val = row_data[0].strip(), row_data[1].strip(), row_data[2].strip()
		
		# Per request, skip 'all' as it's handled programmatically in the menu.
		if key.lower() == 'all':
			return

		table_dat.appendRow([key, label, csv_val])

		# If this row's key is 'custom', set the associated parameter on the owner.
		if key.lower() == 'custom':
			try:
				# The parameter is on the DAT's parent, not the DAT itself.
				parent_comp = table_dat.parent()
				if hasattr(parent_comp.par, 'custom_mask_name'):
					parent_comp.par.custom_mask_name = csv_val
				else:
					debug(f"WARNING: Parameter 'custom_mask_name' not found on {parent_comp.path}")
			except Exception as e:
				debug(f"ERROR: Could not set 'custom_mask_name' on {parent_comp.path}: {e}")

	debug(f"[{table_dat.name}] Loading landmark filter menu...")

	# a) Clears the associated DAT
	table_dat.clear()

	# b) Adds the header row
	table_dat.appendRow(['key', 'label', 'csv'])

	# c) Reads project/data/landmarkFilterMenu.csv
	csv_path_raw = project.folder + '/data/landmarkFilterMenu.csv'
	csv_path = os.path.normpath(csv_path_raw)

	file_found = os.path.isfile(csv_path)

	if file_found:
		try:
			with open(csv_path, 'r', newline='', encoding='utf-8') as f:
				reader = csv.reader(f)

				# Skip first row if it's a header
				header = next(reader, None)
				if header and header[0].strip().lower() == 'key':
					# Header found and skipped, do nothing.
					pass
				elif header:
					# First row is not a header, so process it as the first data row.
					_process_and_add_row(header)
				else:
					# File is empty
					debug(f"WARNING: CSV file is empty: {csv_path}")

				# Add remaining rows to the DAT
				for row in reader:
					_process_and_add_row(row)

		except Exception as e:
			debug(f"ERROR: Failed to process CSV file {csv_path}: {e}")
			file_found = False # Treat as not found on error

	if not file_found:
		debug(f"INFO: CSV not found or failed to load. Using default menu entries.")
		# Clear any partial data and add defaults
		table_dat.clear()
		table_dat.appendRow(['key', 'label', 'csv'])
		_process_and_add_row(['full', 'All Landmarks', 'landmarks_full.csv'])
		_process_and_add_row(['custom', 'Custom', 'mask_custom.csv'])

	# After loading the DAT, rebuild the menu on the parent component.
	rebuildMaskMenu(table_dat)

def onStart():
	"""Called when the project starts."""
	_loadLandmarkMenuCSV(ownerComp)

def onCreate():
	"""Called when the component is created."""
	_loadLandmarkMenuCSV(ownerComp)