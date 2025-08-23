# PoseEffectMASTER README

The Container OP PoseEffectMASTER is the template for creating effects within the PoseEfxSwitch.

## INPUTS

- LandmarksIn (In Chop) - channels of desired landmarks
- inTop - inTop from PoseEfxSwitch
- inMeta - pose meta data DAT (guarded w defaults)

## Internals

### Computes

- PoseEffectMasterExt - ext/PoseEffectMasterExt.py
- parexec1 - default parameter Exec (needs to update?) 
- fxCore - Container that holds the actual fx
  - MASTER holds basic ops w/no compute
  - clones will over ride internal compute
  - clones should NOT rename this component

### Other

- noFx - constant TOP (White)
- inTopGuard (Switch TOP) noFx if no inTop
  - fxCore default simply copies this to its out so if nothing implemented out is White (noFx color)

## OUTPUTS

- fxOut (Out TOP) - results of the Effect

