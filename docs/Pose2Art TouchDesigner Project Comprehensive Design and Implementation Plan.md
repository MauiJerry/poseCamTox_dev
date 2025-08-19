Of course. Here is a comprehensive design and implementation document in Markdown format that consolidates all the planning, critiques, and feature additions we have discussed.

------



# Pose2Art TouchDesigner Project: Comprehensive Design and Implementation Plan





## Executive Summary



This document outlines the comprehensive architecture for the **Pose2Art** project. The system is designed as a professional, reusable, and extensible toolkit for creating interactive art installations based on real-time pose detection.

The project is divided into three distinct repositories for a clean separation of concerns1111:



1. 

   **`poseCamPC`**: A standalone Python application that captures video, detects human poses via MediaPipe, and broadcasts the skeletal data as OSC bundles222222222.

   

   

2. 

   **`poseTDtox`**: A modular and reusable TouchDesigner library of components (`.tox` files) that receives, processes, and visualizes the pose data3333.

   

   

3. 

   **`fuzz-event-client`**: A show-specific "glue" project that imports the `poseTDtox` library and customizes it with event-specific assets, routing, and presets4444.

   

   

The internal architecture of the 

`poseTDtox` project follows a state-driven Model-View-Controller (MVC) pattern to ensure that logic, data, and presentation are cleanly decoupled, making the system robust and easy to maintain5555.



------



## 1. Core Architecture and Philosophy





### State-Driven MVC in TouchDesigner



The project's foundation is a state-driven architecture that avoids the tight coupling of components. A central `state` component serves as the "single source of truth."

- **Model**: Represents the application's data and state. This includes the raw incoming OSC data6, the parsed pose channels, the routing logic, and the persistent session database for the email capture system.

  

  

- **View**: The presentation layer. This consists of all operator-facing UI panels (

  `ui_panel.tox`)7, the effect visuals (

  

  

  `efx_*.tox`), and the email collection interface. The View's only job is to display the current state and capture user input.

- **Controller**: The logic that connects the Model and View. This layer is composed of scripts that respond to state changes or external inputs8. For example, when a show control command is received, a controller script updates the 

  

  

  `state` component; another controller script sees this state change and executes an action, like toggling which effect is active ("cooking")99.

  

  



### The Role of Parameter Binding



Parameter binding is the mechanism that links components.

