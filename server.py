#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DocFlow Pro - Production Web Server Engine with Member Authorization
====================================================================
Features:
1. Member Authentication & Admin Authorization Engine (Default users: Datta / 555, Vinayak / 000).
2. Multi-Section Workflows (Support for New Proprietory Firm Drug License).
3. Robust Multi-Source PDF & Image Processing Engine.
4. Resilient API handlers returning strictly JSON (no HTML error pages).
5. Step-by-step progress logging with explicit stdout flushing.
6. Fault-tolerant image/PDF processing with memory garbage collection.
7. Non-blocking Cloudinary & Firestore logging integrations.
"""

import os
import sys
import gc
import re
import json
import uuid
import base64
import shutil
import zipfile
import traceback
from datetime import datetime
import io
import csv
from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageOps, ExifTags
import requests
import pypdf
import fitz
import tornado.ioloop
import tornado.web

# Disable SSL warnings for MSPC portal
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Safe imports for external services
try:
    from firebase_config import db
except Exception as e:
    print(f"⚠️ Firebase import note: {e}", flush=True)
    db = None

try:
    import cloudinary
    import cloudinary.uploader
    import cloudinary.api
    import cloudinary_config
except Exception as e:
    print(f"⚠️ Cloudinary import note: {e}", flush=True)

# Directory Setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
LOG_FILE = os.path.join(BASE_DIR, "submissions_log.json")
USERS_FILE = os.path.join(BASE_DIR, "users_db.json")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ----------------------------------------------------------------------
# Authorized Users Database & Management
# ----------------------------------------------------------------------
DEFAULT_USERS = {
    "Datta": "555",
    "Vinayak": "000"
}

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data:
                    updated = False
                    for k, v in DEFAULT_USERS.items():
                        if k not in data:
                            data[k] = v
                            updated = True
                    if updated:
                        save_users(data)
                    return data
        except Exception as e:
            print(f"⚠️ Users file read error: {e}", flush=True)
    save_users(DEFAULT_USERS)
    return DEFAULT_USERS

def save_users(users_dict):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users_dict, f, indent=2)
    except Exception as e:
        print(f"⚠️ Users file write error: {e}", flush=True)

USERS_DB = load_users()
ACTIVE_SESSIONS = {}  # token -> {username, created_at}

# EasyOCR setup (Lazy loaded)
EASY_OCR_READER = None

def get_ocr_reader():
    global EASY_OCR_READER
    if EASY_OCR_READER is None:
        try:
            import easyocr
            print("⏳ Initializing EasyOCR Reader...", flush=True)
            EASY_OCR_READER = easyocr.Reader(['en'], gpu=False)
            print("✅ EasyOCR Reader ready.", flush=True)
        except Exception as e:
            print("⚠️ OCR Reader Initialization Note:", e, flush=True)
            EASY_OCR_READER = False
    return EASY_OCR_READER

# ----------------------------------------------------------------------
# Workflow Registry Definition
# ----------------------------------------------------------------------
WORKFLOWS = {
    "ppp_renewal": {
        "id": "ppp_renewal",
        "title": "PPP Card Renewal (MSPC Portal Compliant)",
        "category": "Government & Healthcare",
        "icon": "fa-id-card",
        "description": "Automated document preparation, Auto-OCR document data extraction & MSPC Portal Login Logger.",
        "documents": [
            {
                "id": "old_ppp_card",
                "label": "Old PPP Card",
                "type": "pdf",
                "output_name": "Old_PPP_Card.pdf",
                "max_kb": 100,
                "hint": "Upright PDF document under 100 KB (0° Default)"
            },
            {
                "id": "reg_cert",
                "label": "Registration Certificate",
                "type": "pdf",
                "multi_side": True,
                "output_name": "Registration_Certificate.pdf",
                "max_kb": 100,
                "hint": "Upload Front & Back side. Combined 2-Page PDF under 100 KB"
            },
            {
                "id": "aadhaar",
                "label": "Aadhaar Card",
                "type": "pdf",
                "multi_side": True,
                "output_name": "Aadhaar.pdf",
                "max_kb": 100,
                "hint": "Upload Front & Back side. Combined 2-Page PDF under 100 KB"
            },
            {
                "id": "passport_photo",
                "label": "Passport Photo",
                "type": "image",
                "output_name": "Passport_Photo.jpg",
                "width": 160,
                "height": 160,
                "max_kb": 20,
                "hint": "Resized to exact 160x160 px, JPG under 20 KB"
            },
            {
                "id": "signature",
                "label": "Signature",
                "type": "image",
                "output_name": "Signature.jpg",
                "width": 160,
                "height": 40,
                "max_kb": 20,
                "hint": "Resized to exact 160x40 px, JPG under 20 KB"
            }
        ]
    },
    "new_proprietorship_drug_license": {
        "id": "new_proprietorship_drug_license",
        "title": "New Proprietory Firm Drug License",
        "category": "Pharmacy & Trade",
        "icon": "fa-store",
        "description": "Complete document preparation for New Proprietary Firm Drug License across Proprietor, Pharmacist, and Premises sections.",
        "sections": [
            {
                "id": "proprietor_docs",
                "title": "1. Proprietor Documents",
                "icon": "fa-user-tie",
                "documents": [
                    {
                        "id": "photo",
                        "label": "Photo",
                        "type": "image",
                        "output_name": "Photo.jpg",
                        "width": 160,
                        "height": 160,
                        "max_kb": 50,
                        "hint": "Accepted format: Image (JPG output under 50 KB)"
                    },
                    {
                        "id": "aadhaar_pan",
                        "label": "Aadhaar Card + PAN Card",
                        "type": "pdf",
                        "multi_sources": [
                            {"id": "aadhaar", "label": "Aadhaar Card", "hint": "Upload Aadhaar Card (Image or PDF)"},
                            {"id": "pan", "label": "PAN Card", "hint": "Upload PAN Card (Image or PDF)"}
                        ],
                        "output_name": "Aadhaar_PAN.pdf",
                        "max_kb": 125,
                        "hint": "Upload Aadhaar Card & PAN Card. Combined PDF under 125 KB"
                    },
                    {
                        "id": "qualification",
                        "label": "Qualification Certificate",
                        "type": "pdf",
                        "output_name": "Qualification.pdf",
                        "max_kb": 125,
                        "hint": "Accepted format: Image or PDF (PDF output under 125 KB)"
                    }
                ]
            },
            {
                "id": "pharmacist_docs",
                "title": "2. Pharmacist Documents",
                "icon": "fa-user-nurse",
                "documents": [
                    {
                        "id": "pharmacist_photo",
                        "label": "Pharmacist Photo",
                        "type": "image",
                        "output_name": "Pharmacist_Photo.jpg",
                        "width": 160,
                        "height": 160,
                        "max_kb": 50,
                        "hint": "Accepted format: Image (JPG output under 50 KB)"
                    },
                    {
                        "id": "registration_ppp",
                        "label": "Registration Certificate + PPP Card",
                        "type": "pdf",
                        "multi_sources": [
                            {"id": "reg_cert", "label": "Registration Certificate", "hint": "Upload Registration Certificate (Image or PDF)"},
                            {"id": "ppp_card", "label": "PPP Card", "hint": "Upload PPP Card (Image or PDF)"}
                        ],
                        "output_name": "Registration_PPP.pdf",
                        "max_kb": 125,
                        "hint": "Upload Registration Certificate & PPP Card. Combined PDF under 125 KB"
                    },
                    {
                        "id": "appointment_acceptance_selfdeclaration",
                        "label": "Appointment Letter + Acceptance Letter + Self Declaration",
                        "type": "pdf",
                        "multi_sources": [
                            {"id": "appointment", "label": "Appointment Letter", "hint": "Upload Appointment Letter (Image or PDF)"},
                            {"id": "acceptance", "label": "Acceptance Letter", "hint": "Upload Acceptance Letter (Image or PDF)"},
                            {"id": "self_declaration", "label": "Self Declaration", "hint": "Upload Self Declaration (Image or PDF)"}
                        ],
                        "output_name": "Appointment_Acceptance_SelfDeclaration.pdf",
                        "max_kb": 125,
                        "hint": "Upload Appointment, Acceptance & Self Declaration. Combined PDF under 125 KB"
                    },
                    {
                        "id": "address_proof",
                        "label": "Address Proof",
                        "type": "pdf",
                        "output_name": "Address_Proof.pdf",
                        "max_kb": 125,
                        "hint": "Accepted format: Image or PDF (PDF output under 125 KB)"
                    }
                ]
            },
            {
                "id": "premises_docs",
                "title": "3. Premises Documents",
                "icon": "fa-building",
                "documents": [
                    {
                        "id": "light_bill_cold_storage",
                        "label": "Light Bill + Cold Storage Certificate",
                        "type": "pdf",
                        "multi_sources": [
                            {"id": "light_bill", "label": "Light Bill", "hint": "Upload Light Bill (Image or PDF)"},
                            {"id": "cold_storage", "label": "Cold Storage Certificate", "hint": "Upload Cold Storage Certificate (Image or PDF)"}
                        ],
                        "output_name": "Light_Bill_Cold_Storage.pdf",
                        "max_kb": 125,
                        "hint": "Upload Light Bill & Cold Storage Certificate. Combined PDF under 125 KB"
                    },
                    {
                        "id": "tax_receipt_namuna8",
                        "label": "Tax Receipt + Namuna 8",
                        "type": "pdf",
                        "multi_sources": [
                            {"id": "tax_receipt", "label": "Tax Receipt", "hint": "Upload Tax Receipt (Image or PDF)"},
                            {"id": "namuna_8", "label": "Namuna 8", "hint": "Upload Namuna 8 (Image or PDF)"}
                        ],
                        "output_name": "Tax_Receipt_Namuna8.pdf",
                        "max_kb": 125,
                        "hint": "Upload Tax Receipt & Namuna 8. Combined PDF under 125 KB"
                    },
                    {
                        "id": "rent_agreement",
                        "label": "Rent Agreement (Part 1 + Part 2)",
                        "type": "pdf_only",
                        "multi_sources": [
                            {"id": "rent_part1", "label": "Rent Agreement – Part 1", "hint": "Upload Rent Agreement Part 1 (PDF only)"},
                            {"id": "rent_part2", "label": "Rent Agreement – Part 2", "hint": "Upload Rent Agreement Part 2 (PDF only - Optional)"}
                        ],
                        "output_name": "Rent_Agreement.pdf",
                        "max_kb": 125,
                        "hint": "Upload Part 1 and optional Part 2 (PDF files only). Merged PDF under 125 KB"
                    },
                    {
                        "id": "plan_layout",
                        "label": "Plan Layout",
                        "type": "pdf",
                        "output_name": "Plan_Layout.pdf",
                        "max_kb": 125,
                        "hint": "Accepted format: Image or PDF (PDF output under 125 KB)"
                    }
                ]
            }
        ]
    }
}

def get_workflow_documents(workflow):
    docs = []
    if "sections" in workflow:
        for sec in workflow["sections"]:
            for d in sec["documents"]:
                docs.append(d)
    elif "documents" in workflow:
        docs = workflow["documents"]
    return docs

# ----------------------------------------------------------------------
# MSPC Password & Login ID Helper Functions
# ----------------------------------------------------------------------
def generate_mspc_password(name: str, dob_str: str) -> str:
    name_clean = re.sub(r'^(DR|MR|MRS|SHRI|SMT|KUMAR|MS)[\.\s]+', '', str(name).strip(), flags=re.IGNORECASE).strip()
    clean_name = re.sub(r'[^A-Za-z]', '', name_clean).upper()
    prefix = clean_name[:3] if len(clean_name) >= 3 else (clean_name + "X" * (3 - len(clean_name)))

    day_str, month_str = "01", "01"
    match = re.search(r'(\d{1,2})[/\.\-](\d{1,2})[/\.\-](\d{2,4})', str(dob_str))
    if match:
        day_str = f"{int(match.group(1)):02d}"
        month_str = f"{int(match.group(2)):02d}"
    else:
        match_iso = re.search(r'(\d{4})[/\.\-](\d{1,2})[/\.\-](\d{1,2})', str(dob_str))
        if match_iso:
            month_str = f"{int(match_iso.group(2)):02d}"
            day_str = f"{int(match_iso.group(3)):02d}"

    return f"{prefix}{day_str}{month_str}"

# --------------------------------------------------------
# Logging & External Upload Functions
# --------------------------------------------------------
def log_submission(entry):
    if db is not None:
        try:
            db.collection("submissions").add({
                **entry,
                "created_at": datetime.utcnow()
            })
            print("✅ [FIRESTORE] Saved submission entry successfully.", flush=True)
        except Exception as e:
            print(f"⚠️ [FIRESTORE ERROR] Could not save submission: {e}", flush=True)
    else:
        print("ℹ️ [FIRESTORE] Disabled or unconfigured, skipping remote DB log.", flush=True)

    try:
        submissions = []
        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    submissions = json.load(f)
            except Exception:
                submissions = []

        submissions.append(entry)
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(submissions, f, indent=2)
        print("✅ [LOCAL LOG] Saved submission locally.", flush=True)
    except Exception as e:
        print(f"⚠️ [LOCAL LOG ERROR] Could not write to {LOG_FILE}: {e}", flush=True)


def upload_to_cloudinary(file_path, folder="DocFlow"):
    if not file_path or not os.path.exists(file_path):
        print(f"⚠️ [CLOUDINARY] Target file {file_path} does not exist, skipping upload.", flush=True)
        return None

    try:
        import cloudinary
        import cloudinary.uploader
    except Exception as err:
        print(f"ℹ️ [CLOUDINARY NOTE] Cloudinary module not imported: {err}", flush=True)
        return None

    try:
        config = cloudinary.config()
        if not getattr(config, "api_key", None) or not getattr(config, "cloud_name", None):
            print("ℹ️ [CLOUDINARY] Credentials not configured. Skipping Cloudinary upload.", flush=True)
            return None

        print(f"⏳ [CLOUDINARY] Uploading {file_path} to folder '{folder}'...", flush=True)
        result = cloudinary.uploader.upload(
            file_path,
            resource_type="auto",
            folder=folder
        )
        url = result.get("secure_url")
        print(f"☁ [CLOUDINARY SUCCESS] Uploaded: {url}", flush=True)
        return url
    except Exception as e:
        print(f"⚠️ [CLOUDINARY NOTE] Upload skipped: {e}", flush=True)
        return None

# ----------------------------------------------------------------------
# Image Deblur & Transformation Utilities
# ----------------------------------------------------------------------
def unblur_and_sharpen_image(cv_bgr_img: np.ndarray) -> np.ndarray:
    gaussian = cv2.GaussianBlur(cv_bgr_img, (0, 0), 2.5)
    deblurred = cv2.addWeighted(cv_bgr_img, 1.45, gaussian, -0.45, 0)
    return deblurred


def apply_transformations(cv_img, angle=0, flip_h=False, flip_v=False, free_angle=0.0):
    img = cv_img.copy()

    if flip_h and flip_v:
        img = cv2.flip(img, -1)
    elif flip_h:
        img = cv2.flip(img, 1)
    elif flip_v:
        img = cv2.flip(img, 0)

    if angle == 90:
        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    elif angle == 180:
        img = cv2.rotate(img, cv2.ROTATE_180)
    elif angle == 270:
        img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)

    if abs(free_angle) > 0.1:
        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, free_angle, 1.0)
        img = cv2.warpAffine(img, M, (w, h), borderValue=(255, 255, 255))

    return img


def process_raw_image(cv_bgr_img: np.ndarray, angle: int = 0, flip_h: bool = False, flip_v: bool = False, free_angle: float = 0.0, do_deblur: bool = True) -> np.ndarray:
    if do_deblur:
        cv_bgr_img = unblur_and_sharpen_image(cv_bgr_img)
    transformed = apply_transformations(cv_bgr_img, angle=angle, flip_h=flip_h, flip_v=flip_v, free_angle=free_angle)
    return transformed


def process_signature_image(input_path, output_path, target_w=160, target_h=40, max_kb=20, manual_rotation=0, flip_h=False, flip_v=False, free_angle=0.0):
    if not os.path.exists(input_path) or os.path.getsize(input_path) == 0:
        print(f"⚠️ Signature image path invalid: {input_path}, generating white fallback.", flush=True)
        canvas = Image.new("RGB", (target_w, target_h), color=(255, 255, 255))
        canvas.save(output_path, "JPEG", quality=90)
        return os.path.getsize(output_path) / 1024.0

    pil_img = Image.open(input_path).convert("RGB")
    try:
        pil_img = ImageOps.exif_transpose(pil_img)
    except Exception:
        pass

    cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    cv_img = process_raw_image(cv_img, angle=manual_rotation, flip_h=flip_h, flip_v=flip_v, free_angle=free_angle)

    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25))
    bg = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
    norm = cv2.divide(gray, bg, scale=255)

    _, thresh = cv2.threshold(norm, 220, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    h_img, w_img = cv_img.shape[:2]
    x_min, y_min, x_max, y_max = w_img, h_img, 0, 0
    found_ink = False

    for c in contours:
        if cv2.contourArea(c) > 12:
            x, y, w_c, h_c = cv2.boundingRect(c)
            x_min = min(x_min, x)
            y_min = min(y_min, y)
            x_max = max(x_max, x + w_c)
            y_max = max(y_max, y + h_c)
            found_ink = True

    if found_ink and (x_max > x_min) and (y_max > y_min):
        pad = 12
        x_min = max(0, x_min - pad)
        y_min = max(0, y_min - pad)
        x_max = min(w_img, x_max + pad)
        y_max = min(h_img, y_max + pad)
        cropped_bgr = cv_img[y_min:y_max, x_min:x_max]
        cropped_norm = norm[y_min:y_max, x_min:x_max]
    else:
        cropped_bgr = cv_img
        cropped_norm = norm

    mask_bg = cropped_norm > 210
    enhanced = cv2.convertScaleAbs(cropped_bgr, alpha=1.25, beta=10)
    enhanced[mask_bg] = [255, 255, 255]

    sig_pil = Image.fromarray(cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB))
    sig_w, sig_h = sig_pil.size

    canvas = Image.new("RGB", (target_w, target_h), color=(255, 255, 255))
    scale = min((target_w - 8) / sig_w, (target_h - 6) / sig_h)
    new_w = max(1, int(sig_w * scale))
    new_h = max(1, int(sig_h * scale))

    resized_sig = sig_pil.resize((new_w, new_h), Image.Resampling.LANCZOS)
    offset_x = (target_w - new_w) // 2
    offset_y = (target_h - new_h) // 2
    canvas.paste(resized_sig, (offset_x, offset_y))

    quality = 92
    while True:
        canvas.save(output_path, "JPEG", quality=quality, optimize=True)
        size_kb = os.path.getsize(output_path) / 1024.0
        if size_kb <= max_kb or quality <= 10:
            break
        quality -= 10

    del cv_img, gray, bg, norm, thresh, sig_pil, resized_sig, canvas
    gc.collect()

    return os.path.getsize(output_path) / 1024.0


def sharpen_document_image(pil_img):
    """
    Applies unsharp mask text sharpening to keep document text, stamps, and signatures crystal clear.
    """
    try:
        img_np = np.array(pil_img)
        bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        gaussian = cv2.GaussianBlur(bgr, (0, 0), 2.0)
        sharpened_bgr = cv2.addWeighted(bgr, 1.4, gaussian, -0.4, 0)
        rgb = cv2.cvtColor(sharpened_bgr, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)
    except Exception:
        return pil_img


def process_pdf_document(input_paths, output_path, max_kb=125, manual_rotations=None, flips_h=None, flips_v=None, free_angles=None):
    if manual_rotations is None: manual_rotations = []
    if flips_h is None: flips_h = []
    if flips_v is None: flips_v = []
    if free_angles is None: free_angles = []

    valid_paths = [p for p in input_paths if os.path.exists(p) and os.path.getsize(p) > 0]
    if not valid_paths:
        blank = Image.new("RGB", (600, 800), color=(255, 255, 255))
        blank.save(output_path, "PDF")
        return os.path.getsize(output_path) / 1024.0, 1

    # 1. Direct PyMuPDF Native Stream Merge & Compression (100% Vector/Text Original Quality)
    all_pdfs = all(p.lower().endswith('.pdf') for p in valid_paths)
    no_transforms = not any(manual_rotations) and not any(flips_h) and not any(flips_v) and not any(free_angles)

    if all_pdfs and no_transforms:
        try:
            merged_doc = fitz.open()
            total_pgs = 0
            for p in valid_paths:
                d = fitz.open(p)
                merged_doc.insert_pdf(d)
                total_pgs += len(d)
                d.close()
            
            merged_doc.save(output_path, garbage=4, deflate=True, clean=True)
            merged_doc.close()

            size_kb = os.path.getsize(output_path) / 1024.0
            print(f"⚡ Direct PyMuPDF Crisp Merge Result: {size_kb:.1f} KB (max: {max_kb} KB)", flush=True)

            if size_kb <= max_kb:
                return size_kb, total_pgs
        except Exception as e:
            print(f"⚠️ Direct PDF merge warning: {e}", flush=True)

    # 2. HD 300-DPI Page Extraction with Edge Sharpening Fallback
    images = []
    for idx, path in enumerate(valid_paths):
        try:
            if path.lower().endswith('.pdf'):
                doc = fitz.open(path)
                for page in doc:
                    # 300 DPI for crystal-clear text & signature rendering
                    pix = page.get_pixmap(dpi=300)
                    pil_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    sharp_img = sharpen_document_image(pil_img)
                    images.append(sharp_img)
                doc.close()
            else:
                pil = Image.open(path).convert("RGB")
                try:
                    pil = ImageOps.exif_transpose(pil)
                except Exception:
                    pass

                cv_img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
                
                m_rot = manual_rotations[idx] if idx < len(manual_rotations) else 0
                f_h = flips_h[idx] if idx < len(flips_h) else False
                f_v = flips_v[idx] if idx < len(flips_v) else False
                f_ang = free_angles[idx] if idx < len(free_angles) else 0.0

                processed_bgr = process_raw_image(cv_img, angle=m_rot, flip_h=f_h, flip_v=f_v, free_angle=f_ang)
                processed_rgb = cv2.cvtColor(processed_bgr, cv2.COLOR_BGR2RGB)
                processed_pil = Image.fromarray(processed_rgb)

                clean_pil = Image.new(processed_pil.mode, processed_pil.size)
                clean_pil.paste(processed_pil)
                sharp_img = sharpen_document_image(clean_pil)
                images.append(sharp_img)

                del cv_img, processed_bgr, processed_rgb, processed_pil
        except Exception as err:
            print(f"⚠️ Error processing file {path}: {err}", flush=True)

    if not images:
        blank = Image.new("RGB", (600, 800), color=(255, 255, 255))
        images = [blank]

    quality = 92
    scale_factor = 1.0
    a4_rect = fitz.Rect(0, 0, 595.28, 841.89)

    while True:
        out_doc = fitz.open()
        for img in images:
            w_dim, h_dim = int(img.width * scale_factor), int(img.height * scale_factor)
            resized = img.resize((max(1, w_dim), max(1, h_dim)), Image.Resampling.LANCZOS)

            buf = BytesIO()
            resized.save(buf, format="JPEG", quality=quality)
            img_bytes = buf.getvalue()

            page = out_doc.new_page(width=595.28, height=841.89)
            page.insert_image(a4_rect, stream=img_bytes)

        out_doc.save(output_path, garbage=4, deflate=True, clean=True)
        out_doc.close()

        size_kb = os.path.getsize(output_path) / 1024.0
        if size_kb <= max_kb or (quality <= 30 and scale_factor <= 0.45):
            break

        if quality > 45:
            quality -= 10
        else:
            scale_factor *= 0.88

    del images
    gc.collect()

    return os.path.getsize(output_path) / 1024.0, len(valid_paths)


def process_image_document(input_path, output_path, target_w, target_h, max_kb=20, manual_rotation=0, flip_h=False, flip_v=False, free_angle=0.0):
    if not os.path.exists(input_path) or os.path.getsize(input_path) == 0:
        print(f"⚠️ Image document path invalid: {input_path}, substituting blank image.", flush=True)
        blank = Image.new("RGB", (target_w, target_h), color=(255, 255, 255))
        blank.save(output_path, "JPEG", quality=90)
        return os.path.getsize(output_path) / 1024.0

    pil_img = Image.open(input_path).convert("RGB")
    try:
        pil_img = ImageOps.exif_transpose(pil_img)
    except Exception:
        pass
    
    cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    processed_bgr = process_raw_image(cv_img, angle=manual_rotation, flip_h=flip_h, flip_v=flip_v, free_angle=free_angle)
    pil_img = Image.fromarray(cv2.cvtColor(processed_bgr, cv2.COLOR_BGR2RGB))

    src_w, src_h = pil_img.size
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        left = (src_w - new_w) // 2
        pil_img = pil_img.crop((left, 0, left + new_w, src_h))
    else:
        new_h = int(src_w / target_ratio)
        top = (src_h - new_h) // 2
        pil_img = pil_img.crop((0, top, src_w, top + new_h))

    resized = pil_img.resize((target_w, target_h), Image.Resampling.LANCZOS)

    quality = 90
    while True:
        resized.save(output_path, "JPEG", quality=quality, optimize=True)
        size_kb = os.path.getsize(output_path) / 1024.0
        if size_kb <= max_kb or quality <= 10:
            break
        quality -= 10

    del cv_img, processed_bgr, pil_img, resized
    gc.collect()

    return os.path.getsize(output_path) / 1024.0


# ----------------------------------------------------------------------
# Base HTTP Request Handler (Strict JSON Error Response Guard)
# ----------------------------------------------------------------------
class BaseHandler(tornado.web.RequestHandler):
    def write_error(self, status_code, **kwargs):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        exc_info = kwargs.get("exc_info")
        error_msg = "An unexpected server error occurred."
        tb_str = ""

        if exc_info:
            error_msg = str(exc_info[1])
            tb_str = "".join(traceback.format_exception(*exc_info))

        print(f"❌ [HTTP ERROR {status_code}] {error_msg}\n{tb_str}", flush=True)

        self.finish(json.dumps({
            "status": "error",
            "message": error_msg,
            "traceback": tb_str
        }))

    def get_current_user_name(self):
        auth_header = self.request.headers.get("Authorization", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif self.get_argument("token", default=""):
            token = self.get_argument("token")

        if token in ACTIVE_SESSIONS:
            return ACTIVE_SESSIONS[token]["username"]
        return None

# ----------------------------------------------------------------------
# Member Authorization & Login API Handlers
# ----------------------------------------------------------------------
class ApiLoginHandler(BaseHandler):
    async def post(self):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        try:
            body = json.loads(self.request.body.decode('utf-8')) if self.request.body else {}
            username = body.get("username", self.get_argument("username", default="")).strip()
            password = body.get("password", self.get_argument("password", default="")).strip()

            if not username or not password:
                self.set_status(400)
                self.write({"status": "error", "message": "Username and Password are required."})
                return

            users_db = load_users()
            
            # Case-insensitive username matching
            matched_user = None
            for u_name, u_pass in users_db.items():
                if u_name.lower() == username.lower() and u_pass == password:
                    matched_user = u_name
                    break

            if matched_user:
                token = uuid.uuid4().hex
                ACTIVE_SESSIONS[token] = {
                    "username": matched_user,
                    "created_at": datetime.now().isoformat()
                }
                print(f"✅ User '{matched_user}' logged in successfully. Token: {token}", flush=True)
                self.write({
                    "status": "success",
                    "message": f"Welcome back, {matched_user}!",
                    "token": token,
                    "username": matched_user
                })
            else:
                self.set_status(401)
                self.write({
                    "status": "error",
                    "message": "Invalid Authorized Username or Password!"
                })
        except Exception as e:
            traceback.print_exc()
            self.set_status(500)
            self.write({"status": "error", "message": str(e)})


class ApiAddUserHandler(BaseHandler):
    async def post(self):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        try:
            current_user = self.get_current_user_name()
            if current_user != "Datta":
                self.set_status(403)
                self.write({
                    "status": "error",
                    "message": "Unauthorized! Only Administrator Datta can add new members."
                })
                return

            body = json.loads(self.request.body.decode('utf-8')) if self.request.body else {}
            new_username = body.get("username", self.get_argument("username", default="")).strip()
            new_password = body.get("password", self.get_argument("password", default="")).strip()

            if not new_username or not new_password:
                self.set_status(400)
                self.write({"status": "error", "message": "New username and password required."})
                return

            users_db = load_users()
            if new_username in users_db:
                self.set_status(400)
                self.write({"status": "error", "message": f"Authorized member '{new_username}' already exists!"})
                return

            users_db[new_username] = new_password
            save_users(users_db)

            print(f"🔑 Administrator Datta created new member '{new_username}'", flush=True)
            self.write({
                "status": "success",
                "message": f"Authorized member '{new_username}' added successfully!",
                "members_count": len(users_db)
            })

        except Exception as e:
            traceback.print_exc()
            self.set_status(500)
            self.write({"status": "error", "message": str(e)})


class ApiRemoveUserHandler(BaseHandler):
    async def post(self):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        try:
            current_user = self.get_current_user_name()
            if current_user != "Datta":
                self.set_status(403)
                self.write({
                    "status": "error",
                    "message": "Unauthorized! Only Administrator Datta can remove members."
                })
                return

            body = json.loads(self.request.body.decode('utf-8')) if self.request.body else {}
            target_username = body.get("username", self.get_argument("username", default="")).strip()

            if not target_username:
                self.set_status(400)
                self.write({"status": "error", "message": "Username to remove is required."})
                return

            if target_username == "Datta":
                self.set_status(400)
                self.write({"status": "error", "message": "Cannot remove primary Administrator Datta!"})
                return

            users_db = load_users()
            if target_username not in users_db:
                self.set_status(404)
                self.write({"status": "error", "message": f"Member '{target_username}' not found."})
                return

            del users_db[target_username]
            save_users(users_db)

            print(f"🔑 Administrator Datta removed member '{target_username}'", flush=True)
            self.write({
                "status": "success",
                "message": f"Member '{target_username}' removed successfully!",
                "members_count": len(users_db)
            })

        except Exception as e:
            traceback.print_exc()
            self.set_status(500)
            self.write({"status": "error", "message": str(e)})


class ApiCheckAuthHandler(BaseHandler):
    async def get(self):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        user = self.get_current_user_name()
        if user:
            self.write({"status": "success", "authenticated": True, "username": user})
        else:
            self.write({"status": "success", "authenticated": False})


class MainHandler(BaseHandler):
    def get(self):
        self.render(os.path.join(STATIC_DIR, "index.html"))


class ApiWorkflowsHandler(BaseHandler):
    def get(self):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        user = self.get_current_user_name()
        available_workflows = list(WORKFLOWS.values())
        if user == "Datta":
            available_workflows = [w for w in available_workflows if w["id"] != "ppp_renewal"]

        self.write({
            "status": "success",
            "workflows": available_workflows
        })


class ApiExtractDocumentDataHandler(BaseHandler):
    async def post(self):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        try:
            files = self.request.files.get("file", [])
            if not files:
                self.set_status(400)
                self.write({"status": "error", "message": "No file uploaded for OCR extraction"})
                return

            file_bytes = files[0]['body']
            pil = Image.open(BytesIO(file_bytes)).convert("RGB")
            try:
                pil = ImageOps.exif_transpose(pil)
            except Exception:
                pass

            cv_img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

            full_text = ""
            reader = get_ocr_reader()
            if reader:
                try:
                    results = reader.readtext(cv_img, detail=0)
                    full_text = " ".join(results)
                except Exception as e:
                    print("⚠️ EasyOCR read error:", e, flush=True)

            reg_match = re.search(r'\b(REG\.?\s*NO\.?|NUMBER|NUM|NO)?[\s\:\-]*(\d{5,6})\b', full_text, re.IGNORECASE)
            reg_number = reg_match.group(2) if reg_match else ""

            dob_match = re.search(r'\b(\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{2,4})\b', full_text)
            dob = dob_match.group(1).replace('-', '/').replace('.', '/') if dob_match else ""

            mobile_match = re.search(r'\b([6-9]\d{9})\b', full_text)
            mobile = mobile_match.group(1) if mobile_match else ""

            email_match = re.search(r'\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b', full_text)
            email = email_match.group(1) if email_match else ""

            name_match = re.search(r'\b(SHRI|SMT|KUMAR|PATIL|RAMESH|VINAYAK|SHANKAR|RAMPATI|SINGH)[A-Z\s]{4,35}\b', full_text, re.IGNORECASE)
            extracted_name = name_match.group(0).strip().upper() if name_match else ""

            mspc_pass = generate_mspc_password(extracted_name, dob) if (extracted_name and dob) else ""

            del cv_img, pil
            gc.collect()

            self.write({
                "status": "success",
                "extracted": {
                    "name": extracted_name,
                    "reg_number": reg_number,
                    "dob": dob,
                    "mobile": mobile,
                    "email": email,
                    "login_id": f"MSPC{reg_number}" if reg_number else "",
                    "calculated_password": mspc_pass
                },
                "ocr_text": full_text[:200]
            })

        except Exception as e:
            traceback.print_exc()
            self.write({
                "status": "success",
                "extracted": {
                    "name": "",
                    "reg_number": "",
                    "dob": "",
                    "mobile": "",
                    "email": "",
                    "login_id": "",
                    "calculated_password": ""
                }
            })


class ApiPreviewRotationHandler(BaseHandler):
    async def post(self):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        try:
            files = self.request.files.get("file", [])
            if not files:
                self.set_status(400)
                self.write({"status": "error", "message": "No file uploaded"})
                return

            file_body = files[0]['body']
            pil = Image.open(BytesIO(file_body)).convert("RGB")
            try:
                pil = ImageOps.exif_transpose(pil)
            except Exception:
                pass

            cv_img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
            cv_deblurred = unblur_and_sharpen_image(cv_img)

            carousel = {}
            for ang in [0, 90, 180, 270]:
                rot_img = apply_transformations(cv_deblurred, angle=ang)
                rot_rgb = cv2.cvtColor(rot_img, cv2.COLOR_BGR2RGB)
                
                pil_thumb = Image.fromarray(rot_rgb)
                pil_thumb.thumbnail((320, 320), Image.Resampling.LANCZOS)
                
                buf = BytesIO()
                pil_thumb.save(buf, format="JPEG", quality=85)
                b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                carousel[str(ang)] = f"data:image/jpeg;base64,{b64}"

            raw_thumb = Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))
            raw_thumb.thumbnail((600, 600), Image.Resampling.LANCZOS)
            raw_buf = BytesIO()
            raw_thumb.save(raw_buf, format="JPEG", quality=85)
            raw_b64 = f"data:image/jpeg;base64,{base64.b64encode(raw_buf.getvalue()).decode('utf-8')}"

            del cv_img, cv_deblurred
            gc.collect()

            self.write({
                "status": "success",
                "default_angle": 0,
                "raw_image": raw_b64,
                "carousel": carousel
            })

        except Exception as e:
            traceback.print_exc()
            self.set_status(500)
            self.write({"status": "error", "message": str(e), "traceback": traceback.format_exc()})


class ApiLiveRenderHandler(BaseHandler):
    async def post(self):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        try:
            files = self.request.files.get("file", [])
            if not files:
                self.set_status(400)
                self.write({"status": "error", "message": "No file uploaded"})
                return

            angle = int(self.get_body_argument("angle", default="0"))
            flip_h = self.get_body_argument("flip_h", default="false").lower() == "true"
            flip_v = self.get_body_argument("flip_v", default="false").lower() == "true"
            free_angle = float(self.get_body_argument("free_angle", default="0.0"))
            do_deblur = self.get_body_argument("deblur", default="true").lower() == "true"

            file_body = files[0]['body']
            pil = Image.open(BytesIO(file_body)).convert("RGB")
            try:
                pil = ImageOps.exif_transpose(pil)
            except Exception:
                pass

            cv_img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
            processed = process_raw_image(cv_img, angle=angle, flip_h=flip_h, flip_v=flip_v, free_angle=free_angle, do_deblur=do_deblur)

            processed_rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
            pil_prev = Image.fromarray(processed_rgb)
            pil_prev.thumbnail((600, 600), Image.Resampling.LANCZOS)

            buf = BytesIO()
            pil_prev.save(buf, format="JPEG", quality=85)
            b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

            del cv_img, processed, processed_rgb, pil_prev
            gc.collect()

            self.write({
                "status": "success",
                "preview": f"data:image/jpeg;base64,{b64}"
            })
        except Exception as e:
            traceback.print_exc()
            self.set_status(500)
            self.write({"status": "error", "message": str(e), "traceback": traceback.format_exc()})


class ApiProcessWorkflowHandler(BaseHandler):
    async def post(self):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        try:
            print("==================================================", flush=True)
            print("🚀 [STEP 1] Starting /api/process_workflow request...", flush=True)

            workflow_id = self.get_body_argument("workflow_id", default="ppp_renewal")
            
            user = self.get_current_user_name()
            if user == "Datta" and workflow_id == "ppp_renewal":
                self.set_status(403)
                self.write({
                    "status": "error",
                    "message": "Access Denied! User 'Datta' does not have access to the PP Renewal workflow."
                })
                return

            workflow = WORKFLOWS.get(workflow_id, WORKFLOWS["ppp_renewal"])
            all_documents = get_workflow_documents(workflow)
            
            applicant_name = self.get_body_argument("applicant_name", default="Applicant").strip()
            email = self.get_body_argument("email", default="Not Provided").strip()
            mobile = self.get_body_argument("mobile", default="Not Provided").strip()
            reg_number = self.get_body_argument("reg_number", default="000000").strip()
            login_id = self.get_body_argument("login_id", default="").strip()
            dob = self.get_body_argument("dob", default="01/01/2000").strip()
            folder_name = self.get_body_argument("folder_name", default=f"{applicant_name}_Package").strip()

            print(f"📋 [STEP 1 OK] Parameters: workflow={workflow_id}, applicant='{applicant_name}', reg='{reg_number}', dob='{dob}'", flush=True)

            if not login_id:
                login_id = f"MSPC{reg_number}"

            folder_name = "".join([c if c.isalnum() or c in ['_', '-'] else '_' for c in folder_name])
            if not folder_name:
                folder_name = "DocFlow_Package"

            job_id = uuid.uuid4().hex[:8]
            job_output_dir = os.path.join(OUTPUT_DIR, job_id, folder_name)

            os.makedirs(job_output_dir, exist_ok=True)
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            print(f"📁 [STEP 2] Job Output Directory Created: {job_output_dir}", flush=True)

            processed_files_summary = []

            print(f"📄 [STEP 3] Starting document processing for {len(all_documents)} items...", flush=True)

            for idx_doc, doc_cfg in enumerate(all_documents, start=1):
                doc_id = doc_cfg["id"]
                target_filename = doc_cfg["output_name"]
                target_path = os.path.join(job_output_dir, target_filename)

                print(f"   ➜ [STEP 3.{idx_doc}] Processing document '{doc_id}' -> '{target_filename}'", flush=True)

                if doc_cfg.get("multi_sources"):
                    # Merging multiple separate uploaded files into one PDF
                    uploaded_paths = []
                    manual_rots = []
                    flips_h = []
                    flips_v = []

                    for src in doc_cfg["multi_sources"]:
                        src_id = src["id"]
                        files = self.request.files.get(src_id, [])
                        rot = int(self.get_body_argument(f"rot_{src_id}", default="0"))
                        fliph = self.get_body_argument(f"fliph_{src_id}", default="false").lower() == "true"
                        flipv = self.get_body_argument(f"flipv_{src_id}", default="false").lower() == "true"

                        for f in files:
                            tmp_p = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}_{f['filename']}")
                            with open(tmp_p, "wb") as out_f:
                                out_f.write(f['body'])
                            if os.path.exists(tmp_p) and os.path.getsize(tmp_p) > 0:
                                uploaded_paths.append(tmp_p)
                                manual_rots.append(rot)
                                flips_h.append(fliph)
                                flips_v.append(flipv)

                    if not uploaded_paths:
                        print(f"   ⏩ [SKIPPED] No files uploaded for '{doc_id}'", flush=True)
                        continue

                    merged_kb, page_count = process_pdf_document(
                        uploaded_paths,
                        target_path,
                        max_kb=doc_cfg.get("max_kb", 125),
                        manual_rotations=manual_rots,
                        flips_h=flips_h,
                        flips_v=flips_v
                    )

                    download_url = f"/outputs/{job_id}/{folder_name}/{target_filename}"
                    processed_files_summary.append({
                        "filename": target_filename,
                        "label": doc_cfg["label"],
                        "size_kb": round(merged_kb, 1),
                        "status": f"✓ Combined PDF ({page_count} pg) | {merged_kb:.1f} KB (<{doc_cfg['max_kb']} KB)",
                        "download_url": download_url
                    })

                elif doc_cfg.get("multi_side"):
                    files_front = self.request.files.get(f"{doc_id}_front", [])
                    files_back = self.request.files.get(f"{doc_id}_back", [])

                    rot_front = int(self.get_body_argument(f"rot_{doc_id}_front", default="0"))
                    rot_back = int(self.get_body_argument(f"rot_{doc_id}_back", default="0"))
                    fliph_front = self.get_body_argument(f"fliph_{doc_id}_front", default="false").lower() == "true"
                    fliph_back = self.get_body_argument(f"fliph_{doc_id}_back", default="false").lower() == "true"
                    flipv_front = self.get_body_argument(f"flipv_{doc_id}_front", default="false").lower() == "true"
                    flipv_back = self.get_body_argument(f"flipv_{doc_id}_back", default="false").lower() == "true"

                    uploaded_front_paths = []
                    uploaded_back_paths = []

                    for f in files_front:
                        tmp_p = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}_{f['filename']}")
                        with open(tmp_p, "wb") as out_f:
                            out_f.write(f['body'])
                        if os.path.exists(tmp_p) and os.path.getsize(tmp_p) > 0:
                            uploaded_front_paths.append(tmp_p)

                    for f in files_back:
                        tmp_p = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}_{f['filename']}")
                        with open(tmp_p, "wb") as out_f:
                            out_f.write(f['body'])
                        if os.path.exists(tmp_p) and os.path.getsize(tmp_p) > 0:
                            uploaded_back_paths.append(tmp_p)

                    if not uploaded_front_paths and not uploaded_back_paths:
                        print(f"   ⏩ [SKIPPED] No files uploaded for '{doc_id}'", flush=True)
                        continue

                    if not uploaded_front_paths:
                        blank = Image.new("RGB", (800, 500), color=(255, 255, 255))
                        tmp_p = os.path.join(UPLOAD_DIR, f"blank_front_{uuid.uuid4().hex}.jpg")
                        blank.save(tmp_p)
                        uploaded_front_paths = [tmp_p]

                    if not uploaded_back_paths:
                        blank = Image.new("RGB", (800, 500), color=(255, 255, 255))
                        tmp_p = os.path.join(UPLOAD_DIR, f"blank_back_{uuid.uuid4().hex}.jpg")
                        blank.save(tmp_p)
                        uploaded_back_paths = [tmp_p]

                    merged_kb, page_count = process_pdf_document(
                        uploaded_front_paths + uploaded_back_paths,
                        target_path,
                        max_kb=doc_cfg.get("max_kb", 100),
                        manual_rotations=[rot_front, rot_back],
                        flips_h=[fliph_front, fliph_back],
                        flips_v=[flipv_front, flipv_back]
                    )

                    download_url = f"/outputs/{job_id}/{folder_name}/{target_filename}"
                    processed_files_summary.append({
                        "filename": target_filename,
                        "label": f"{doc_cfg['label']} (Combined 2-Page PDF)",
                        "size_kb": round(merged_kb, 1),
                        "status": f"✓ Combined PDF ({page_count} pg) | {merged_kb:.1f} KB (<{doc_cfg['max_kb']} KB)",
                        "download_url": download_url
                    })

                else:
                    files = self.request.files.get(doc_id, [])
                    rot = int(self.get_body_argument(f"rot_{doc_id}", default="0"))
                    fliph = self.get_body_argument(f"fliph_{doc_id}", default="false").lower() == "true"
                    flipv = self.get_body_argument(f"flipv_{doc_id}", default="false").lower() == "true"

                    uploaded_paths = []
                    manual_rots = []
                    flips_h = []
                    flips_v = []

                    for f in files:
                        tmp_p = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}_{f['filename']}")
                        with open(tmp_p, "wb") as out_f:
                            out_f.write(f['body'])
                        if os.path.exists(tmp_p) and os.path.getsize(tmp_p) > 0:
                            uploaded_paths.append(tmp_p)
                            manual_rots.append(rot)
                            flips_h.append(fliph)
                            flips_v.append(flipv)

                    if not uploaded_paths:
                        print(f"   ⏩ [SKIPPED] No file uploaded for '{doc_id}'", flush=True)
                        continue

                    if doc_id == "signature":
                        final_kb = process_signature_image(
                            uploaded_paths[0], target_path,
                            target_w=doc_cfg.get("width", 160),
                            target_h=doc_cfg.get("height", 40),
                            max_kb=doc_cfg.get("max_kb", 20),
                            manual_rotation=manual_rots[0] if manual_rots else 0,
                            flip_h=flips_h[0] if flips_h else False,
                            flip_v=flips_v[0] if flips_v else False
                        )
                        status_text = f"✓ Signature Scan (160x40 px, White BG) | {final_kb:.1f} KB (<20 KB)"
                    elif doc_cfg.get("type") in ["pdf", "pdf_only"]:
                        final_kb, page_count = process_pdf_document(
                            uploaded_paths, target_path,
                            max_kb=doc_cfg.get("max_kb", 125),
                            manual_rotations=manual_rots,
                            flips_h=flips_h,
                            flips_v=flips_v
                        )
                        status_text = f"✓ PDF Document ({page_count} pg) | {final_kb:.1f} KB (<{doc_cfg['max_kb']} KB)"
                    else:
                        final_kb = process_image_document(
                            uploaded_paths[0], target_path,
                            target_w=doc_cfg.get("width", 160),
                            target_h=doc_cfg.get("height", 160),
                            max_kb=doc_cfg.get("max_kb", 50),
                            manual_rotation=manual_rots[0] if manual_rots else 0,
                            flip_h=flips_h[0] if flips_h else False,
                            flip_v=flips_v[0] if flips_v else False
                        )
                        status_text = f"✓ Resized {doc_cfg.get('width', 160)}x{doc_cfg.get('height', 160)} px JPG | {final_kb:.1f} KB (<{doc_cfg['max_kb']} KB)"

                    download_url = f"/outputs/{job_id}/{folder_name}/{target_filename}"
                    processed_files_summary.append({
                        "filename": target_filename,
                        "label": doc_cfg["label"],
                        "size_kb": round(final_kb, 1),
                        "status": status_text,
                        "download_url": download_url
                    })

                gc.collect()

            print("✅ [STEP 3 OK] Requested document processing step complete.", flush=True)

            print("📝 [STEP 4] Generating Details.txt...", flush=True)
            mspc_password = generate_mspc_password(applicant_name, dob)
            current_date_str = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

            details_content = f"""Applicant Name        : {applicant_name}
