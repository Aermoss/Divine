#version 460

layout (location = 0) in vec3 position;
layout (location = 1) in vec3 texCoord;
layout (location = 2) in float shading;
layout (location = 3) in float light;
layout (location = 4) in float skylight;

out vec3 fragTexCoord;
out vec3 fragLight;

uniform mat4 view;
uniform mat4 projection;

uniform float daylight;

void main() {
    fragTexCoord = texCoord;

    float blocklightMultiplier = pow(0.8f, 15.0f - light);
	float skylightMultiplier = pow(0.8f, 15.0f - skylight);

	fragLight = vec3(
		clamp(blocklightMultiplier * 1.5f, skylightMultiplier * daylight, 1.0f),
		clamp(blocklightMultiplier * 1.25f, skylightMultiplier * daylight, 1.0f),
		clamp(skylightMultiplier * (2.0f - pow(daylight, 2)), blocklightMultiplier, 1.0f)
	) * shading;

    gl_Position = projection * view * vec4(position, 1.0f);
}