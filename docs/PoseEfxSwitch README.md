# PoseEfxSwitch README

PoseEfx Switch is part of Pose2Art working with the PoseCam COMP to switch various effects on/off. Actual effects are instantiated as clones of PoseEffectMASTER inside the effects container

## INPUTS
- inCHOP - a single person's channel landmarks filtered from PoseCam
- inTop - might be the NDI input or unconnected if efx dont need video input
- inMeta - pose meta data table

## Internal Ops
- noFx (Constant TOP) - constant color (Red)
- guardTopSwitch (Switch TOP) - switches to noFx if nothing connected to inTop
- guardedMeta (Table DAT) - inMeta guarded to hold defaults
- effects (Container) - contains PoseEffectMASTER and instantiated clones (fxCore)
- LandmarkFilterMenu_csv - config/LandmarkFilterMenu.csv

## Compute Ops
- exec_init (Execute DAT) - runs scripts/poseEfxSwitch_exec_init.py => ext.PoseEfxSwitchExt.Initialize() 
- PoseEfxSwitchExt (Text DAT) - runs ext/PoseEfxSwitchExt.py
- parexec1 - (Parameter Execute DAT) - runs scripts/poseEfxSwitch_paramExec.py
- inMeta_exec (DAT Execute) - runs inmeta_exec.py
- guard_meta (Text DAT) - scripts/guard_meta.py

## Outputs

outTop - output of the selected TOP

## Parameters
See the parexec1 Parameter Execute DAT.

### Parameters Page
- Active Effect - menu of effects, set by ResetEffectsMenu
- Refresh Meta Data - pulse
- Rebuild Effects Menu - pulse
- Active Index

### Defaults
used to guard the inMeta to insure it has image_height, image_width, aspect rows
- Default Canvas Width (1280)
- Default Canvas Height (720)




