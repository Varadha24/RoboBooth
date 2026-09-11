from flask import Flask, render_template, request, jsonify, Response, redirect, url_for, session, send_file
import requests
import json
from queue import Queue
from datetime import datetime
from werkzeug.security import check_password_hash
from database import SessionLocal, PhotoboothSession, AdminUser, init_db
import os

app = Flask(__name__)
app.secret_key = "1393adf8d29475f50c28b10bd3eb653b"  # Change this!

# --- Configuration ---
WHATSAPP_ACCESS_TOKEN = "EAAmOw9tq0dUBP7uZA3lf32huFWZBlvN5BZBRDFShoKRtCeNQQZCojJHIp8sfJomlX0MqBEFb1dj5xTBp4b8jTZA9LZCJ2qC1s0t1ZApMJAmb77vDISq0RgvfBZBL1w4BVTZA8ZAWaiVaHZCIObFwY2RZBZCxZA8myX6JkjPSRViZBFq2F9ZAvfhwSYfr953kpBCdbYXci9ghFwZDZD"
YOUR_PHONE_NUMBER_ID = "766963433177408"
VERIFY_TOKEN = "verifytoken1234"
WHATSAPP_API_URL = f"https://graph.facebook.com/v19.0/{YOUR_PHONE_NUMBER_ID}/messages"

VIDEO_STORAGE_PATH = r"C:\platform-tools-latest-windows\platform-tools\Recorded_Videos"

# Global state for current session
current_session = {
    "active": False,
    "phone_number": None,
    "db_id": None
}

subscribers = []

# Init DB
init_db()

158282837372377
@app.route('/')
def page1():
    return render_template('frame1.html')


@app.route('/page2')
def page2():
    return render_template('frame2.html')


@app.route('/stream')
def stream():
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


# ======================================================
#          UPDATED WEBHOOK WITH REJECTION LOGIC
# ======================================================
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    global current_session

    # VERIFY WEBHOOK
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
        return "Invalid verification token", 403

    # HANDLE POST MESSAGE
    if request.method == "POST":
        body = request.json
        print(f"\nIncoming Webhook:\n{json.dumps(body, indent=2)}\n")

        try:
            if (body.get("object") == "whatsapp_business_account" and
                body.get("entry") and
                body["entry"][0].get("changes") and
                body["entry"][0]["changes"][0].get("value") and
                body["entry"][0]["changes"][0]["value"].get("messages")):

                msg = body["entry"][0]["changes"][0]["value"]["messages"][0]
                from_number = msg["from"]
                msg_body = msg.get("text", {}).get("body", "").strip()

                # --------------------------------------------------------
                # CASE-1: If someone ELSE tries messaging during a session
                # --------------------------------------------------------
                if current_session["active"] and from_number != current_session["phone_number"]:
                    print(f"❌ REJECTED MESSAGE from {from_number}. Session active with {current_session['phone_number']}.")

                    # Optional: send WhatsApp rejection notice
                    send_whatsapp_message(
                        from_number,
                        "⚠️ The photobooth is currently busy with another user. Please try again in a few minutes."
                    )

                    # Optional: create log entry in console
                    print(f"Logged rejected user: {from_number} at {datetime.now()}")

                    # (Optional) Save rejected attempts in DB:
                    # db = SessionLocal()
                    # db.close()

                    return jsonify({"status": "rejected"}), 200

                # --------------------------------------------------------
                # CASE-2: Start new session with "hello_photobooth"
                # --------------------------------------------------------
                if msg_body.lower() == "hello_photobooth":
                    print(f"📸 Starting new session for {from_number}")

                    current_session["active"] = True
                    current_session["phone_number"] = from_number
                    current_session["db_id"] = None

                    for q in list(subscribers):
                        q.put("change")

                    send_whatsapp_message(
                        from_number,
                        "Hi 👋! Welcome to the Cinematic Photobooth. What's your name?"
                    )

                    return jsonify({"status": "started"}), 200

                # --------------------------------------------------------
                # CASE-3: Name received
                # --------------------------------------------------------
                if current_session["active"] and from_number == current_session["phone_number"]:
                    print(f"Name received: {msg_body}")

                    db = SessionLocal()
                    try:
                        entry = PhotoboothSession(
                            name=msg_body,
                            phone_number=from_number,
                            timestamp=datetime.now()
                        )
                        db.add(entry)
                        db.commit()
                        db.refresh(entry)
                        current_session["db_id"] = entry.id
                        print(f"DB entry created ID={entry.id}")
                    except Exception as e:
                        db.rollback()
                        print("DB Error:", e)
                    finally:
                        db.close()

                    for q in list(subscribers):
                        q.put("redirect")

                    send_whatsapp_message(
                        from_number,
                        f"Awesome {msg_body}! Get ready, the countdown is about to begin on the screen. The robot will start moving and the camera will record in just a few seconds. Action time!"
                    )

                    return jsonify({"status": "name_saved"}), 200

                return jsonify({"status": "ignored"}), 200

        except Exception as e:
            print("Webhook error:", e)
            return jsonify({"status": "error"}), 500

    return jsonify({"error": "Method not allowed"}), 405


