import cv2
import numpy as np

cap = cv2.VideoCapture(r"C:\Users\LUSAN\Downloads\Video-20807.mp4")
fps = cap.get(cv2.CAP_PROP_FPS)

# Extract 10 consecutive frames at t=60s (2 seconds of video at 5 fps)
frames = []
for i in range(10):
    cap.set(cv2.CAP_PROP_POS_MSEC, (60.0 + i * 0.2) * 1000)
    ret, f = cap.read()
    if ret:
        frames.append(f)
        cv2.imwrite(f"d:/EV/scratch/video_seq_{i:02d}.png", f)

print(f"Extracted {len(frames)} frames from Video-20807")

# Let's compute optical flow between frame 0 and frame 4 (0.8 seconds apart)
g0 = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)
g4 = cv2.cvtColor(frames[4], cv2.COLOR_BGR2GRAY)

flow = cv2.calcOpticalFlowFarneback(g0, g4, None, 0.5, 3, 15, 3, 5, 1.2, 0)
mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])

# Look at flow directions in different quadrants around the core center
# Find the bright center
min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(g0)
cx, cy = max_loc
print(f"Core center in video: ({cx}, {cy})")

# Quadrants:
# Top (above core):
top_mask = (mag > 1.0) & (np.abs(np.arange(g0.shape[0])[:, None] - cy) > 50) & (np.arange(g0.shape[0])[:, None] < cy)
bottom_mask = (mag > 1.0) & (np.abs(np.arange(g0.shape[0])[:, None] - cy) > 50) & (np.arange(g0.shape[0])[:, None] > cy)
left_mask = (mag > 1.0) & (np.arange(g0.shape[1])[None, :] < cx - 50)
right_mask = (mag > 1.0) & (np.arange(g0.shape[1])[None, :] > cx + 50)

print("Top flow dx, dy:", np.mean(flow[top_mask, 0]), np.mean(flow[top_mask, 1]))
print("Bottom flow dx, dy:", np.mean(flow[bottom_mask, 0]), np.mean(flow[bottom_mask, 1]))
print("Left flow dx, dy:", np.mean(flow[left_mask, 0]), np.mean(flow[left_mask, 1]))
print("Right flow dx, dy:", np.mean(flow[right_mask, 0]), np.mean(flow[right_mask, 1]))