MSPC Portal Login ID  : {login_id}
MSPC Portal Password  : {mspc_password}
Pharmacy Reg Number   : {reg_number}
Date of Birth (DD/MM) : {dob}
Registered Mobile No  : {mobile}
Registered Email ID    : {email}
Generated Date        : {current_date_str}
"""
            details_path = os.path.join(job_output_dir, "Details.txt")
            with open(details_path, "w", encoding="utf-8") as f:
                f.write(details_content)

            if os.path.exists(details_path):
                details_download_url = f"/outputs/{job_id}/{folder_name}/Details.txt"
                processed_files_summary.append({
                    "filename": "Details.txt",
                    "label": "User Information & Credentials File",
                    "size_kb": round(os.path.getsize(details_path) / 1024.0, 1),
                    "status": "✓ Generated & Verified",
                    "download_url": details_download_url
                })
                print("✅ [STEP 4 OK] Details.txt created.", flush=True)

            print("📦 [STEP 5] Building output ZIP file archive...", flush=True)
            zip_filename = f"{folder_name}.zip"
            zip_path = os.path.join(OUTPUT_DIR, job_id, zip_filename)

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(job_output_dir):
                    for file in files:
                        full_file_path = os.path.join(root, file)
                        arcname = os.path.relpath(full_file_path, os.path.join(OUTPUT_DIR, job_id))
                        zipf.write(full_file_path, arcname)

            if not os.path.exists(zip_path) or os.path.getsize(zip_path) == 0:
                raise FileNotFoundError(f"Failed to create ZIP archive at {zip_path}")

            zip_size_kb = round(os.path.getsize(zip_path) / 1024.0, 1)
            zip_download_url = f"/outputs/{job_id}/{zip_filename}"
            print(f"✅ [STEP 5 OK] ZIP file generated: {zip_path} ({zip_size_kb} KB)", flush=True)

            print("☁ [STEP 6] Uploading ZIP file to Cloudinary...", flush=True)
            cloudinary_zip_url = upload_to_cloudinary(
                zip_path,
                folder=f"DocFlow/{folder_name}"
            )
            print(f"✅ [STEP 6 OK] Cloudinary ZIP URL: {cloudinary_zip_url}", flush=True)

            sub_payload = {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "name": applicant_name,
                "reg_number": reg_number,
                "login_id": login_id,
                "dob": dob,
                "mspc_password": mspc_password,
                "workflow": workflow["title"],
                "email": email,
                "mobile": mobile,
                "folder": folder_name,
                "files_count": len(processed_files_summary),
                "zip_size_kb": zip_size_kb,
                "cloudinary_zip_url": cloudinary_zip_url
            }
            log_submission(sub_payload)
            sync_workflow_to_bcwa(sub_payload)
            print("✅ [STEP 7 OK] DB Submission log & BCWA Master Database Sync complete.", flush=True)

            print("🎉 [STEP 8] Returning JSON response to client.", flush=True)
            print("==================================================", flush=True)

            self.write({
                "status": "success",
                "message": f"Workflow {workflow['title']} completed successfully!",
                "folder_name": folder_name,
                "job_id": job_id,
                "zip_download_url": zip_download_url,
                "cloudinary_zip_url": cloudinary_zip_url,
                "zip_filename": zip_filename,
                "zip_size_kb": zip_size_kb,
                "mspc_credentials": {
                    "portal_url": "https://online.mspcindia.org/",
                    "applicant_name": applicant_name,
                    "login_id": login_id,
                    "password": mspc_password,
                    "reg_number": reg_number,
                    "dob": dob,
                    "mobile": mobile,
                    "email": email,
                    "generated_date": current_date_str
                },
                "files": processed_files_summary
            })

        except Exception as e:
            err_tb = traceback.format_exc()
            print(f"❌ [CRITICAL ERROR in process_workflow]: {e}\n{err_tb}", flush=True)

            self.set_status(500)
            self.write({
                "status": "error",
                "message": str(e),
                "traceback": err_tb
            })


class ApiEditPdfStandaloneHandler(BaseHandler):
    async def post(self):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        try:
            files = self.request.files.get("file", [])
            if not files:
                self.set_status(400)
                self.write({"status": "error", "message": "No PDF file uploaded for editing"})
                return

            annotations_raw = self.get_body_argument("annotations", default="{}")
            annotations = json.loads(annotations_raw) if annotations_raw else {}

            target_filename = self.get_body_argument("output_name", default="Edited_Document.pdf").strip()
            if not target_filename.lower().endswith(".pdf"):
                target_filename += ".pdf"

            max_kb = float(self.get_body_argument("max_kb", default="125"))

            job_id = uuid.uuid4().hex[:8]
            job_output_dir = os.path.join(OUTPUT_DIR, job_id)
            os.makedirs(job_output_dir, exist_ok=True)

            pdf_bytes = files[0]['body']
            src_reader = pypdf.PdfReader(BytesIO(pdf_bytes))
            writer = pypdf.PdfWriter()

            from reportlab.pdfgen import canvas
            from reportlab.lib.colors import HexColor

            for page_idx, page in enumerate(src_reader.pages, start=1):
                page_width = float(page.mediabox.width)
                page_height = float(page.mediabox.height)

                page_annos = annotations.get(str(page_idx), annotations.get(page_idx, {}))
                text_items = page_annos.get("texts", [])
                sig_items = page_annos.get("signatures", [])
                whiteout_items = page_annos.get("whiteouts", [])

                if text_items or sig_items or whiteout_items:
                    packet = BytesIO()
                    can = canvas.Canvas(packet, pagesize=(page_width, page_height))

                    # 1. Whiteout Blocks
                    for w in whiteout_items:
                        can.setFillColor(HexColor("#ffffff"))
                        wx = float(w.get("x", 0))
                        wy = float(w.get("y", 0))
                        ww = float(w.get("w", 100))
                        wh = float(w.get("h", 30))
                        ry = page_height - wy - wh
                        can.rect(wx, ry, ww, wh, fill=1, stroke=0)

                    # 2. Text Annotations
                    for t in text_items:
                        txt_val = str(t.get("text", "")).strip()
                        if txt_val:
                            tx = float(t.get("x", 0))
                            ty = float(t.get("y", 0))
                            size = int(t.get("size", 14))
                            color_hex = str(t.get("color", "#0f172a"))
                            try:
                                can.setFillColor(HexColor(color_hex))
                            except Exception:
                                can.setFillColor(HexColor("#0f172a"))
                            can.setFont("Helvetica", size)
                            ry = page_height - ty - size
                            can.drawString(tx, ry, txt_val)

                    # 3. Signature Stamps
                    for s in sig_items:
                        b64_data = s.get("image_data", "")
                        if "," in b64_data:
                            b64_data = b64_data.split(",")[1]
                        if b64_data:
                            img_bytes = base64.b64decode(b64_data)
                            pil_sig = Image.open(BytesIO(img_bytes)).convert("RGBA")
                            
                            tmp_sig_path = os.path.join(UPLOAD_DIR, f"sig_{uuid.uuid4().hex}.png")
                            pil_sig.save(tmp_sig_path, "PNG")

                            sx = float(s.get("x", 0))
                            sy = float(s.get("y", 0))
                            sw = float(s.get("w", 140))
                            sh = float(s.get("h", 50))
                            ry = page_height - sy - sh

                            can.drawImage(tmp_sig_path, sx, ry, width=sw, height=sh, mask='auto')
                            if os.path.exists(tmp_sig_path):
                                os.remove(tmp_sig_path)

                    can.save()
                    packet.seek(0)
                    overlay_pdf = pypdf.PdfReader(packet)
                    page.merge_page(overlay_pdf.pages[0])

                page.compress_content_streams()
                writer.add_page(page)

            out_path = os.path.join(job_output_dir, target_filename)
            with open(out_path, "wb") as f_out:
                writer.write(f_out)

            size_kb = os.path.getsize(out_path) / 1024.0
            print(f"✅ Standalone PDF edited and saved: {out_path} ({size_kb:.1f} KB)", flush=True)

            gc.collect()

            self.write({
                "status": "success",
                "message": "PDF edited and exported successfully!",
                "filename": target_filename,
                "file_size_kb": round(size_kb, 1),
                "download_url": f"/outputs/{job_id}/{target_filename}"
            })

        except Exception as e:
            traceback.print_exc()
            self.set_status(500)
            self.write({"status": "error", "message": str(e), "traceback": traceback.format_exc()})


class ApiMergePdfsHandler(BaseHandler):
    async def post(self):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        try:
            uploaded_files = []
            for key in self.request.files:
                uploaded_files.extend(self.request.files[key])

            if not uploaded_files:
                self.set_status(400)
                self.write({"status": "error", "message": "No files uploaded to merge"})
                return

            target_filename = self.get_body_argument("output_name", default="Merged_Document.pdf").strip()
            if not target_filename.lower().endswith(".pdf"):
                target_filename += ".pdf"

            max_kb = float(self.get_body_argument("max_kb", default="125"))

            job_id = uuid.uuid4().hex[:8]
            job_output_dir = os.path.join(OUTPUT_DIR, job_id)
            os.makedirs(job_output_dir, exist_ok=True)

            temp_paths = []
            for i, f in enumerate(uploaded_files):
                tmp_p = os.path.join(UPLOAD_DIR, f"merge_{job_id}_{i}_{f['filename']}")
                with open(tmp_p, "wb") as f_out:
                    f_out.write(f['body'])
                temp_paths.append(tmp_p)

            merged_temp_path = os.path.join(job_output_dir, f"raw_{target_filename}")
            writer = pypdf.PdfWriter()

            for p in temp_paths:
                ext = os.path.splitext(p)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png', '.bmp']:
                    pil_img = Image.open(p).convert("RGB")
                    img_pdf_bytes = BytesIO()
                    pil_img.save(img_pdf_bytes, "PDF")
                    img_pdf_bytes.seek(0)
                    img_reader = pypdf.PdfReader(img_pdf_bytes)
                    for pg in img_reader.pages:
                        writer.add_page(pg)
                else:
                    reader = pypdf.PdfReader(p)
                    for pg in reader.pages:
                        writer.add_page(pg)

            with open(merged_temp_path, "wb") as f_merged:
                writer.write(f_merged)

            final_out_path = os.path.join(job_output_dir, target_filename)

            process_pdf_document([merged_temp_path], final_out_path, max_kb=max_kb)

            for p in temp_paths:
                if os.path.exists(p):
                    os.remove(p)
            if os.path.exists(merged_temp_path):
                os.remove(merged_temp_path)

            size_kb = os.path.getsize(final_out_path) / 1024.0
            print(f"✅ PDFs merged & compressed: {final_out_path} ({size_kb:.1f} KB / Target: {max_kb} KB)", flush=True)

            gc.collect()

            self.write({
                "status": "success",
                "message": "PDF files merged and compressed successfully!",
                "filename": target_filename,
                "file_size_kb": round(size_kb, 1),
                "max_kb_target": max_kb,
                "download_url": f"/outputs/{job_id}/{target_filename}"
            })

        except Exception as e:
            traceback.print_exc()
            self.set_status(500)
            self.write({"status": "error", "message": str(e), "traceback": traceback.format_exc()})


# --- SMART PDF AUTO-FILL ENGINE ---
def detect_pdf_blanks(pdf_path):
    doc = fitz.open(pdf_path)
    detected_fields = []
    
    for page_idx, page in enumerate(doc):
        words = page.get_text("words")
        lines_map = {}
        for w in words:
            line_no = w[6]
            if line_no not in lines_map:
                lines_map[line_no] = []
            lines_map[line_no].append(w)

        sorted_line_nos = sorted(lines_map.keys())

        for l_idx, l_no in enumerate(sorted_line_nos):
            line_words = lines_map[l_no]
            for w_i, w in enumerate(line_words):
                w_str = w[4]
                if '_' in w_str and len(w_str.replace('_', '')) < 3:
                    x0, y0, x1, y1 = w[0], w[1], w[2], w[3]

                    preceding_words = [w_prev[4] for w_prev in line_words[:w_i]]
                    preceding_text = " ".join(preceding_words).strip()

                    prev_line_text = ""
                    if l_idx > 0:
                        prev_line_no = sorted_line_nos[l_idx - 1]
                        prev_line_text = " ".join([w_prev[4] for w_prev in lines_map[prev_line_no]]).strip()

                    full_context = f"{prev_line_text} {preceding_text}".strip()

                    # Exclude signature lines
                    if any(sig_term in full_context.lower() for sig_term in ["sincerely", "best regards", "regards,", "signature"]):
                        continue

                    label = "Blank Field"
                    ctx_lower = full_context.lower()

                    if "date" in ctx_lower:
                        if "acceptance" in ctx_lower or page_idx == 1:
                            label = "Acceptance Date"
                        else:
                            label = "Date"
                    elif "dear" in ctx_lower or "i," in ctx_lower or "pharmacist" in ctx_lower:
                        label = "Pharmacist Name"
                    elif "effective from" in ctx_lower or "joining" in ctx_lower:
                        label = "Joining Date / Effective Date"
                    elif "proprietor" in ctx_lower or "medical" in ctx_lower or "store" in ctx_lower:
                        label = "Medical Store / Proprietor Name"
                    elif "to" in ctx_lower:
                        label = "Addressee / Store Details"

                    key = re.sub(r'[^a-z0-9_]', '', label.lower().replace(' ', '_'))
                    if not key:
                        key = f"field_{page_idx}_{l_no}_{w_i}"

                    detected_fields.append({
                        "key": key,
                        "label": label,
                        "page": page_idx + 1,
                        "rect": [x0, y0, x1, y1],
                        "context": full_context
                    })

    doc.close()

    unique_fields = []
    seen_keys = set()
    for f in detected_fields:
        if f["key"] not in seen_keys:
            seen_keys.add(f["key"])
            unique_fields.append({
                "key": f["key"],
                "label": f["label"],
                "occurrences": len([x for x in detected_fields if x["key"] == f["key"]])
            })

    return {
        "all_fields": detected_fields,
        "unique_fields": unique_fields
    }


def auto_fill_pdf(pdf_path, output_path, detected_fields, field_values, max_kb=125):
    doc = fitz.open(pdf_path)

    for field in detected_fields:
        key = field["key"]
        val = str(field_values.get(key, "")).strip()
        if not val:
            continue

        page_idx = field["page"] - 1
        if page_idx < 0 or page_idx >= len(doc):
            continue

        page = doc[page_idx]
        rect = fitz.Rect(field["rect"])

        padded_rect = fitz.Rect(rect.x0 - 1, rect.y0 - 2, rect.x1 + 1, rect.y1 + 2)
        page.draw_rect(padded_rect, color=(1, 1, 1), fill=(1, 1, 1))

        avail_width = rect.width
        fontsize = 11
        estimated_width = len(val) * 6.0
        if estimated_width > avail_width and avail_width > 20:
            fontsize = max(8, int(11 * (avail_width / estimated_width)))

        text_pos = fitz.Point(rect.x0 + 2, rect.y1 - 2)
        page.insert_text(text_pos, val, fontsize=fontsize, fontname="helv", color=(0.06, 0.09, 0.16))

    temp_filled = output_path + ".raw.pdf"
    doc.save(temp_filled)
    doc.close()

    process_pdf_document([temp_filled], output_path, max_kb=max_kb)
    if os.path.exists(temp_filled):
        os.remove(temp_filled)


class ApiDetectPdfBlanksHandler(BaseHandler):
    async def post(self):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        try:
            files = self.request.files.get("file", [])
            if not files:
                self.set_status(400)
                self.write({"status": "error", "message": "No template PDF uploaded"})
                return

            job_id = uuid.uuid4().hex[:8]
            job_output_dir = os.path.join(OUTPUT_DIR, job_id)
            os.makedirs(job_output_dir, exist_ok=True)

            template_path = os.path.join(job_output_dir, "template.pdf")
            with open(template_path, "wb") as f_out:
                f_out.write(files[0]['body'])

            res_data = detect_pdf_blanks(template_path)
            res_data["job_id"] = job_id
            res_data["status"] = "success"

            self.write(res_data)

        except Exception as e:
            traceback.print_exc()
            self.set_status(500)
            self.write({"status": "error", "message": str(e), "traceback": traceback.format_exc()})


class ApiAutoFillPdfHandler(BaseHandler):
    async def post(self):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        try:
            job_id = self.get_body_argument("job_id", default="")
            field_values_raw = self.get_body_argument("field_values", default="{}")
            field_values = json.loads(field_values_raw) if field_values_raw else {}
            max_kb = float(self.get_body_argument("max_kb", default="125"))

            job_dir = os.path.join(OUTPUT_DIR, job_id)
            template_path = os.path.join(job_dir, "template.pdf")

            if not os.path.exists(template_path):
                files = self.request.files.get("file", [])
                if files:
                    job_id = uuid.uuid4().hex[:8]
                    job_dir = os.path.join(OUTPUT_DIR, job_id)
                    os.makedirs(job_dir, exist_ok=True)
                    template_path = os.path.join(job_dir, "template.pdf")
                    with open(template_path, "wb") as f_out:
                        f_out.write(files[0]['body'])
                else:
                    self.set_status(400)
                    self.write({"status": "error", "message": "Template PDF not found"})
                    return

            detection_res = detect_pdf_blanks(template_path)
            out_path = os.path.join(job_dir, "AutoFilled_Document.pdf")

            auto_fill_pdf(template_path, out_path, detection_res["all_fields"], field_values, max_kb=max_kb)

            size_kb = os.path.getsize(out_path) / 1024.0
            print(f"✅ Auto-filled PDF generated: {out_path} ({size_kb:.1f} KB)", flush=True)

            gc.collect()

            self.write({
                "status": "success",
                "message": "PDF form auto-filled and generated successfully!",
                "filename": "AutoFilled_Document.pdf",
                "file_size_kb": round(size_kb, 1),
                "download_url": f"/outputs/{job_id}/AutoFilled_Document.pdf"
            })

        except Exception as e:
            traceback.print_exc()
            self.set_status(500)
class ApiFillAppointmentAcceptanceHandler(BaseHandler):
    async def post(self):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        try:
            files = self.request.files.get("file", [])
            
            job_id = uuid.uuid4().hex[:8]
            job_dir = os.path.join(OUTPUT_DIR, job_id)
            os.makedirs(job_dir, exist_ok=True)
            
            template_path = os.path.join(STATIC_DIR, "templates", "appointment_acceptance_letter.pdf")
            if files:
                template_path = os.path.join(job_dir, "custom_template.pdf")
                with open(template_path, "wb") as f_out:
                    f_out.write(files[0]['body'])

            appointment_date = self.get_body_argument("appointment_date", default="").strip()
            pharmacist_name = self.get_body_argument("pharmacist_name", default="").strip()
            joining_date = self.get_body_argument("joining_date", default="").strip()
            proprietor_name = self.get_body_argument("proprietor_name", default="").strip()
            acceptance_date = self.get_body_argument("acceptance_date", default="").strip()
            medical_store_name = self.get_body_argument("medical_store_name", default="").strip()

            max_kb = float(self.get_body_argument("max_kb", default="125"))

            doc = fitz.open(template_path)
            
            for page_idx, page in enumerate(doc):
                words = page.get_text("words")
                words = sorted(words, key=lambda w: (round(w[1] / 10) * 10, w[0]))

                for w in words:
                    w_str = w[4]
                    if '_' in w_str:
                        x0, y0, x1, y1 = w[0], w[1], w[2], w[3]
                        val_to_fill = ""

                        if y0 < 120:
                            val_to_fill = appointment_date
                        elif 130 <= y0 < 170:
                            val_to_fill = medical_store_name
                        elif 190 <= y0 < 225:
                            val_to_fill = pharmacist_name
                        elif 230 <= y0 < 265:
                            val_to_fill = joining_date
                        elif 360 <= y0 < 430:
                            # Skip Appointment Letter signature lines
                            continue
                        elif 470 <= y0 < 510:
                            val_to_fill = acceptance_date
                        elif 540 <= y0 < 580:
                            val_to_fill = medical_store_name
                        elif 620 <= y0 < 645:
                            val_to_fill = pharmacist_name
                        elif 645 <= y0 < 680:
                            if x0 < 300:
                                val_to_fill = medical_store_name
                            else:
                                val_to_fill = joining_date
                        elif y0 >= 680:
                            # Skip Acceptance Letter signature lines
                            continue

                        if val_to_fill:
                            rect = fitz.Rect(x0, y0, x1, y1)
                            padded = fitz.Rect(rect.x0 - 1, rect.y0 - 2, rect.x1 + 1, rect.y1 + 2)
                            page.draw_rect(padded, color=(1,1,1), fill=(1,1,1))

                            avail_width = rect.width
                            fontsize = 11
                            estimated_width = len(val_to_fill) * 6.0
                            if estimated_width > avail_width and avail_width > 20:
                                fontsize = max(8, int(11 * (avail_width / estimated_width)))

                            page.insert_text(fitz.Point(rect.x0 + 2, rect.y1 - 2), val_to_fill, fontsize=fontsize, fontname="helv", color=(0.06, 0.09, 0.16))

            out_raw = os.path.join(job_dir, "raw_filled.pdf")
            doc.save(out_raw)
            doc.close()

            final_out = os.path.join(job_dir, "Appointment_Acceptance_Letter.pdf")
            process_pdf_document([out_raw], final_out, max_kb=max_kb)

            if os.path.exists(out_raw):
                os.remove(out_raw)

            size_kb = os.path.getsize(final_out) / 1024.0
            print(f"✅ Dedicated Appointment & Acceptance Letter filled: {final_out} ({size_kb:.1f} KB)", flush=True)

            gc.collect()

            self.write({
                "status": "success",
                "message": "Appointment & Acceptance Letter generated successfully!",
                "filename": "Appointment_Acceptance_Letter.pdf",
                "file_size_kb": round(size_kb, 1),
                "download_url": f"/outputs/{job_id}/Appointment_Acceptance_Letter.pdf"
            })

        except Exception as e:
            traceback.print_exc()
            self.set_status(500)
            self.write({"status": "error", "message": str(e), "traceback": traceback.format_exc()})


class ApiGenerateSelfDeclarationHandler(BaseHandler):
    async def post(self):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        try:
            job_id = uuid.uuid4().hex[:8]
            job_dir = os.path.join(OUTPUT_DIR, job_id)
            os.makedirs(job_dir, exist_ok=True)

            pharmacist_name = self.get_body_argument("pharmacist_name", default="").strip()
            reg_no = self.get_body_argument("reg_no", default="").strip()
            address = self.get_body_argument("address", default="").strip()
            date_str = self.get_body_argument("date_str", default="").strip()
            store_name = self.get_body_argument("store_name", default="").strip()
            max_kb = float(self.get_body_argument("max_kb", default="125"))

            doc = fitz.open()
            page = doc.new_page(width=595, height=842) # A4

            page.insert_text(fitz.Point(200, 60), "SELF DECLARATION", fontsize=16, fontname="helv", color=(0,0,0))

            text_body = f"""