- **Simple Control:** For direct links (e.g., a UI fader controlling an effect's opacity), a direct parameter bind can act as a simple controller.

- 

  **Complex Control:** For actions requiring logic (e.g., sending an OSC message, capturing a file, managing cooking states), the controller is an explicit script (e.g., in a `Parameter Execute DAT`) that contains the necessary logic1010101010. This project relies on scripted controllers for all non-trivial actions.

  

  

------



## 2. `poseTDtox` Library: Component Breakdown



The `poseTDtox` repository contains the core toolkit as a set of modular `.tox` components.



### `state.tox` (Model/State)



- **Role**: The global state machine and single source of truth.
- **Implementation**: A `Parameter COMP` holding all system-wide custom parameters.
- **Parameters**: `ActiveEffect`, `Fader`, `Blackout`, `PersonMode`, `PersonID`, `RecordingActive`, etc.



### `controllers.tox` (Controller)



- **Role**: A container for all logic-only components that respond to state changes.

- **Implementation**: A `Base COMP` containing several `... Execute DATs`.

  - 

    **`cooking_controller`**: Watches `state.par.ActiveEffect` and toggles the `allowCooking` flag on all effects in the `efx_switcher`111111111111111111. This ensures only the active effect uses GPU resources12121212.

    

    

  - 

    **`posecam_controller`**: Watches parameters like `state.par.Start` and `state.par.Source` and sends the corresponding OSC command to the remote `poseCamPC` application13131313.

    

    

  - 

    **`show_control_mapper`**: Contains an `OSC In DAT` (and optional MIDI/Art-Net DATs)14. Its callback script updates parameters on 

    

    

    `state.tox` in response to external commands15151515.

    

    

  - **`submission_controller`**: Manages the logic for the email capture system.



### `pose_in.tox` (Model/Input)



- 

  **Role**: Ingests and parses OSC data from `poseCamPC`16.

  

  

- 

  **Implementation**: An `OSC In DAT` for receiving data bundles 17171717and a 

  

  

  `Script CHOP` that uses `pose_fanout.py` to "fan out" the OSC messages into individual CHOP channels (e.g., `p1_head_x`, `p1_head_y`, etc.)181818181818181818.

  

  



### `person_router.tox` (Model/Processor)



- 

  **Role**: Selects a single person's skeleton data from the multi-person stream191919191919191919.

  

  

- 

  **Implementation**: A component that watches `state.par.PersonID` and `state.par.PersonMode` to filter the CHOP channels from `pose_in.tox`20.

  

  



### `efx_switcher.tox` (View/Controller)



- 

  **Role**: Contains all visual effect components and manages which one is active21.

  

  

- **Implementation**: A container holding multiple `efx_*.tox` children. It uses a `Switch TOP/CHOP` whose index is bound to `state.par.ActiveEffect`. It also contains logic to dynamically populate the `ActiveEffect` menu on the `state.tox` component.



### `ui_panel.tox` (View)



- 

  **Role**: The main operator control panel222222222222222222.

  

  

- **Implementation**: A container with widgets (sliders, menus, buttons) that are bi-directionally bound to the parameters on `state.tox`. It has no internal logic; it only reads from and writes to the central state.

------



## 3. Show Control and Interaction





### Receiving External Commands



The system is designed to be driven by professional show control systems232323232323232323. The 



`show_control_mapper` listens for commands and translates them into state changes.

- 

  **OSC Endpoints**: A baseline of OSC addresses is defined24242424:

  

  

  - 

    `/show/efx/select i` 252525252525252525

    

    

  - 

    `/show/efx/next` 262626262626262626

    

    

  - 

    `/show/fader t` 272727272727272727

    

    

  - 

    `/show/person/id i` 282828282828282828

    

    

  - 

    `/show/posecam/start` / `/show/posecam/stop` 292929292929292929

    

    

  - 

    `/show/blackout b` 303030303030303030

    

    



### Capture and Delivery System



For public installations, the system includes features to capture user-generated content and collect email addresses for later delivery.



#### `email_ui.tox` (View)



- A user-facing UI panel with a text field for email entry and a submit button, designed for touch screen or keyboard input.



#### `session_data.tox` (Model)



- A `Table DAT` acts as a persistent database, saving its contents to an external `session_log.csv` file.
- **Columns**: `email_address`, `capture_paths`, `timestamp`, `review_status`, `sent_status`.



#### `submission_controller` (Controller)



- **Trigger**: The "Submit" button on the `email_ui.tox`.
- **Action**: A script that reads the email, gets the paths of the user's recently captured files, and appends a new row to the `session_data` `Table DAT`.



### Example `show_control_mapper.py`



This script demonstrates how incoming OSC is mapped to state changes and controller actions.

Python

```
# td/scripts/show_control_mapper.py
# This script runs in the OSC In DAT's callback within controllers.tox

def onReceiveOSC(dat, rowIndex, message, bytes, timeStamp, address, args, peer):
    # --- Base Show Control (from source documents) ---
    if address == '/show/efx/select':
        op('state').par.Activeeffect = int(args[0])
    elif address == '/show/efx/next':
        # Logic to increment and wrap the Activeeffect menu index
        current_val = op('state').par.Activeeffect.eval()
        op('state').par.Activeeffect = (int(current_val) + 1) % len(op('state').par.Activeeffect.menuNames)
    elif address == '/show/fader':
        op('state').par.Fader = float(args[0])
    
    # --- NEW: Capture and Delivery Commands ---
    elif address == '/show/capture/still':
        # Trigger the still capture logic in a dedicated controller
        op('capture_controller').CaptureStill()
    
    elif address == '/show/capture/video/toggle':
        # Toggle the recording state directly
        op('state').par.RecordingActive = not op('state').par.RecordingActive
    
    return
```

------



## 4. Post-Event Workflow



To ensure data privacy and content quality, a human-in-the-loop review process is critical. This workflow is handled by a standalone Python script, completely separate from the real-time TouchDesigner environment.

1. **Run the Review Script**: After the event, the operator runs a Python script from their computer.
2. **Load Data**: The script loads the `session_log.csv` file generated during the event.
3. **Review Interface**: The script presents a simple interface (command-line or basic GUI) for the operator to review each entry (email and associated files).
4. **Approve/Reject/Edit**: The operator can approve entries for sending, reject them, or edit typos in email addresses. These decisions are saved back to the CSV file.
5. **Bulk Send**: Once the review is complete, a final script iterates through all "approved" entries and sends the personalized emails with their attachments.

------



## 5. Project Structure and File Layout (`poseTDtox` Repo)



```
poseTDtox/
│
├── td/
│   ├── tox/                  # The core, reusable components
│   │   ├── 0_state.tox
│   │   ├── 1_controllers.tox
│   │   ├── 2_pose_in.tox
│   │   ├── 3_person_router.tox
│   │   ├── 4_efx_switcher.tox
│   │   ├── 5_ui_panel.tox
│   │   └── 6_email_ui.tox
│   │
│   ├── effects/              # Folder for effect TOXs [cite: 300]
│   │   ├── efx_hands.tox     [cite: 60, 301, 717]
│   │   └── efx_skeleton.tox  [cite: 61, 302, 718]
│   │
│   ├── scripts/              # All external Python scripts [cite: 62, 297, 720]
│   │   ├── pose_fanout.py
│   │   ├── state_init.py
│   │   ├── cooking_controller.py
│   │   ├── posecam_controller.py
│   │   └── show_control_mapper.py
│   │
│   └── data/                 # Data files like CSVs [cite: 70, 726]
│       └── session_log.csv
│
├── demo/                     # Example project file [cite: 73]
│   └── Pose2Art_Demo.toe     [cite: 74]
│
└── docs/                     # Documentation [cite: 75, 304]
    ├── README.md
    └── TOX_Reference.md
```