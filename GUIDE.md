# AI Image Detector: Full Setup Guide (GitHub Pages + Python backend)

## 0. What's in this package

```
ai-detector/
├── GUIDE.md                  <- this file
├── backend/                  <- goes to your Python host (Hugging Face Space)
│   ├── app.py                <- Flask API (your 3 models + detection logic)
│   ├── requirements.txt      <- Python packages
│   ├── Dockerfile            <- build recipe for the host
│   ├── README.md             <- Hugging Face Space settings (must stay named README.md)
│   ├── .dockerignore
│   └── detector_original.py  <- your original script, kept for reference only (not deployed)
└── frontend/                 <- goes to your GitHub Pages repo
    ├── index.html
    ├── style.css
    ├── script.js             <- sends the image, shows the result
    └── config.js             <- the backend URL lives here
```

Your three models are unchanged: `umm-maybe/AI-image-detector`, `Organika/sdxl-detector`, `dima806/ai_vs_real_image_detection`.
The averaging, thresholds (75% / 25%) and metadata checks are copied from your script.

I could not see your existing GitHub frontend. The HTML here is minimal. **If you already have a design, keep it**: see section 5.

---

## 1. Architecture: how the two sides talk

```
 Visitor's browser                                        Your Python server
┌──────────────────────────┐   1. POST /predict          ┌───────────────────────────┐
│ GitHub Pages site        │      (image as form-data)   │ Flask app (app.py)        │
│ index.html + script.js   │ ───────────────────────────>│  - checks CORS            │
│                          │                             │  - runs 3 models          │
│ 3. shows verdict + %     │ <───────────────────────────│  - averages the scores    │
└──────────────────────────┘   2. JSON response          └───────────────────────────┘
```

Key facts for a beginner:

- **GitHub Pages only serves static files** (HTML/CSS/JS). It cannot run Python. That is why the backend must be hosted elsewhere.
- Your page and your server are on **different domains**, so the browser applies a safety rule called **CORS**. The server must explicitly say "this website may call me". That's the `ALLOWED_ORIGINS` setting.
- The image travels as **multipart form-data** in a field named `image`. Python sends back **JSON** like:

```json
{
  "verdict": "LIKELY AI-GENERATED",
  "ai_probability": 0.8123,
  "confidence_percent": 81.23,
  "model_scores": {"umm-maybe/AI-image-detector": 0.91, "...": 0.72},
  "notes": ["No camera make/model in EXIF ..."]
}
```

---

## 2. Which platform to host the backend

**Recommendation: Hugging Face Spaces (Docker Space), free CPU tier.**

Why: your models are PyTorch/transformers models and are already hosted on Hugging Face, so downloads are fast. The free tier has far more RAM than most free hosts (check the current limits on the Spaces page). Three models need a few GB of RAM.

Trade-offs you should know:

| Platform | Fit | Catch |
|---|---|---|
| **Hugging Face Spaces (free)** | Best for this project | Free Spaces go to sleep after inactivity; the first request afterwards is slow (up to ~1 minute) |
| Render / Railway / Fly.io | Fine if you pay | Free tiers usually have too little RAM for 3 PyTorch models |
| Your own VPS | Full control | You manage the server and HTTPS yourself |

Everything below uses Hugging Face Spaces.

---

## 3. Test everything on your computer first

You need Python 3.10+ installed. Use two terminals.

### Terminal 1: backend

```bash
cd ai-detector/backend
python -m venv venv
# Activate it:
#   Windows (PowerShell):  venv\Scripts\Activate.ps1
#   Windows (cmd):         venv\Scripts\activate.bat
#   Mac/Linux:             source venv/bin/activate
pip install -r requirements.txt
python app.py
```

The first run downloads the three models (a few hundred MB to a few GB, so wait). When you see `Ready. 3 model(s) loaded.` and `Running on http://0.0.0.0:5000`, it works.
Quick check: open `http://127.0.0.1:5000/health` in your browser. You should see `{"models_loaded":3,"status":"ok"}`.

### Terminal 2: frontend

```bash
cd ai-detector/frontend
python -m http.server 8000
```

Open **http://localhost:8000** (not by double-clicking the HTML file: opening it as `file://` breaks CORS).
Upload an image, click **Analyze image**. `config.js` already points at `http://127.0.0.1:5000`.
The default `ALLOWED_ORIGINS` already allows `http://localhost:8000`, so no extra setup locally.

You can also test the API alone, without the website:

```bash
curl -X POST -F "image=@photo.jpg" http://127.0.0.1:5000/predict
```

---

## 4. Deploy the backend (Hugging Face Spaces)

### 4.1 Create the Space
1. Sign up at https://huggingface.co.
2. Click your profile picture, then **New Space**.
3. Name: e.g. `ai-image-detector`. **SDK: Docker** (choose "Blank"). Hardware: **CPU basic (free)**. Visibility: **Public** (a public Space is simplest, since your website must reach it without a login).
4. Click **Create Space**.

### 4.2 Upload the backend files
Easiest way (no Git): in your Space, open **Files, then Add file, then Upload files**, and upload these from your `backend/` folder:
`app.py`, `requirements.txt`, `Dockerfile`, `README.md`, `.dockerignore`
(Skip `detector_original.py`. The Space already has a default `README.md`; overwrite it with mine. It must contain the `sdk: docker` and `app_port: 7860` header.)
Commit the upload.

*Git alternative:*
```bash
git clone https://huggingface.co/spaces/YOUR_USERNAME/ai-image-detector
cd ai-image-detector
# copy the backend files into this folder, then:
git add .
git commit -m "Add backend"
git push
```
(When Git asks for a password, use a Hugging Face access token with write permission from Settings, then Access Tokens.)

