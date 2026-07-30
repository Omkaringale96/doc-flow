import os
import cloudinary

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_file = os.path.join(BASE_DIR, ".env")

if os.path.exists(env_file):
    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip().strip("'\"")
    except Exception as e:
        print(f"⚠️ Error reading .env file: {e}", flush=True)

try:
    cloudinary_url = os.getenv("CLOUDINARY_URL")
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    api_secret = os.getenv("CLOUDINARY_API_SECRET")

    if cloudinary_url:
        cloudinary.config(cloudinary_url=cloudinary_url, secure=True)
        print("✅ Cloudinary configured successfully via CLOUDINARY_URL.", flush=True)
    elif cloud_name and api_key and api_secret:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True
        )
        print("✅ Cloudinary configured successfully via API credentials.", flush=True)
    else:
        print("ℹ️ Cloudinary credentials not configured in environment. Using local ZIP package links.", flush=True)
except Exception as e:
    print(f"⚠️ Cloudinary configuration error: {e}", flush=True)