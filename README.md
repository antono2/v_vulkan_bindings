# Vulkan binding generator for V

[Project portfolio](https://oreskin.de/projects_en.php)

Generates Vulkan and Vulkan Video bindings for [V](https://vlang.io/) from the
[Khronos API registries](https://github.com/KhronosGroup/Vulkan-Docs/tree/main/xml).

For application development, use the published
[`antono2.vulkan` module](https://github.com/antono2/vulkan#install-and-setup).
This repository contains the generator and maintenance workflows.

## Quick start

Full regeneration requires Git, V 0.5.2 or newer and Python 3 with the
`venv` module. Vulkan Video can be regenerated separately using only V and
a copy of `video.xml`. On Ubuntu or Debian, install the native
prerequisites with:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv
```

The setup script creates an isolated Python environment, checks out the
Vulkan-Docs tag recorded by this generator checkout in `VERSION`, installs the
Python dependency and regenerates both binding files:

```bash
git clone https://github.com/antono2/v_vulkan_bindings.git
cd v_vulkan_bindings
v run scripts/generate.vsh
```

The same V command works on Windows. PowerShell users can also use the
existing wrapper:

```powershell
git clone https://github.com/antono2/v_vulkan_bindings.git
Set-Location v_vulkan_bindings
.\scripts\generate.ps1
```

Pass a Vulkan-Docs tag to generate a different registry release. For example,
this explicitly selects the historical `v1.4.362` snapshot:

```bash
v run scripts/generate.vsh v1.4.362
```

```powershell
.\scripts\generate.ps1 v1.4.362
```

The script refuses to switch an existing `vulkandocs` checkout if it contains
tracked changes. The generated files are `src/vulkan.v` and
`src/vulkan_video.v`. Review their diff before committing.

Platform extensions are selected with V compile flags derived from the
registry's `<platform>` names. For example, `-d vulkan_xlib` includes the
Xlib declarations and supplies `VK_USE_PLATFORM_XLIB_KHR` to the C compiler.
XCB and Wayland have separate flags (`vulkan_xcb` and `vulkan_wayland`).
The same rule applies to Android, Win32, Metal and the other registry
platforms. Extension name and spec-version constants remain available without
the flag; platform types and commands require it and the platform's native
development headers.

## Generate Vulkan Video on its own

With `vulkandocs/xml/video.xml` in place, run these commands from the repository root.

```sh
v run scripts/generate_video.vsh
v fmt -w src/vulkan_video.v
```

| Option | Default | Use |
| --- | --- | --- |
| `--registry` | `vulkandocs/xml/video.xml` | Supply a Vulkan SDK registry or another copy of `video.xml`. |
| `--output` | `src/vulkan_video.v` | Write to a different file to compare registry versions. |
| `--help` | | Show usage. |

For example, this reads the Vulkan Video registry from a system SDK.

```sh
v run scripts/generate_video.vsh --registry /usr/share/vulkan/registry/video.xml
v fmt -w src/vulkan_video.v
```

## Generate the core bindings on their own

Prepare the pinned Vulkan-Docs checkout and Python environment with
`v run scripts/generate.vsh`. The core generator uses Python helpers from
that checkout for registry traversal. V resolves enum offsets and flag values
and emits enums, constants, version helpers, C-backed structs and unions,
callbacks, and commands.

```sh
v run scripts/generate_core.vsh --registry /usr/share/vulkan/registry/vk.xml
v fmt -w src/vulkan.v
```

| Option | Default | Use |
| --- | --- | --- |
| `--registry` | `vulkandocs/xml/vk.xml` | Read a different core registry. |
| `--output` | `src/vulkan.v` | Write to a separate file for comparison. |
| `--python` | The Python executable in `.venv` | Use another environment with the registry helpers installed. |

Use the pinned checkout for reproducible releases. An installed SDK may ship
a different registry revision.

## Publishing

`update_bindings_and_push_to_vulkan.yml` checks the newest numeric Vulkan-Docs
tag each day, regenerates the bindings against that tag and opens a generated
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
CI coverage or publication behavior. Keep exact moving pins in `VERSION`,
metadata files and workflows, and link to those sources from prose. Historical
tag examples should be labeled as examples rather than presented as the latest
release. The public module's README is maintained in
[`antono2/vulkan`](https://github.com/antono2/vulkan); include a companion update
there when a generator change affects application users.

## Source navigation and snapshot versions

[`src/main.py`](src/main.py) configures Khronos registry traversal for the
core bindings. [`src/vgenerator.py`](src/vgenerator.py) emits the header
and remaining type aliases, function-pointer typedefs, and defines.
[`scripts/coregen/`](scripts/coregen/) emits imported aggregates, enum and
flag groups, standalone constants, and commands. [`scripts/generate_video.vsh`](scripts/generate_video.vsh)
reads the video registry and emits the Vulkan Video declarations. Upstream files in `vulkandocs/`
retain their Khronos headers and are not maintained as local source.

`VERSION` selects the registry tag for the committed snapshots as well as the
default setup command. The current snapshots use Vulkan-Docs `v1.4.365`
(commit `8c9361ba8180c1f4164c0bf79de2f6e817770b0d`) and match the published
module's declarations.

Use V 0.5.2 for the committed formatting, regenerate with the default setup
command and check for drift before submitting changes:

```sh
v run scripts/generate.vsh
git diff --exit-code -- src/vulkan.v src/vulkan_video.v
```

The default-snapshot CI check enforces this correspondence. Historical registry
lanes intentionally generate other API versions and are separate compatibility
checks; do not copy those outputs into the committed current snapshots. In the
published module, `REGISTRY_COMMIT` pins Vulkan-Headers, not Vulkan-Docs.
