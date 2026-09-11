import subprocess
import time
import os
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from pathlib import Path
import logging
import threading
from PIL import Image
import serial
import serial.tools.list_ports
import requests  # NEW: For calling Flask API
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("adb-video-server")

app = FastAPI()

# Serve static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- CONFIG ---
PHONE_VIDEO_DIR = "/sdcard/DCIM/Camera/"
PC_SAVE_DIR = r"C:\platform-tools-latest-windows\platform-tools\Recorded_Videos"
MUSIC_FILE = r"C:\platform-tools-latest-windows\platform-tools\music\m1.mp3"
BRAND_LOGO = r"C:\platform-tools-latest-windows\platform-tools\brand\logo1.png"
BRAND_LOGO_2 = r"C:\platform-tools-latest-windows\platform-tools\brand\logo2.png"
BRAND_LOGO_3 = r"C:\platform-tools-latest-windows\platform-tools\brand\logo3.png"

AUTO_STOP_DELAY = 8
SLOWMO_FACTOR = 1.5
FFMPEG_THREADS = 4

# Arduino serial configuration
ARDUINO_PORT = "COM14"
BAUD_RATE = 9600
ARDUINO = None

# Flask server URL (for database updates)
FLASK_SERVER_URL = "http://127.0.0.1:5000"

Path(PC_SAVE_DIR).mkdir(parents=True, exist_ok=True)

# --- GLOBALS ---
LATEST_PROCESSED_VIDEO = None
SLOMO_MODE = 0
PENDING_VIDEO = False

# --- ARDUINO SETUP ---
def init_arduino():
    """Initialize Arduino serial connection manually."""
    global ARDUINO
    try:
        ARDUINO = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=1)
        logger.info(f"✓ Arduino connected at {ARDUINO_PORT}")
    except Exception as e:
        logger.error(f"✗ Failed to connect to Arduino at {ARDUINO_PORT}: {e}")
        ARDUINO = None

def send_to_arduino(command: str):
    """Send 'on' or 'off' to Arduino safely."""
    global ARDUINO
    if ARDUINO and ARDUINO.is_open:
        try:
            ARDUINO.write((command + "\n").encode())
            logger.info(f"✓ Sent to Arduino: {command}")
        except Exception as e:
            logger.error(f"✗ Failed to send to Arduino: {e}")
    else:
        logger.warning("⚠ Arduino not connected. Command not sent.")

init_arduino()

# --- UTILS ---
def run_adb(args, capture_output=True, check=False, text=True):
    return subprocess.run(["adb"] + args, capture_output=capture_output, check=check, text=text)

def get_latest_remote_filename():
    cp = run_adb(["shell", "ls", "-t", PHONE_VIDEO_DIR])
    lines = [l.strip() for l in cp.stdout.splitlines() if l.strip()]
    return lines[0] if lines else None

def pull_remote_file(remote_filename):
    remote_path = f"{PHONE_VIDEO_DIR}{remote_filename}"
    cp = run_adb(["pull", remote_path, PC_SAVE_DIR])
    if cp.returncode != 0:
        raise RuntimeError(f"adb pull failed: {cp.stderr}")
    return os.path.join(PC_SAVE_DIR, remote_filename)

def rename_with_timestamp(local_path):
    ext = Path(local_path).suffix
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    new_name = f"video_{ts}{ext}"
    dest = os.path.join(PC_SAVE_DIR, new_name)
    os.replace(local_path, dest)
    return dest

# --- LOGO RESIZE SETUP ---
RESIZED_LOGO = BRAND_LOGO.replace(".png", "_resized.png")
RESIZED_LOGO_2 = BRAND_LOGO_2.replace(".png", "_resized.png")
RESIZED_LOGO_3 = BRAND_LOGO_3.replace(".png", "_resized.png")

def resize_logo(input_path, output_path, width=250):
    """Resize brand logo while keeping aspect ratio."""
    img = Image.open(input_path)
    w_percent = (width / float(img.size[0]))
    h_size = int((float(img.size[1]) * float(w_percent)))
    img = img.resize((width, h_size), Image.LANCZOS)
    img.save(output_path)
    return output_path

if not os.path.exists(RESIZED_LOGO):
    resize_logo(BRAND_LOGO, RESIZED_LOGO, width=250)

def resize_logo_2(input_path, output_path, width=50):
    """Resize brand logo while keeping aspect ratio."""
    img = Image.open(input_path)
    w_percent = (width / float(img.size[0]))
    h_size = int((float(img.size[1]) * float(w_percent)))
    img = img.resize((width, h_size), Image.LANCZOS)
    img.save(output_path)
    return output_path

if not os.path.exists(RESIZED_LOGO_2):
    resize_logo(BRAND_LOGO_2, RESIZED_LOGO_2, width=50)

def resize_logo_3(input_path, output_path, width=100):
    """Resize brand logo while keeping aspect ratio."""
    img = Image.open(input_path)
    w_percent = (width / float(img.size[0]))
    h_size = int((float(img.size[1]) * float(w_percent)))
    img = img.resize((width, h_size), Image.LANCZOS)
    img.save(output_path)
    return output_path

if not os.path.exists(RESIZED_LOGO_3):
    resize_logo(BRAND_LOGO_3, RESIZED_LOGO_3, width=100)

