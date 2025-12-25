import piexif
from pathlib import Path
import os
import sys

# Get the storage path from config or use default
storage_path = "C:/Projects/3d_Printer_Converter/storage/inputs"
job_id = "job_e7d155912df7" # From logs

def check_exif():
    job_dir = Path(storage_path) / job_id
    if not job_dir.exists():
        print(f"Directory {job_dir} not found.")
        return

    images = list(job_dir.glob("*.jpg")) + list(job_dir.glob("*.png"))
    if not images:
        print("No images found.")
        return

    img_path = images[0]
    print(f"Checking EXIF for {img_path}")
    try:
        exif_dict = piexif.load(str(img_path))
        exif = exif_dict.get("Exif", {})
        
        tags = {
            "FocalLength": piexif.ExifIFD.FocalLength,
            "FocalLengthIn35mmFilm": piexif.ExifIFD.FocalLengthIn35mmFilm,
            "FocalPlaneXResolution": piexif.ExifIFD.FocalPlaneXResolution,
            "FocalPlaneYResolution": piexif.ExifIFD.FocalPlaneYResolution,
            "FocalPlaneResolutionUnit": piexif.ExifIFD.FocalPlaneResolutionUnit,
            "PixelXDimension": piexif.ExifIFD.PixelXDimension,
            "PixelYDimension": piexif.ExifIFD.PixelYDimension,
        }
        
        for name, tag in tags.items():
            val = exif.get(tag)
            print(f"{name}: {val}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_exif()
