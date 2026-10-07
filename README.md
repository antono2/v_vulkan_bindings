# Vulkan binding generator for V

[Project portfolio](https://oreskin.de/projects_en.php)

Generates Vulkan and Vulkan Video bindings for [V](https://vlang.io/) from the
[Khronos API registries](https://github.com/KhronosGroup/Vulkan-Docs/tree/main/xml).

For application development, use the published
[`antono2.vulkan` module](https://github.com/antono2/vulkan#install-and-setup).
This repository contains the generator and maintenance workflows.

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

On Windows, run the equivalent PowerShell script:

```powershell
git clone https://github.com/antono2/v_vulkan_bindings.git
Set-Location v_vulkan_bindings
.\scripts\generate.ps1
```

Pass a Vulkan-Docs tag to generate a different registry release. For example,
this explicitly selects the historical `v1.4.362` snapshot:

```bash
./scripts/generate.sh v1.4.362
```

```powershell
.\scripts\generate.ps1 v1.4.362
```

The script refuses to switch an existing `vulkandocs` checkout if it contains
local changes. Generated files are written to `src/vulkan.v` and
`src/vulkan_video.v`; review their diff before committing.

Platform extensions are selected with V compile flags derived from the
registry's `<platform>` names. For example, `-d vulkan_xlib` includes the
Xlib declarations and supplies `VK_USE_PLATFORM_XLIB_KHR` to the C compiler.
XCB and Wayland have separate flags (`vulkan_xcb` and `vulkan_wayland`).
The same rule applies to Android, Win32, Metal, and the other registry
platforms. Extension name and spec-version constants remain available without
the flag; platform types and commands require it and the platform's native
development headers.

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

## Using an installed registry

The generator also needs the helper Python modules from a compatible
`vulkandocs` checkout. After preparing those dependencies as above, you can
point it at registry files installed by a Vulkan SDK. For example, on a Linux
system that provides `/usr/share/vulkan/registry`:

```sh
.venv/bin/python src/main.py -registry /usr/share/vulkan/registry/vk.xml vulkan.v
.venv/bin/python src/main.py -registry /usr/share/vulkan/registry/video.xml vulkan_video.v
```

For reproducible output, prefer the pinned registry checkout used by the setup
script; an installed SDK's registry version may differ.

## Publishing

`update_bindings_and_push_to_vulkan.yml` checks the newest numeric Vulkan-Docs
tag each day, regenerates the bindings against that tag, and opens a generated
pull request in
[`antono2/vulkan`](https://github.com/antono2/vulkan). Review and merge it after
the target repository's required checks pass. The registry snapshot then becomes
available on the target's default branch. To publish a package release, update
its semantic version in `v.mod` through a separate pull request and create the
matching `v<package-version>` tag after CI passes. The target's tag workflow
validates the version and publishes the GitHub release.
The proposal also copies the matching Vulkan and video C headers from the
same Vulkan-Headers tag. The compile smoke test uses those bundled headers
and the target module's pinned Volk sources. Registry downgrades are rejected.
The generator checkout's own `VERSION` remains a reproducible local generation
default; the scheduled workflow selects the newest tag independently.

When the registry tag is already published but the generator itself needs a
compatibility correction, run the workflow manually with `force_regenerate`.
It opens a `compat/generated-<tag>` pull request without changing `VERSION` or
using the release-only `generated/*` branch namespace.

`publish-compatibility-tags.yml` is a manual maintenance workflow for old
registry releases whose original generated layout is not accepted by current
V. It publishes new `+vcompat.N` tags and never rewrites the historical tags.

## Documentation maintenance

Include README review when changing setup, generation, platform selection,
CI coverage, or publication behavior. Keep exact moving pins in `VERSION`,
metadata files, and workflows, and link to those sources from prose. Historical
tag examples should be labeled as examples rather than presented as the latest
release. The public module's README is maintained in
[`antono2/vulkan`](https://github.com/antono2/vulkan); include a companion update
there when a generator change affects application users.

## Source navigation and snapshot versions

[`src/main.py`](src/main.py) configures Khronos registry traversal;
[`src/vgenerator.py`](src/vgenerator.py) emits V declarations and owns their
file introduction. Keep binding-purpose and regeneration guidance in that
emitter so future generation preserves it. Upstream files in `vulkandocs/`
retain their Khronos headers and are not maintained as local source.

The committed `src/vulkan.v` snapshot reports header version 347, while
`VERSION` currently selects v1.4.335. Do not treat those as interchangeable or
copy this snapshot over a newer published module. A full regeneration/version
reconciliation must review the API diff and ABI checks; this documentation
change preserves the existing snapshot. Until that reconciliation, `src/vulkan.v` remains a coverage exception to the new emitter
introduction. `src/vulkan_video.v` was regenerated at v1.4.347 with unchanged
declarations and now includes that introduction. The published module records its own input revisions.
