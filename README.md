# v_vulkan_bindings
[Project portfolio](https://oreskin.de/projects_en.php)

Generates the [vulkan bindings](https://github.com/antono2/vulkan) for [V](https://vlang.io/) from the current [KhronosGroup](https://github.com/KhronosGroup/) [API description](https://github.com/KhronosGroup/Vulkan-Docs/blob/main/xml/vk.xml).

## Quick start

Requirements: Git, Python 3 with the `venv` module, and V if the generated
files should be formatted. On Ubuntu or Debian, install the native
prerequisites with:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv
```

The setup script creates an isolated Python environment, checks out the
Vulkan-Docs tag recorded by this generator checkout in `VERSION`, installs the
Python dependency, and regenerates both binding files:

```bash
git clone https://github.com/antono2/v_vulkan_bindings.git
cd v_vulkan_bindings
./scripts/generate.sh
```

Pass a Vulkan-Docs tag to generate a different registry release:

```bash
./scripts/generate.sh v1.4.362
```

The script refuses to switch an existing `vulkandocs` checkout if it contains
local changes. Generated files are written to `src/vulkan.v` and
`src/vulkan_video.v`; review their diff before committing.

## Manual generation

The generator imports helper modules from a `vulkandocs` checkout at the
repository root:

```bash
git clone --depth 1 --branch "$(cat VERSION)" \
  https://github.com/KhronosGroup/Vulkan-Docs.git vulkandocs
python3 -m venv .venv
.venv/bin/python -m pip install -r .github/generator-requirements.txt
.venv/bin/python src/main.py -registry vulkandocs/xml/vk.xml vulkan.v
.venv/bin/python src/main.py -registry vulkandocs/xml/video.xml vulkan_video.v
v fmt -w src/vulkan.v src/vulkan_video.v
```

## Example Setup using preinstalled vulkan registry
```bash
Working Directory: ~/workspace/v_vulkan_bindings

Script Name:        src/main.py
Params Vulkan:      -registry ../../../../usr/share/vulkan/registry/vk.xml vulkan.v
Params VulkanVideo: -registry ../../../../usr/share/vulkan/registry/video.xml vulkan_video.v
```

## Publishing

`update_bindings_and_push_to_vulkan.yml` regenerates the current bindings,
validates them with V, and opens a generated pull request in
[`antono2/vulkan`](https://github.com/antono2/vulkan). Merging that pull request
creates the matching immutable version tag after the target repository's
required checks pass.

`publish-compatibility-tags.yml` is a manual maintenance workflow for old
registry releases whose original generated layout is not accepted by current
V. It publishes new `+vcompat.N` tags and never rewrites the historical tags.
