# siyi-camera-ros2

This is a ROS 2 Humble package allowing interfacing with a SIYI camera.

This node connects to the camera's UDP server permitting gimbal control, and uses GStreamer to capture the RTSP video feed, publishing it as a ROS 2 image message.

## Dependencies

* Python 3
* OpenCV (for Python)
* `cv_bridge`, `sensor_msgs` and `geometry_msgs` ROS 2 packages
* `siyi_sdk`

## Installation

1. Clone this repository into the `src` folder of the ROS 2 workspace.
2. Build the workspace (in your workspace directory) using
   ```bash
   colcon build
   ```
3. Source your workspace
   ```bash
   source install/setup.bash
   ```

## Usage

You can now run the node by running (not necessarily exactly)
  ```bash
  ros2 run <package_name> siyi_camera_interface --ros-args -p camera_ip:="192.168.144.25" -p fps:=30.0
  ```

## Node Details

### Published Topics

* **`/camera/image_raw`** (`sensor_msgs/msg/Image`)
  Outputs the live video feed retrieved from the camera's RTSP stream. The images are published in the normal `bgr8` format.
* **`/camera/camera_info`** (`sensor_msgs/msg/CameraInfo`)
  Outputs basic metadata simultaneously with the image feed. For now, it only provides the message timestamp and the `frame_id` (set to `camera_link`), time and location, to allow for time-syncing across the ROS network.

### Subscribed Topics

* **`/camera/gimbal_cmd`** (`geometry_msgs/msg/Vector3`)
  Listens for target angles to physically move the camera gimbal. 
  * `z`: Controls the Yaw angle.
  * `y`: Controls the Pitch angle.
* **`/camera/mode_cmd`** (`std_msgs/msg/Int8`)
  Listens for integer commands to change the gimbal's internal stabilization behavior. Accepts values `0`, `1`, or `2` (the SIYI A8 Camera Manual contains more information on these modes).

### Parameters

* **`camera_ip`** (string, default: `'192.168.144.25'`)
  The IP address of the SIYI camera on the network. Used for both the UDP connection and the video stream.
* **`camera_port`** (int, default: `37260`)
  The specific UDP port used to send hardware control commands (gimbal movement and mode changes) via the SIYI SDK.
* **`fps`** (double, default: `30.0`)
  The target frames per second. In other words, how many times per second the node attempts to grab a frame from the GStreamer pipeline and publish it to `/camera/image_raw`.



