# ==============================================================================
# DocFlow Pro - Production Dockerfile for Render
# Python 3.11 + OpenCV + EasyOCR + PyTorch (CPU)
# ==============================================================================

FROM python:3.11-slim

# Environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PORT=8501

# Install system dependencies required by OpenCV & EasyOCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Upgrade pip
RUN pip install --upgrade pip

# Install PyTorch CPU first
RUN pip install --no-cache-dir \
    torch \
    torchvision \
    --index-url https://download.pytorch.org/whl/cpu

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create runtime folders
RUN mkdir -p uploads outputs

# (Optional) Pre-download EasyOCR model during build
RUN python -c "import easyocr; easyocr.Reader(['en'], gpu=False)"

# Expose application port
EXPOSE 8501

# Start the application
CMD ["python", "server.py"]