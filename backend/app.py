"""
AI Image Detector - Flask backend (API server)
==============================================

What this file does:
  1. Starts a small web server.
  2. Loads your THREE detection models once, when the server starts.
  3. Exposes two URLs (called "endpoints"):
       GET  /health   -> quick check that the server is alive
       POST /predict  -> receives an image, returns JSON with the result
  4. Allows ONLY your GitHub Pages site to call it (CORS).

The detection logic (models, labels, averaging, thresholds, metadata checks)
is copied from your existing ai_image_detector.py. Only the "plumbing" changed:
instead of reading a file path, we read the uploaded image from memory.
"""

import io
import os

import torch
from flask import Flask, jsonify, request
from flask_cors import CORS
from PIL import ExifTags, Image
from transformers import pipeline

# ---------------------------------------------------------------------------
# 1. SETTINGS (read from environment variables so you never hard-code them)
# ---------------------------------------------------------------------------

# Which websites may call this API. Comma-separated list.
# Example: https://yourname.github.io
# NOTE: only the "origin" (no path!). Not https://yourname.github.io/my-repo/
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
    if o.strip()
]

# Reject uploads bigger than this (megabytes). Protects your server.
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "10"))

# ---------------------------------------------------------------------------
# 2. YOUR EXISTING DETECTION SETTINGS (unchanged)
# ---------------------------------------------------------------------------

MODELS = [
    "umm-maybe/AI-image-detector",
    "Organika/sdxl-detector",
    "dima806/ai_vs_real_image_detection",
]

AI_WORDS = ("artificial", "ai", "fake", "generated", "synthetic")

AI_SOFTWARE_HINTS = (
    "midjourney", "stable diffusion", "dall", "firefly", "comfyui",
    "automatic1111", "novelai", "leonardo", "ideogram", "flux", "imagen",
)

# ---------------------------------------------------------------------------
# 3. FLASK APP + CORS
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

# CORS = Cross-Origin Resource Sharing. Browsers BLOCK a website from calling
# a different domain unless that server says "this website is allowed".
# This line tells the browser: only ALLOWED_ORIGINS may call us.
CORS(app, origins=ALLOWED_ORIGINS)

# ---------------------------------------------------------------------------
# 4. LOAD MODELS ONCE AT STARTUP (loading is slow, so never do it per request)
# ---------------------------------------------------------------------------


def load_detectors():
    device = 0 if torch.cuda.is_available() else -1
    detectors = []
    for name in MODELS:
        try:
            print(f"Loading model: {name}", flush=True)
            detectors.append((name, pipeline("image-classification", model=name, device=device)))
        except Exception as e:  # model unavailable -> skip it (same as your original)
            print(f"[warn] could not load {name}: {e}", flush=True)
    if not detectors:
        raise RuntimeError("No detector models could be loaded.")
    return detectors


DETECTORS = load_detectors()
print(f"Ready. {len(DETECTORS)} model(s) loaded.", flush=True)

# ---------------------------------------------------------------------------
# 5. DETECTION LOGIC (same as your original script)
# ---------------------------------------------------------------------------


def ai_probability(det, img):
    """Return P(AI-generated) from one classifier."""
    preds = det(img, top_k=None)
    p_ai = 0.0
    for p in preds:
        label = p["label"].lower()
        if any(w == label or w in label for w in AI_WORDS):
            p_ai += p["score"]
    return p_ai


def metadata_signals(data, img):
    """Weak hints only. Absence of metadata proves nothing."""
    notes = []
    try:
        exif = img.getexif()
        tags = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
        software = str(tags.get("Software", "")).lower()
        if any(h in software for h in AI_SOFTWARE_HINTS):
            notes.append(f"EXIF Software tag mentions an AI tool: {software}")
        if not tags.get("Make") and not tags.get("Model"):
            notes.append("No camera make/model in EXIF (common for AI images, but also for screenshots/edited photos)")
    except Exception:
        pass
    for key in ("parameters", "prompt", "workflow", "Comment"):
        if key in getattr(img, "info", {}):
            notes.append(f"PNG metadata contains '{key}' field (typical of AI generators)")
    try:
        if b"c2pa" in data[:200000].lower():
            notes.append("Contains C2PA Content Credentials manifest - inspect with c2patool")
    except Exception:
        pass
    return notes


def analyze(data):
    """Run the full detection on raw image bytes. Returns a dict."""
    img = Image.open(io.BytesIO(data)).convert("RGB")
    scores = {name: ai_probability(det, img) for name, det in DETECTORS}
    avg = sum(scores.values()) / len(scores)

    raw = Image.open(io.BytesIO(data))
    notes = metadata_signals(data, raw)

    if any("AI tool" in n or "AI generators" in n for n in notes):
        avg = max(avg, 0.9)

    if avg >= 0.75:
        verdict = "LIKELY AI-GENERATED"
    elif avg <= 0.25:
        verdict = "LIKELY REAL"
    else:
        verdict = "UNCERTAIN"

    return {
        "verdict": verdict,
        "ai_probability": round(avg, 4),      # 0.0 - 1.0
        "confidence_percent": round(avg * 100, 2),
        "model_scores": {n: round(s, 4) for n, s in scores.items()},
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# 6. API ENDPOINTS
# ---------------------------------------------------------------------------


@app.get("/")
def home():
    return jsonify({"service": "AI Image Detector API", "status": "ok", "predict": "POST /predict"})


@app.get("/health")
def health():
    return jsonify({"status": "ok", "models_loaded": len(DETECTORS)})


@app.post("/predict")
def predict():
    # The frontend sends the file in a form field called "image".
    if "image" not in request.files:
        return jsonify({"error": "No file received. Send it in a form field named 'image'."}), 400

    file = request.files["image"]
    data = file.read()
    if not data:
        return jsonify({"error": "The uploaded file is empty."}), 400

    try:
        result = analyze(data)
    except Exception:
        # Pillow could not open it -> not a valid image
        return jsonify({"error": "Could not read this file as an image (use JPG, PNG or WEBP)."}), 400

    return jsonify(result)


@app.errorhandler(413)
def too_large(_e):
    return jsonify({"error": f"File too large. Maximum is {MAX_UPLOAD_MB} MB."}), 413


# ---------------------------------------------------------------------------
# 7. RUN LOCALLY:  python app.py     (production uses gunicorn, see Dockerfile)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
