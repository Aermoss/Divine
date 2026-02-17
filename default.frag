#version 460

out vec4 fragColor;

uniform sampler2DArray albedoMap;

in vec3 fragTexCoord;
in vec3 fragLight;

vec3 default_ = vec3(142.0f, 185.0f, 113.0f);
vec3 plains = vec3(145.0f, 189.0f, 89.0f);
vec3 snowyPlains = vec3(128.0f, 180.0f, 151.0f);
vec3 lushCaves = vec3(185.0f, 183.0f, 91.0f);
vec3 desert = vec3(191.0f, 183.0f, 85.0f);
vec3 badlands = vec3(144.0f, 129.0f, 77.0f);
vec3 swamp = vec3(106.0f, 112.0f, 57.0f);
vec3 forest = vec3(121.0f, 192.0f, 90.0f);
vec3 darkForest = vec3(80.0f, 122.0f, 50.0f);
vec3 taiga = vec3(134.0f, 183.0f, 131.0f);
vec3 jungle = vec3(89.0f, 201.0f, 60.0f);
vec3 meadow = vec3(131.0f, 187.0f, 109.0f);
vec3 cherryGrove = vec3(182.0f, 219.0f, 97.0f);
vec3 magenta = vec3(255.0f, 0.0f, 255.0f);
vec3 cyan = vec3(0.0f, 255.0f, 255.0f);

void main() {
    vec4 albedo = texture(albedoMap, fragTexCoord);
    vec4 grassColor = vec4(cherryGrove / 255.0f, 1.0f);

    if (fragTexCoord.z == 1.0f) {
        vec4 color = texture(albedoMap, vec3(fragTexCoord.xy, 0.0f));
        if (color.a != 0.0f) albedo = color * grassColor;
    }

    if (fragTexCoord.z == 2.0f)
        albedo = albedo * grassColor;

    if (albedo.a == 0.0f)
        discard;

    fragColor = albedo * vec4(fragLight, 1.0f);
}