# ======================================================
# WHATSAPP SENDING UTILITIES
# ======================================================
def send_whatsapp_message(to_number, message_text):
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
        res = requests.post(WHATSAPP_API_URL, headers=headers, json=payload)
        res.raise_for_status()
        print(f"Sent message to {to_number}")
    except Exception as e:
        print(f"❌ WhatsApp send error: {e}")


def send_whatsapp_video(to_number, video_url):
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
            "caption": "IT'S READY! 🎉 Your cinematic slow-motion video is attached below. We hope you enjoyed the experience! 🎬✨"
        }
    }

    try:
        res = requests.post(WHATSAPP_API_URL, headers=headers, json=payload)
        res.raise_for_status()
        print(f"Video sent to {to_number}")
        return True
    except Exception as e:
        print("Video send error:", e)
        return False


def get_public_video_url(video_filename):
    NGROK_URL = "https://newsier-peeringly-joselyn.ngrok-free.dev"
    return f"{NGROK_URL}/videos/{video_filename}"


@app.route('/update_video', methods=['POST'])
def update_video():
    global current_session

    data = request.json
    video_path = data.get("video_path")
    video_filename = os.path.basename(video_path)

    db_id = current_session.get("db_id")
    phone_number = current_session.get("phone_number")

    if not db_id:
        return jsonify({"error": "No active session"}), 400

    db = SessionLocal()
    try:
        entry = db.query(PhotoboothSession).filter_by(id=db_id).first()
        if entry:
            entry.video_path = video_path
            entry.video_filename = video_filename
            db.commit()

            public_url = get_public_video_url(video_filename)
            print("Public video URL:", public_url)

            if phone_number:
                sent = send_whatsapp_video(phone_number, public_url)
                if sent:
                    entry.whatsapp_sent = True
                    entry.whatsapp_sent_at = datetime.now()
                    db.commit()

            # SESSION END
            current_session["active"] = False
            current_session["phone_number"] = None
            current_session["db_id"] = None

            return jsonify({"status": "success"}), 200

    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


# ---------------- ADMIN PANEL -------------------

@app.route('/admin')
def admin_login_page():
    if 'admin_logged_in' in session:
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_login.html')


@app.route('/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    db = SessionLocal()
    try:
        admin = db.query(AdminUser).filter_by(username=username).first()
        if admin and check_password_hash(admin.password_hash, password):
            session['admin_logged_in'] = True
            session['admin_username'] = username
            return jsonify({"status": "success"}), 200
        return jsonify({"error": "Invalid credentials"}), 401
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
        entry = db.query(PhotoboothSession).filter_by(id=session_id).first()
        if entry and entry.video_path and os.path.exists(entry.video_path):
            return send_file(entry.video_path, mimetype="video/mp4")
        return jsonify({"error": "Video not found"}), 404
    finally:
        db.close()


@app.route('/videos/<filename>')
def serve_video(filename):
    file_path = os.path.join(VIDEO_STORAGE_PATH, filename)

    if os.path.exists(file_path):
        return send_file(file_path, mimetype="video/mp4")
    return jsonify({"error": "Video not found"}), 404


if __name__ == "__main__":
    app.run(port=5000, debug=True, threaded=True)