I, {pharmacist_name}, residing at {address}, hereby solemnly declare that:

1. I am a Registered Pharmacist under the Maharashtra State Pharmacy Council (MSPC) bearing Registration No. {reg_no}.

2. I am currently appointed as a Registered Pharmacist at {store_name}.

3. I am personally responsible for dispensing medicines, maintaining drug records, and ensuring full compliance with the Drugs and Cosmetics Act, 1940 and Rules thereunder.

4. The information provided above is true and correct to the best of my knowledge and belief.

DATE : {date_str}
PLACE : ____________________


                                              ___________________________________
                                              Signature of Registered Pharmacist
                                              ({pharmacist_name})
"""

            rect = fitz.Rect(50, 100, 545, 750)
            page.insert_textbox(rect, text_body, fontsize=11, fontname="helv", color=(0,0,0), align=0)

            out_raw = os.path.join(job_dir, "raw_sd.pdf")
            doc.save(out_raw)
            doc.close()

            final_out = os.path.join(job_dir, "Self_Declaration.pdf")
            process_pdf_document([out_raw], final_out, max_kb=max_kb)

            if os.path.exists(out_raw):
                os.remove(out_raw)

            size_kb = os.path.getsize(final_out) / 1024.0
            print(f"✅ Self Declaration SD generated: {final_out} ({size_kb:.1f} KB)", flush=True)

            gc.collect()

            self.write({
                "status": "success",
                "message": "Self Declaration (SD) generated successfully!",
                "filename": "Self_Declaration.pdf",
                "file_size_kb": round(size_kb, 1),
                "download_url": f"/outputs/{job_id}/Self_Declaration.pdf"
            })
        except Exception as e:
            traceback.print_exc()
            self.set_status(500)
            self.write({"status": "error", "message": str(e), "traceback": traceback.format_exc()})


class ApiGenerateCombinedAppointmentAcceptanceSdHandler(BaseHandler):
    async def post(self):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        try:
            job_id = uuid.uuid4().hex[:8]
            job_dir = os.path.join(OUTPUT_DIR, job_id)
            os.makedirs(job_dir, exist_ok=True)

            appointment_date = self.get_body_argument("appointment_date", default="").strip()
            pharmacist_name = self.get_body_argument("pharmacist_name", default="").strip()
            joining_date = self.get_body_argument("joining_date", default="").strip()
            proprietor_name = self.get_body_argument("proprietor_name", default="").strip()
            acceptance_date = self.get_body_argument("acceptance_date", default="").strip()
            medical_store_name = self.get_body_argument("medical_store_name", default="").strip()
            reg_no = self.get_body_argument("reg_no", default="").strip()
            address = self.get_body_argument("address", default="").strip()

            max_kb = float(self.get_body_argument("max_kb", default="125"))

            template_path = os.path.join(STATIC_DIR, "templates", "appointment_acceptance_letter.pdf")

            # 1. Page 1: Appointment & Acceptance Letter
            doc1 = fitz.open(template_path)
            page1 = doc1[0]
            words = page1.get_text("words")
            words = sorted(words, key=lambda w: (round(w[1] / 10) * 10, w[0]))

            for w in words:
                w_str = w[4]
                if '_' in w_str:
                    x0, y0, x1, y1 = w[0], w[1], w[2], w[3]
                    val_to_fill = ""

                    if y0 < 120:
                        val_to_fill = appointment_date
                    elif 130 <= y0 < 170:
                        val_to_fill = medical_store_name
                    elif 190 <= y0 < 225:
                        val_to_fill = pharmacist_name
                    elif 230 <= y0 < 265:
                        val_to_fill = joining_date
                    elif 360 <= y0 < 430:
                        continue
                    elif 470 <= y0 < 510:
                        val_to_fill = acceptance_date
                    elif 540 <= y0 < 580:
                        val_to_fill = medical_store_name
                    elif 620 <= y0 < 645:
                        val_to_fill = pharmacist_name
                    elif 645 <= y0 < 680:
                        if x0 < 300:
                            val_to_fill = medical_store_name
                        else:
                            val_to_fill = joining_date
                    elif y0 >= 680:
                        continue

                    if val_to_fill:
                        rect = fitz.Rect(x0, y0, x1, y1)
                        padded = fitz.Rect(rect.x0 - 1, rect.y0 - 2, rect.x1 + 1, rect.y1 + 2)
                        page1.draw_rect(padded, color=(1,1,1), fill=(1,1,1))

                        avail_width = rect.width
                        fontsize = 11
                        estimated_width = len(val_to_fill) * 6.0
                        if estimated_width > avail_width and avail_width > 20:
                            fontsize = max(8, int(11 * (avail_width / estimated_width)))

                        page1.insert_text(fitz.Point(rect.x0 + 2, rect.y1 - 2), val_to_fill, fontsize=fontsize, fontname="helv", color=(0.06, 0.09, 0.16))

            # 2. Page 2: Self Declaration (SD)
            doc2 = fitz.open()
            page2 = doc2.new_page(width=595, height=842)
            page2.insert_text(fitz.Point(200, 60), "SELF DECLARATION", fontsize=16, fontname="helv", color=(0,0,0))

            text_body = f"""
