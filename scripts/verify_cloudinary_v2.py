import os
import django
from django.conf import settings
from cloudinary.uploader import upload
from cloudinary.api import resource
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

def verify_cloudinary():
    print("Verifying Cloudinary configuration...")
    
    # Check if settings are loaded
    # Cloudinary settings might be lazy loaded, access them directly
    cloud_name = settings.CLOUDINARY_STORAGE.get('CLOUD_NAME')
    api_key = settings.CLOUDINARY_STORAGE.get('API_KEY')
    api_secret = settings.CLOUDINARY_STORAGE.get('API_SECRET')

    if all([cloud_name, api_key, api_secret]):
        print(f"✅ Cloudinary credentials found in settings.")
        print(f"   Cloud Name: {cloud_name}")
        print(f"   API Key: {api_key[:4]}...{api_key[-4:]}")
    else:
        print("❌ Missing Cloudinary credentials in settings.")
        return

    # Create a dummy image file
    dummy_image_path = 'test_image.txt'
    with open(dummy_image_path, 'w') as f:
        f.write('This is a test file to verify Cloudinary upload.')

    try:
        print("\nAttempting to upload a test file...")
        # Upload the file
        response = upload(dummy_image_path, public_id='test_upload_verify_v2', resource_type='raw')
        
        print(f"✅ Upload successful!")
        print(f"   Public ID: {response.get('public_id')}")
        print(f"   URL: {response.get('url')}")
        
        # Clean up local file
        os.remove(dummy_image_path)
        
        # Verify resource exists - optional but good check
        # res = resource('test_upload_verify_v2', resource_type='raw')
        # print(f"✅ Resource verified on Cloudinary: {res.get('secure_url')}")

    except Exception as e:
        print(f"\n❌ Cloudinary verification failed: {e}")
        if os.path.exists(dummy_image_path):
            os.remove(dummy_image_path)

if __name__ == '__main__':
    verify_cloudinary()
