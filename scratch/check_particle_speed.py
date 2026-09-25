import numpy as np

# In cosmic_depth.vert:
# omega = (0.054 / (1.0 + r / 85.0) + 0.0118) * speedFactor;
# theta = phaseSeed * TAU + timeSeconds * (omega * speedMult);
# x = activeR * cos(latAngle) * sin(theta)
# z = activeR * cos(latAngle) * cos(theta)

# In 1 second of wall time:
# If state == 'IDLE', timeSeconds advances by dt * 0.95 = 0.95 s
# If state == 'WARNING', timeSeconds advances by dt * 0.25 = 0.25 s

for r in [50, 150, 250, 400]:
    omega_calibrated = (0.054 / (1.0 + r / 85.0) + 0.0118)
    # dtheta per wall-second in IDLE:
    dtheta_idle = 0.95 * omega_calibrated
    # tangential velocity (px/s in world space at z=0):
    v_tan_idle = r * dtheta_idle
    print(f"r={r:3d}: omega={omega_calibrated:.4f}, dtheta={np.degrees(dtheta_idle):.2f} deg/s, v_tan={v_tan_idle:.2f} px/s")

print("\nCompared to original uncalibrated omega (0.22 / (1 + r/85) + 0.048):")
for r in [50, 150, 250, 400]:
    omega_orig = (0.22 / (1.0 + r / 85.0) + 0.048)
    dtheta_orig_warning = 0.25 * omega_orig
    v_tan_orig_warning = r * dtheta_orig_warning
    print(f"r={r:3d}: omega_orig={omega_orig:.4f}, dtheta_warning={np.degrees(dtheta_orig_warning):.2f} deg/s, v_tan_warning={v_tan_orig_warning:.2f} px/s")
