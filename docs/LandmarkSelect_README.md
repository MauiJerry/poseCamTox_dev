# LandmarkSelect COMP README

The `LandmarkSelect` component is a part of the Pose2Art project, designed to filter incoming landmark CHOP channels. It allows for dynamic selection of landmark subsets (like just the face, or just the hands) based on user-configurable filters.

This filtering is managed by the `LandmarkSelectExt` extension, which lives on the `landmarkSelect` COMP.

## Core Functionality

The extension generates a space-separated list of channel name patterns (e.g., `nose* left_eye* right_eye*`) and feeds this list into a Select CHOP. This allows for precise filtering of the full landmark data stream.

The system is data-driven, building its filter options from a manifest file and corresponding landmark lists located in the project's `/data` folder.

## Parameters

The component's behavior is controlled by these custom parameters:

-   **`Landmarkfiltermenu` (Menu):** A dropdown menu to select the active landmark filter. The options in this menu are dynamically generated from a manifest file.
-   **`Defaultfilter` (String):** An override parameter. If this string is not empty, its value will be used as the filter name, ignoring the selection in `Landmarkfiltermenu`. This is useful for setting a default state or controlling the filter from a higher-level component.
-   **`Currentfilter` (String):** A read-only field that displays the currently active filter name, whether it comes from the menu or the `Defaultfilter` override.
-   **`Customfiltercsv` (String):** Specifies the path to a user-provided CSV file containing a list of landmarks. This file is used only when the active filter is set to `Custom`.
-   **`Rebuildmenu` (Pulse):** A button that, when pressed, forces the extension to re-read the manifest file and rebuild the options for the `Landmarkfiltermenu`.

## Filter & Data Files

-   **Manifest File (`/data/landmark_filter_manifest.csv`):** This central CSV file defines the filters available in the `Landmarkfiltermenu`. It has two columns: `name` (the user-facing filter name, e.g., "Face") and `csv_file` (the corresponding data file, e.g., "mask_face.csv").

-   **Landmark List CSVs (`/data/mask_*.csv`, etc.):** These are simple, single-column CSV files.
    -   The script reads the **first column** to get the list of landmark base names (e.g., `nose`, `left_wrist`).
    -   It will intelligently skip a header row if the first cell contains `key`, `name`, or `landmark` (case-insensitive).
    -   Each landmark name is automatically converted into a wildcard pattern by appending a `*`. For example, a row with `nose` becomes the pattern `nose*`, which will match channels like `p1_nose_x`, `p1_nose_y`, `p2_nose_x`, etc.

## Special Filters

-   **`all`:** If the active filter is named `all`, the Select CHOP is bypassed, allowing all landmark channels to pass through.
-   **`Custom`:** When selected, the extension will read the landmark list from the file specified in the `Customfiltercsv` parameter.

## Integration

The script is referenced by a Text DAT called `LandmarkSelectExt` and the COMP's Extension Object is initialized via:

```python
op('./LandmarkSelectExt').module.LandmarkSelectExt(me)
```
