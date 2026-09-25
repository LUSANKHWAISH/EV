VARYING vec2 vUv;
VARYING vec3 vWorld;
VARYING vec3 vNormal;
VARYING vec3 vLocal;
void MAIN() {
    vUv=UV0;
    vec3 pos=VERTEX;
    // Sub-pixel filament shimmer; the shell and orbital radii stay rigid.
    if(kind==2 || kind==4) {
        float amount=kind==4?.65:.3;
        pos.z+=amount*sin(UV0.x*28.0-timeSeconds*.7+seed);
    }
    vLocal=pos;
    vec4 world=MODEL_MATRIX*vec4(pos,1.0);
    vWorld=world.xyz;
    vNormal=normalize(NORMAL_MATRIX*NORMAL);
    POSITION=PROJECTION_MATRIX*VIEW_MATRIX*world;
}
