from flask import Flask, render_template, request, jsonify, Response, redirect, url_for, session, send_file
import requests
import json
from queue import Queue
from datetime import datetime
from werkzeug.security import check_password_hash
from database import SessionLocal, PhotoboothSession, AdminUser, init_db
import os
import threading

app = Flask(__name__)
app.secret_key = "1393adf8d29475f50c28b10bd3eb653b"  # Change this!

# --- Configuration ---
WHATSAPP_ACCESS_TOKEN = "EAAmOw9tq0dUBP7uZA3lf32huFWZBlvN5BZBRDFShoKRtCeNQQZCojJHIp8sfJomlX0MqBEFb1dj5xTBp4b8jTZA9LZCJ2qC1s0t1ZApMJAmb77vDISq0RgvfBZBL1w4BVTZA8ZAWaiVaHZCIObFwY2RZBZCxZA8myX6JkjPSRViZBFq2F9ZAvfhwSYfr953kpBCdbYXci9ghFwZDZD"
YOUR_PHONE_NUMBER_ID = "766963433177408"
VERIFY_TOKEN = "verifytoken1234"
WHATSAPP_API_URL = f"https://graph.facebook.com/v19.0/{YOUR_PHONE_NUMBER_ID}/messages"

# Path to recorded videos (must match main.py)
VIDEO_STORAGE_PATH = r"C:\platform-tools-latest-windows\platform-tools\Recorded_Videos"

# Global state for current user session
current_session = {}
subscribers = []

# Initialize database
init_db()


@app.route('/')
def page1():
    """Serves the first page (frame1.html)."""
    return render_template('frame1.html')


@app.route('/page2')
def page2():
    """Serves the second page (frame2.html)."""
    return render_template('frame2.html')


