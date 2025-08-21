# PoseEffect_Master README.md

PoseEffect_Master is a template component  for building single person target effects for Pose2Art.

out of date readme

# Inputs

in1 CHOP - channels for a single person, connects to landmark_select COMP

in2 TOP - optional image input, connects to switch1

# Processing

noFx TOP: red square. connects to switch1

switch1 TOP:  shows noFx if no inputs on in2, outputs to fxCore

landmark_switch: COMP that selects landmarks to pass to fxCore

fxCore COMP: inputs CHOP of landmarks+ TOP, outputs Efx (default copies inTOP to outTop)

# Output

out1 TOP - result of fxCore