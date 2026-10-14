import atexit
import time

import cv2
import RPi.GPIO as GPIO
from flask import Flask, Response, jsonify, render_template, request

# ----------------------------------------------------------------------
# Broches GPIO des moteurs (modifiables ici, ou depuis l'interface web)
# ----------------------------------------------------------------------
PIN_RIGHT_FORWARD = 21   # roues droites - avant
PIN_RIGHT_BACKWARD = 20  # roues droites - arrière
PIN_LEFT_FORWARD = 12    # roues gauches - avant
PIN_LEFT_BACKWARD = 16   # roues gauches - arrière

PINS = {
    "right_forward": PIN_RIGHT_FORWARD,
    "right_backward": PIN_RIGHT_BACKWARD,
    "left_forward": PIN_LEFT_FORWARD,
    "left_backward": PIN_LEFT_BACKWARD,
}

# Combinaison de broches à activer pour chaque mouvement
MOVES = {
    "forward": {"right_forward", "left_forward"},
    "backward": {"right_backward", "left_backward"},
    "right": {"left_forward", "right_backward"},
    "left": {"right_forward", "left_backward"},
    "stop": set(),
}

GPIO.setmode(GPIO.BCM)
for _pin in PINS.values():
    GPIO.setup(_pin, GPIO.OUT, initial=GPIO.LOW)

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


def apply_move(action):
    """Active les broches nécessaires au mouvement demandé, coupe les autres."""
    active_pins = MOVES[action]
    for key, pin in PINS.items():
        GPIO.output(pin, GPIO.HIGH if key in active_pins else GPIO.LOW)


def configure_pins(new_pins):
    """Reconfigure les broches GPIO utilisées par les moteurs."""
    GPIO.output(list(PINS.values()), GPIO.LOW)
    GPIO.cleanup(list(PINS.values()))
    PINS.update(new_pins)
    for pin in PINS.values():
        GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/video_feed")
def video_feed():
    return Response(
        gen_frames(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/move/<action>", methods=["POST"])
def move(action):
    if action not in MOVES:
        return jsonify(error="Action inconnue"), 400
    apply_move(action)
    return jsonify(status=action)


@app.route("/gpio/config", methods=["GET"])
def gpio_config_get():
    return jsonify(PINS)


@app.route("/gpio/config", methods=["POST"])
def gpio_config_post():
    data = request.get_json(silent=True) or {}
    try:
        new_pins = {key: int(data[key]) for key in PINS}
    except (KeyError, TypeError, ValueError):
        return jsonify(error="Configuration invalide"), 400

    try:
        configure_pins(new_pins)
    except Exception as exc:  # broche invalide, déjà utilisée, etc.
        return jsonify(error=str(exc)), 400

    return jsonify(PINS)


@app.route("/gpio/test/<key>", methods=["POST"])
def gpio_test(key):
    """Active brièvement une broche seule, pour vérifier son câblage."""
    if key not in PINS:
        return jsonify(error="Broche inconnue"), 400
    pin = PINS[key]
    GPIO.output(pin, GPIO.HIGH)
    time.sleep(0.7)
    GPIO.output(pin, GPIO.LOW)
    return jsonify(status="tested", pin=key)


def cleanup():
    """Coupe les moteurs et libère les ressources GPIO/caméra à l'arrêt."""
    GPIO.output(list(PINS.values()), GPIO.LOW)
    GPIO.cleanup()
    camera.release()


atexit.register(cleanup)

if __name__ == "__main__":
    # host="0.0.0.0" pour accéder depuis un autre appareil sur le réseau local
    app.run(host="0.0.0.0", port=5000, threaded=True)