### 4.3 Set the CORS environment variable
In the Space: **Settings, then Variables and secrets, then New variable**
- Name: `ALLOWED_ORIGINS`
- Value: `https://YOUR_GITHUB_USERNAME.github.io`

Rules: include `https://`, **no trailing slash, no repo path**. For several sites separate with commas, e.g. `https://you.github.io,http://localhost:8000`.
Saving restarts the Space.

### 4.4 Wait for the build
Open the **App** tab. You'll see build logs (the first build takes several minutes because it downloads PyTorch and the models). When status is **Running**, test:

`https://YOUR_USERNAME-ai-image-detector.hf.space/health`

(Format: `https://<username>-<space-name>.hf.space`. You can also copy it from the Space's menu, then **Embed this Space**, then **Direct URL**.)
You should see `{"models_loaded":3,"status":"ok"}`.

---

## 5. Connect the frontend and publish on GitHub Pages

### Option A: use my frontend as-is
Copy `index.html`, `style.css`, `script.js`, `config.js` into your GitHub Pages repository (root folder, or `/docs` if that's what Pages uses).

### Option B: keep your existing design (recommended if you already have one)
1. Add `config.js` and `script.js` to your repo.
2. In your existing HTML make sure these elements exist with exactly these IDs:
   - `<input type="file" id="imageInput">`
   - `<img id="preview">`
   - `<button id="analyzeBtn">`
   - `<p id="status">`
   - `<div id="result">`
3. Add before `</body>` (in this order):
   ```html
   <script src="config.js"></script>
   <script src="script.js"></script>
   ```
4. If your IDs differ, change the `getElementById("...")` lines at the top of `script.js`.

### Set the backend URL
Edit `config.js`:
```js
const API_URL = "https://YOUR_USERNAME-ai-image-detector.hf.space";
```
No trailing slash. It **must be `https://`**: a GitHub Pages site (https) is not allowed to call an `http://` address.

### Publish
```bash
cd your-github-pages-repo
git add .
git commit -m "Connect to backend"
git push
```
In GitHub: **Repo, Settings, Pages**, choose branch `main` and folder `/ (root)`. After a minute your site is live at `https://YOUR_USERNAME.github.io/REPO_NAME/`. Open it, upload an image, and it works.

---

## 6. What each important code section does

**backend/app.py**
- `ALLOWED_ORIGINS` / `CORS(...)`: lets only your site call the API.
- `MAX_UPLOAD_MB`: refuses huge files (default 10 MB).
- `load_detectors()`: loads your 3 models **once** at startup (loading per request would take minutes).
- `ai_probability()`, `metadata_signals()`, `analyze()`: your original logic, now reading the image from memory instead of a file path.
- `@app.post("/predict")`: receives the `image` field, calls `analyze()`, returns JSON. Bad input returns a clear error (400/413) instead of crashing.

**frontend/script.js**
- Reads the chosen file, shows a preview.
- `FormData` + `fetch(... "/predict")` uploads it. `try/catch` shows errors on the page.
- `showResult()` builds the result display; `escapeHtml()` prevents injecting unsafe text into the page.

**Dockerfile**: installs CPU-only PyTorch (much smaller), installs packages, pre-downloads the models during the build, then starts `gunicorn` (a production-grade server; Flask's built-in one is for development only) on port 7860.

---

## 7. Common errors and fixes

| Symptom | Cause | Fix |
|---|---|---|
| Browser console: `blocked by CORS policy` | `ALLOWED_ORIGINS` doesn't match your site | Value must be exactly `https://username.github.io`, no slash, no `/repo-name`. Save, wait for the Space to restart |
| `Failed to fetch` / `NetworkError` | Wrong `API_URL`, backend asleep/crashed, or `http://` used from an https site | Open `API_URL/health` in a new tab. Use `https://`. Check Space logs |
| First request very slow or times out | Free Space was sleeping | Wait ~1 minute and retry. Open the Space page to wake it |
| `Mixed Content` error | Page is https, `API_URL` is http | Use the https Space URL |
| Space status **Build error** | Typo in a file, or Dockerfile couldn't download | Read the **Logs** tab; fix and push again |
| Space **Runtime error** / "out of memory" | Not enough RAM | Check Logs; consider paid hardware or removing a model (ask me before changing models) |
| `{"error":"No file received..."}` | Form field name mismatch | `formData.append("image", ...)` must match `request.files["image"]` |
| 413 `File too large` | Over 10 MB | Raise `MAX_UPLOAD_MB` variable in the Space |
| `Could not read this file as an image` | Unsupported/corrupt file | Use JPG/PNG/WEBP |
| `[warn] could not load <model>` in logs | A model couldn't download | The app continues with the others (same as your original), but check your connection/model name |
| `ModuleNotFoundError` locally | venv not activated or install failed | Activate venv, rerun `pip install -r requirements.txt` |
| Page works locally but not on GitHub | `config.js` still points to `127.0.0.1` | Change `API_URL` and push; hard-refresh (Ctrl+Shift+R) |
| Old JS still running after update | Browser cache | Hard-refresh |
| Locally opened HTML via double-click fails | `file://` origin | Use `python -m http.server 8000` |

---

## 8. Honest limitations

- Detection scores are **probabilities**, not proof. Accuracy drops on new generators, compressed or edited images.
- Anyone who finds your Space URL can call it. For a public project, consider adding rate limiting (e.g. `flask-limiter`) if you see abuse.
- Free tiers sleep and can change their limits; check the host's current terms.
