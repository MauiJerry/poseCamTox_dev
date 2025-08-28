# ext/PoseEfxSwitchExt.py
# -----------------------------------------------------------------------------
# PoseEfxSwitchExt
# -----------------------------------------------------------------------------
# Attach this extension to the PoseEfxSwitch COMP.
#
# Responsibilities (finalized 23 Aug):
#   • Build the ActiveEffect menu labels from PoseEffect parent.par.UiDisplayName
#     (fall back to pretty OP name). Menu values remain stable keys (OP names).
#   • Keep ActiveEffect (menu) and Activeindex (int) in sync WITHOUT loops.
#   • Activate exactly one PoseEffect_*:
#       - Route out_switch.index
#       - fx.allowCooking  = True for active, False for others
#       - fxCore.bypass    = False for active, True for others
#       - fx.ext.PoseEffectMasterExt.SetActive(active)
# 
# Expected nodes inside PoseEfxSwitch:
#   - effects/                (Base COMP container for PoseEffect_* children)
#   - out_switch              (Switch TOP)
#
# UI parameters on PoseEfxSwitch (Customize Component…):
#   - ActiveEffect       (Menu)     ← user-facing effect picker (values = OP names)
#   - Activeindex        (Int)      ← internal index (hide if you like)
#   - RebuildEffectsMenu (Pulse)    ← manual refresh
#
# Initialization:
#   - Put an Execute DAT *inside* PoseEfxSwitch with:
#       def onStart(): op('.').ext.PoseEfxSwitchExt.Initialize()
# -----------------------------------------------------------------------------

import os, csv, glob

