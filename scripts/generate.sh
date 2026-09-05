#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)
registry_ref=${1:-$(cat "$project_dir/VERSION")}
docs_dir="$project_dir/vulkandocs"
venv_dir="$project_dir/.venv"
python_bin=${PYTHON:-python3}

command -v git >/dev/null || { echo 'git is required' >&2; exit 1; }
command -v "$python_bin" >/dev/null || { echo "$python_bin is required" >&2; exit 1; }

if [[ ! -d "$docs_dir/.git" ]]; then
	git clone --depth 1 --branch "$registry_ref" \
		https://github.com/KhronosGroup/Vulkan-Docs.git "$docs_dir"
else
	if ! git -C "$docs_dir" diff --quiet || \
		! git -C "$docs_dir" diff --cached --quiet; then
		echo 'vulkandocs has local changes; refusing to change its revision' >&2
		exit 1
	fi
	git -C "$docs_dir" fetch --depth 1 origin "refs/tags/$registry_ref"
	git -C "$docs_dir" checkout --quiet --detach FETCH_HEAD
fi

if [[ ! -x "$venv_dir/bin/python" ]]; then
	"$python_bin" -m venv "$venv_dir"
fi
if ! "$venv_dir/bin/python" -m pip --version >/dev/null 2>&1; then
	echo '.venv is incomplete; move or remove it, then run this script again' >&2
	exit 1
fi
"$venv_dir/bin/python" -m pip install --quiet --requirement \
	"$project_dir/.github/generator-requirements.txt"

cd "$project_dir"
"$venv_dir/bin/python" src/main.py -registry vulkandocs/xml/vk.xml vulkan.v
"$venv_dir/bin/python" src/main.py -registry vulkandocs/xml/video.xml vulkan_video.v

if command -v v >/dev/null; then
	v fmt -w src/vulkan.v
	v fmt -w src/vulkan_video.v
else
	echo 'V was not found; generated files were not formatted' >&2
fi

printf 'Generated Vulkan bindings from Vulkan-Docs %s\n' "$registry_ref"
