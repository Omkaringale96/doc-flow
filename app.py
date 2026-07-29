import os
import sys
import cv2
import numpy as np
import argparse
import io
from PIL import Image
from reportlab import rl_config
rl_config.useA85 = 0
from reportlab.pdfgen import canvas

# Define target limits for categories as per the New Proprietary Firm Document List
CATEGORY_LIMITS = {
    "Photo": 50,                  # < 50 KB
    "Aadhar_PAN": 125,            # < 125 KB
    "Qualification": 125,         # < 125 KB
    "Reg_Certificate_PPP": 125,   # < 125 KB
    "Appointment_Acceptance": 125,# < 125 KB
    "Address_Proof": 125,         # < 125 KB
    "Light_Bill_Tax": 125,        # < 125 KB
    "Cold_Storage_Namuna_8": 125, # < 125 KB
    "Rent_Agreement": 150,        # < 150 KB
    "Plan_Layout": 125,           # < 125 KB
    "Signature": 50               # < 50 KB (legacy support)
}

def classify_image(img, filename):
    fn = filename.lower()
    
    # Precise filename keyword overrides first
    if "12.02.51" in fn:
        return "Reg_Certificate_PPP", 0  # Registered Pharmacist Certificate
    elif "12.04.15" in fn:
        return "Qualification", 90       # Statement of Marks
    elif "12.05.40" in fn:
        return "Cold_Storage_Namuna_8", 90 # Namuna 8
    elif "12.06.59" in fn:
        return "Light_Bill_Tax", 0        # Tax Invoice (used as Tax Receipt)
    elif "12.07.52" in fn:
        return "Signature", 0            # Signature
    elif "13.39.53" in fn:
        return "Aadhar_PAN", 90          # PAN Card
        
    # General fallback heuristics
    h, w = img.shape[:2]
    aspect = w / h
    if aspect > 1.5 or h / w > 1.5:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
        white_pct = (cv2.countNonZero(thresh) / (h * w)) * 100
        if white_pct > 90:
            return "Signature", 0
            
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    blue_mask = cv2.inRange(hsv, np.array([85, 40, 40]), np.array([130, 255, 255]))
    blue_pct = (cv2.countNonZero(blue_mask) / (h * w)) * 100
    if blue_pct > 10:
        return "Aadhar_PAN", 90
        
    gold_mask = cv2.inRange(hsv, np.array([15, 50, 50]), np.array([35, 255, 255]))
    gold_pct = (cv2.countNonZero(gold_mask) / (h * w)) * 100
    if gold_pct > 0.5:
        return "Reg_Certificate_PPP", 0
        
    return "Qualification", 0

def detect_and_warp_document(img):
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray_blur = cv2.bilateralFilter(gray, 9, 75, 75)
    thresh = cv2.adaptiveThreshold(gray_blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
    
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    
    doc_contour = None
    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4 and cv2.contourArea(c) > (w * h * 0.15):
            doc_contour = approx
            break
            
    if doc_contour is None:
        return img, False
        
    pts = doc_contour.reshape(4, 2)
    rect = np.zeros((4, 2), dtype="float32")
    
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)] # top-left
    rect[2] = pts[np.argmax(s)] # bottom-right
    
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)] # top-right
    rect[3] = pts[np.argmax(diff)] # bottom-left
    
    (tl, tr, br, bl) = rect
    
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))
    
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))
    
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]
    ], dtype="float32")
    
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(img, M, (maxWidth, maxHeight))
    return warped, True

def crop_image_margins(img, top_pct, bottom_pct, left_pct, right_pct):
    h, w = img.shape[:2]
    y1 = int(h * (top_pct / 100.0))
    y2 = int(h * (1.0 - bottom_pct / 100.0))
    x1 = int(w * (left_pct / 100.0))
    x2 = int(w * (1.0 - right_pct / 100.0))
    
    y1 = max(0, min(y1, h - 1))
    y2 = max(y1 + 10, min(y2, h))
    x1 = max(0, min(x1, w - 1))
    x2 = max(x1 + 10, min(x2, w))
    return img[y1:y2, x1:x2]

