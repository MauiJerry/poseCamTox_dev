# LandmarkSelect COMP README

LandmarkSelect component is part of Pose2Art/PoseEffect_Master. It selects a subset of landmarks depending on its Menu and the contents of external data/*.csv files.

This extension lives on the `landmarkSelect` COMP. It builds a list of CHOP
channel names (patterns) to feed into a Select CHOP based on user parameters:
- Filtermode: All | Hands | BasicPose | Face | CustomCSV
- Filtercsv:  Path to a user CSV (used only when Filtermode=CustomCSV)

the script is referenced by a Text DAT called LandmarkSelectExt
and the COMP's Extension Object is op('./LandmarkSelectExt').module.LandmarkSelectExt(me)

Supported CSV schemas in data/
- landmark_names.csv:       header has 'name' (case-insensitive)
- mask_*.csv / custom.csv: either 'name' (landmark names) or 'chan'
with contents being a single column of landmark names 
'name'  -> expanded to p{pid}_name_x/y/z
'chan'  -> used verbatim (wildcards allowed - really? not tested.)
