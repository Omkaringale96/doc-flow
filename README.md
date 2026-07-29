# DocFlow Pro - 24/7 Cloud Deployment Guide

This repository contains the complete DocFlow Pro web application engine with Docker runtime support for 24/7 continuous cloud hosting.

---

## 🚀 24/7 Deployment Instructions (Render.com)

### 1. Push Code to GitHub
```bash
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/docflow-pro.git
git push -u origin master
```

### 2. Deploy on Render.com
1. Go to [https://render.com](https://render.com) and log in with GitHub.
2. Click **New +** -> **Web Service**.
3. Connect your `docflow-pro` repository.
4. Render will automatically detect the `Dockerfile` and `render.yaml` configuration.
5. Click **Deploy Web Service**.

Your website will be live 24/7 at `https://docflow-pro.onrender.com`.

---

## 🛠 Local Development & Testing

### Run Server Locally:
```bash
python server.py 8501
```
Access at [http://localhost:8501](http://localhost:8501)
