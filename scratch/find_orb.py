import cv2
import numpy as np

img = cv2.imread("d:/EV/scratch/ref_video_frame_3.png")
h, w = img.shape[:2]

# The glowing orb is bright cyan/white in the middle of the monitor
# Crop only the monitor area: y in [300, 700], x in [200, 800]
crop = img[300:700, 200:800]
gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
min_v, max_v, min_l, max_l = cv2.minMaxLoc(gray)

orb_x = 200 + max_l[0]
orb_y = 300 + max_l[1]
print(f"Actual glowing orb center: ({orb_x}, {orb_y})")

# Let's save a zoomed crop around the orb and its particles to see how they look and move!
zoom = img[orb_y-250:orb_y+250, orb_x-250:orb_x+250]
cv2.imwrite("d:/EV/scratch/orb_zoom.png", zoom)
print("Saved orb_zoom.png")
