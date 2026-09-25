import re

path = 'd:/EV/prototypes/cinematic_v4/qml/StarkArcReactorCore.qml'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# Pattern for "rgba(r, g, b, a)"
def repl(m):
    r, g, b, a = m.group(1), m.group(2), m.group(3), m.group(4)
    rf = float(r) / 255.0
    gf = float(g) / 255.0
    bf = float(b) / 255.0
    af = float(a)
    return f"Qt.rgba({rf:.2f}, {gf:.2f}, {bf:.2f}, {af:.2f})"

# Match "rgba(0, 240, 255, 0.15)" with or without quotes
new_text = re.sub(r'"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([0-9.]+)\)"', repl, text)

with open(path, 'w', encoding='utf-8') as f:
    f.write(new_text)

print("Successfully replaced all rgba strings in StarkArcReactorCore.qml")
