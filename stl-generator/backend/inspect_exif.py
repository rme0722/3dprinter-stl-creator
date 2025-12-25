import piexif
from pathlib import Path
import cv2

path = Path(r"c:\Projects\3d_Printer_Converter\storage\inputs\job_2fd18eedf3d8\01.JPG")
img = cv2.imread(str(path))
h, w = img.shape[:2]

exif_dict = piexif.load(str(path))
exif = exif_dict.get("Exif", {})
focal_rat = exif.get(piexif.ExifIFD.FocalLength)
focal_35 = exif.get(piexif.ExifIFD.FocalLengthIn35mmFilm)
f_plane_res = exif.get(piexif.ExifIFD.FocalPlaneXResolution)
f_plane_unit = exif.get(piexif.ExifIFD.FocalPlaneResolutionUnit)

print(f"Image Resolution: {w}x{h}")
print(f"FocalLength (rational): {focal_rat}")
print(f"FocalLengthIn35mmFilm: {focal_35}")
print(f"FocalPlaneXResolution: {f_plane_res}")
print(f"FocalPlaneResolutionUnit: {f_plane_unit}")

if focal_35:
    f_px_35 = (focal_35 / 36.0) * w
    print(f"Focal Length (via 35mm): {f_px_35} px")

if focal_rat:
    f_mm = focal_rat[0] / focal_rat[1]
    print(f"Focal Length (mm): {f_mm} mm")
    if f_plane_res and f_plane_unit == 2: # Inches
        f_px_res = (f_mm / 25.4) * (f_plane_res[0] / f_plane_res[1])
        print(f"Focal Length (via FocalPlaneRes): {f_px_res} px")
