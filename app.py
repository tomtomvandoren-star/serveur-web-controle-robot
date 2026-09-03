import atexit
import re
import subprocess
import threading
import time

import cv2
import RPi.GPIO as GPIO
from flask import Flask, Response, jsonify, render_template, request

# ----------------------------------------------------------------------
# Broches GPIO des moteurs (modifiables ici, ou depuis l'interface web)
# ----------------------------------------------------------------------
PIN_RIGHT_FORWARD = 17   # roues droites - avant
PIN_RIGHT_BACKWARD = 27  # roues droites - arrière
PIN_LEFT_FORWARD = 22    # roues gauches - avant
PIN_LEFT_BACKWARD = 23   # roues gauches - arrière

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

# ----------------------------------------------------------------------
# Micro distant -> haut-parleur du Raspberry Pi (via ffplay)
# ----------------------------------------------------------------------
audio_process = None
audio_lock = threading.Lock()

# ----------------------------------------------------------------------
# Bluetooth (jumelage / connexion des périphériques, sortie audio)
# ----------------------------------------------------------------------
BT_DEVICE_RE = re.compile(r"^Device ([0-9A-Fa-f:]{17}) (.+)$")
BT_MAC_RE = re.compile(r"^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$")
BT_ACTIONS = {"pair", "connect", "disconnect", "trust", "remove"}

try:
    subprocess.run(["rfkill", "unblock", "bluetooth"], capture_output=True, timeout=5)
except (FileNotFoundError, subprocess.TimeoutExpired):
    pass
try:
    subprocess.run(["bluetoothctl", "power", "on"], capture_output=True, timeout=10)
except (FileNotFoundError, subprocess.TimeoutExpired):
    pass

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


def start_audio_process():
    """Démarre ffplay pour lire en direct le flux audio reçu sur son entrée standard."""
    return subprocess.Popen(
        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-i", "pipe:0"],
        stdin=subprocess.PIPE,
    )


def stop_audio_process():
    global audio_process
    if audio_process is not None:
        try:
            audio_process.stdin.close()
        except OSError:
            pass
        audio_process.terminate()
        audio_process = None


def bt(*args, timeout=10):
    """Exécute une commande bluetoothctl en mode « one-shot » et renvoie sa sortie."""
    try:
        result = subprocess.run(
            ["bluetoothctl", *args], capture_output=True, text=True, timeout=timeout
        )
        return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def bt_device_info(mac, fallback_name=None):
    info = {
        "mac": mac,
        "name": fallback_name or mac,
        "paired": False,
        "connected": False,
        "trusted": False,
    }
    for line in bt("info", mac).splitlines():
        line = line.strip()
        if line.startswith("Name:"):
            info["name"] = line.split(":", 1)[1].strip()
        elif line.startswith("Paired:"):
            info["paired"] = line.endswith("yes")
        elif line.startswith("Connected:"):
            info["connected"] = line.endswith("yes")
        elif line.startswith("Trusted:"):
            info["trusted"] = line.endswith("yes")
    return info


def list_bt_devices():
    devices = []
    for line in bt("devices").splitlines():
        match = BT_DEVICE_RE.match(line.strip())
        if match:
            devices.append(bt_device_info(match.group(1), fallback_name=match.group(2)))
    return devices


def set_default_audio_sink(mac):
    """Bascule la sortie audio (PulseAudio/PipeWire) vers le périphérique Bluetooth connecté."""
    sink_name = f"bluez_sink.{mac.replace(':', '_')}.a2dp_sink"
    try:
        subprocess.run(["pactl", "set-default-sink", sink_name], capture_output=True, timeout=5)
        streams = subprocess.run(
            ["pactl", "list", "short", "sink-inputs"], capture_output=True, text=True, timeout=5
        )
        for line in streams.stdout.splitlines():
            fields = line.split()
            if fields:
                subprocess.run(
                    ["pactl", "move-sink-input", fields[0], sink_name],
                    capture_output=True, timeout=5,
                )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


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


@app.route("/audio/stream", methods=["POST"])
def audio_stream():
    global audio_process
    chunk = request.get_data()
    with audio_lock:
        if audio_process is None or audio_process.poll() is not None:
            audio_process = start_audio_process()
        try:
            audio_process.stdin.write(chunk)
            audio_process.stdin.flush()
        except (BrokenPipeError, OSError):
            audio_process = None
    return ("", 204)


@app.route("/audio/stop", methods=["POST"])
def audio_stop():
    with audio_lock:
        stop_audio_process()
    return jsonify(status="stopped")


@app.route("/bluetooth/devices", methods=["GET"])
def bluetooth_devices():
    return jsonify(list_bt_devices())


@app.route("/bluetooth/scan", methods=["POST"])
def bluetooth_scan():
    # Un scan long (BR/EDR classique + LE) laisse le temps aux enceintes/casques
    # d'être découverts et à leur nom d'être résolu.
    bt("--timeout", "20", "scan", "on", timeout=25)
    return jsonify(list_bt_devices())


@app.route("/bluetooth/<action>", methods=["POST"])
def bluetooth_action(action):
    if action not in BT_ACTIONS:
        return jsonify(error="Action inconnue"), 400

    data = request.get_json(silent=True) or {}
    mac = str(data.get("mac", "")).upper()
    if not BT_MAC_RE.match(mac):
        return jsonify(error="Adresse MAC invalide"), 400

    if action == "pair":
        bt("--agent=NoInputNoOutput", "pair", mac, timeout=20)
    elif action == "connect":
        bt("connect", mac, timeout=15)
        set_default_audio_sink(mac)
    elif action == "disconnect":
        bt("disconnect", mac, timeout=10)
    elif action == "trust":
        bt("trust", mac, timeout=10)
    elif action == "remove":
        bt("remove", mac, timeout=10)

    return jsonify(list_bt_devices())


def cleanup():
    """Coupe les moteurs et libère les ressources GPIO/caméra/audio à l'arrêt."""
    GPIO.output(list(PINS.values()), GPIO.LOW)
    GPIO.cleanup()
    camera.release()
    with audio_lock:
        stop_audio_process()


atexit.register(cleanup)

if __name__ == "__main__":
    # host="0.0.0.0" pour accéder depuis un autre appareil sur le réseau local.
    # HTTPS (certificat auto-signé) est nécessaire : les navigateurs bloquent
    # l'accès au micro (getUserMedia) sur une origine non sécurisée autre que
    # « localhost ».
    app.run(host="0.0.0.0", port=5000, threaded=True, ssl_context="adhoc")
