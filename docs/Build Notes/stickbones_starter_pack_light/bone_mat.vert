#version 330 core
uniform mat4 uTDMat;
uniform float uLen;
uniform float uR0;
uniform float uR1;
in vec3 P;
in vec2 uv[1];
out vec2 vUV;
void main(){
    float t = clamp(uv[0].y, 0.0, 1.0);
    float radius = mix(uR0,uR1,t);
    vec2 local = vec2(P.x * radius, (uv[0].y - 0.5) * uLen);
    gl_Position = uTDMat * vec4(local, 0.0, 1.0);
    vUV = uv[0];
}
