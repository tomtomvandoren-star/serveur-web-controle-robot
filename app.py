import atexit

import cv2
import RPi.GPIO as GPIO
from flask import Flask, Response, jsonify, render_template

# ----------------------------------------------------------------------
# Configuration GPIO (identique au script original)
# ----------------------------------------------------------------------
MOTOR_PIN = 17
GPIO.setmode(GPIO.BCM)
GPIO.setup(MOTOR_PIN, GPIO.OUT, initial=GPIO.LOW)

# ----------------------------------------------------------------------
# Configuration webcam (v4l2:/dev/video0)
# ----------------------------------------------------------------------
CAMERA_DEVICE = "/dev/video0"
camera = cv2.VideoCapture(CAMERA_DEVICE, cv2.CAP_V4L2)
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

app = Flask(__name__)


def gen_frames():
    """Génère le flux MJPEG à partir de la webcam."""
    while True:
        success, frame = camera.read()
        if not success:
            break
        ok, buffer = cv2.imencode(".jpg", frame)
        if not ok:
            continue
        frame_bytes = buffer.tobytes()
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/video_feed")
def video_feed():
    return Response(
        gen_frames(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/motor/on", methods=["POST"])
def motor_on():
    GPIO.output(MOTOR_PIN, GPIO.HIGH)
    return jsonify(status="on")


@app.route("/motor/off", methods=["POST"])
def motor_off():
    GPIO.output(MOTOR_PIN, GPIO.LOW)
    return jsonify(status="off")


def cleanup():
    """Coupe le moteur et libère les ressources GPIO/caméra à l'arrêt."""
    GPIO.output(MOTOR_PIN, GPIO.LOW)
    GPIO.cleanup()
    camera.release()


atexit.register(cleanup)

if __name__ == "__main__":
    # host="0.0.0.0" pour accéder depuis un autre appareil sur le réseau local
    app.run(host="0.0.0.0", port=5000, threaded=True)
