from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
import requests
import os
from config import GEMINI_API_KEY, USERS, SECRET_KEY

# Use local dist folder (for Render deployment) or ../frontend/dist (for local dev)
static_folder = 'dist' if os.path.exists('dist') else '../frontend/dist'
app = Flask(__name__, static_folder=static_folder, static_url_path='')
app.secret_key = SECRET_KEY
CORS(app, supports_credentials=True)

# Gemini API endpoint
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={GEMINI_API_KEY}"

# ============ AUTH ROUTES ============

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '')
    password = data.get('password', '')

    if username in USERS and USERS[username] == password:
        session['user'] = username
        return jsonify({'success': True, 'message': 'Login successful'})

    return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return jsonify({'success': True, 'message': 'Logged out'})

@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    if 'user' in session:
        return jsonify({'authenticated': True, 'user': session['user']})
    return jsonify({'authenticated': False}), 401

# ============ GEMINI API PROXY ============

@app.route('/api/process-image', methods=['POST'])
def process_image():
    # Check authentication
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    prompt = data.get('prompt', '')
    image_base64 = data.get('image', '')
    mime_type = data.get('mimeType', 'image/jpeg')

    # Build request for Gemini API
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": image_base64
                    }
                }
            ]
        }],
        "generationConfig": {
            "responseModalities": ["image", "text"],
            "responseMimeType": "text/plain"
        }
    }

    try:
        response = requests.post(
            GEMINI_API_URL,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=120
        )

        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({
                'error': f'Gemini API error: {response.status_code}',
                'details': response.text
            }), response.status_code

    except requests.exceptions.Timeout:
        return jsonify({'error': 'Request timeout'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============ SERVE REACT APP ============

@app.route('/')
def serve():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def static_proxy(path):
    file_path = os.path.join(app.static_folder, path)
    if os.path.exists(file_path):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
