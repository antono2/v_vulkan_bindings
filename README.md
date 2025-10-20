# v_vulkan_bindings
Generates the vulkan bindings for [V](https://vlang.io/) from the current [KhronosGroup](https://github.com/KhronosGroup/) [API description](https://github.com/KhronosGroup/Vulkan-Docs/blob/main/xml/vk.xml).

## run
```bash
python3 src/main.py -registry vulkandocs/xml/vk.xml vulkan.v
python3 src/main.py -registry vulkandocs/xml/video.xml vulkan_video.v
```

Make sure to clone vulkandocs first

`git clone --depth 1 https://github.com/KhronosGroup/Vulkan-Docs.git vulkandocs`

## Example Setup using preinstalled vulkan registry
```bash
Working Directory: ~/workspace/v_vulkan_bindings

Script Name:        src/main.py
Params Vulkan:      -registry ../../../../usr/share/vulkan/registry/vk.xml vulkan.v
Params VulkanVideo: -registry ../../../../usr/share/vulkan/registry/video.xml vulkan_video.v
```

