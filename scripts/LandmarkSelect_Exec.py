# td/scripts/LandmarkSelect_Exec.py
# This script, for an Execute DAT, manages the landmark mask menu for its parent component.
# It reads 'data/landmarkFilterMenu.csv' to build a validated menu of landmark masks.

import os
import csv

def _get_parent(comp=None):
	"""Gets the parent component, assuming this script is on an Execute DAT inside it."""
	return comp or ownerComp.parent()

def _write_table(table_dat, rows):
	"""Safely clears and writes new rows to a table DAT."""
	if table_dat:
		table_dat.clear()
		for r in rows:
			table_dat.appendRow(r)

def _update_current_mask(parent_comp):
	"""Reads the current value of LandmarkFilterMenu and updates the Currentmask parameter."""
	try:
		current_key = parent_comp.par.LandmarkFilterMenu.eval()
		if hasattr(parent_comp.par, 'Currentmask'):
			parent_comp.par.Currentmask = current_key
		else:
			debug(f"WARNING: Parameter 'Currentmask' not found on {parent_comp.path}. Cannot update.")
	except AttributeError:
		debug(f"ERROR: Parameter 'LandmarkFilterMenu' not found on {parent_comp.path}. Cannot update Currentmask.")
	except Exception as e:
		debug(f"ERROR: Failed to update Currentmask on {parent_comp.path}: {e}")

def load_and_populate_menu():
	"""
	Reads 'data/landmarkFilterMenu.csv' to build a validated menu of landmark masks.
	Ensures 'all' and 'custom' entries exist and that other entries have a backing CSV file.
	This is the main logic function.
	"""
	parent_comp = _get_parent()
	target_table = parent_comp.op('LandmarkFilterMenu_csv')

	if not target_table:
		debug(f"ERROR: Cannot find target table 'LandmarkFilterMenu_csv' in {parent_comp.path}")
		return

	data_folder = os.path.join(project.folder, 'data')
	manifest_path = os.path.join(data_folder, 'landmarkFilterMenu.csv')

	# 1. Read all potential rows from the manifest file.
	rows_from_csv = []
	try:
		if os.path.isfile(manifest_path):
			with open(manifest_path, 'r', newline='', encoding='utf-8') as f:
				reader = csv.reader(f)
				for i, row in enumerate(reader):
					if not row or len(row) < 2 or not row[0] or not row[1]:
						if any(row):
							debug(f"WARNING: Skipping malformed row {i+1} in '{manifest_path}'")
						continue
					rows_from_csv.append([row[0].strip(), row[1].strip()])
		else:
			debug(f"Warning: Manifest file not found at '{manifest_path}'. Using defaults.")
	except Exception as e:
		debug(f"ERROR: Failed while reading '{manifest_path}': {e}")

	# 2. Validate rows and build the final menu, ensuring uniqueness and order.
	final_menu_rows = []
	processed_keys = set()

	# Add default 'all' and 'custom' to the list of candidates to ensure they are considered.
	all_candidates = rows_from_csv + [['all', 'All Landmarks'], ['custom', 'Custom']]

	for key, label in all_candidates:
		if key in processed_keys:
			continue  # Skip duplicates, first one wins.

		# 'all' and 'custom' are always valid.
		if key == 'all' or key == 'custom':
			final_menu_rows.append([key, label])
			processed_keys.add(key)
			continue

		# For all other keys, validate the corresponding CSV file.
		csv_filename = f"landmarks_{key}.csv"
		csv_path = os.path.join(data_folder, csv_filename)

		if os.path.isfile(csv_path):
			debug(f"Validated landmark mask '{key}': Found '{csv_path}'")
			final_menu_rows.append([key, label])
			processed_keys.add(key)
		else:
			debug(f"WARNING: Landmark mask '{key}' defined but CSV not found at '{csv_path}'. Skipping.")

	# 3. Write to table and update parameter.
	_write_table(target_table, final_menu_rows)

	try:
		names = [r[0] for r in final_menu_rows]
		labels = [r[1] for r in final_menu_rows]
		menu_par = parent_comp.par.LandmarkFilterMenu
		menu_par.menuNames = names
		menu_par.menuLabels = labels
		debug(f"Rebuilt 'LandmarkFilterMenu' on {parent_comp.path} with {len(names)} items.")
	except AttributeError:
		debug(f"ERROR: Parameter 'LandmarkFilterMenu' not found on {parent_comp.path}. Does it exist?")
		return
	except Exception as e:
		debug(f"ERROR: Failed to set menu on 'LandmarkFilterMenu' for {parent_comp.path}. Details: {e}")
		return

	# 4. Sync the Currentmask parameter with the menu's new state.
	_update_current_mask(parent_comp)

def onStart():
	"""
	This callback is executed when the project starts.
	It triggers the menu loading process.
	"""
	load_and_populate_menu()
	return

def onValueChange(par, prev):
	"""
	This callback is executed when a parameter on the parent component changes.
	It keeps the 'Currentmask' parameter in sync with the menu selection.
	"""
	if par.name == 'LandmarkFilterMenu':
		_update_current_mask(ownerComp.parent())
	return

def onPulse(par):
	"""
	This callback is executed when a pulse parameter is pressed.
	We can use this to manually reload the menu.
	"""
	if par.name == 'Reloadmenu':
		load_and_populate_menu()
	return