I, {pharmacist_name}, residing at {address}, hereby solemnly declare that:

1. I am a Registered Pharmacist under the Maharashtra State Pharmacy Council (MSPC) bearing Registration No. {reg_no}.

2. I am currently appointed as a Registered Pharmacist at {medical_store_name}.

3. I am personally responsible for dispensing medicines, maintaining drug records, and ensuring full compliance with the Drugs and Cosmetics Act, 1940 and Rules thereunder.

4. The information provided above is true and correct to the best of my knowledge and belief.

DATE : {appointment_date}
PLACE : ____________________


                                              ___________________________________
                                              Signature of Registered Pharmacist
                                              ({pharmacist_name})
"""

            rect2 = fitz.Rect(50, 100, 545, 750)
            page2.insert_textbox(rect2, text_body, fontsize=11, fontname="helv", color=(0,0,0), align=0)

            # Merge Page 1 + Page 2 into single PDF
            combined_doc = fitz.open()
            combined_doc.insert_pdf(doc1)
            combined_doc.insert_pdf(doc2)

            out_raw = os.path.join(job_dir, "raw_combined.pdf")
            combined_doc.save(out_raw)
            combined_doc.close()
            doc1.close()
            doc2.close()

            final_out = os.path.join(job_dir, "Appointment_Acceptance_SelfDeclaration.pdf")
            process_pdf_document([out_raw], final_out, max_kb=max_kb)

            if os.path.exists(out_raw):
                os.remove(out_raw)

            size_kb = os.path.getsize(final_out) / 1024.0
            print(f"✅ Combined Appointment + Acceptance + Self Declaration generated: {final_out} ({size_kb:.1f} KB)", flush=True)

            gc.collect()

            self.write({
                "status": "success",
                "message": "Combined Appointment, Acceptance & Self Declaration generated successfully!",
                "filename": "Appointment_Acceptance_SelfDeclaration.pdf",
                "file_size_kb": round(size_kb, 1),
                "download_url": f"/outputs/{job_id}/Appointment_Acceptance_SelfDeclaration.pdf"
            })
        except Exception as e:
            traceback.print_exc()
            self.set_status(500)
            self.write({"status": "error", "message": str(e), "traceback": traceback.format_exc()})


class ApiSubmissionsHistoryHandler(BaseHandler):
    async def get(self):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        try:
            workflow_filter = self.get_argument("workflow", default="").strip()
            history = []

            if db is not None:
                try:
                    docs = db.collection("submissions").limit(100).stream()
                    for d in docs:
                        item = d.to_dict()
                        if "created_at" in item and hasattr(item["created_at"], "isoformat"):
                            item["created_at"] = item["created_at"].isoformat()
                        history.append(item)
                    print(f"✅ Fetched {len(history)} submission records from Firebase Firestore.", flush=True)
                except Exception as e:
                    print(f"⚠️ Firestore query note: {e}", flush=True)

            if not history and os.path.exists(LOG_FILE):
                try:
                    with open(LOG_FILE, "r", encoding="utf-8") as f:
                        history = json.load(f)
                    history.reverse()
                except Exception:
                    history = []

            if workflow_filter:
                history = [h for h in history if workflow_filter.lower() in str(h.get("workflow", "")).lower()]

            self.write({
                "status": "success",
                "submissions": history,
                "count": len(history)
            })

        except Exception as e:
            traceback.print_exc()
            self.set_status(500)
            self.write({"status": "error", "message": str(e)})


# ----------------------------------------------------------------------
# BCWA (Boisar Welfare Chemist Association) Management Handlers
# ----------------------------------------------------------------------
BCWA_STORES_FILE = os.path.join(BASE_DIR, "bcwa_stores.json")
BCWA_PHARMACISTS_FILE = os.path.join(BASE_DIR, "bcwa_pharmacists.json")
BCWA_RENEWALS_FILE = os.path.join(BASE_DIR, "bcwa_renewals.json")
BCWA_DOCUMENTS_FILE = os.path.join(BASE_DIR, "bcwa_documents.json")
BCWA_ACTIVITY_LOGS_FILE = os.path.join(BASE_DIR, "bcwa_activity_logs.json")
BCWA_NOTIFICATIONS_FILE = os.path.join(BASE_DIR, "bcwa_notifications.json")

def load_bcwa_activity_logs():
    logs = []
    if db is not None:
        try:
            docs = db.collection("bcwa_activity_logs").stream()
            for d in docs:
                item = d.to_dict()
                item["id"] = d.id
                logs.append(item)
            if logs:
                logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
                return logs
        except Exception as e:
            print(f"⚠️ Firestore activity logs fetch note: {e}", flush=True)

    if os.path.exists(BCWA_ACTIVITY_LOGS_FILE):
        try:
            with open(BCWA_ACTIVITY_LOGS_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
            if logs:
                logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
                return logs
        except Exception:
            pass
    return []

def save_bcwa_activity_logs(logs):
    try:
        with open(BCWA_ACTIVITY_LOGS_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2)
    except Exception as e:
        print(f"⚠️ Could not write {BCWA_ACTIVITY_LOGS_FILE}: {e}", flush=True)

def log_bcwa_activity(action, details, store_id=None, store_name=None):
    entry = {
        "id": f"log_{int(datetime.now().timestamp()*1000)}",
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "details": details,
        "store_id": store_id or "",
        "store_name": store_name or ""
    }
    logs = load_bcwa_activity_logs()
    logs.insert(0, entry)
    save_bcwa_activity_logs(logs)
    if db is not None:
        try:
            db.collection("bcwa_activity_logs").document(entry["id"]).set(entry)
        except Exception as e:
            print(f"⚠️ Firestore log save note: {e}", flush=True)

def load_bcwa_documents():
    docs_list = []
    if db is not None:
        try:
            docs = db.collection("bcwa_documents").stream()
            for d in docs:
                item = d.to_dict()
                item["id"] = d.id
                docs_list.append(item)
            if docs_list:
                return docs_list
        except Exception as e:
            print(f"⚠️ Firestore documents fetch note: {e}", flush=True)

    if os.path.exists(BCWA_DOCUMENTS_FILE):
        try:
            with open(BCWA_DOCUMENTS_FILE, "r", encoding="utf-8") as f:
                docs_list = json.load(f)
            if docs_list:
                return docs_list
        except Exception:
            pass
    return []

def save_bcwa_documents(docs_list):
    try:
        with open(BCWA_DOCUMENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(docs_list, f, indent=2)
    except Exception as e:
        print(f"⚠️ Could not write {BCWA_DOCUMENTS_FILE}: {e}", flush=True)

def load_bcwa_renewals():
    renewals = []
    if db is not None:
        try:
            docs = db.collection("bcwa_renewals").stream()
            for d in docs:
                item = d.to_dict()
                item["id"] = d.id
                renewals.append(item)
            if renewals:
                renewals.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
                return renewals
        except Exception as e:
            print(f"⚠️ Firestore renewals fetch note: {e}", flush=True)

    if os.path.exists(BCWA_RENEWALS_FILE):
        try:
            with open(BCWA_RENEWALS_FILE, "r", encoding="utf-8") as f:
                renewals = json.load(f)
            if renewals:
                renewals.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
                return renewals
        except Exception:
            pass
    return []

def save_bcwa_renewals(renewals):
    try:
        with open(BCWA_RENEWALS_FILE, "w", encoding="utf-8") as f:
            json.dump(renewals, f, indent=2)
    except Exception as e:
        print(f"⚠️ Could not write {BCWA_RENEWALS_FILE}: {e}", flush=True)

def get_default_bcwa_sample_stores():
    return [
        {
            "id": "store_101",
            "store_name": "Apollo Pharmacy Boisar",
            "owner_name": "Shri Rajesh Patil",
            "business_type": "Proprietorship",
            "address": "Shop No. 4, Tarapur Road, Boisar West, Palghar - 401501",
            "contact_number": "9823456781",
            "email": "apollo.boisar@gmail.com",
            "dl_20b": "MH-TZ4-20B-18923",
            "dl_21b": "MH-TZ4-21B-18924",
            "dl_issue_date": "2021-09-10",
            "dl_expiry": "2026-09-09",
            "fssai_number": "11521024000189",
            "fssai_issue_date": "2022-01-15",
            "fssai_expiry": "2027-01-14",
            "rent_agreement_expiry": "2026-08-30",
            "cold_storage_cert": "Yes",
            "compliance_score": 98
        },
        {
            "id": "store_102",
            "store_name": "Sai Samarth Medical & General",
            "owner_name": "Shankar Rampati Singh",
            "business_type": "Proprietorship",
            "address": "Plot 12, MIDC Main Road, Boisar, Palghar - 401501",
            "contact_number": "8830185054",
            "email": "shankarsingh40717@gmail.com",
            "dl_20b": "MH-TZ4-20B-40161",
            "dl_21b": "MH-TZ4-21B-40162",
            "dl_issue_date": "2020-05-01",
            "dl_expiry": "2026-08-25",
            "fssai_number": "11520024000401",
            "fssai_issue_date": "2020-06-01",
            "fssai_expiry": "2026-08-05",
            "rent_agreement_expiry": "2027-05-01",
            "cold_storage_cert": "Yes",
            "compliance_score": 92
        },
        {
            "id": "store_103",
            "store_name": "Wellness Forever Chemist",
            "owner_name": "Smt. Sunita Sharma",
            "business_type": "Partnership",
            "address": "Navapur Naka, Boisar East, Palghar - 401501",
            "contact_number": "9970123456",
            "email": "boisar.wellness@gmail.com",
            "dl_20b": "MH-TZ4-20B-12345",
            "dl_21b": "MH-TZ4-21B-12346",
            "dl_issue_date": "2021-03-01",
            "dl_expiry": "2026-11-15",
            "fssai_number": "11522024000999",
            "fssai_issue_date": "2021-04-01",
            "fssai_expiry": "2026-10-10",
            "rent_agreement_expiry": "2028-03-31",
            "cold_storage_cert": "Yes",
            "compliance_score": 99
        },
        {
            "id": "store_104",
            "store_name": "Lifecare Chemists & Druggists",
            "owner_name": "Shri Amit Shah",
            "business_type": "Proprietorship",
            "address": "Station Road, Near Railway Flyover, Boisar - 401501",
            "contact_number": "9898765432",
            "email": "lifecare.boisar@gmail.com",
            "dl_20b": "MH-TZ4-20B-99881",
            "dl_21b": "MH-TZ4-21B-99882",
            "dl_issue_date": "2019-07-01",
            "dl_expiry": "2026-08-03",
            "fssai_number": "11519024000888",
            "fssai_issue_date": "2019-08-01",
            "fssai_expiry": "2026-08-01",
            "rent_agreement_expiry": "2026-08-02",
            "cold_storage_cert": "Yes",
            "compliance_score": 75
        }
    ]

def get_default_bcwa_sample_pharmacists():
    return [
        {
            "id": "pharm_101",
            "store_id": "store_101",
            "pharmacist_name": "Kartik Bhosale",
            "pharmacist_mobile": "8766759824",
            "pharmacist_email": "kartik.pharma@gmail.com",
            "mspc_reg_no": "189423",
            "ppp_number": "PPP-401501-A",
            "ppp_expiry": "2026-08-15",
            "reg_expiry": "2028-12-31",
            "joining_date": "2022-04-01",
            "qualification": "B.Pharm",
            "leaving_date": ""
        },
        {
            "id": "pharm_102",
            "store_id": "store_101",
            "pharmacist_name": "Aniket Patil",
            "pharmacist_mobile": "9822334455",
            "pharmacist_email": "aniket.patil@gmail.com",
            "mspc_reg_no": "201452",
            "ppp_number": "PPP-401501-A2",
            "ppp_expiry": "2026-11-20",
            "reg_expiry": "2029-05-10",
            "joining_date": "2023-02-15",
            "qualification": "D.Pharm",
            "leaving_date": ""
        },
        {
            "id": "pharm_103",
            "store_id": "store_102",
            "pharmacist_name": "Vinayak Bhosale",
            "pharmacist_mobile": "9876543210",
            "pharmacist_email": "vinayak.b@gmail.com",
            "mspc_reg_no": "40161",
            "ppp_number": "PPP-401501-B",
            "ppp_expiry": "2026-08-10",
            "reg_expiry": "2027-06-30",
            "joining_date": "2020-01-15",
            "qualification": "M.Pharm",
            "leaving_date": ""
        },
        {
            "id": "pharm_104",
            "store_id": "store_103",
            "pharmacist_name": "Rohit Sharma",
            "pharmacist_mobile": "9812345678",
            "pharmacist_email": "rohit.pharma@gmail.com",
            "mspc_reg_no": "123456",
            "ppp_number": "PPP-401501-C",
            "ppp_expiry": "2026-09-30",
            "reg_expiry": "2029-01-01",
            "joining_date": "2023-01-10",
            "qualification": "B.Pharm",
            "leaving_date": ""
        },
        {
            "id": "pharm_105",
            "store_id": "store_104",
            "pharmacist_name": "Pooja Mehta",
            "pharmacist_mobile": "9765432109",
            "pharmacist_email": "pooja.mehta@gmail.com",
            "mspc_reg_no": "154321",
            "ppp_number": "PPP-401501-D",
            "ppp_expiry": "2026-08-02",
            "reg_expiry": "2026-08-01",
            "joining_date": "2021-08-01",
            "qualification": "D.Pharm",
            "leaving_date": ""
        }
    ]

def load_bcwa_stores():
    stores = []
    if db is not None:
        try:
            docs = db.collection("bcwa_stores").stream()
            for d in docs:
                item = d.to_dict()
                item["id"] = d.id
                stores.append(item)
            if stores:
                return stores
        except Exception as e:
            print(f"⚠️ Firestore BCWA stores fetch note: {e}", flush=True)

    if os.path.exists(BCWA_STORES_FILE):
        try:
            with open(BCWA_STORES_FILE, "r", encoding="utf-8") as f:
                stores = json.load(f)
            if stores:
                return stores
        except Exception as e:
            print(f"⚠️ Local BCWA stores JSON read note: {e}", flush=True)

    default_stores = get_default_bcwa_sample_stores()
    save_bcwa_stores(default_stores)
    return default_stores

def save_bcwa_stores(stores):
    try:
        with open(BCWA_STORES_FILE, "w", encoding="utf-8") as f:
            json.dump(stores, f, indent=2)
    except Exception as e:
        print(f"⚠️ Could not write to {BCWA_STORES_FILE}: {e}", flush=True)

def load_bcwa_pharmacists():
    pharmacists = []
    if db is not None:
        try:
            docs = db.collection("bcwa_pharmacists").stream()
            for d in docs:
                item = d.to_dict()
                item["id"] = d.id
                pharmacists.append(item)
            if pharmacists:
                return pharmacists
        except Exception as e:
            print(f"⚠️ Firestore BCWA pharmacists fetch note: {e}", flush=True)

    if os.path.exists(BCWA_PHARMACISTS_FILE):
        try:
            with open(BCWA_PHARMACISTS_FILE, "r", encoding="utf-8") as f:
                pharmacists = json.load(f)
            if pharmacists:
                return pharmacists
        except Exception as e:
            print(f"⚠️ Local BCWA pharmacists JSON read note: {e}", flush=True)

    default_pharmacists = get_default_bcwa_sample_pharmacists()
    save_bcwa_pharmacists(default_pharmacists)
    return default_pharmacists

def save_bcwa_pharmacists(pharmacists):
    try:
        with open(BCWA_PHARMACISTS_FILE, "w", encoding="utf-8") as f:
            json.dump(pharmacists, f, indent=2)
    except Exception as e:
        print(f"⚠️ Could not write to {BCWA_PHARMACISTS_FILE}: {e}", flush=True)

def sync_workflow_to_bcwa(submission_data):
    """
    Automatically syncs completed workflow data (e.g. ppp_renewal, new_proprietorship_drug_license)
    into BCWA Master Database (Stores & Pharmacists collections).
    """
    try:
        applicant_name = submission_data.get("name", "").strip()
        reg_no = submission_data.get("reg_number", "").strip()
        email = submission_data.get("email", "").strip()
        mobile = submission_data.get("mobile", "").strip()
        workflow_title = submission_data.get("workflow", "")

        stores = load_bcwa_stores()
        pharmacists = load_bcwa_pharmacists()

        # Match existing store by owner or name
        matched_store = None
        for s in stores:
            if s.get("owner_name", "").lower() == applicant_name.lower() or applicant_name.lower() in s.get("store_name", "").lower():
                matched_store = s
                break

        if not matched_store:
            store_id = f"store_{int(datetime.now().timestamp()*1000)}"
            matched_store = {
                "id": store_id,
                "store_name": f"{applicant_name}'s Medical & General",
                "owner_name": applicant_name,
                "business_type": "Proprietorship",
                "address": "Boisar, Palghar",
                "contact_number": mobile,
                "email": email,
                "compliance_score": 95,
                "created_via_workflow": workflow_title,
                "updated_at": datetime.now().isoformat()
            }
            stores.append(matched_store)
            save_bcwa_stores(stores)
            if db is not None:
                try:
                    db.collection("bcwa_stores").document(store_id).set(matched_store)
                except Exception:
                    pass
            print(f"🔄 [BCWA SYNC] Created new Store '{matched_store['store_name']}' from workflow.", flush=True)

        matched_pharm = None
        for p in pharmacists:
            if (reg_no and p.get("mspc_reg_no") == reg_no) or p.get("pharmacist_name", "").lower() == applicant_name.lower():
                matched_pharm = p
                break

        if matched_pharm:
            if reg_no: matched_pharm["mspc_reg_no"] = reg_no
            if mobile: matched_pharm["pharmacist_mobile"] = mobile
            if email: matched_pharm["pharmacist_email"] = email
            matched_pharm["store_id"] = matched_store["id"]
            matched_pharm["updated_at"] = datetime.now().isoformat()
            save_bcwa_pharmacists(pharmacists)
            if db is not None:
                try:
                    db.collection("bcwa_pharmacists").document(matched_pharm["id"]).set(matched_pharm)
                except Exception:
                    pass
            print(f"🔄 [BCWA SYNC] Updated existing Pharmacist '{matched_pharm['pharmacist_name']}' for Store '{matched_store['store_name']}'.", flush=True)
        else:
            pharm_id = f"pharm_{int(datetime.now().timestamp()*1000)}"
            new_pharm = {
                "id": pharm_id,
                "store_id": matched_store["id"],
                "pharmacist_name": applicant_name,
                "pharmacist_mobile": mobile,
                "pharmacist_email": email,
                "mspc_reg_no": reg_no,
                "ppp_number": f"PPP-401501-{reg_no[-3:] if reg_no else 'NEW'}",
                "ppp_expiry": "2027-12-31",
                "reg_expiry": "2029-12-31",
                "joining_date": datetime.now().strftime("%Y-%m-%d"),
                "qualification": "Registered Pharmacist",
                "created_via_workflow": workflow_title,
                "updated_at": datetime.now().isoformat()
            }
            pharmacists.append(new_pharm)
            save_bcwa_pharmacists(pharmacists)
            if db is not None:
                try:
                    db.collection("bcwa_pharmacists").document(pharm_id).set(new_pharm)
                except Exception:
                    pass
            print(f"🔄 [BCWA SYNC] Created & Linked new Pharmacist '{applicant_name}' to Store '{matched_store['store_name']}'.", flush=True)

        # Add to Renewal History & Activity Log
        renewal_entry = {
            "id": f"ren_{int(datetime.now().timestamp()*1000)}",
            "store_id": matched_store["id"],
            "store_name": matched_store["store_name"],
            "applicant": applicant_name,
            "workflow": workflow_title,
            "reg_number": reg_no,
            "timestamp": datetime.now().isoformat(),
            "status": "COMPLETED"
        }
        renewals = load_bcwa_renewals()
        renewals.insert(0, renewal_entry)
        save_bcwa_renewals(renewals)
        if db is not None:
            try:
                db.collection("bcwa_renewals").document(renewal_entry["id"]).set(renewal_entry)
            except Exception:
                pass

        log_bcwa_activity("WORKFLOW_SYNC", f"Completed workflow '{workflow_title}' for '{applicant_name}'", store_id=matched_store["id"], store_name=matched_store["store_name"])

    except Exception as e:
        print(f"⚠️ [BCWA SYNC ERROR]: {e}", flush=True)

class ApiBcwaStoresHandler(BaseHandler):
    async def get(self):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        stores = load_bcwa_stores()
        pharmacists = load_bcwa_pharmacists()
        for s in stores:
            s["pharmacists"] = [p for p in pharmacists if p.get("store_id") == s.get("id")]
        self.write({"status": "success", "stores": stores, "count": len(stores)})

    async def post(self):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        try:
            raw_body = self.request.body.decode("utf-8")
            data = json.loads(raw_body)
            stores = load_bcwa_stores()

            # Duplicate prevention check if new store (no explicit ID given)
            existing_match = None
            if not data.get("id"):
                dl_20b = (data.get("dl_20b") or "").strip().lower()
                fssai = (data.get("fssai_number") or "").strip().lower()
                store_name = (data.get("store_name") or "").strip().lower()
                owner_mobile = (data.get("contact_number") or "").strip()

                for s in stores:
                    s_dl = (s.get("dl_20b") or "").strip().lower()
                    s_fssai = (s.get("fssai_number") or "").strip().lower()
                    s_name = (s.get("store_name") or "").strip().lower()
                    s_mobile = (s.get("contact_number") or "").strip()

                    if (dl_20b and dl_20b == s_dl) or (fssai and fssai == s_fssai) or (store_name and s_name == store_name and owner_mobile and owner_mobile == s_mobile):
                        existing_match = s
                        break

            if existing_match:
                store_id = existing_match["id"]
                data["id"] = store_id
                action_text = f"Updated existing Store record '{data.get('store_name')}' via duplicate check"
            else:
                store_id = data.get("id") or f"store_{int(datetime.now().timestamp()*1000)}"
                data["id"] = store_id
                action_text = f"Registered new Medical Store '{data.get('store_name')}'"

            data["updated_at"] = datetime.now().isoformat()

            updated = False
            for idx, s in enumerate(stores):
                if s.get("id") == store_id:
                    stores[idx] = data
                    updated = True
                    break
            if not updated:
                stores.append(data)

            save_bcwa_stores(stores)

            # Save embedded pharmacists from wizard Step 5 if provided
            embedded_pharmacists = data.get("pharmacists")
            if embedded_pharmacists and isinstance(embedded_pharmacists, list):
                all_pharmacists = load_bcwa_pharmacists()
                for p in embedded_pharmacists:
                    if isinstance(p, dict) and p.get("pharmacist_name"):
                        p["store_id"] = store_id
                        p_id = p.get("id") or f"pharm_{int(datetime.now().timestamp()*1000)}"
                        p["id"] = p_id
                        p["updated_at"] = datetime.now().isoformat()
                        
                        p_updated = False
                        for p_idx, existing_p in enumerate(all_pharmacists):
                            if existing_p.get("id") == p_id or (existing_p.get("mspc_reg_no") and existing_p.get("mspc_reg_no") == p.get("mspc_reg_no")):
                                all_pharmacists[p_idx] = p
                                p_updated = True
                                break
                        if not p_updated:
                            all_pharmacists.append(p)
                        
                        if db is not None:
                            try:
                                db.collection("bcwa_pharmacists").document(p_id).set(p)
                            except Exception as e:
                                print(f"⚠️ Firestore embedded pharmacist save note: {e}", flush=True)
                save_bcwa_pharmacists(all_pharmacists)

            if db is not None:
                try:
                    db.collection("bcwa_stores").document(store_id).set(data)
                    print(f"✅ Saved BCWA store '{data.get('store_name')}' to Firestore.", flush=True)
                except Exception as e:
                    print(f"⚠️ Firestore store save note: {e}", flush=True)

            log_bcwa_activity("STORE_SAVED", action_text, store_id=store_id, store_name=data.get("store_name"))

            self.write({"status": "success", "message": "BCWA Store profile saved successfully!", "store": data})
        except Exception as e:
            traceback.print_exc()
            self.set_status(500)
            self.write({"status": "error", "message": str(e)})

    async def delete(self):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        try:
            store_id = self.get_argument("id", default="")
            if not store_id:
                self.set_status(400)
                return self.write({"status": "error", "message": "Store ID required."})

            stores = load_bcwa_stores()
            target_store = next((s for s in stores if s.get("id") == store_id), None)
            store_name = target_store.get("store_name", store_id) if target_store else store_id

            stores = [s for s in stores if s.get("id") != store_id]
            save_bcwa_stores(stores)

            # Unlink or remove pharmacists belonging to deleted store
            pharmacists = load_bcwa_pharmacists()
            pharmacists = [p for p in pharmacists if p.get("store_id") != store_id]
            save_bcwa_pharmacists(pharmacists)

            if db is not None:
                try:
                    db.collection("bcwa_stores").document(store_id).delete()
                except Exception as e:
                    print(f"⚠️ Firestore store delete note: {e}", flush=True)

            log_bcwa_activity("STORE_DELETED", f"Deleted Medical Store '{store_name}' and unlinked child pharmacists", store_id=store_id, store_name=store_name)

            self.write({"status": "success", "message": "Store deleted successfully."})
        except Exception as e:
            traceback.print_exc()
            self.set_status(500)
            self.write({"status": "error", "message": str(e)})


class ApiBcwaPharmacistsHandler(BaseHandler):
    async def get(self):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        store_id = self.get_argument("store_id", default="")
        pharmacists = load_bcwa_pharmacists()
        if store_id:
            pharmacists = [p for p in pharmacists if p.get("store_id") == store_id]
        self.write({"status": "success", "pharmacists": pharmacists, "count": len(pharmacists)})

    async def post(self):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        try:
            raw_body = self.request.body.decode("utf-8")
            data = json.loads(raw_body)
            pharmacists = load_bcwa_pharmacists()

            # Duplicate prevention check if new pharmacist
            existing_match = None
            if not data.get("id"):
                mspc = (data.get("mspc_reg_no") or "").strip().lower()
                ppp = (data.get("ppp_number") or "").strip().lower()
                p_mobile = (data.get("pharmacist_mobile") or "").strip()

                for p in pharmacists:
                    p_mspc = (p.get("mspc_reg_no") or "").strip().lower()
                    p_ppp = (p.get("ppp_number") or "").strip().lower()
                    p_mob = (p.get("pharmacist_mobile") or "").strip()

                    if (mspc and mspc == p_mspc) or (ppp and ppp == p_ppp) or (p_mobile and p_mobile == p_mob):
                        existing_match = p
                        break

            if existing_match:
                pharm_id = existing_match["id"]
                data["id"] = pharm_id
                action_text = f"Updated Pharmacist profile '{data.get('pharmacist_name')}' via duplicate check"
            else:
                pharm_id = data.get("id") or f"pharm_{int(datetime.now().timestamp()*1000)}"
                data["id"] = pharm_id
                action_text = f"Added Pharmacist profile '{data.get('pharmacist_name')}'"

            data["updated_at"] = datetime.now().isoformat()

            updated = False
            for idx, p in enumerate(pharmacists):
                if p.get("id") == pharm_id:
                    pharmacists[idx] = data
                    updated = True
                    break
            if not updated:
                pharmacists.append(data)

            save_bcwa_pharmacists(pharmacists)

            if db is not None:
                try:
                    db.collection("bcwa_pharmacists").document(pharm_id).set(data)
                    print(f"✅ Saved BCWA pharmacist '{data.get('pharmacist_name')}' to Firestore.", flush=True)
                except Exception as e:
                    print(f"⚠️ Firestore pharmacist save note: {e}", flush=True)

            log_bcwa_activity("PHARMACIST_SAVED", action_text, store_id=data.get("store_id"), store_name=data.get("pharmacist_name"))

            self.write({"status": "success", "message": "Pharmacist profile saved successfully!", "pharmacist": data})
        except Exception as e:
            traceback.print_exc()
            self.set_status(500)
            self.write({"status": "error", "message": str(e)})

    async def delete(self):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        try:
            pharm_id = self.get_argument("id", default="")
            if not pharm_id:
                self.set_status(400)
                return self.write({"status": "error", "message": "Pharmacist ID required."})

            pharmacists = load_bcwa_pharmacists()
            target = next((p for p in pharmacists if p.get("id") == pharm_id), None)
            pharm_name = target.get("pharmacist_name", pharm_id) if target else pharm_id

            pharmacists = [p for p in pharmacists if p.get("id") != pharm_id]
            save_bcwa_pharmacists(pharmacists)

            if db is not None:
                try:
                    db.collection("bcwa_pharmacists").document(pharm_id).delete()
                except Exception as e:
                    print(f"⚠️ Firestore pharmacist delete note: {e}", flush=True)

            log_bcwa_activity("PHARMACIST_DELETED", f"Deleted Pharmacist profile '{pharm_name}'")

            self.write({"status": "success", "message": "Pharmacist deleted successfully."})
        except Exception as e:
            traceback.print_exc()
            self.set_status(500)
            self.write({"status": "error", "message": str(e)})


class ApiBcwaStoreDetailHandler(BaseHandler):
    async def get(self):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        try:
            store_id = self.get_argument("id", default="")
            if not store_id:
                self.set_status(400)
                return self.write({"status": "error", "message": "Store ID required."})

            stores = load_bcwa_stores()
            target_store = next((s for s in stores if s.get("id") == store_id), None)
            if not target_store:
                self.set_status(404)
                return self.write({"status": "error", "message": "Medical store not found."})

            pharmacists = load_bcwa_pharmacists()
            store_pharms = [p for p in pharmacists if p.get("store_id") == store_id]

            docs_list = load_bcwa_documents()
            store_docs = [d for d in docs_list if d.get("store_id") == store_id]

            renewals = load_bcwa_renewals()
            store_renewals = [r for r in renewals if r.get("store_id") == store_id or r.get("store_name") == target_store.get("store_name")]

            all_logs = load_bcwa_activity_logs()
            store_logs = [l for l in all_logs if l.get("store_id") == store_id or l.get("store_name") == target_store.get("store_name")]

            self.write({
                "status": "success",
                "store": target_store,
                "pharmacists": store_pharms,
                "documents": store_docs,
                "renewals": store_renewals,
                "activity_logs": store_logs
            })
        except Exception as e:
            traceback.print_exc()
            self.set_status(500)
            self.write({"status": "error", "message": str(e)})


class ApiBcwaExportCsvHandler(BaseHandler):
    async def get(self):
        self.set_header("Content-Type", "text/csv; charset=UTF-8")
        self.set_header("Content-Disposition", "attachment; filename=BCWA_Medical_Stores_Compliance.csv")
        try:
            stores = load_bcwa_stores()
            pharmacists = load_bcwa_pharmacists()

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "Store ID", "Store Name", "Business Type", "Owner Name", "Owner Contact", "Owner Email",
                "Address", "DL 20B", "DL 21B", "DL Expiry", "FSSAI Number", "FSSAI Expiry", "Rent Expiry",
                "Compliance Score", "Primary Pharmacist", "MSPC Reg No", "PPP Number", "PPP Expiry", "Pharmacist Mobile"
            ])

            for s in stores:
                s_pharms = [p for p in pharmacists if p.get("store_id") == s.get("id")]
                p1 = s_pharms[0] if s_pharms else {}
                writer.writerow([
                    s.get("id", ""),
                    s.get("store_name", ""),
                    s.get("business_type", ""),
                    s.get("owner_name", ""),
                    s.get("contact_number", ""),
                    s.get("email", ""),
                    s.get("address", ""),
                    s.get("dl_20b", ""),
                    s.get("dl_21b", ""),
                    s.get("dl_expiry", ""),
                    s.get("fssai_number", ""),
                    s.get("fssai_expiry", ""),
                    s.get("rent_agreement_expiry", ""),
                    s.get("compliance_score", "95"),
                    p1.get("pharmacist_name", ""),
                    p1.get("mspc_reg_no", ""),
                    p1.get("ppp_number", ""),
                    p1.get("ppp_expiry", ""),
                    p1.get("pharmacist_mobile", "")
                ])

            self.write(output.getvalue())
        except Exception as e:
            traceback.print_exc()
            self.set_status(500)
            self.write(f"Error generating CSV: {e}")


class ApiBcwaImportCsvHandler(BaseHandler):
    async def post(self):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        try:
            raw_body = self.request.body.decode("utf-8")
            stores_to_import = []

            if raw_body.strip().startswith("["):
                stores_to_import = json.loads(raw_body)
            else:
                # Parse CSV content
                f = io.StringIO(raw_body)
                reader = csv.DictReader(f)
                for row in reader:
                    stores_to_import.append({
                        "store_name": row.get("Store Name") or row.get("store_name"),
                        "owner_name": row.get("Owner Name") or row.get("owner_name"),
                        "business_type": row.get("Business Type") or row.get("business_type") or "Proprietorship",
                        "contact_number": row.get("Owner Contact") or row.get("contact_number"),
                        "email": row.get("Owner Email") or row.get("email"),
                        "address": row.get("Address") or row.get("address"),
                        "dl_20b": row.get("DL 20B") or row.get("dl_20b"),
                        "dl_21b": row.get("DL 21B") or row.get("dl_21b"),
                        "dl_expiry": row.get("DL Expiry") or row.get("dl_expiry"),
                        "fssai_number": row.get("FSSAI Number") or row.get("fssai_number"),
                        "fssai_expiry": row.get("FSSAI Expiry") or row.get("fssai_expiry"),
                        "rent_agreement_expiry": row.get("Rent Expiry") or row.get("rent_agreement_expiry"),
                        "compliance_score": 95
                    })

            stores = load_bcwa_stores()
            imported_count = 0

            for new_s in stores_to_import:
                if not new_s.get("store_name") or not new_s.get("owner_name"):
                    continue
                s_id = f"store_{int(datetime.now().timestamp()*1000)}_{imported_count}"
                new_s["id"] = s_id
                new_s["updated_at"] = datetime.now().isoformat()
                stores.append(new_s)

                if db is not None:
                    try:
                        db.collection("bcwa_stores").document(s_id).set(new_s)
                    except Exception:
                        pass
                imported_count += 1

            save_bcwa_stores(stores)
            log_bcwa_activity("CSV_IMPORT", f"Bulk imported {imported_count} Medical Stores via CSV")

            self.write({"status": "success", "message": f"Successfully imported {imported_count} Medical Stores!", "count": imported_count})
        except Exception as e:
            traceback.print_exc()
            self.set_status(500)
            self.write({"status": "error", "message": str(e)})


class ApiBcwaNotificationHandler(BaseHandler):
    async def post(self):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        try:
            raw_body = self.request.body.decode("utf-8")
            data = json.loads(raw_body)
            channel = data.get("channel", "WhatsApp")
            recipient = data.get("recipient", "Officer")
            phone = data.get("phone", "")
            store_name = data.get("store_name", "")
            doc_name = data.get("doc_name", "Renewal Notice")

            notif_entry = {
                "id": f"notif_{int(datetime.now().timestamp()*1000)}",
                "timestamp": datetime.now().isoformat(),
                "channel": channel,
                "recipient": recipient,
                "phone": phone,
                "store_name": store_name,
                "doc_name": doc_name,
                "status": "SENT"
            }

            # Save notification
            notifications = []
            if os.path.exists(BCWA_NOTIFICATIONS_FILE):
                try:
                    with open(BCWA_NOTIFICATIONS_FILE, "r", encoding="utf-8") as f:
                        notifications = json.load(f)
                except Exception:
                    pass
            notifications.insert(0, notif_entry)
            try:
                with open(BCWA_NOTIFICATIONS_FILE, "w", encoding="utf-8") as f:
                    json.dump(notifications, f, indent=2)
            except Exception:
                pass

            if db is not None:
                try:
                    db.collection("bcwa_notifications").document(notif_entry["id"]).set(notif_entry)
                except Exception:
                    pass

            log_bcwa_activity("NOTIFICATION_SENT", f"Dispatched {channel} alert for '{doc_name}' to {recipient} ({phone})", store_name=store_name)

            self.write({"status": "success", "message": f"{channel} reminder sent successfully to {recipient}!", "notification": notif_entry})
        except Exception as e:
            traceback.print_exc()
            self.set_status(500)
            self.write({"status": "error", "message": str(e)})


def make_app():
    return tornado.web.Application([
        (r"/", MainHandler),
        (r"/api/login", ApiLoginHandler),
        (r"/api/add_user", ApiAddUserHandler),
        (r"/api/remove_user", ApiRemoveUserHandler),
        (r"/api/check_auth", ApiCheckAuthHandler),
        (r"/api/workflows", ApiWorkflowsHandler),
        (r"/api/submissions", ApiSubmissionsHistoryHandler),
        (r"/api/bcwa/stores", ApiBcwaStoresHandler),
        (r"/api/bcwa/add_store", ApiBcwaStoresHandler),
        (r"/api/bcwa/store_detail", ApiBcwaStoreDetailHandler),
        (r"/api/bcwa/pharmacists", ApiBcwaPharmacistsHandler),
        (r"/api/bcwa/add_pharmacist", ApiBcwaPharmacistsHandler),
        (r"/api/bcwa/export_csv", ApiBcwaExportCsvHandler),
        (r"/api/bcwa/import_csv", ApiBcwaImportCsvHandler),
        (r"/api/bcwa/send_notification", ApiBcwaNotificationHandler),
        (r"/api/extract_document_data", ApiExtractDocumentDataHandler),
        (r"/api/preview_rotation", ApiPreviewRotationHandler),
        (r"/api/live_render", ApiLiveRenderHandler),
        (r"/api/process_workflow", ApiProcessWorkflowHandler),
        (r"/api/edit_pdf_standalone", ApiEditPdfStandaloneHandler),
        (r"/api/merge_pdfs", ApiMergePdfsHandler),
        (r"/api/detect_pdf_blanks", ApiDetectPdfBlanksHandler),
        (r"/api/autofill_pdf", ApiAutoFillPdfHandler),
        (r"/api/fill_appointment_letter", ApiFillAppointmentAcceptanceHandler),
        (r"/api/generate_self_declaration", ApiGenerateSelfDeclarationHandler),
        (r"/api/generate_combined_appointment_acceptance_sd", ApiGenerateCombinedAppointmentAcceptanceSdHandler),
        (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": STATIC_DIR}),
        (r"/outputs/(.*)", tornado.web.StaticFileHandler, {"path": OUTPUT_DIR}),
    ], debug=True)


if __name__ == "__main__":
    port = 8501
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass

    app = make_app()
    app.listen(port)
    print(f"==================================================", flush=True)
    print(f"🚀 DocFlow Pro Authorized Server Engine Running on Port {port}!", flush=True)
    print(f"==================================================", flush=True)
    tornado.ioloop.IOLoop.current().start()
