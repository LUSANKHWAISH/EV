import cv2
import numpy as np

# Load frame_01 and frame_02 from calm_speed_test
f1 = cv2.imread("d:/EV/scratch/calm_speed_test/frame_01.png")
f2 = cv2.imread("d:/EV/scratch/calm_speed_test/frame_02.png")

# Look at regions away from the center nucleus (e.g. x in [1200, 1800], y in [200, 800])
# where only cosmic depth particles exist!
crop1 = f1[200:800, 1200:1800]
crop2 = f2[200:800, 1200:1800]

g1 = cv2.cvtColor(crop1, cv2.COLOR_BGR2GRAY)
g2 = cv2.cvtColor(crop2, cv2.COLOR_BGR2GRAY)

diff = cv2.absdiff(crop1, crop2)
print("Mean diff in particle-only outer region:", np.mean(diff))

# Detect particle spots in crop1 and crop2
params = cv2.SimpleBlobDetector_Params()
params.filterByColor = True
params.blobColor = 255
params.filterByArea = True
params.minArea = 2
params.maxArea = 1000

detector = cv2.SimpleBlobDetector_create(params)
kp1 = detector.detect(g1)
kp2 = detector.detect(g2)

print(f"Detected {len(kp1)} particles in frame 1, {len(kp2)} in frame 2")

# For each particle in kp1, find the closest matching particle in kp2
displacements = []
for p1 in kp1:
    best_dist = 999.0
    best_p2 = None
    for p2 in kp2:
        d = np.hypot(p1.pt[0] - p2.pt[0], p1.pt[1] - p2.pt[1])
        if d < best_dist and abs(p1.size - p2.size) < 5:
            best_dist = d
            best_p2 = p2
    if best_dist < 15.0: # matched same particle moving smoothly
        dx = best_p2.pt[0] - p1.pt[0]
        dy = best_p2.pt[1] - p1.pt[1]
        displacements.append((dx, dy, best_dist, p1.size))

if displacements:
    dxs = [d[0] for d in displacements]
    dys = [d[1] for d in displacements]
    speeds = [d[2] for d in displacements]
    sizes = [d[3] for d in displacements]
    print(f"Matched {len(displacements)} particles:")
    print(f"Average dx: {np.mean(dxs):.3f} px/s (positive means moving LEFT TO RIGHT)")
    print(f"Average dy: {np.mean(dys):.3f} px/s")
    print(f"Average speed: {np.mean(speeds):.3f} px/s")
    print(f"Particle sizes min/mean/max: {np.min(sizes):.1f} / {np.mean(sizes):.1f} / {np.max(sizes):.1f} px")
