import cv2
import numpy as np

cap = cv2.VideoCapture(r"F:\OneDrive\Videos\NVIDIA\Desktop\Desktop 2026.09.21 - 23.07.10.01.mp4")
fps = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
duration = total_frames / fps
print(f"Video FPS: {fps}, Total Frames: {total_frames}, Duration: {duration:.2f}s")

# Let's read frames around t=10s (IDLE) and t=22s (WARNING)
cap.set(cv2.CAP_PROP_POS_MSEC, 10000)
ret, f_idle_1 = cap.read()
cap.set(cv2.CAP_PROP_POS_MSEC, 11000)
ret, f_idle_2 = cap.read()

cap.set(cv2.CAP_PROP_POS_MSEC, 21000)
ret, f_warn_1 = cap.read()
cap.set(cv2.CAP_PROP_POS_MSEC, 22000)
ret, f_warn_2 = cap.read()

# Save them to scratch
cv2.imwrite(r"d:\EV\scratch\video_idle_10s.png", f_idle_1)
cv2.imwrite(r"d:\EV\scratch\video_idle_11s.png", f_idle_2)
cv2.imwrite(r"d:\EV\scratch\video_warn_21s.png", f_warn_1)
cv2.imwrite(r"d:\EV\scratch\video_warn_22s.png", f_warn_2)

# Measure particle motion in outer region for both IDLE and WARNING in user's video
crop_i1 = f_idle_1[200:800, 1200:1800]
crop_i2 = f_idle_2[200:800, 1200:1800]
crop_w1 = f_warn_1[200:800, 1200:1800]
crop_w2 = f_warn_2[200:800, 1200:1800]

print("Video IDLE outer diff:", np.mean(cv2.absdiff(crop_i1, crop_i2)))
print("Video WARNING outer diff:", np.mean(cv2.absdiff(crop_w1, crop_w2)))
