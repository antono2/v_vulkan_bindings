# v_vulkan_bindings
Generates the vulkan bindings for Vlang from the vulkan registry


## TMP
Download vulkan sdk versions available and get the closest match
v1.3.290 -> 1.3.290.0
`curl -s https://vulkan.lunarg.com/sdk/versions.json | jq -r --slurp --arg regex "1\\.3\\.290.*" '.[]|map(match($regex)|.string)|first'`


