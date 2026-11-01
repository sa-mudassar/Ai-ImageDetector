# Dockerfile = recipe that tells the host how to build and run your backend.
FROM python:3.11-slim

# Hugging Face Spaces runs containers as a non-root user (id 1000)
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH" \
    HF_HOME=/home/user/.cache/huggingface \
    PYTHONUNBUFFERED=1

WORKDIR /home/user/app

# Install CPU-only PyTorch first (much smaller than the default GPU build)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user . .

# Download the 3 models during build so the server starts fast
RUN python -c "from transformers import pipeline; \
[pipeline('image-classification', model=m) for m in ['umm-maybe/AI-image-detector','Organika/sdxl-detector','dima806/ai_vs_real_image_detection']]"

# Hugging Face Spaces expects the app on port 7860
EXPOSE 7860
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:7860", "--workers", "1", "--threads", "2", "--timeout", "180"]
