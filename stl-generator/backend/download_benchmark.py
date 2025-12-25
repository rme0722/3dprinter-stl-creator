import os
import io
import zipfile
import urllib.request
from pathlib import Path

# Config
DATASET_URL = "https://github.com/openMVG/ImageDataset_SceauxCastle/archive/refs/heads/master.zip"
TARGET_DIR = Path(__file__).parent.parent / "validation_photos" / "sceaux_castle"

def download_and_extract():
    print(f"Downloading benchmark dataset from: {DATASET_URL}")
    print("This may take a moment...")
    
    try:
        # Download
        with urllib.request.urlopen(DATASET_URL) as response:
            if response.status != 200:
                print(f"Failed to download: HTTP {response.status}")
                return
            
            data = response.read()
            print(f"Download complete! Size: {len(data) / 1024 / 1024:.2f} MB")
            
            # Extract
            print("Extracting...")
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                # The zip contains a root folder "ImageDataset_SceauxCastle-master/images"
                # We want to extract just the images to our target dir
                
                if not TARGET_DIR.exists():
                    os.makedirs(TARGET_DIR)
                    
                count = 0
                for file_info in z.infolist():
                    if file_info.filename.endswith(('.jpg', '.JPG', '.png')):
                        # Strip the top directory
                        filename = os.path.basename(file_info.filename)
                        if not filename: continue
                        
                        target_path = TARGET_DIR / filename
                        with open(target_path, "wb") as f:
                            f.write(z.read(file_info))
                        count += 1
                        
                print(f"Success! Extracted {count} images to:")
                print(f"{TARGET_DIR.absolute()}")
                print("\nYou can now create a new job in the UI and drag-and-drop these photos.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    download_and_extract()