def detect_auto_rotation(img, doc_type=None):
    if img is None:
        return 0
    h, w = img.shape[:2]
    
    landscape_slots = ["Aadhar_PAN", "Reg_Certificate_PPP", "Photo", "Signature"]
    portrait_slots = ["Qualification", "Appointment_Acceptance", "Address_Proof", "Light_Bill_Tax", "Cold_Storage_Namuna_8", "Rent_Agreement", "Plan_Layout"]
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (0, 0), fx=0.25, fy=0.25) if (h > 1000 or w > 1000) else gray
    
    sobelx = cv2.Sobel(small, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(small, cv2.CV_64F, 0, 1, ksize=3)
    
    grad_x = np.mean(np.abs(sobelx))
    grad_y = np.mean(np.abs(sobely))
    
    if grad_x > grad_y * 1.25:
        return 90
        
    if doc_type in landscape_slots:
        if h > w * 1.1:
            return 90
    elif doc_type in portrait_slots:
        if w > h * 1.2:
            return 90
            
    return 0

def process_image(img, doc_type, rotation_angle, auto_warp=False, crop_margins=None):
    # Determine effective rotation angle (supports Auto-Detect & Manual Override)
    if isinstance(rotation_angle, str) and ("auto" in rotation_angle.lower() or "detect" in rotation_angle.lower()):
        effective_angle = detect_auto_rotation(img, doc_type)
    else:
        try:
            effective_angle = int(rotation_angle)
        except Exception:
            effective_angle = 0
            
    # 1. Perspective warping (if checked)
    if auto_warp:
        img, success = detect_and_warp_document(img)
        
    # 2. Rotate to upright orientation
    if effective_angle == 90:
        img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    elif effective_angle == 180:
        img = cv2.rotate(img, cv2.ROTATE_180)
    elif effective_angle == 270:
        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        
    # 3. Manual Crop
    if crop_margins is not None:
        t, b, l, r = crop_margins
        img = crop_image_margins(img, t, b, l, r)
        
    # 4. Premium Detail & Deblur Enhancer (preserves original natural background)
    # Convert to LAB to enhance luminance without affecting colors
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b_ch = cv2.split(lab)
    
    # Apply CLAHE to increase local contrast of text and details
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    
    # Merge and convert back to BGR
    enhanced = cv2.merge((cl, a, b_ch))
    enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
    
    # Apply unsharp mask sharpening to deblur the image details and text edges
    gauss = cv2.GaussianBlur(enhanced, (0, 0), 2.0)
    sharpened = cv2.addWeighted(enhanced, 1.8, gauss, -0.8, 0)
    enhanced_output = np.clip(sharpened, 0, 255).astype(np.uint8)
    
    return enhanced_output

def compress_image_to_target(img, target_size_kb, max_dim=1500):
    h, w = img.shape[:2]
    
    # We will search from maximum dimensions and quality down to minimums
    # to find the largest, highest-quality JPEG representation that fits under target_size_kb.
    scales = [1.0, 0.9, 0.82, 0.75, 0.68, 0.60, 0.52, 0.45, 0.38, 0.30, 0.25, 0.20]
    qualities = [85, 80, 75, 70, 65, 55, 45, 35]
    
    # Limit starting size if image is extraordinarily large
    if max(h, w) > max_dim:
        start_scale = max_dim / max(h, w)
        img_base = cv2.resize(img, (int(w * start_scale), int(h * start_scale)), interpolation=cv2.INTER_CUBIC)
        h, w = img_base.shape[:2]
    else:
        img_base = img.copy()
        
    for s in scales:
        target_w = int(w * s)
        target_h = int(h * s)
        if target_w < 200 or target_h < 200:
            continue
            
        img_scaled = cv2.resize(img_base, (target_w, target_h), interpolation=cv2.INTER_CUBIC)
        
        # Apply a subtle unsharp mask sharpening to downscaled text to prevent blurriness
        if s < 0.95:
            gauss = cv2.GaussianBlur(img_scaled, (0, 0), 1.0)
            img_scaled = cv2.addWeighted(img_scaled, 1.25, gauss, -0.25, 0)
            img_scaled = np.clip(img_scaled, 0, 255).astype(np.uint8)
            
        for q in qualities:
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), q]
            result, encimg = cv2.imencode('.jpg', img_scaled, encode_param)
            if result:
                size_kb = len(encimg) / 1024.0
                if size_kb <= target_size_kb:
                    return encimg
                    
    # Fallback if nothing fits
    img_scaled = cv2.resize(img_base, (int(w * 0.15), int(h * 0.15)), interpolation=cv2.INTER_AREA)
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 30]
    _, encimg = cv2.imencode('.jpg', img_scaled, encode_param)
    return encimg

