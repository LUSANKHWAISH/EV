VARYING vec2 vUv;
VARYING float vAlpha;
VARYING float vHeat;
VARYING float vJunction;
void MAIN() {
    vec2 p=vUv*2.0-1.0;
    float r2=dot(p,p);
    float core=exp(-r2*19.0);
    float halo=exp(-r2*6.0)*.13;
    float star=(exp(-abs(p.x)*38.0-abs(p.y)*5.0)+exp(-abs(p.y)*42.0-abs(p.x)*4.0))*.38*vJunction;
    float a=(core+halo+star)*(1.0-smoothstep(.7,1.0,sqrt(r2)))*vAlpha*coverage;
    vec3 color=mix(vec3(1.0,.34,.012),vec3(1.0,.87,.31),vHeat);
    FRAGCOLOR=vec4(color*min(gain*1.2,2.2),min(a*1.95,.97));
}