# --- VIDEO PROCESSING ---
def add_music_logo_slowmo(input_path, output_path, mode):
    """Single-mode FFmpeg processing: slowmo + logos + music overlay."""
    temp_video = output_path.replace(".mp4", "_temp_video.mp4")

    # Slow-mo middle section, properly connected and concatenated
    filter_complex = (
    f"[0:v]setpts={SLOWMO_FACTOR}*PTS[vslow];"
    f"[vslow][1:v]overlay=0:H-h[tmp1];"
    f"[tmp1][2:v]overlay=10:10[tmp2];"
    f"[tmp2][3:v]overlay=W-w-10:10[v]"
)
    
    cmd1 = [
        "ffmpeg", "-y",
        "-threads", str(FFMPEG_THREADS),
        "-i", input_path,
        "-i", RESIZED_LOGO,
        "-i", RESIZED_LOGO_2,
        "-i", RESIZED_LOGO_3,
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-an",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        temp_video
    ]

    cp1 = subprocess.run(cmd1, capture_output=True, text=True)
    if cp1.returncode != 0:
        raise RuntimeError(f"FFmpeg pass1 failed: {cp1.stderr}")

    cmd2 = [
        "ffmpeg", "-y",
        "-i", temp_video,
        "-i", MUSIC_FILE,
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        output_path
    ]

    cp2 = subprocess.run(cmd2, capture_output=True, text=True)
    if cp2.returncode != 0:
        raise RuntimeError(f"FFmpeg pass2 failed: {cp2.stderr}")

    if os.path.exists(temp_video):
        os.remove(temp_video)

    return output_path
# --- RECORDING LOGIC ---
def auto_stop_and_save():
    """Auto-stop, pull, process video, update database, and send to WhatsApp."""
    global LATEST_PROCESSED_VIDEO, SLOMO_MODE, PENDING_VIDEO
    PENDING_VIDEO = True

    time.sleep(AUTO_STOP_DELAY)
    run_adb(["shell", "input", "keyevent", "KEYCODE_CAMERA"])
    send_to_arduino("off")
    time.sleep(1)

    latest = get_latest_remote_filename()
    if not latest:
        logger.error("✗ No videos found to pull")
        PENDING_VIDEO = False
        return

    try:
        local_temp = pull_remote_file(latest)
        final_path = rename_with_timestamp(local_temp)
        processed_path = final_path.replace(".mp4", "_final.mp4")

        logger.info(f"⚙ Processing in SlowMo Mode: {SLOMO_MODE}")
        add_music_logo_slowmo(final_path, processed_path, SLOMO_MODE)

        os.replace(processed_path, final_path)
        LATEST_PROCESSED_VIDEO = final_path

        SLOMO_MODE = 1 - SLOMO_MODE
        logger.info(f"✓ Saved final video: {final_path}")
        
        # NEW: Update Flask database and trigger WhatsApp send
        try:
            response = requests.post(
                f"{FLASK_SERVER_URL}/update_video",
                json={"video_path": final_path},
                timeout=5
            )
            if response.status_code == 200:
                logger.info("✓ Database updated and WhatsApp notification sent")
            else:
                logger.error(f"✗ Failed to update database: {response.text}")
        except Exception as e:
            logger.error(f"✗ Error calling Flask API: {e}")
            
    except Exception as e:
        logger.exception("✗ Processing failed: %s", e)
    finally:
        PENDING_VIDEO = False

def send_video_to_whatsapp(name, phone_number, video_path):
    """Send processed video to WhatsApp service"""
    try:
        url = "http://127.0.0.1:5000/send_whatsapp_video"
        payload = {
            "name": name,
            "phone_number": phone_number,
            "video_path": video_path
        }
        headers = {"Content-Type": "application/json"}
        res = requests.post(url, data=json.dumps(payload), headers=headers, timeout=10)
        
        if res.status_code == 200:
            print(f"✅ WhatsApp video sent to {phone_number}")
        else:
            print(f"⚠️ Failed to send WhatsApp video: {res.text}")
    except Exception as e:
        print(f"❌ Error sending video to WhatsApp: {e}")
        

# --- ROUTES ---
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/start")
def start_recording():
    global PENDING_VIDEO
    if PENDING_VIDEO:
        return {"status": "busy", "message": "Previous video still processing. Wait."}

    run_adb([
    "shell",
    "am", "start",
    "-a", "android.media.action.VIDEO_CAPTURE",
    "--ei", "android.intent.extra.videoQuality", "1"
])
    time.sleep(1.0)
    run_adb(["shell", "input", "keyevent", "KEYCODE_CAMERA"])
    send_to_arduino("on")
    logger.info("✓ Recording started")
    threading.Thread(target=auto_stop_and_save, daemon=True).start()
    return {"status": "recording_started", "auto_stop_after_sec": AUTO_STOP_DELAY}

@app.get("/latest")
def latest_video():
    wait_time = 0
    while PENDING_VIDEO and wait_time < 60:
        time.sleep(0.5)
        wait_time += 0.5

    if LATEST_PROCESSED_VIDEO is None:
        return {"error": "No video ready yet"}
    return FileResponse(LATEST_PROCESSED_VIDEO, media_type="video/mp4")
