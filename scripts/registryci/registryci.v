// Share checked-out registry generation and module staging across CI workflows.
module registryci

import os

pub const core = 'src/vulkan.v'
pub const video = 'src/vulkan_video.v'
pub const generated = [core, video]

pub fn command(args []string) ! {
	executable := os.find_abs_path_of_executable(args[0])!
	mut process := os.new_process(executable)
	defer { process.close() }
	process.set_args(args[1..])
	process.run()
	process.wait()
	if process.code != 0 {
		return error('${args.join(' ')} failed (exit ${process.code})')
	}
}

pub fn verify_files() ! {
	for path in generated {
		if !os.is_file(path) {
			return error('Missing generated bindings: ${path}')
		}
	}
}

pub fn generate_current() ! {
	for generator in ['generate_core.vsh', 'generate_video.vsh'] {
		command([@VEXE, 'run', os.join_path('scripts', generator)])!
	}
	verify_files()!
}

pub fn prepare_module(stage string) ! {
	command([@VEXE, 'run', 'scripts/stage_generated_release.vsh', 'install-check'])!
	organization := os.join_path(stage, 'antono2')
	os.mkdir(organization)!
	os.symlink(os.abs_path('published'), os.join_path(organization, 'vulkan'))!
	os.setenv('VMODULES', stage, true)
}
