VARYING vec2 vUv;
VARYING float vAlpha;
VARYING float vHeat;
VARYING float vJunction;
void MAIN() {
    vec4 seed=INSTANCE_DATA;
    float age=fract(seed.x+timeSeconds*(.2+seed.w*.18));
    float phi=seed.y*6.2831853;
    float cosTheta=seed.z*2.0-1.0;
    float sinTheta=sqrt(max(0.0,1.0-cosTheta*cosTheta));
    float radius;
    float alpha;
    float size;
    float junction=step(.52,seed.w)*(1.0-step(.86,seed.w));
    if(seed.w<.52) {
        // Curving inward currents; a short visible lifetime leaves dark gaps.
        radius=16.0+86.0*(1.0-age);
        phi+=age*2.2+timeSeconds*.035;
        alpha=smoothstep(.02,.10,age)*(1.0-smoothstep(.72,1.0,age));
        size=.5+seed.z*.65;
    } else if(seed.w<.86) {
        // Fixed-volume junctions ignite independently, then fully extinguish.
        radius=38.0+seed.x*65.0;
        phi+=timeSeconds*.028;
        alpha=smoothstep(.02,.045,age)*(1.0-smoothstep(.08,.23,age));
        size=1.5+seed.z*1.8+step(.88,seed.x)*1.4;
    } else {
        radius=78.0+age*32.0;
        phi+=age*.35;
        alpha=smoothstep(0.0,.025,age)*pow(1.0-age,2.0)*.95;
        size=.8+seed.z*.6;
    }
    vec3 center=radius*vec3(sinTheta*cos(phi),cosTheta,sinTheta*sin(phi));
    vec4 world=MODEL_MATRIX*vec4(center,1.0);
    vec4 viewCenter=VIEW_MATRIX*world;
    vec2 offset=VERTEX.xy*size*.01*(1.0+activity*.22);
    if(seed.w>=.86) {
        vec2 outward=(VIEW_MATRIX*MODEL_MATRIX*vec4(normalize(center),0.0)).xy;
        outward/=max(length(outward),.001);
        offset=outward*offset.x*(2.4+seed.x*2.0)+vec2(-outward.y,outward.x)*offset.y*.55;
    }
    viewCenter.xy+=offset;
    POSITION=PROJECTION_MATRIX*viewCenter;
    vUv=UV0;
    vAlpha=alpha*(1.0+activity*(.45+junction*.7))*smoothstep(.35+seed.x*.24,.65+seed.x*.24,deployment);
    vHeat=min(1.0,.16+alpha*.68);
    vJunction=junction;
}
