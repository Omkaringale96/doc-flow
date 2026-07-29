#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Universal Document & Image Toolkit - Streamlit & Standalone Launcher
====================================================================
Serves the full glassmorphism Universal Document & Image Toolkit platform.
"""

import os
import sys
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_INDEX = os.path.join(BASE_DIR, "static", "index.html")

try:
    import streamlit as st
    import streamlit.components.v1 as components
    
    st.set_page_config(
        page_title="Universal Document & Image Toolkit",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    # Inject custom CSS to remove standard Streamlit margins and padding
    st.markdown("""
        <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .block-container {padding: 0rem !important; max-width: 100% !important;}
            iframe {border: none; width: 100vw; height: 100vh;}
        </style>
    """, unsafe_allow_html=True)

    # Read and render index.html directly inside Streamlit
    if os.path.exists(STATIC_INDEX):
        with open(STATIC_INDEX, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Inline styles and app.js for seamless single-file rendering inside iframe
        css_path = os.path.join(BASE_DIR, "static", "styles.css")
        js_path = os.path.join(BASE_DIR, "static", "app.js")
        
        if os.path.exists(css_path):
            with open(css_path, "r", encoding="utf-8") as f:
                css_data = f.read()
            html_content = html_content.replace('<link rel="stylesheet" href="/static/styles.css">', f'<style>{css_data}</style>')

        if os.path.exists(js_path):
            with open(js_path, "r", encoding="utf-8") as f:
                js_data = f.read()
            html_content = html_content.replace('<script src="/static/app.js"></script>', f'<script>{js_data}</script>')

        components.html(html_content, height=1000, scrolling=True)
    else:
        st.error("Static files missing. Please ensure static/index.html exists.")

except ImportError:
    # If run directly as python3 web_app.py
    print("Streamlit not detected, launching Tornado server...")
    subprocess.run([sys.executable, os.path.join(BASE_DIR, "server.py")])
