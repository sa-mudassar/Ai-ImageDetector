// script.js - runs in the visitor's browser.
// Flow: user picks image -> we send it to the backend -> we show the JSON result.

const fileInput = document.getElementById("imageInput");
const preview = document.getElementById("preview");
const analyzeBtn = document.getElementById("analyzeBtn");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");

let selectedFile = null;

// 1) When the user chooses a file: remember it and show a preview.
fileInput.addEventListener("change", () => {
  selectedFile = fileInput.files[0] || null;
  resultEl.innerHTML = "";
  statusEl.textContent = "";
  if (selectedFile) {
    preview.src = URL.createObjectURL(selectedFile);
    preview.style.display = "block";
    analyzeBtn.disabled = false;
  }
});

// 2) When the user clicks "Analyze": send the image to the backend.
analyzeBtn.addEventListener("click", async () => {
  if (!selectedFile) return;

  // FormData is how browsers upload files. The field name "image"
  // MUST match request.files["image"] in app.py.
  const formData = new FormData();
  formData.append("image", selectedFile);

  analyzeBtn.disabled = true;
  resultEl.innerHTML = "";
  statusEl.textContent = "Analyzing... (the first request can take up to a minute if the server was asleep)";

  try {
    const response = await fetch(`${API_URL}/predict`, {
      method: "POST",
      body: formData, // do NOT set Content-Type yourself; the browser does it
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "Server error");
    }
    showResult(data);
    statusEl.textContent = "";
  } catch (err) {
    // Network/CORS failures land here too (see the guide's "Common errors").
    statusEl.textContent = "Error: " + err.message;
  } finally {
    analyzeBtn.disabled = false;
  }
});

// 3) Turn the JSON from Python into something readable.
function showResult(data) {
  const cls =
    data.verdict === "LIKELY AI-GENERATED" ? "ai" :
    data.verdict === "LIKELY REAL" ? "real" : "unsure";

  const rows = Object.entries(data.model_scores)
    .map(([name, score]) => `<li>${escapeHtml(name)}: ${(score * 100).toFixed(1)}% AI</li>`)
    .join("");
  const notes = data.notes.map((n) => `<li>${escapeHtml(n)}</li>`).join("");

  resultEl.innerHTML = `
    <div class="verdict ${cls}">${escapeHtml(data.verdict)}</div>
    <p>AI probability: <strong>${data.confidence_percent}%</strong></p>
    <details><summary>Model breakdown</summary><ul>${rows}</ul></details>
    ${notes ? `<details><summary>Metadata notes</summary><ul>${notes}</ul></details>` : ""}
  `;
}

// Safety: never insert server text into the page without escaping it.
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
