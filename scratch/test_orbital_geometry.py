import numpy as np


# Simulate 3D orbits around core (0,0,0)
# We want:
# 1. Core at (0, 0, 0)
# 2. Orbits are closed 3D ellipses/circles around the core
# 3. Viewed from front with realistic perspective tilt
# 4. Particles move smoothly: back -> left -> front -> right -> back (or counter-clockwise)
# 5. Foreground (z > 0) moves left-to-right

def orbital_pos(r, inclination, yaw, theta):
    # Orbit in its own plane:
    x_plane = r * np.sin(theta)
    z_plane = r * np.cos(theta)
    y_plane = 0.0
    
    # Incline around X-axis:
    # y' = -z_plane * sin(inc)
    # z' =  z_plane * cos(inc)
    y_inc = -z_plane * np.sin(inclination)
    z_inc =  z_plane * np.cos(inclination)
    x_inc =  x_plane
    
    # Yaw around Y-axis (optional tilt of orbital plane orientation):
    x = x_inc * np.cos(yaw) + z_inc * np.sin(yaw)
    y = y_inc
    z = -x_inc * np.sin(yaw) + z_inc * np.cos(yaw)
    
    return x, y, z

# Let's test a viewing perspective tilt:
view_pitch = np.radians(28.0) # 28 degrees pitch down gives a beautiful 3D elliptical depth

# For a particle at r=200, inc=15 deg, yaw=10 deg:
thetas = np.linspace(0, 2*np.pi, 100)
positions = []
for th in thetas:
    x, y, z = orbital_pos(200, np.radians(15), np.radians(10), th)
    # Apply view pitch
    y_view = y * np.cos(view_pitch) - z * np.sin(view_pitch)
    z_view = y * np.sin(view_pitch) + z * np.cos(view_pitch)
    positions.append((x, y_view, z_view))

positions = np.array(positions)
print("Orbit bounds on screen:")
print(f"X range: [{positions[:,0].min():.1f}, {positions[:,0].max():.1f}]")
print(f"Y range: [{positions[:,1].min():.1f}, {positions[:,1].max():.1f}]")
print(f"Z range: [{positions[:,2].min():.1f}, {positions[:,2].max():.1f}]")

# Check direction of motion when z_view > 0 (foreground):
front_mask = positions[:, 2] > 0
print(f"Points in foreground: {np.sum(front_mask)} / {len(thetas)}")
# Check if dx/dtheta > 0 in foreground
dtheta = thetas[1] - thetas[0]
dx = np.diff(positions[:, 0])
front_dx = dx[front_mask[:-1]]
print(f"Foreground dx mean: {np.mean(front_dx):.3f} (positive means LEFT TO RIGHT)")