@app.route('/stream')
def stream():
    """Server-Sent Event (SSE) stream for real-time page updates."""
    def event_stream():
        client_queue = Queue()
        subscribers.append(client_queue)
        print(f"Client connected. Total subscribers: {len(subscribers)}")

        try:
            while True:
                event = client_queue.get()
                yield f"data: {event}\n\n"
        except GeneratorExit:
            print("Client disconnected.")
        finally:
            subscribers.remove(client_queue)
            print(f"Removed subscriber. Total subscribers: {len(subscribers)}")

    return Response(event_stream(), content_type='text/event-stream')


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    """Handles incoming WhatsApp webhooks."""
    global current_session

    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
        else:
            return "Error, invalid verification token", 403

    if request.method == "POST":
        body = request.json
        print(f"Full webhook payload: {json.dumps(body, indent=2)}")

        try:
            if (body.get("object") == "whatsapp_business_account" and
                    body.get("entry") and
                    body["entry"][0].get("changes") and
                    body["entry"][0]["changes"][0].get("value") and
                    body["entry"][0]["changes"][0]["value"].get("messages")):

                message_details = body["entry"][0]["changes"][0]["value"]["messages"][0]
                from_number = message_details["from"]
                msg_body = message_details.get("text", {}).get("body", "").strip()

                if msg_body.lower() == 'hello_photobooth':
                    print(f"'hello_photobooth' message received from {from_number}. Broadcasting 'change' event.")
                    current_session['phone_number'] = from_number
                    current_session['timestamp'] = datetime.now()

                    for q in list(subscribers):
                        q.put('change')
                    send_whatsapp_message(from_number, "Hello there! 👋 Welcome to the Cinematic Experience! To get started, what's your name?")

                elif msg_body and msg_body.lower() != 'hello_photobooth':
                    print(f"Name received: {msg_body} from {from_number}. Broadcasting 'redirect' event.")
                    current_session['name'] = msg_body
                    current_session['phone_number'] = from_number

                    db = SessionLocal()
                    try:
                        new_session = PhotoboothSession(
                            name=msg_body,
                            phone_number=from_number,
                            timestamp=datetime.now()
                        )
                        db.add(new_session)
                        db.commit()
                        db.refresh(new_session)
                        current_session['db_id'] = new_session.id
                        print(f"✓ Database entry created: ID={new_session.id}")
                    except Exception as e:
                        db.rollback()
                        print(f"✗ Database error: {e}")
                    finally:
                        db.close()

                    for q in list(subscribers):
                        q.put('redirect')
                    send_whatsapp_message(from_number, f"Hello {msg_body}! Get ready, the countdown is about to begin. 🎥 Action time!")

                return jsonify({"status": "success"}), 200
            else:
                print("Received a non-message webhook or malformed payload.")
                return jsonify({"status": "ignored"}), 200

        except Exception as e:
            print(f"Error processing webhook: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "error", "message": "Method not allowed"}), 405


def send_whatsapp_message(to_number, message_text):
    """Sends a text message using the WhatsApp Cloud API."""
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message_text},
    }

    try:
        response = requests.post(WHATSAPP_API_URL, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        print(f"Successfully sent message to {to_number}: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending WhatsApp message: {e}")
        if getattr(e, "response", None):
            print(f"Response body: {e.response.text}")


def send_whatsapp_video(to_number, video_url):
    """Sends a video via WhatsApp using the Cloud API."""
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "video",
        "video": {
            "link": video_url,
            "caption": "IT'S READY! 🎉 Your cinematic slow-motion video is attached below. Enjoy!"
        }
    }

    try:
        response = requests.post(WHATSAPP_API_URL, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        print(f"✓ Successfully sent video to {to_number}")
        print(f"✓ Video URL: {video_url}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"✗ Error sending WhatsApp video: {e}")
        if getattr(e, "response", None):
            print(f"Response body: {e.response.text}")
        return False


def get_public_video_url(video_filename):
    """Generate public URL for video file (replace NGROK_URL with your actual one)."""
    NGROK_URL = "https://overconservative-booker-nonerroneous.ngrok-free.dev"  # UPDATE THIS!
    return f"{NGROK_URL}/videos/{video_filename}"


@app.route('/update_video', methods=['POST'])
def update_video():
    """Called by main.py after video processing — async WhatsApp sending (no timeout)."""
    global current_session
    
    data = request.json
    video_path = data.get('video_path')
    video_filename = os.path.basename(video_path)
    
    db_id = current_session.get('db_id')
    phone_number = current_session.get('phone_number')
    
    if not db_id:
        return jsonify({"status": "error", "message": "No active session"}), 400
    
    db = SessionLocal()
    try:
        session_record = db.query(PhotoboothSession).filter_by(id=db_id).first()
        if session_record:
            session_record.video_path = video_path
            session_record.video_filename = video_filename
            db.commit()
            print(f"✓ Updated database with video path for session {db_id}")
            
            public_video_url = get_public_video_url(video_filename)
            print(f"📹 Public video URL: {public_video_url}")
            
            if phone_number:
                print(f"📤 Scheduling WhatsApp video send in background for {phone_number}...")

                def send_video_async(phone_number, video_url, db_id):
                    """Background thread to send WhatsApp video and update DB."""
                    db_thread = SessionLocal()
                    try:
                        success = send_whatsapp_video(phone_number, video_url)
                        if success:
                            record = db_thread.query(PhotoboothSession).filter_by(id=db_id).first()
                            if record:
                                record.whatsapp_sent = True
                                record.whatsapp_sent_at = datetime.now()
                                db_thread.commit()
                                print(f"✅ WhatsApp video sent and DB updated for {phone_number}")
                        else:
                            print(f"⚠️ WhatsApp video send failed for {phone_number}")
                    except Exception as e:
                        print(f"✗ Error in background thread: {e}")
                    finally:
                        db_thread.close()

                threading.Thread(target=send_video_async, args=(phone_number, public_video_url, db_id)).start()

                return jsonify({
                    "status": "success",
                    "message": "Video saved and will be sent to WhatsApp shortly.",
                    "video_url": public_video_url
                }), 200
            else:
                print(f"⚠️ No phone number available for session {db_id}")
                return jsonify({
                    "status": "partial_success",
                    "message": "Video saved but no phone number"
                }), 200
            
        else:
            return jsonify({"status": "error", "message": "Session not found"}), 404
    except Exception as e:
        db.rollback()
        print(f"✗ Error updating video: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


# ==================== ADMIN PANEL ====================

@app.route('/admin')
def admin_login_page():
    if 'admin_logged_in' in session:
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_login.html')


@app.route('/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    db = SessionLocal()
    try:
        admin = db.query(AdminUser).filter_by(username=username).first()
        if admin and check_password_hash(admin.password_hash, password):
            session['admin_logged_in'] = True
            session['admin_username'] = username
            return jsonify({"status": "success"}), 200
        else:
            return jsonify({"status": "error", "message": "Invalid credentials"}), 401
    finally:
        db.close()


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    return redirect(url_for('admin_login_page'))


@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin_login_page'))
    return render_template('admin_dashboard.html')


@app.route('/admin/api/sessions')
def admin_get_sessions():
    if 'admin_logged_in' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    db = SessionLocal()
    try:
        sessions = db.query(PhotoboothSession).order_by(PhotoboothSession.timestamp.desc()).all()
        return jsonify([s.to_dict() for s in sessions]), 200
    finally:
        db.close()


@app.route('/admin/api/video/<int:session_id>')
def admin_get_video(session_id):
    if 'admin_logged_in' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    db = SessionLocal()
    try:
        session_record = db.query(PhotoboothSession).filter_by(id=session_id).first()
        if session_record and session_record.video_path and os.path.exists(session_record.video_path):
            return send_file(session_record.video_path, mimetype='video/mp4')
        else:
            return jsonify({"error": "Video not found"}), 404
    finally:
        db.close()


@app.route('/videos/<filename>')
def serve_video(filename):
    video_path = os.path.join(VIDEO_STORAGE_PATH, filename)
    if os.path.exists(video_path):
        print(f"📹 Serving video publicly: {filename}")
        return send_file(video_path, mimetype='video/mp4')
    else:
        print(f"❌ Video not found: {filename}")
        return jsonify({"error": "Video not found"}), 404


if __name__ == "__main__":
    app.run(port=5000, debug=True, threaded=True)