class PoseEfxSwitchExt:
    """
    Manages the selection and activation of child "PoseEffect" components.
    This extension is attached to a parent COMP (the "switch") and handles
    UI menu building, state synchronization, and resource management (cooking).
    """
    def __init__(self, owner):
        """Initializes the extension.
        
        Args:
            owner (COMP): The component this extension is attached to.
        """
        debug("init PoseEfxSwitchExt")
        self.owner = owner
        self._syncing = False  # Re-entrancy guard to prevent parameter feedback loops.
        # _mask_dispatch is a placeholder for future mask management logic.
        self._mask_dispatch = {}   # NEW: key -> absolute csv path

    # ===== Lifecycle ==========================================================
    def Initialize(self):
        """Called by the embedded Execute DAT on project start."""
        debug("Initialize PoseEfxSwitchExt")
        
        self.BuildEffectsMenu()

        # Set initial active effect: keep current if valid, else use the first effect.
        key = (self.owner.par.ActiveEffect.eval() or '').strip()
        keys = self._menuKeys()
        if key in keys:
            self.SetActiveEffect(key)
        elif keys:
            self.SetActiveEffect(keys[0])
        else:
            self.SetActiveIndex(0)

    # ===== Effect menu (ActiveEffect) =========================================
    def BuildEffectsMenu(self):
        """
        Auto-discover PoseEffect_* children and build ActiveEffect menu.
        Values = OP names (stable). Labels = parent.par.UiDisplayName if set,
        else derived from OP name ("PoseEffect_Dots2" -> "Dots 2").
        """
        debug("BuildEffectsMenu PoseEfxSwitchExt")
        keys, labels = [], []
        for fx in self._effects():
            key = fx.name  # OP name is the stable key
            lab = self._label_for_effect(fx)
            keys.append(key)
            labels.append(lab)

        # Stamp the UI menu
        self.owner.par.Activeeffect.menuNames  = keys
        self.owner.par.Activeeffect.menuLabels = labels

        # After rebuilding, ensure the current selection is still valid.
        # If not, select the first effect in the new list.
        cur = (self.owner.par.Activeeffect.eval() or '').strip()
        if cur not in keys and keys:
            self.owner.par.Activeeffect = keys[0]
        # Trigger a refresh of the active state.
        self.OnActiveEffectChanged()

    def _label_for_effect(self, fx):
        """Prefer PoseEffect.UiDisplayName (non-'Master'), else pretty OP name."""
        try:
            # Check if the effect has a 'Uidisplayname' custom parameter.
            p = getattr(fx.par, 'Uidisplayname', None)
            if p:
                val = (p.eval() or '').strip()
                # Use the parameter's value if it's not empty or 'master'.
                if val and val.lower() != 'master':
                    return val
        except Exception:
            # Ignore errors if the parameter doesn't exist or fails to evaluate.
            pass
        # Fallback: generate a "pretty" name from the operator's name.
        # e.g., "PoseEffect_My_Effect" -> "My Effect"
        return fx.name.replace('PoseEffect_', '').replace('_', ' ').title()

    def OnActiveEffectChanged(self):
        """
        Callback for when the 'ActiveEffect' (menu) parameter changes.
        Synchronizes the 'ActiveIndex' parameter to match the new effect selection.
        This uses a re-entrancy guard to prevent infinite loops with OnActiveIndexChanged.
        """
        debug("OnActiveEffectChanged PoseEfxSwitchExt")
        if self._syncing:
            return  # Avoid feedback loop if change was triggered by OnActiveIndexChanged

        self._syncing = True
        try:
            # Get the selected effect's name (the key) from the menu.
            key = (self.owner.par.Activeeffect.eval() or '').strip()
            # Find the numerical index for this effect.
            idx = self._indexForOpName(key)

            # If the index is found and different from the current Activeindex, update it.
            # This will trigger OnActiveIndexChanged, but the _syncing flag will prevent a loop.
            if idx is not None and int(self.owner.par.Activeindex.eval() or -1) != idx:
                self.owner.par.Activeindex = idx
            
            # Directly call SetActiveIndex to apply the change immediately.
            # This ensures the correct effect is activated even if the index was already correct.
            self.SetActiveIndex(int(self.owner.par.Activeindex.eval() or 0))
        finally:
            self._syncing = False

    def OnActiveIndexChanged(self):
        """
        Callback for when the 'ActiveIndex' (int) parameter changes.
        Synchronizes the 'ActiveEffect' (menu) parameter to match the new index.
        This uses a re-entrancy guard to prevent infinite loops with OnActiveEffectChanged.
        """
        debug("OnActiveIndexChanged PoseEfxSwitchExt")
        if self._syncing:
            return  # Avoid feedback loop if change was triggered by OnActiveEffectChanged

        self._syncing = True
        try:
            # Get the new index.
            idx = int(self.owner.par.Activeindex.eval() or 0)
            # Find the effect COMP at this index.
            fx  = self._effectAtIndex(idx)
            key = fx.name if fx else ''

            # If the effect exists and its name is different from the current menu selection,
            # update the menu parameter. This will trigger OnActiveEffectChanged.
            if key and (self.owner.par.Activeeffect.eval() or '') != key:
                self.owner.par.ActiveEffect = key
            
            # Apply the activation logic for the new index.
            self.SetActiveIndex(idx)
        finally:
            self._syncing = False

    def SetActiveEffect(self, key: str):
        """Programmatic activation by OP name (updates both params + activation)."""
        debug("SetActiveEffect PoseEfxSwitchExt", key)
        key = (key or '').strip()
        keys = self._menuKeys()
        if not keys:
            return
        if key not in keys:
            key = keys[0]
        self.owner.par.Activeeffect = key  # This assignment triggers OnActiveEffectChanged

    def SetActiveIndex(self, idx: int):
        """
        Activate exactly one PoseEffect_* and route out_switch to that index.
        """
        debug("SetActiveIndex PoseEfxSwitchExt", idx)
        # Route output switch
        sw = self.owner.op('out_switch')
        if sw:
            sw.par.index = int(idx)

        # Gate cooking and notify each effect of its active state.
        # This ensures only the active effect consumes resources, and allows
        # the effect to run its own activation logic via its SetActive method.
        for i, fx in enumerate(self._effects()):
            is_active = (i == int(idx))
            fx.allowCooking = is_active
            if hasattr(fx.ext, 'PoseEffectMasterExt'):
                fx.ext.PoseEffectMasterExt.SetActive(is_active)


    # ===== Helpers =============================================================
  

    def _effects(self):
        """Return all PoseEffect_* COMPs under ./effects."""
        eff = self.owner.op('effects')
        if not eff:
            return []
        return [c for c in eff.children if c.isCOMP and c.name.startswith('PoseEffect_')]

    def _menuKeys(self):
        """Return menu values (OP names)."""
        return list(self.owner.par.ActiveEffect.menuNames or [])

    def _effectAtIndex(self, idx: int):
        effs = self._effects()
        if 0 <= idx < len(effs):
            return effs[idx]
        return None

    def _indexForOpName(self, name: str):
        effs = self._effects()
        for i, fx in enumerate(effs):
            if fx.name == name:
                return i
        return None
