// Prepare a pinned registry checkout and run the existing Vulkan generator.
import os

fn command(args []string) string {
	return args.map(os.quoted_path(it)).join(' ')
}

fn run(args []string) ! {
	status := os.system(command(args))
	if status != 0 {
		return error('${args[0]} exited with status ${status}')
	}
}

fn generate(args []string) ! {
	if args.len > 1 {
		return error('usage: v run scripts/generate.vsh [Vulkan-Docs tag]')
	}
	root := os.dir(@DIR)
	os.chdir(root)!
	registry_ref := if args.len == 1 { args[0] } else { os.read_file('VERSION')!.trim_space() }
	docs := os.join_path(root, 'vulkandocs')
	venv := os.join_path(root, '.venv')
	python_name := os.getenv_opt('PYTHON') or { 'python3' }
	python := os.find_abs_path_of_executable(python_name) or {
		return error('${python_name} is required by the registry generator')
	}
	if !os.is_dir(os.join_path(docs, '.git')) {
		run(['git', 'clone', '--depth', '1', '--branch', registry_ref,
			'https://github.com/KhronosGroup/Vulkan-Docs.git', docs])!
	} else {
		status := os.execute_opt(command(['git', '-C', docs, 'status', '--porcelain',
			'--untracked-files=no']))!
		if status.output.trim_space() != '' {
			return error('vulkandocs has local changes; refusing to change its revision')
		}
		run(['git', '-C', docs, 'fetch', '--depth', '1', 'origin', 'refs/tags/${registry_ref}'])!
		run(['git', '-C', docs, 'checkout', '--quiet', '--detach', 'FETCH_HEAD'])!
	}
	venv_python := if os.user_os() == 'windows' {
		os.join_path(venv, 'Scripts', 'python.exe')
	} else {
		os.join_path(venv, 'bin', 'python')
	}
	if !os.is_file(venv_python) {
		run([python, '-m', 'venv', venv])!
	}
	os.execute_opt(command([venv_python, '-m', 'pip', '--version'])) or {
		return error('.venv is incomplete; move or remove it, then run this script again')
	}
	run([venv_python, '-m', 'pip', 'install', '--quiet', '--requirement',
		'.github/generator-requirements.txt'])!
	for registry, output in {
		'vk.xml':    'vulkan.v'
		'video.xml': 'vulkan_video.v'
	} {
		run([venv_python, 'src/main.py', '-registry', os.join_path('vulkandocs', 'xml', registry),
			output])!
		run([@VEXE, 'fmt', '-w', os.join_path('src', output)])!
	}
	println('Generated Vulkan bindings from Vulkan-Docs ${registry_ref}')
}

generate(os.args[1..]) or {
	eprintln(err)
	exit(1)
}
