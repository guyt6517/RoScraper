from flask import Flask, request, jsonify
import requests
import os
import io
from PIL import Image
from datetime import datetime
from nsfw_detector import predict

# Load NSFW classifier
model = predict.load_model("./nsfw_model")  # Downloaded model folder path

def classify_image(image: Image.Image) -> str:
    """
    Classifies image using NSFW model.
    """
    temp_path = "temp.jpg"
    image.save(temp_path)
    result = predict.classify(model, temp_path)
    os.remove(temp_path)

    scores = list(result.values())[0]
    top_class = max(scores, key=scores.get)

    # Consider these NSFW
    nsfw_categories = ['porn', 'hentai', 'sexy']
    if top_class in nsfw_categories and scores[top_class] > 0.7:
        return f"{top_class.upper()} ({scores[top_class]*100:.1f}%)"
    return "Safe"

def log_violation(link: str, reason: str):
    with open("violation_log.txt", "a") as f:
        f.write(f"[{datetime.utcnow()}] LINK: {link} | REASON: {reason}\n")

def download_image_from_url(url: str) -> Image.Image:
    """
    Downloads image from a URL.
    """
    response = requests.get(url)
    if not response.ok:
        raise Exception("Image download failed")
    return Image.open(io.BytesIO(response.content))

app = Flask(__name__)

@app.route('/check', methods=['POST'])
def check_roblox_link():
    data = request.json
    url = data.get("url")
    if not url:
        return jsonify({"error": "Missing 'url'"}), 400
    
    try:
        image = download_image_from_url(url)
        result = classify_image(image)
        if result != "Safe":
            log_violation(url, result)
            return jsonify({"status": "Violation detected", "reason": result}), 200
        else:
            return jsonify({"status": "Clean"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def home():
    return "Roblox TOS NSFW Scanner"

if __name__ == "__main__":
    app.run(debug=True)
