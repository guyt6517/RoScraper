import os
import io
from datetime import datetime
from flask import Flask, request, jsonify
import requests
from PIL import Image
from nsfw_detector import predict
from dotenv import load_dotenv

# Load environment variables from .env in local development
if not os.environ.get("DISCORD_WEBHOOK_URL"):
    load_dotenv()

# Constants
MODEL_PATH = "./nsfw_model"
LOG_FILE = "violation_log.txt"
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# Ensure NSFW model is downloaded
def ensure_model():
    if not os.path.exists(MODEL_PATH):
        print("Downloading NSFW model...")
        predict.download_model(MODEL_PATH)

ensure_model()

# Load NSFW model once
model = predict.load_model(MODEL_PATH)

# Initialize Flask app
app = Flask(__name__)

def classify_image(image: Image.Image) -> str:
    temp_path = "temp.jpg"
    image.save(temp_path)
    result = predict.classify(model, temp_path)
    os.remove(temp_path)

    scores = list(result.values())[0]
    top_class = max(scores, key=scores.get)

    nsfw_categories = ['porn', 'hentai', 'sexy']
    if top_class in nsfw_categories and scores[top_class] > 0.7:
        return f"{top_class.upper()} ({scores[top_class]*100:.1f}%)"
    return "Safe"

def log_violation(link: str, reason: str):
    with open(LOG_FILE, "a") as f:
        f.write(f"[{datetime.utcnow()}] LINK: {link} | REASON: {reason}\n")

def send_to_discord(message: str):
    if not DISCORD_WEBHOOK_URL:
        print("Discord webhook URL not set, skipping sending to Discord.")
        return
    payload = {
        "content": message
    }
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        if response.status_code != 204:
            print(f"Failed to send to Discord webhook: {response.status_code} {response.text}")
    except Exception as e:
        print(f"Error sending to Discord webhook: {e}")

def download_image_from_url(url: str) -> Image.Image:
    response = requests.get(url)
    if not response.ok:
        raise Exception(f"Failed to download image, status code {response.status_code}")
    return Image.open(io.BytesIO(response.content))

@app.route('/check', methods=['POST'])
def check_roblox_link():
    data = request.json
    if not data or "url" not in data:
        return jsonify({"error": "Missing 'url' in JSON body"}), 400

    url = data["url"]
    try:
        image = download_image_from_url(url)
        result = classify_image(image)
        if result != "Safe":
            log_violation(url, result)
            send_to_discord(f"🚨 NSFW Violation Detected!\nLink: {url}\nReason: {result}\nTime: {datetime.utcnow()} UTC")
            return jsonify({"status": "Violation detected", "reason": result}), 200
        else:
            return jsonify({"status": "Clean"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def home():
    return "Roblox NSFW Content Scanner Running."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
