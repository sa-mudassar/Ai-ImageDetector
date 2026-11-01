"""
AI-generated vs real photo detector
-----------------------------------
Ensemble of pretrained Hugging Face image classifiers + metadata checks.

Install:
    pip install torch transformers pillow

Usage:
    python ai_image_detector.py photo.jpg
    python ai_image_detector.py folder_with_images/
"""

import sys
from pathlib import Path

import torch
from PIL import Image, ExifTags
from transformers import pipeline

# Several independent detectors -> more robust than any single one.
MODELS = [
    "umm-maybe/AI-image-detector",
    "Organika/sdxl-detector",
    "dima806/ai_vs_real_image_detection",
]

AI_WORDS = ("artificial", "ai", "fake", "generated", "synthetic")
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

AI_SOFTWARE_HINTS = (
    "midjourney", "stable diffusion", "dall", "firefly", "comfyui",
    "automatic1111", "novelai", "leonardo", "ideogram", "flux", "imagen",
)


def load_detectors():
    device = 0 if torch.cuda.is_available() else -1
    detectors = []
    for name in MODELS:
        try:
            detectors.append((name, pipeline("image-classification", model=name, device=device)))
        except Exception as e:  # model unavailable -> skip it
            print(f"[warn] could not load {name}: {e}")
    if not detectors:
        sys.exit("No detector models could be loaded (check internet connection).")
    return detectors


def ai_probability(det, img):
    """Return P(AI-generated) from one classifier."""
    preds = det(img, top_k=None)
    p_ai = 0.0
    for p in preds:
        label = p["label"].lower()
        if any(w == label or w in label for w in AI_WORDS):
            p_ai += p["score"]
    return p_ai


def metadata_signals(path, img):
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
    # Stable Diffusion UIs often embed prompts in PNG text chunks
    for key in ("parameters", "prompt", "workflow", "Comment"):
        if key in getattr(img, "info", {}):
            notes.append(f"PNG metadata contains '{key}' field (typical of AI generators)")
    # C2PA / Content Credentials marker
    try:
        if b"c2pa" in Path(path).read_bytes()[:200000].lower():
            notes.append("Contains C2PA Content Credentials manifest - inspect with c2patool")
    except Exception:
        pass
    return notes


def analyze(path, detectors):
    img = Image.open(path).convert("RGB")
    scores = {}
    for name, det in detectors:
        scores[name] = ai_probability(det, img)
    avg = sum(scores.values()) / len(scores)
    raw = Image.open(path)
    notes = metadata_signals(path, raw)

    if any("AI tool" in n or "AI generators" in n for n in notes):
        avg = max(avg, 0.9)

    if avg >= 0.75:
        verdict = "LIKELY AI-GENERATED"
    elif avg <= 0.25:
        verdict = "LIKELY REAL"
    else:
        verdict = "UNCERTAIN"

    print(f"\n=== {path} ===")
    for n, s in scores.items():
        print(f"  {n:45s} AI prob: {s:.2%}")
    print(f"  Ensemble AI probability: {avg:.2%}  ->  {verdict}")
    for n in notes:
        print(f"  note: {n}")
    return avg, verdict


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    target = Path(sys.argv[1])
    files = [target] if target.is_file() else sorted(
        p for p in target.rglob("*") if p.suffix.lower() in IMG_EXT
    )
    detectors = load_detectors()
    for f in files:
        try:
            analyze(f, detectors)
        except Exception as e:
            print(f"[error] {f}: {e}")


if __name__ == "__main__":
    main()
