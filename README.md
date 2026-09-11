# Robotic Photobooth

The Robotic Photobooth integrates a Doosan collaborative robot (cobot), Android camera, backend server, and supporting hardware to create an automated cinematic slow-motion video experience.

This README covers the initial setup steps required for the backend and camera environment.

## 1. Prerequisites

The following hardware components are required:

- Doosan Cobot (6-DOF)
- Backend Server / Mini Desktop PC
- Android Camera
- USB A-to-C Cable
- 40"/50" Display
- Arduino + Relay
- Wired LAN connection for the cobot
- Local Wi-Fi connection for the camera

## 2. Software Requirements

Install the following software and packages:

- Python
- FastAPI
- Uvicorn
- Flask
- PySerial
- Pillow
- Jinja2
- FFmpeg
- Android Debug Bridge (ADB)
- Arduino IDE
- Ngrok
- SQLite

The backend uses Python with FastAPI and Flask. FFmpeg is used for video processing, while ADB is used to control and transfer video from the Android camera.

## 3. Python Setup

### 3.1 Install Python

Install Python on the backend server.

Add the following Python directories to the system `PATH`:

```text
C:\Users\<YourUsername>\AppData\Local\Programs\Python\Python3x\
C:\Users\<YourUsername>\AppData\Local\Programs\Python\Python3x\Scripts\
```

> Replace `<YourUsername>` and `Python3x` with the appropriate values for your system.

### 3.2 Verify Python Installation

Open Command Prompt and run:

```bash
python --version
```

The installed Python version should be displayed.

### 3.3 Install Required Python Packages

Install the required packages:

```bash
pip install fastapi uvicorn pyserial pillow jinja2
```

Verify the installed packages:

```bash
pip list
```

## 4. FFmpeg Setup

FFmpeg is used for video post-processing, including:

- Slow-motion effects
- Background music
- Branding
- Video effects

### 4.1 Add FFmpeg to PATH

Add the following directory to the system `PATH`:

```text
C:\ffmpeg\bin
```

### 4.2 Verify FFmpeg Installation

Open Command Prompt and run:

```bash
ffmpeg -version
```

The FFmpeg version information should be displayed.

## 5. ADB Setup

Android Debug Bridge (ADB) is used to communicate with the Android camera from the backend PC.

The camera workflow uses ADB commands to:

- Start video recording
- Stop video recording
- Transfer the recorded video to the PC

### 5.1 Add ADB to PATH

Add the following directory to the system `PATH`:

```text
C:\platform-tools-latest-windows\platform-tools
```

### 5.2 Connect the Android Camera

Connect the Android camera to the backend PC and ensure ADB access is enabled.

### 5.3 Verify the Camera Connection

Open Command Prompt and run:

```bash
adb devices
```

The connected Android device should appear in the device list.

### 5.4 Camera Recording Workflow

The camera integration follows this sequence:

```text
Connect PC to Android Camera via ADB
              ↓
Send ADB command to start recording
              ↓
Start video recording
              ↓
Doosan executes cinematic motion
              ↓
Send ADB command to stop recording
              ↓
Pull recorded video to PC
```

Example video transfer command:

```bash
adb pull ... /selected_dir
```

The camera supports 1080p–4K video depending on the phone model. Slow-motion recording is limited by the capabilities of the selected phone, with high-end phones supporting up to 240 FPS.

---

## Setup Verification

Before continuing with the remaining photobooth setup, verify the following:

### Python

```bash
python --version
pip list
```

### FFmpeg

```bash
ffmpeg -version
```

### ADB

```bash
adb devices
```

All three tools should be available from Command Prompt before proceeding with the remaining system configuration.
