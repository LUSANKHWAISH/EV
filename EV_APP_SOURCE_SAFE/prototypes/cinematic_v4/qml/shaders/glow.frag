#version 440
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    vec2 texelStep;
    float glowGain;
    int tapCount;
} ubuf;
layout(binding = 1) uniform sampler2D source;

vec3 emission(vec2 uv) {
    vec3 c=texture(source,uv).rgb;
    // Bloom only luminous traces; the dark circuitry must retain sharp gaps.
    float peak=max(c.r,max(c.g,c.b));
    return c*smoothstep(.22,.78,peak);
}
void main() {
    vec3 sum = emission(qt_TexCoord0) * 0.2;
    float total = 0.2;
    int count = ubuf.tapCount - 1;
    for(int i=0;i<12;i++) {
        if(i >= count) break;
        float angle = 6.2831853 * float(i) / float(count);
        float radius = (i%2 == 0) ? 1.0 : 2.4;
        vec2 uv = qt_TexCoord0 + vec2(cos(angle),sin(angle)) * ubuf.texelStep * radius;
        if(all(greaterThanEqual(uv,vec2(0.0))) && all(lessThanEqual(uv,vec2(1.0)))) {
            sum += emission(uv);
        }
        total += 1.0;
    }
    vec3 glow = sum / total * ubuf.glowGain;
    float coverage = clamp(max(glow.r,max(glow.g,glow.b)) * 0.35,0.0,0.5);
    // Black/transparent source stays zero; alpha is derived from emitted light.
    fragColor = vec4(glow,coverage) * ubuf.qt_Opacity;
}
