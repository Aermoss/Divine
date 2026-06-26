/*
 * Copyright 2026 Yusuf Rençber
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#version 460

layout (location = 0) in vec3 position;
layout (location = 1) in vec3 texCoord;
layout (location = 2) in float shading;
layout (location = 3) in float light;
layout (location = 4) in float skylight;

out vec3 fragTexCoord;
out vec3 fragPosition;
out vec3 fragLight;

uniform mat4 view;
uniform mat4 projection;

uniform float sunHeight;

const vec3 DAY_TINT = vec3(1.0f, 1.0f, 1.0f);
const vec3 SUNSET_TINT = vec3(1.05f, 0.95f, 0.85f); 
const vec3 NIGHT_TINT = vec3(0.7f, 0.7f, 0.85f);
const vec3 TORCH_COLOR = vec3(1.2f, 1.1f, 0.8f);

void main() {
    fragTexCoord = texCoord;
    fragPosition = position;

    float blockIntensity = pow(0.8f, 15.0f - light);
    float skyIntensity = pow(0.8f, 15.0f - skylight);
    vec3 currentSkyTint;

    if (sunHeight > 0.4f) {
        currentSkyTint = mix(SUNSET_TINT, DAY_TINT, (sunHeight - 0.4f) / 0.6f);
    } else {
        currentSkyTint = mix(NIGHT_TINT, SUNSET_TINT, sunHeight / 0.4f);
    }

    vec3 finalBlockLight = blockIntensity * TORCH_COLOR;
    vec3 finalSkyLight = skyIntensity * currentSkyTint * max(0.15f, sunHeight);
    fragLight = max(finalSkyLight, finalBlockLight) * shading;

    gl_Position = projection * view * vec4(position, 1.0f);
}