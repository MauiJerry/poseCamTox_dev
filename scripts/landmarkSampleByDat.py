# td/scripts/landmarkSampleByDat.py
# for Script Chop TouchDesigner.
# calculates geometric properties for a line segment
# COMP has start/end landmark names  and radii parm
# also image height/width, aspect, flipy param
# does fancy manipulations 
# The results are output as new CHOP channels.


import math

def cook(script_op):
    """
    This function is executed by the Script CHOP on every cook.
    """
    owner_comp = script_op.parent()

    # Find the source CHOP containing landmark data.
    source_chop = owner_comp.op('inLandmarks') 
    if source_chop is None:
        # The parent_comp variable was removed in a previous edit, correct path to owner_comp
        debug(f"LandmarkSample source CHOP ('inLandmarks') not found in {owner_comp.path}")
        return

    # Get the names of the start and end landmarks from the component's parameters.
    start_landmark_name = owner_comp.par.Startlandmark.eval().strip()
    end_landmark_name = owner_comp.par.Endlandmark.eval().strip()

    def get_channel_value(name):
        """Safely retrieves a single sample value from a channel by name."""
        # The .channels attribute is a list. To get a channel by name,
        # use the op.chan() method or op['name'] syntax.
        channel = source_chop.chan(name)
        return channel[0] if channel and len(channel) else 0.0

    def get_landmark_data(landmark_name):
        """
        Retrieves the (x, y, z, visibility) data for a given landmark name.
        Handles virtual landmarks like 'hips_mid' and 'shoulders_mid' by
        first attempting to find pre-computed channels, and falling back to
        calculating them from their constituent parts if not found.
        The 'z' channel is positional depth. Visibility is assumed to be 1.0.
        """
        # Handle virtual landmarks. Note: The landmark names for constituent parts
        # (e.g., 'hip_l') match the convention from landmark_names.csv.
        if landmark_name == 'hip_mid':
            # First, check if a pre-computed version exists in the source CHOP.
            # Use the .chan() method to check for a channel's existence.
            if source_chop.chan('hip_mid_x'):
                # If it exists, we can treat it like a standard landmark.
                # The code will fall through to the standard lookup below.
                pass
            else:
                # If not pre-computed, calculate it as a fallback.
                left_x, left_y, left_z, _ = get_landmark_data('hip_l')
                right_x, right_y, right_z, _ = get_landmark_data('hip_r')
                # ignore Visibility for now, it is always 1.0.
                return ((left_x + right_x) * 0.5, (left_y + right_y) * 0.5, (left_z + right_z) * 0.5, 1.0)
        
        if landmark_name == 'shoulder_mid':
            # First, check if a pre-computed version exists.
            if source_chop.chan('shoulder_mid_x'):
                # Fall through to standard lookup.
                pass
            else:
                # Calculate as a fallback.
                left_x, left_y, left_z, _ = get_landmark_data('shoulder_l')
                right_x, right_y, right_z, _ = get_landmark_data('shoulder_r')
                return ((left_x + right_x) * 0.5, (left_y + right_y) * 0.5, (left_z + right_z) * 0.5, 1.0)

        # For standard landmarks (or pre-computed virtual ones that fell through),
        # fetch their x, y, and z (visibility) channels.
        x = get_channel_value(f'{landmark_name}_x')
        y = get_channel_value(f'{landmark_name}_y')
        z = get_channel_value(f'{landmark_name}_z')
        # Per request, visibility is not used from the data source.
        # We return a 4-tuple to maintain a consistent function signature.
        visibility = 1.0
        return (x, y, z, visibility)

    # Get image dimensions and flip settings from this component (owner_comp, the BoneUnit).
    image_width = max(1, int(owner_comp.par.Imagewidth))
    image_height = max(1, int(owner_comp.par.Imageheight))
    flip_y = bool(owner_comp.par.Flipy)

    # Get normalized coordinates [0,1] and visibility for start and end landmarks.
    start_x_norm, start_y_norm, start_z_norm, _ = get_landmark_data(start_landmark_name)
    end_x_norm, end_y_norm, end_z_norm, _ = get_landmark_data(end_landmark_name)

    # Convert normalized [0,1] coordinates to pixel coordinates.
    # using the parameters vs inMeta
    start_x_px = start_x_norm * image_width
    start_y_px = (1.0 - start_y_norm) * image_height if flip_y else start_y_norm * image_height
    
    end_x_px = end_x_norm * image_width
    end_y_px = (1.0 - end_y_norm) * image_height if flip_y else end_y_norm * image_height

    # --- Calculate segment properties in pixel space ---

    # 1. Center point of the segment.
    center_x_px = 0.5 * (start_x_px + end_x_px)
    center_y_px = 0.5 * (start_y_px + end_y_px)

    # 2. Length of the segment.
    delta_x_px = end_x_px - start_x_px
    delta_y_px = end_y_px - start_y_px
    length_px = (delta_x_px**2 + delta_y_px**2)**0.5

    # 3. Angle of the segment in radians.
    # The math.atan2 function directly returns radians, which is efficient for
    # calculating the direction vector. This value is output as 'angle_rad'.
    angle_rad = math.atan2(delta_y_px, delta_x_px)

    # Calculate the normalized direction vector directly from the radian angle.
    dir_x = math.cos(angle_rad)
    dir_y = math.sin(angle_rad)

    # 4. Alpha, based on visibility.
    # Per request, visibility is not used from the data source and alpha is
    # always 1.0. The original logic is removed.
    final_alpha = 1.0

    # grab some parameters to stuff them into channels
    r0 = float(owner_comp.par.Startradius)  # or your exact par names
    r1 = float(owner_comp.par.Endradius)
    ravg = 0.5*(r0+r1)
    # scale attributes
    sx = ravg
    sy = length_px
    sz = ravg


    # --- Output results as CHOP channels ---
    script_op.clear()
    
    output_channels = {
        'center_x_px': center_x_px,
        'center_y_px': center_y_px,
        'length_px': length_px,
        'angle_rad': angle_rad,
        'dir_x': dir_x,
        'dir_y': dir_y,
        'alpha': final_alpha,
        'start_x_px': start_x_px,
        'start_y_px': start_y_px,
        'end_x_px': end_x_px,
        'end_y_px': end_y_px,
        'cz': 0,
        'vz': 0,
        'r0': r0,
        'r1': r1,
        'sx': sx,
        'sy': sy,
        'sz': sz
    }

    for name, value in output_channels.items():
        channel = script_op.appendChan(name)
        channel[0] = value
