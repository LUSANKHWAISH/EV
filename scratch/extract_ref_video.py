import cv2

cap = cv2.VideoCapture(r"C:\Users\LUSAN\Downloads\Video-20807.mp4")
fps = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
duration = total_frames / fps
print(f"Video-20807: FPS={fps}, Total Frames={total_frames}, Duration={duration:.2f}s")

# Extract 4 frames across the video
timestamps = [0.5, duration * 0.25, duration * 0.5, duration * 0.75]
for i, ts in enumerate(timestamps):
    cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
    ret, frame = cap.read()
    if ret:
        cv2.imwrite(f"d:/EV/scratch/ref_video_frame_{i+1}.png", frame)
        print(f"Saved ref_video_frame_{i+1}.png at {ts:.2f}s")
