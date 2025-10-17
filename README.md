# v_vulkan_bindings
Generates the vulkan bindings for [V](https://vlang.io/) from the current [KhronosGroup](https://github.com/KhronosGroup/) [API description](https://github.com/KhronosGroup/Vulkan-Docs/blob/main/xml/vk.xml).

# v_vulkan_bindings
Generates the vulkan bindings for V from the vulkan registry

To run
`python src/main.py -registry vulkandocs/xml/vk.xml vulkan.v`

Note that vulkandocs is in `.gitignore` and has to be cloned manually

`git clone --depth 1 https://github.com/KhronosGroup/Vulkan-Docs.git vulkandocs`

# Example Setup using preinstalled vulkan registry
```
~/workspace/v_vulkan_bindings

Script Name: ~/workspace/v_vulkan_bindings/src/main.py
Script Parameters Vulkan: -registry ../../../../usr/share/vulkan/registry/vk.xml vulkan.v
Script Parameters Vulkan Video: -registry ../../../../usr/share/vulkan/registry/video.xml vulkan_video.v
Working Directory: ~/workspace/v_vulkan_bindings
```
