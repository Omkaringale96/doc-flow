import os
import cloudinary

try:
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    api_secret = os.getenv("CLOUDINARY_API_SECRET")

    if cloud_name and api_key and api_secret:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True
        )
        print("✅ Cloudinary configured successfully.", flush=True)
    else:
        print("⚠️ Cloudinary environment variables missing. Direct Cloudinary upload disabled.", flush=True)
except Exception as e:
    print(f"⚠️ Cloudinary configuration error: {e}", flush=True)