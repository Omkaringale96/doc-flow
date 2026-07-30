import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

db = None

try:
    if "FIREBASE_CREDENTIALS" in os.environ:
        raw_cred = os.environ["FIREBASE_CREDENTIALS"]
        firebase_credentials = json.loads(raw_cred)
        cred = credentials.Certificate(firebase_credentials)

        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)

        db = firestore.client()
        print("✅ Firebase Firestore initialized successfully.", flush=True)
    else:
        print("⚠️ FIREBASE_CREDENTIALS env var not set. Firestore logging disabled.", flush=True)
except Exception as e:
    print(f"⚠️ Firebase initialization error: {e}", flush=True)
    db = None