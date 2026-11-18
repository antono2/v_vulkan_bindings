// Prepare a pinned registry checkout and generate both binding modules.
import os

fn run(args []string) !string {
	result := os.exec(args)
	if result.exit_code != 0 {
		return error('${args[0]} exited with status ${result.exit_code}\n${result.output}')
	}
	return result.output
}

fn generate(args []string) ! {
	if args.len > 1 {
		return error('usage: v run scripts/generate.vsh [Vulkan-Docs tag]')
	}
	root := os.dir(@DIR)
	os.chdir(root)!
	registry_ref := if args.len == 1 { args[0] } else { os.read_file('VERSION')!.trim_space() }
	parts := registry_ref.trim_string_left('v').split('.')
	if !registry_ref.starts_with('v') || parts.len != 3 || parts.any(it == ''
		|| !it.bytes().all(it.is_digit())) {
		return error('invalid Vulkan-Docs tag: ${registry_ref}')
	}
	docs := os.join_path(root, 'vulkandocs')
	if !os.exists(os.join_path(docs, '.git')) {
		if os.exists(docs) {
			return error('vulkandocs exists but is not a Git checkout')
		}
		run(['git', 'clone', '--depth', '1', '--branch', registry_ref,
			'https://github.com/KhronosGroup/Vulkan-Docs.git', docs])!
	} else {
		status := run(['git', '-C', docs, 'status', '--porcelain', '--untracked-files=no'])!
		if status.trim_space() != '' {
			return error('vulkandocs has local changes; refusing to change its revision')
		}
		run(['git', '-C', docs, 'fetch', '--depth', '1', 'origin', 'refs/tags/${registry_ref}'])!
		run(['git', '-C', docs, 'checkout', '--quiet', '--detach', 'FETCH_HEAD'])!
	}
	run([@VEXE, 'run', 'scripts/generate_core.vsh'])!
	run([@VEXE, 'run', 'scripts/generate_video.vsh'])!
	run([@VEXE, 'fmt', '-w', 'src/vulkan.v', 'src/vulkan_video.v'])!
	println('Generated Vulkan bindings from Vulkan-Docs ${registry_ref}')
}

generate(os.args[1..]) or {
	eprintln(err)
	exit(1)
}
