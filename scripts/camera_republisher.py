# camera_subscriber.py
#!/usr/bin/env python
import rospy
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
from flask import Flask, Response
import numpy as np
from time import sleep
import threading

app = Flask(__name__)

WIDTH = 640
HEIGHT = 480
bridge = CvBridge()
current_frame = None
frame_lock = threading.Lock()
is_running = True
topic_name = "/sc/rgb/image"

def image_callback(msg):
    global current_frame
    try:
        cv_image = bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        _, jpeg = cv2.imencode('.jpg', cv_image, [cv2.IMWRITE_JPEG_QUALITY, 50])
        with frame_lock:
            current_frame = jpeg.tobytes()
    except Exception as e:
        rospy.logerr("Error converting image: %s", str(e))


def ros_image_listener():
    rospy.Subscriber(topic_name, Image, image_callback)
    rospy.loginfo(f"Subscribed to {topic_name}")
    rospy.spin()

def generate_frames():
    while True:
        with frame_lock:
            if current_frame is None:
                continue
            frame_to_send = current_frame
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_to_send + b'\r\n')
        sleep(0.01)  # Optional: throttle the output


@app.route('/')
def index():
    return """
    <!DOCTYPE html>
    <html>
        <head>
            <style>
                body { margin: 0; padding: 0; }
                img { width: 100vw; height: 100vh; object-fit: contain; }
            </style>
        </head>
        <body>
            <img src="/video">
        </body>
    </html>
    """

@app.route('/video')
def video():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

def start_flask():
    app.run(host='0.0.0.0', port=8283, threaded=True)

if __name__ == '__main__':
    # Initialize the ROS node in the main thread
    rospy.init_node("camera_stream_subscriber", anonymous=True)

    # Start the Flask server in a separate thread
    flask_thread = threading.Thread(target=start_flask)
    flask_thread.daemon = True
    flask_thread.start()

    try:
        ros_image_listener()
    except rospy.ROSInterruptException:
        pass
    finally:
        is_running = False
        rospy.loginfo("Shutting down camera stream")
