import os
import glob
import json
import firebase_admin
from firebase_admin import credentials, firestore

db = None
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    cred = None
    if "FIREBASE_CREDENTIALS" in os.environ:
        raw_cred = os.environ["FIREBASE_CREDENTIALS"]
        try:
            firebase_credentials = json.loads(raw_cred)
            cred = credentials.Certificate(firebase_credentials)
            print("🔑 Loaded Firebase credentials from FIREBASE_CREDENTIALS env var.", flush=True)
        except Exception as e:
            print(f"⚠️ Error parsing FIREBASE_CREDENTIALS env var: {e}", flush=True)

    if cred is None:
        json_candidates = glob.glob(os.path.join(BASE_DIR, "doc-flow-*.json")) + glob.glob(os.path.join(BASE_DIR, "*firebase*.json"))
        if json_candidates:
            key_path = json_candidates[0]
            cred = credentials.Certificate(key_path)
            print(f"🔑 Loaded Firebase service account key from: {os.path.basename(key_path)}", flush=True)

    if cred:
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)

        db = firestore.client()
        print("✅ Firebase Firestore initialized successfully.", flush=True)
    else:
        print("⚠️ No Firebase credentials or service account JSON found. Remote Firestore logging disabled.", flush=True)

except Exception as e:
    print(f"⚠️ Firebase initialization error: {e}", flush=True)
    db = None