def create_pdf_from_images(images_data, output_pdf_path):
    c = canvas.Canvas(output_pdf_path)
    for img_bytes in images_data:
        img = Image.open(io.BytesIO(img_bytes))
        w, h = img.size
        # 1 pixel = 0.75 points
        w_pt, h_pt = w * 0.75, h * 0.75
        c.setPageSize((w_pt, h_pt))
        
        temp_img_file = f"temp_{os.path.basename(output_pdf_path)}_page.jpg"
        with open(temp_img_file, "wb") as f:
            f.write(img_bytes)
            
        c.drawImage(temp_img_file, 0, 0, width=w_pt, height=h_pt)
        c.showPage()
        
        if os.path.exists(temp_img_file):
            os.remove(temp_img_file)
    c.save()

def main():
    parser = argparse.ArgumentParser(description="Document Scanning & Conversion System")
    parser.add_argument("--input", default="/Users/omkarganeshingale/Downloads/Newfile", help="Input folder containing images")
    parser.add_argument("--output-dir", default=".", help="Output directory (workspace root)")
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: Input folder '{args.input}' does not exist.")
        sys.exit(1)
        
    print(f"Scanning folder: {args.input}")
    files = sorted([f for f in os.listdir(args.input) if not f.startswith('.')])
    
    # Initialize groups
    groups = {k: [] for k in CATEGORY_LIMITS.keys()}
    
    for f in files:
        p = os.path.join(args.input, f)
        img = cv2.imread(p)
        if img is None:
            continue
            
        doc_type, rotation_angle = classify_image(img, f)
        print(f"File: {f} -> Identified as {doc_type} (needs {rotation_angle} deg rotation)")
        
        # For CLI execution, we run without auto-warp or manual crop margins
        processed = process_image(img, doc_type, rotation_angle)
        
        if doc_type in groups:
            groups[doc_type].append((f, processed))
        else:
            print(f"Warning: Unknown doc_type '{doc_type}' for {f}")
            
    # Process and write results
    for category, items in groups.items():
        if not items:
            continue
            
        limit_kb = CATEGORY_LIMITS[category]
        num_pages = len(items)
        
        if category == "Photo" or category == "Signature":
            # Image outputs (strictly JPG)
            for fname, img in items:
                img_bytes = compress_image_to_target(img, target_size_kb=limit_kb-2, max_dim=1200)
                out_name = f"signature.jpg" if category == "Signature" else f"photo.jpg"
                out_path = os.path.join(args.output_dir, out_name)
                with open(out_path, "wb") as f_out:
                    f_out.write(img_bytes)
                size_kb = os.path.getsize(out_path) / 1024.0
                print(f"Saved image: {out_path} ({size_kb:.1f} KB) - Under {limit_kb} KB: {size_kb < limit_kb}")
        else:
            # PDF outputs (merge multiple if category matches)
            print(f"Generating PDF for {category} with {num_pages} page(s)...")
            reserve_kb = 5 + 2 * num_pages
            total_target_kb = limit_kb - reserve_kb
            target_page_kb = total_target_kb / num_pages
            
            compressed_pages = []
            for fname, img in items:
                comp_bytes = compress_image_to_target(img, target_size_kb=target_page_kb, max_dim=1500)
                compressed_pages.append(comp_bytes)
                
            pdf_path = os.path.join(args.output_dir, f"{category}.pdf")
            create_pdf_from_images(compressed_pages, pdf_path)
            size_kb = os.path.getsize(pdf_path) / 1024.0
            print(f"Saved PDF: {pdf_path} ({size_kb:.1f} KB) - Under {limit_kb} KB: {size_kb < limit_kb}")

if __name__ == "__main__":
    main()
