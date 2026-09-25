import numpy as np

# Test spherical orbital distribution
n_particles = 1000
radii = np.random.uniform(60, 360, n_particles)

# Symmetrical latitude angle from -pi/2 to +pi/2
# Using cosine distribution so more particles cluster around the orbital plane (equator)
# while still richly populating the upper and lower hemispheres!
u = np.random.uniform(-1, 1, n_particles)
lat = np.arcsin(u) * 0.75 # [-67.5 deg, +67.5 deg] covers both top and bottom beautifully!

theta = np.random.uniform(0, 2*np.pi, n_particles)

x = radii * np.cos(lat) * np.sin(theta)
y = radii * np.sin(lat)
z = radii * np.cos(lat) * np.cos(theta)

# Tilt by 14 degrees
tilt = np.radians(14.0)
y_tilt = y * np.cos(tilt) - z * np.sin(tilt)
z_tilt = y * np.sin(tilt) + z * np.cos(tilt)

print("Y distribution:")
print("Min Y:", np.min(y_tilt))
print("Max Y:", np.max(y_tilt))
print("Mean Y:", np.mean(y_tilt))
print("Particles above center (Y > 0):", np.sum(y_tilt > 0), "out of", n_particles)
print("Particles below center (Y < 0):", np.sum(y_tilt < 0), "out of", n_particles)

# Foreground particles:
front = z_tilt > 0
print("\nForeground particles (Z > 0):")
print("Particles in front:", np.sum(front))
print("Foreground Y above center:", np.sum((y_tilt > 0) & front))
print("Foreground Y below center:", np.sum((y_tilt < 0) & front))
