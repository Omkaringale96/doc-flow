# ==============================================================================
# DocFlow Pro - Production Dockerfile
# Optimized for Python 3.11, PyTorch (CPU), OpenCV Headless & EasyOCR Runtime
# ==============================================================================
FROM python:3.11-slim

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system C/C++ build tools and OpenCV/PyTorch image dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip and install PyTorch CPU version explicitly for fast, small build
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Copy requirements and install remaining packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download EasyOCR english model during build phase to accelerate cold startup
RUN python -c "import easyocr; easyocr.Reader(['en'], gpu=False)"

# Copy application codebase
COPY . .

# Create required output and upload directories
RUN mkdir -p uploads outputs

# Expose default HTTP Port 8501
EXPOSE 8501

ENV PORT=8501

# Launch Tornado Application Server Daemon
CMD ["python", "server.py", "8501"]
