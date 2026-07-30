import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate(
    "doc-flow-d161b-firebase-adminsdk-fbsvc-7f68650a69.json"
)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()