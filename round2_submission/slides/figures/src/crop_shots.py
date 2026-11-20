"""Crop the key replay screenshots to their banner region for slide 10 (run after capture.cjs).
Run: uv run --with pillow python crop_shots.py"""
import os
from PIL import Image
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for n in ["replay-rejected", "replay-verified", "replay-reopened"]:
    Image.open(os.path.join(D, n + ".png")).crop((190, 125, 1730, 790)).save(os.path.join(D, n + "-crop.png"))
print("cropped")
