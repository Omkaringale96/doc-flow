# Streamlit App Deployment Guide

## Overview
This repository contains a Streamlit app (`web_app.py`) that provides a modern login portal.

## Deployment Platform
We have chosen **Streamlit Cloud (share.streamlit.io)** as the deployment platform because it offers one‑click deployment from a GitHub repository and automatically rebuilds the app on each commit.

## Prerequisites
- A GitHub (or GitLab) account.
- Git installed locally.
- The `requirements.txt` file (added by the assistant) that lists the necessary Python packages.

## Step‑by‑Step Deployment
1. **Initialize a Git repository (if not already)**
   ```bash
   cd /Users/omkarganeshingale/Documents/antigravity/brave-planck
   git init
   git add .
   git commit -m "Initial commit – Streamlit login portal"
   ```
2. **Create a remote repository** on GitHub and push the code:
   ```bash
   git remote add origin https://github.com/<YOUR_USERNAME>/<REPO_NAME>.git
   git branch -M main
   git push -u origin main
   ```
   Replace `<YOUR_USERNAME>` and `<REPO_NAME>` with your own values.
3. **Sign in to Streamlit Cloud** at https://share.streamlit.io.
4. **Create a new app** and connect it to the GitHub repository you just pushed.
   - Choose the branch (e.g., `main`).
   - Specify the entry point file: `web_app.py`.
   - Streamlit Cloud will detect `requirements.txt` and install dependencies automatically.
5. **Deploy** – click *Deploy*. After a short build, your app will be available at a URL like `https://your‑app‑name‑xxxxx.streamlit.app`.

## Updating the App After Deployment
- Make any code changes locally.
- Commit and push the changes to the same GitHub repository.
- Streamlit Cloud detects the new commit, rebuilds, and the live app updates automatically.

## Optional: Adding Secrets
If your app needs secret keys (e.g., API tokens), you can add them in the Streamlit Cloud dashboard under **Secrets**. The app can read them via `st.secrets`.

---

**That’s it!** Your Streamlit login portal is now live and can be updated simply by pushing new commits.
