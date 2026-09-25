import cv2
import numpy as np

img = cv2.imread("d:/EV/scratch/ref_video_frame_3.png")

# Let's find the brightest point in the lower half of the monitor: y in [400, 700], x in [300, 700]
crop = img[400:700, 300:700]
gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
min_v, max_v, min_l, max_l = cv2.minMaxLoc(gray)

cx = 300 + max_l[0]
cy = 400 + max_l[1]
print(f"Correct orb center: ({cx}, {cy})")

zoom = img[cy-200:cy+200, cx-200:cx+200]
cv2.imwrite("d:/EV/scratch/orb_centered.png", zoom)

# Now let's extract 5 frames of this exact crop across 1 second to see the trajectory of individual particles!
cap = cv2.VideoCapture(r"C:\Users\LUSAN\Downloads\Video-20807.mp4")
crops = []
for i in range(5):
    cap.set(cv2.CAP_PROP_POS_MSEC, (60.0 + i * 0.2) * 1000)
    ret, f = cap.read()
    if ret:
        c = f[cy-200:cy+200, cx-200:cx+200]
        crops.append(c)
        cv2.imwrite(f"d:/EV/scratch/orb_crop_{i}.png", c)

# Let's compute optical flow on this centered crop
g0 = cv2.cvtColor(crops[0], cv2.COLOR_BGR2GRAY)
g4 = cv2.cvtColor(crops[4], cv2.COLOR_BGR2GRAY)
flow = cv2.calcOpticalFlowFarneback(g0, g4, None, 0.5, 3, 15, 3, 5, 1.2, 0)

# Flow above orb vs below orb vs left vs right:
mask_top = np.zeros_like(g0, dtype=bool)
mask_top[:150, :] = True
mask_bottom = np.zeros_like(g0, dtype=bool)
mask_bottom[250:, :] = True
mask_left = np.zeros_like(g0, dtype=bool)
mask_left[:, :150] = True
mask_right = np.zeros_like(g0, dtype=bool)
mask_right[:, 250:] = True

print("Above orb flow: dx =", np.mean(flow[mask_top, 0]), "dy =", np.mean(flow[mask_top, 1]))
print("Below orb flow: dx =", np.mean(flow[mask_bottom, 0]), "dy =", np.mean(flow[mask_bottom, 1]))
print("Left of orb flow: dx =", np.mean(flow[mask_left, 0]), "dy =", np.mean(flow[mask_left, 1]))
print("Right of orb flow: dx =", np.mean(flow[mask_right, 0]), "dy =", np.mean(flow[mask_right, 1]))
