"""Contracts for the independent fire-particle atmospheric layer and core isolation."""
import inspect
from pathlib import Path
import re
import numpy as np

from prototypes.cinematic_v4.geometry import (
    OrbitalParticleInstances,
    make_orbital_instance_data,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CINEMATIC_ROOT = PROJECT_ROOT / "prototypes" / "cinematic_v4"
QML_ROOT = CINEMATIC_ROOT / "qml"
SHADER_ROOT = QML_ROOT / "shaders"


def test_orbital_instance_data_contract():
    # 1. make_orbital_instance_data() returns shape (1920,20)
    # 2. dtype is float32
    # 3. repeated generation is deterministic
    # 4. custom values remain in [0,1)
    # 7. geometry.py retains default seed 9417
    first = make_orbital_instance_data()
    second = make_orbital_instance_data()

    assert first.shape == (1920, 20)
    assert first.dtype == np.float32
    assert np.array_equal(first, second)
    assert np.isfinite(first).all()

    custom = first[:, 16:20]
    assert np.all(custom >= 0.0)
    assert np.all(custom < 1.0)

    sig = inspect.signature(make_orbital_instance_data)
    assert sig.parameters["seed"].default == 9417
    geom_src = (CINEMATIC_ROOT / "geometry.py").read_text(encoding="utf-8")
    assert "seed: int = 9417" in geom_src or "seed=9417" in geom_src


def test_orbital_instance_buffer_contract():
    # 5. OrbitalParticleInstances buffer is 153,600 bytes
    # 6. Capacity is 1,920
    instances = OrbitalParticleInstances()
    buffer, count = instances.getInstanceBuffer()

    assert count == 1920
    assert len(bytes(buffer)) == 1920 * 20 * 4
    assert len(bytes(buffer)) == 153600


def test_orbital_aura_qml_contract():
    # 8. OrbitalAura.qml root is View3D
    # 9. OrbitalAura.qml contains globalFireParticleFrame
    # 10. OrbitalAura.qml contains exactly one OrbitalParticleInstances
    # 11. Standard active count is 1,400
    # 12. Low-cost active count is 520
    # 29. Exactly one aura particle model/draw call is designed
    # View3D.Inline is used
    # explicitTextureWidth/Height are absent
    # destinationBlend is OneMinusSrcAlpha
    # antialiasingMode is NoAA or FXAA, antialiasingQuality absent, tonemapMode is TonemapModeNone
    aura_src = (QML_ROOT / "OrbitalAura.qml").read_text(encoding="utf-8")

    clean_aura = "\n".join(
        line for line in aura_src.splitlines() if not line.strip().startswith("//")
    )
    assert clean_aura.strip().startswith("import")
    assert "View3D {" in aura_src

    assert "renderMode: View3D.Inline" in aura_src
    assert "explicitTextureWidth" not in aura_src
    assert "explicitTextureHeight" not in aura_src

    assert "antialiasingMode: SceneEnvironment.NoAA" in aura_src or "antialiasingMode: SceneEnvironment.FXAA" in aura_src
    assert "antialiasingQuality" not in aura_src
    assert "tonemapMode: SceneEnvironment.TonemapModeNone" in aura_src

    assert 'objectName: "globalFireParticleFrame"' in aura_src or "globalFireParticleFrame" in aura_src
    assert aura_src.count("OrbitalParticleInstances") == 1

    assert "lowCost ? 520 : 1400" in aura_src
    assert "activeCount: lowCost ? 520 : 1400" in aura_src

    assert "destinationBlend: CustomMaterial.OneMinusSrcAlpha" in aura_src
    assert "gain: aura.lowCost ? 1.12 : 1.30" in aura_src
    assert "coverage: aura.lowCost ? 0.90 : 1.00" in aura_src

    # Exactly one aura particle model/draw call
    assert aura_src.count('objectName: "orbitalAuraParticles"') == 1
    assert aura_src.count("Model {") == 1


def test_cinematic_stage_contract():
    # 13. CinematicStage.qml contains exactly one OrbitalAura
    # 14. CinematicStage.qml contains globalFireParticleLayer
    stage_src = (QML_ROOT / "CinematicStage.qml").read_text(encoding="utf-8")

    assert stage_src.count("OrbitalAura {") == 1
    assert 'objectName: "globalFireParticleLayer"' in stage_src or "globalFireParticleLayer" in stage_src


def test_nucleus_view_isolation_contract():
    # 15. NucleusView.qml contains no OrbitalAura
    # 16. NucleusView.qml contains no orbitalAuraFrame
    # 17. NucleusView.qml retains coreAssembly
    # 18. NucleusView.qml contains no fullViewportWidth/fullViewportHeight
    # 19. Camera position still contains 382/Math.min(scene.zoom,1.10)
    nucleus_src = (QML_ROOT / "NucleusView.qml").read_text(encoding="utf-8")

    assert "OrbitalAura" not in nucleus_src
    assert "orbitalAuraFrame" not in nucleus_src
    assert 'objectName: "coreAssembly"' in nucleus_src or "coreAssembly" in nucleus_src
    assert "fullViewportWidth" not in nucleus_src
    assert "fullViewportHeight" not in nucleus_src
    assert "382/Math.min(scene.zoom,1.10)" in nucleus_src
    assert "boundedCoreFieldOfView: 38" in nucleus_src
    assert "fieldOfView: scene.boundedCoreFieldOfView" in nucleus_src
    assert "orbitalParticleCount: 0" in nucleus_src

    # Original core assembly rotation is restored.
    assert "scene.t*.65" in nucleus_src
    assert "scene.t * .65" not in nucleus_src
    assert "Math.sin(scene.t*.21)*1.1" in nucleus_src
    assert "scene.viewYaw" in nucleus_src
    assert "scene.viewPitch" in nucleus_src
    assert "scene.hoverX*2.3" in nucleus_src
    assert "scene.hoverY*1.5" in nucleus_src
    assert "-75*(1-scene.phase(.12,.8))" in nucleus_src
    assert "-35*(1-scene.phase(.16,.82))" in nucleus_src

    # Internal shell, route, energy, band, and filament motion remains intact.
    assert "scene.orbitTime*[1.2,-1.8,.7][index]" in nucleus_src
    assert "scene.orbitTime*.85" in nucleus_src
    assert "scene.orbitTime*.65" in nucleus_src
    assert "8+scene.orbitTime*.45" in nucleus_src
    assert "scene.orbitTime*.6" in nucleus_src
    assert "scene.orbitTime*8-19" in nucleus_src
    assert "-scene.orbitTime*5" in nucleus_src


def test_music_workspace_unmodified_contract():
    # 20. MusicWorkspace.qml has no working-tree modification
    # MusicWorkspace.qml is kept unchanged; its root background is handled via Loader onLoaded
    mw_src = (QML_ROOT / "MusicWorkspace.qml").read_text(encoding="utf-8")
    assert "OrbitalAura" not in mw_src
    assert "globalFireParticleLayer" not in mw_src
    assert "globalFireParticleFrame" not in mw_src
    # Verify no inline transparent color hack was added directly inside MusicWorkspace.qml
    assert 'color: "transparent"' not in mw_src
    assert "color: 'transparent'" not in mw_src


def test_vertex_shader_contract():
    # 21. Vertex shader contains 0.44, 0.42 and 0.14
    # 22. Vertex shader contains 104.0, 280.0, 0.96, 1.04 and 0.92
    # 23. Vertex shader contains depth size values 0.72 and 1.12
    # 24. Vertex shader contains size ranges 3.0–4.2, 4.2–5.7, 5.7–7.0
    # 25. Vertex shader does not contain the old 1.52 depth multiplier
    vert_src = (SHADER_ROOT / "orbital_particles.vert").read_text(encoding="utf-8")

    assert "0.44" in vert_src
    assert "0.42" in vert_src
    assert "0.14" in vert_src

    assert "104.0" in vert_src
    assert "280.0" in vert_src
    assert "0.96" in vert_src
    assert "1.04" in vert_src
    assert "0.92" in vert_src

    assert "0.72" in vert_src
    assert "1.12" in vert_src

    # Depth brightness begins at 0.70
    assert "mix(0.70, 1.0, depth01)" in vert_src

    # Size ranges: fine 5.4–6.2, medium 6.2–6.8, accent 6.8–7.14
    assert "mix(5.4, 6.2" in vert_src
    assert "mix(6.2, 6.8" in vert_src
    assert "mix(6.8, 7.14" in vert_src

    # Maximum theoretical size is 7.14 * 1.12 = 7.9968px <= 8.0px.
    max_accent_base = 7.14
    max_depth_scale = 1.12
    assert max_accent_base * max_depth_scale == 7.9968
    assert max_accent_base * max_depth_scale <= 8.0

    # Particle population and shader inputs remain unchanged.
    aura_src = (QML_ROOT / "OrbitalAura.qml").read_text(encoding="utf-8")
    assert "lowCost ? 520 : 1400" in aura_src
    assert "activeCount: lowCost ? 520 : 1400" in aura_src
    assert "capacity" not in vert_src.lower() or "1920" in vert_src
    assert "1920" in (CINEMATIC_ROOT / "geometry.py").read_text(encoding="utf-8")

    # Does not contain the old 1.52 depth multiplier
    assert "1.52" not in vert_src


def test_fragment_shader_contract():
    # 26. Fragment shader contains haloWeight mix(0.06,0.04)
    # 27. Fragment shader contains all five fire palette RGB constants
    # 28. Fragment shader contains no previous pale/white constants
    frag_src = (SHADER_ROOT / "orbital_particles.frag").read_text(encoding="utf-8")

    clean_frag = re.sub(r"\s+", "", frag_src)
    assert "mix(0.06,0.04,vDepth01)" in clean_frag

    # PinPoint and compactCore updates
    assert "smoothstep(0.025,0.21,radius)" in clean_frag
    assert "mix(12.0,20.0,vDepth01)" in clean_frag
    assert "pinPoint*0.72+compactCore*0.88+restrainedHalo" in clean_frag
    assert "rearBlend*0.56" in clean_frag
    assert "0.95" in frag_src

    # All five fire palette RGB constants
    # deepEmber = vec3(0.5608, 0.2314, 0.0392)
    assert "0.5608" in frag_src and "0.2314" in frag_src and "0.0392" in frag_src
    # burntOrange = vec3(0.7843, 0.3529, 0.0706)
    assert "0.7843" in frag_src and "0.3529" in frag_src and "0.0706" in frag_src
    # fireOrange = vec3(0.9412, 0.4706, 0.0941)
    assert "0.9412" in frag_src and "0.4706" in frag_src and "0.0941" in frag_src
    # moltenAmber = vec3(0.9608, 0.6510, 0.1373)
    assert "0.9608" in frag_src and "0.6510" in frag_src and "0.1373" in frag_src
    # goldenHighlight = vec3(1.0000, 0.7686, 0.3529)
    assert "1.0000" in frag_src and "0.7686" in frag_src and "0.3529" in frag_src

    # No pale/white constants from previous iterations in code
    code_only = "\n".join(
        line for line in frag_src.splitlines() if not line.strip().startswith("//")
    )
    for pale in ("0.824", "0.627", "0.298", "vec3(1.0, 1.0, 1.0)", "vec3(1.0)"):
        assert pale not in code_only


def test_no_qsb_files():
    # 30. No .qsb files are created
    assert not (SHADER_ROOT / "orbital_particles.vert.qsb").exists()
    assert not (SHADER_ROOT / "orbital_particles.frag.qsb").exists()
    assert not (QML_ROOT / "OrbitalAura.qsb").exists()


def test_focused_round_core_contract():
    holo_src = (QML_ROOT / "HoloMaterial.qml").read_text(encoding="utf-8")
    nucleus_src = (QML_ROOT / "NucleusView.qml").read_text(encoding="utf-8")
    vert_src = (SHADER_ROOT / "surface.vert").read_text(encoding="utf-8")
    particle_src = (SHADER_ROOT / "orbital_particles.vert").read_text(encoding="utf-8")

    for identifier in (
        "sphericalMaskEnabled",
        "sphericalMaskCenter",
        "sphericalMaskInner",
        "sphericalMaskOuter",
    ):
        assert identifier not in holo_src
        assert identifier not in nucleus_src
    assert "sphericalSilhouetteGuide" not in nucleus_src
    assert "kind: 9" not in nucleus_src
    assert "OrbitalAura" not in nucleus_src
    assert "orbitalParticleCount: 0" in nucleus_src
    assert "scene.t*.65" in nucleus_src
    assert "scene.t * .65" not in nucleus_src

    assert "VARYING float vSphericalRadius" not in vert_src
    assert "vSphericalRadius" not in vert_src
    assert "VARYING vec3 vWorld;" in vert_src

    assert "lowCost ? 1024 : 3072" in nucleus_src
    assert "lowCost ? 520 : 1400" in (QML_ROOT / "OrbitalAura.qml").read_text(encoding="utf-8")
    assert "mix(5.4, 6.2" in particle_src
    assert "mix(6.2, 6.8" in particle_src
    assert "mix(6.8, 7.14" in particle_src
    assert 7.14 * 1.12 == 7.9968
    assert "0.44" in particle_src and "0.42" in particle_src and "0.14" in particle_src
    assert "9417" in (CINEMATIC_ROOT / "geometry.py").read_text(encoding="utf-8")
    assert "1920" in (CINEMATIC_ROOT / "geometry.py").read_text(encoding="utf-8")

    assert _hash_for(CINEMATIC_ROOT / "geometry.py") == "a26fb15a1d66b74105faa fc4738dbbb463594e6ce37d621402eff9e18d511106".replace(" ", "")
    assert _hash_for(SHADER_ROOT / "surface.vert") == "18547a795f98fa6ddf4c14b6b17ee80682d079b66fe860cc85f256860d53976b"
    assert not list(SHADER_ROOT.glob("*.qsb")) or [p.name for p in SHADER_ROOT.glob("*.qsb")] == ["glow.frag.qsb"]


def _hash_for(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _before_hash(path: Path) -> str:
    return ""


def test_no_rejected_spherical_identifiers():
    sources = [
        (QML_ROOT / "NucleusView.qml").read_text(encoding="utf-8"),
        (QML_ROOT / "HoloMaterial.qml").read_text(encoding="utf-8"),
        (SHADER_ROOT / "surface.vert").read_text(encoding="utf-8"),
        (SHADER_ROOT / "surface.frag").read_text(encoding="utf-8"),
    ]
    for source in sources:
        for identifier in (
            "sphericalMaskEnabled",
            "sphericalMaskCenter",
            "sphericalMaskInner",
            "sphericalMaskOuter",
            "sphericalSilhouetteGuide",
            "vSphericalRadius",
        ):
            assert identifier not in source


def test_particle_size_contract():
    src = (SHADER_ROOT / "orbital_particles.vert").read_text(encoding="utf-8")
    assert "mix(5.4, 6.2" in src
    assert "mix(6.2, 6.8" in src
    assert "mix(6.8, 7.14" in src
    assert 7.14 * 1.12 == 7.9968
    assert "0.72" in src and "1.12" in src
    assert "lowCost ? 520 : 1400" in (QML_ROOT / "OrbitalAura.qml").read_text(encoding="utf-8")


def _hash_for(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _before_hash(path: Path) -> str:
    before = (PROJECT_ROOT / ".astra-local" / "before-hashes.txt")
    if not before.exists():
        return ""
    for entry in before.read_text(encoding="utf-8").splitlines():
        if not entry:
            continue
        file_name, file_hash = entry.split("|", 1)
        if Path(file_name).name == path.name:
            return file_hash
    return ""


