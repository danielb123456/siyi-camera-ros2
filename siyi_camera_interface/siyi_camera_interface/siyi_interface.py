import sys
import os
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from geometry_msgs.msg import Vector3
from std_msgs.msg import Int8
from cv_bridge import CvBridge
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
import cv2

# this is here so that the SIYI files can locate each other
# in the siyi_camera_interface folder. Otherwise, siyi_sdk.py 
# imports its own subfiles, like siyi_message
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from siyi_sdk import SIYISDK

class SiyiRos2Interface(Node):
    def __init__(self):
        super().__init__('siyi_camera_interface')
        
        # we change this to whatever the actual camera ip and port is
        self.declare_parameter('camera_ip', '192.168.144.25')
        self.declare_parameter('camera_port', 37260)
        self.declare_parameter('fps', 30.0)
        
        self.cam_ip = self.get_parameter('camera_ip').value
        self.cam_port = self.get_parameter('camera_port').value
        self.fps = self.get_parameter('fps').value
        
        # try to connect
        self.cam = SIYISDK(server_ip=self.cam_ip, port=self.cam_port)
        self.connected = False
        self.connect_to_camera()

        # BEST_EFFORT permits UDP behaviour (doesn't matter whether a packet gets dropped)
        # KEEP_LAST and depth=1 only keeps the newest frame in the queue
        # (avoids congestion in the network)
        video_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )

        # publishes to a channel "camera/image_raw"
        self.image_pub = self.create_publisher(Image, 'camera/image_raw', video_qos)
        
        # publishes to a channel "camera/camera_info" permitting CV algorithms
        # basically turns the camera images to OpenCV matrices
        self.camera_info_pub = self.create_publisher(CameraInfo, 'camera/camera_info', video_qos)
        
        # CvBridge translates between OpenCV matrices and ROS 2 Images
        self.bridge = CvBridge()
        
        # subscribe to gimbal_cmd and mode_cmd, so that the camera can
        # receive action commands
        self.gimbal_sub = self.create_subscription(Vector3, 'camera/gimbal_cmd', self.gimbal_cmd_callback, 10)
        self.mode_sub = self.create_subscription(Int8, 'camera/mode_cmd', self.mode_cmd_callback, 10)

        # placeholder for video feed
        self.cap = None

        # start the video pipeline
        self.init_gstreamer()
        
        # publish frame once every 1/30 seconds
        timer_period = 1.0 / self.fps
        self.timer = self.create_timer(timer_period, self.publish_frame)
        
        # makes sure UDP connection is still active, also that
        # GStreamer pipeline is still active
        self.connection_check_timer = self.create_timer(5.0, self.maintain_connection)

    def connect_to_camera(self):
        if self.cam.connect():
            self.connected = True
            self.get_logger().info("Connected to SIYI camera UDP server.")
        else:
            self.connected = False
            self.get_logger().error("Failed to connect. Retrying.")

    def init_gstreamer(self):

        # rtspsrc location=rtsp://{self.cam_ip}:8554/main.264 defines where GStreamer should listen
        
        # latency=0 prevents buffering
        
        # rtph264depay, h264parse and avdec_h264
        # decode from H.264 network packets to raw pixel matrices
        
        # videoconvert converts colors
        # appsink pushes video feed into OpenCV

        gstreamer_str = (
            f"rtspsrc location=rtsp://{self.cam_ip}:8554/main.264 latency=0 ! "
            "rtph264depay ! h264parse ! avdec_h264 ! "
            "videoconvert ! appsink"
        )

        # GStreamer pipeline is binded to self.cap 
        self.cap = cv2.VideoCapture(gstreamer_str, cv2.CAP_GSTREAMER)

    def publish_frame(self):
        
        if self.cap is None or not self.cap.isOpened():
            return

        # get image (matrix of pixels)
        ret, frame = self.cap.read()
        if ret:
            # OpenCV to ROS 2 Image
            ros_image = self.bridge.cv2_to_imgmsg(frame, "bgr8")
            
            # time
            ros_image.header.stamp = self.get_clock().now().to_msg()
            
            # location
            ros_image.header.frame_id = 'camera_link'

            # publish image to camera/image_raw
            self.image_pub.publish(ros_image)
            
            # publish info to camera/camera_info
            info_msg = CameraInfo()
            info_msg.header = ros_image.header
            self.camera_info_pub.publish(info_msg)

    def gimbal_cmd_callback(self, msg):

        # listens to messages coming from gimbal_cmd
        # then sets its yaw and pitch as the z and y
        # values of the message
        # (I'm not too sure if z is yaw or z is pitch,
        # we can check later)
        if self.connected:
            self.cam.setGimbalRotation(msg.z, msg.y)

    def mode_cmd_callback(self, msg):

        # listens to messages coming from mode_cmd
        # then sets its mode to 0, 1 or 2 to determine
        # the stabilization behaviour
        if self.connected:
            self.cam.setGimbalMode(msg.data)

    def maintain_connection(self):
        if not self.connected:
            self.connect_to_camera()
        
        if self.cap is None or not self.cap.isOpened():
            self.get_logger().warn("Video stream lost. Restarting GStreamer pipeline.")
            self.init_gstreamer()

def main(args=None):

    # start ROS 2 comms
    rclpy.init(args=args)

    # start up node
    node = SiyiRos2Interface()
    
    try:
        # endless loop
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        
        # disconnect camera
        if hasattr(node, 'cam'):
            node.cam.disconnect()
        
        # release video feed
        if hasattr(node, 'cap') and node.cap is not None:
            node.cap.release()

        # destroy node
        node.destroy_node()

        # stop ROS 2 comms
        rclpy.shutdown()

if __name__ == '__main__':
    main()