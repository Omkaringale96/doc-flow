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
from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageOps, ExifTags
import requests
import pypdf
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
                        "id": "light_bill_tax_receipt",
                        "label": "Light Bill + Tax Receipt",
                        "type": "pdf",
                        "multi_sources": [
                            {"id": "light_bill", "label": "Light Bill", "hint": "Upload Light Bill (Image or PDF)"},
                            {"id": "tax_receipt", "label": "Tax Receipt", "hint": "Upload Tax Receipt (Image or PDF)"}
                        ],
                        "output_name": "Light_Bill_Tax_Receipt.pdf",
                        "max_kb": 125,
                        "hint": "Upload Light Bill & Tax Receipt. Combined PDF under 125 KB"
                    },
                    {
                        "id": "cold_storage_namuna8",
                        "label": "Cold Storage + Namuna 8",
                        "type": "pdf",
                        "multi_sources": [
                            {"id": "cold_storage", "label": "Cold Storage Certificate", "hint": "Upload Cold Storage Certificate (Image or PDF)"},
                            {"id": "namuna_8", "label": "Namuna 8", "hint": "Upload Namuna 8 (Image or PDF)"}
                        ],
                        "output_name": "Cold_Storage_Namuna8.pdf",
                        "max_kb": 125,
                        "hint": "Upload Cold Storage Certificate & Namuna 8. Combined PDF under 125 KB"
                    },
                    {
                        "id": "rent_agreement",
                        "label": "Rent Agreement",
                        "type": "pdf_only",
                        "output_name": "Rent_Agreement.pdf",
                        "max_kb": 150,
                        "hint": "Accepted format: PDF only (PDF output under 150 KB)"
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
    clean_name = re.sub(r'[^A-Za-z]', '', str(name)).upper()
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
        print(f"⚠️ [CLOUDINARY ERROR] Upload failed: {e}", flush=True)
        traceback.print_exc()
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


def process_pdf_document(input_paths, output_path, max_kb=100, manual_rotations=None, flips_h=None, flips_v=None, free_angles=None):
    if manual_rotations is None: manual_rotations = []
    if flips_h is None: flips_h = []
    if flips_v is None: flips_v = []
    if free_angles is None: free_angles = []

    # Check if inputs contain existing PDF files
    has_pdf_file = any(p.lower().endswith('.pdf') for p in input_paths if os.path.exists(p))

    if has_pdf_file and len(input_paths) == 1 and input_paths[0].lower().endswith('.pdf'):
        # Direct PDF optimization
        src_pdf = input_paths[0]
        try:
            reader = pypdf.PdfReader(src_pdf)
            writer = pypdf.PdfWriter()
            for page in reader.pages:
                page.compress_content_streams()
                writer.add_page(page)
            
            with open(output_path, "wb") as f_out:
                writer.write(f_out)
            
            size_kb = os.path.getsize(output_path) / 1024.0
            if size_kb <= max_kb:
                return size_kb, len(reader.pages)
        except Exception as e:
            print(f"⚠️ Direct PDF copy warning: {e}", flush=True)

    images = []
    for idx, path in enumerate(input_paths):
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            print(f"⚠️ Input path {path} invalid/missing, substituting blank canvas.", flush=True)
            blank = Image.new("RGB", (600, 800), color=(255, 255, 255))
            images.append(blank)
            continue

        try:
            if path.lower().endswith('.pdf'):
                # Extract pages or convert via PyPDF
                try:
                    reader = pypdf.PdfReader(path)
                    for page in reader.pages:
                        for img_obj in page.images:
                            pil_img = Image.open(BytesIO(img_obj.data)).convert("RGB")
                            images.append(pil_img)
                except Exception as pdf_err:
                    print(f"⚠️ PDF extraction fallback for {path}: {pdf_err}", flush=True)
                    blank = Image.new("RGB", (600, 800), color=(255, 255, 255))
                    images.append(blank)
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
                images.append(clean_pil)

                del cv_img, processed_bgr, processed_rgb, processed_pil
        except Exception as err:
            print(f"⚠️ Skipping file {path}: {err}", flush=True)

    if not images:
        blank = Image.new("RGB", (600, 800), color=(255, 255, 255))
        images = [blank]

    quality = 88
    scale_factor = 1.0

    while True:
        temp_imgs = []
        for img in images:
            w_dim, h_dim = int(img.width * scale_factor), int(img.height * scale_factor)
            resized = img.resize((max(1, w_dim), max(1, h_dim)), Image.Resampling.LANCZOS)
            temp_imgs.append(resized)

        temp_imgs[0].save(
            output_path, "PDF",
            save_all=True,
            append_images=temp_imgs[1:],
            resolution=72.0,
            quality=quality
        )

        size_kb = os.path.getsize(output_path) / 1024.0
        if size_kb <= max_kb or (quality <= 15 and scale_factor <= 0.3):
            break

        if quality > 20:
            quality -= 15
        else:
            scale_factor *= 0.75

    del images, temp_imgs
    gc.collect()

    return os.path.getsize(output_path) / 1024.0, len(input_paths)


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
            if username in users_db and users_db[username] == password:
                token = uuid.uuid4().hex
                ACTIVE_SESSIONS[token] = {
                    "username": username,
                    "created_at": datetime.now().isoformat()
                }
                print(f"✅ User '{username}' logged in successfully. Token: {token}", flush=True)
                self.write({
                    "status": "success",
                    "message": f"Welcome back, {username}!",
                    "token": token,
                    "username": username
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
            if not current_user:
                self.set_status(403)
                self.write({
                    "status": "error",
                    "message": "Unauthorized! Only existing authorized members can add new members."
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

            print(f"🔑 Authorized member '{current_user}' created new member '{new_username}'", flush=True)
            self.write({
                "status": "success",
                "message": f"Authorized member '{new_username}' added successfully!",
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
        self.write({
            "status": "success",
            "workflows": list(WORKFLOWS.values())
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
                        blank_img = Image.new("RGB", (600, 800), color=(255, 255, 255))
                        tmp_p = os.path.join(UPLOAD_DIR, f"placeholder_{uuid.uuid4().hex}.jpg")
                        blank_img.save(tmp_p)
                        uploaded_paths = [tmp_p]
                        manual_rots = [0]
                        flips_h = [False]
                        flips_v = [False]

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
                        blank_img = Image.new("RGB", (600, 800), color=(255, 255, 255))
                        tmp_p = os.path.join(UPLOAD_DIR, f"placeholder_{uuid.uuid4().hex}.jpg")
                        blank_img.save(tmp_p)
                        uploaded_paths = [tmp_p]
                        manual_rots = [0]
                        flips_h = [False]
                        flips_v = [False]

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

            print("✅ [STEP 3 OK] All requested documents generated.", flush=True)

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

            print("💾 [STEP 7] Saving submission entry to DB...", flush=True)
            log_submission({
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
            })
            print("✅ [STEP 7 OK] DB Submission log complete.", flush=True)

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


def make_app():
    return tornado.web.Application([
        (r"/", MainHandler),
        (r"/api/login", ApiLoginHandler),
        (r"/api/add_user", ApiAddUserHandler),
        (r"/api/check_auth", ApiCheckAuthHandler),
        (r"/api/workflows", ApiWorkflowsHandler),
        (r"/api/extract_document_data", ApiExtractDocumentDataHandler),
        (r"/api/preview_rotation", ApiPreviewRotationHandler),
        (r"/api/live_render", ApiLiveRenderHandler),
        (r"/api/process_workflow", ApiProcessWorkflowHandler),
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
