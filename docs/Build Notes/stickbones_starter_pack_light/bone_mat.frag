#version 330 core
uniform sampler2D sTD2DInputs[1];
uniform vec2  uTiling;
uniform float uAlpha;
uniform float uAlphaCut;
in vec2 vUV;
out vec4 fragColor;
void main(){
    vec4 tex = texture(sTD2DInputs[0], vUV * uTiling);
    float a = tex.a * uAlpha;
    if (a < uAlphaCut) discard;
    fragColor = vec4(tex.rgb, a);
}
