import numpy as np

# Test 3D Keplerian orbits with various inclinations
# We want:
# 1. Closed 3D orbits centered at (0, 0, 0)
# 2. Visibly rotating and curving around the core (both X and Y move!)
# 3. 3D depth: small when z < 0 (back), big when z > 0 (front)
# 4. Foreground motion sweeps generally from left to right

def get_orbit_pos(r, inc, yaw, theta, pitch_view=np.radians(15)):
    # Orbit in plane:
    # We want counter-clockwise in XZ plane when inc=0 so foreground (z>0) moves left-to-right (dx>0)
    # At inc=0, yaw=0:
    # x = r * sin(theta), z = r * cos(theta), y = 0
    # dx/dtheta = r * cos(theta) > 0 when z > 0 (front)!
    x_p = r * np.sin(theta)
    z_p = r * np.cos(theta)
    y_p = 0.0
    
    # Incline plane by angle inc around X axis:
    # y' = -z_p * sin(inc)
    # z' =  z_p * cos(inc)
    # x' =  x_p
    x_i = x_p
    y_i = -z_p * np.sin(inc)
    z_i =  z_p * np.cos(inc)
    
    # Rotate by yaw around Y axis:
    x_y =  x_i * np.cos(yaw) + z_i * np.sin(yaw)
    y_y =  y_i
    z_y = -x_i * np.sin(yaw) + z_i * np.cos(yaw)
    
    # View pitch (pitch down towards viewer):
    x_v = x_y
    y_v = y_y * np.cos(pitch_view) - z_y * np.sin(pitch_view)
    z_v = y_y * np.sin(pitch_view) + z_y * np.cos(pitch_view)
    
    return x_v, y_v, z_v

# Test 20 particles with different inclinations:
thetas = np.linspace(0, 2*np.pi, 100)
for inc_deg in [-45, -30, -15, 0, 15, 30, 45]:
    inc = np.radians(inc_deg)
    yaw = np.radians(inc_deg * 0.5) # coupled yaw for natural gyroscopic tilt
    r = 200.0
    
    traj = [get_orbit_pos(r, inc, yaw, th) for th in thetas]
    traj = np.array(traj)
    
    dx_screen = np.ptp(traj[:, 0])
    dy_screen = np.ptp(traj[:, 1])
    dz_screen = np.ptp(traj[:, 2])
    
    front = traj[:, 2] > 0
    dx_front = np.diff(traj[:, 0])[front[:-1]]
    
    print(f"Inc={inc_deg:+3d} deg: Screen dX={dx_screen:.1f}, dY={dy_screen:.1f}, dZ={dz_screen:.1f} | Front dx mean={np.mean(dx_front):.2f}")
