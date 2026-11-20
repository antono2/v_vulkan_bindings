// Prepare, verify and stage generated bindings for the existing proposal publisher.
import os
import rand
import registryci

const usage = 'Usage: release_workflow.vsh self-test | generate TAG | smoke | publish TAG BRANCH'

fn test_publisher() ! {
	for script in ['publish_generated_branch.vsh', 'open_generated_proposal.vsh',
		'select_registry_version.vsh', 'stage_generated_release.vsh'] {
		registryci.command([@VEXE, 'run', os.join_path(@DIR, script), '--self-test'])!
	}
	registryci.command([@VEXE, 'run',
		os.join_path(os.dir(@DIR), 'test', 'compatibility_workflow', 'check.vsh')])!
}

fn generate(tag string) ! {
	registryci.generate_current()!
	registryci.command([@VEXE, 'fmt', '-w', registryci.core, registryci.video])!
	registryci.command([@VEXE, 'run', os.join_path(@DIR, 'stage_generated_release.vsh'),
		'prepare', tag])!
}

fn smoke() ! {
	stage := os.join_path(os.temp_dir(), 'vulkan-release-check-' + rand.uuid_v4())
	os.mkdir(stage, mode: 0o700)!
	defer { os.rmdir_all(stage) or {} }
	registryci.prepare_module(stage)!
	registryci.command([@VEXE, '-cc', 'gcc', 'run', 'test'])!
}

fn publish(tag string, branch string) ! {
	actual := os.read_file('generated/VERSION')!.trim_right('\n')
	if actual != tag {
		return error('Release artifact version ${actual} does not match the selected tag ${tag}')
	}
	registryci.command([@VEXE, 'run', os.join_path(@DIR, 'stage_generated_release.vsh'),
		'install-proposal'])!
	registryci.command(['git', 'diff', '--check'])!
	registryci.command(['git', 'add', '--', 'vulkan.v', 'vulkan_video.v', 'VERSION',
		'REGISTRY_COMMIT', 'c/vendor/include/vulkan', 'c/vendor/include/vk_video'])!
	registryci.command([@VEXE, 'run', os.join_path(@DIR, 'publish_generated_branch.vsh'),
		branch, 'Generated bindings ${tag}'])!
}

fn run(args []string) ! {
	if args in [['--help'], ['-h']] {
		println(usage)
		return
	}
	if args.len == 3 && args[0] == 'publish' {
		// The caller is in the destination module checkout, with generated/ from CI.
		return publish(args[1], args[2])
	}
	os.chdir(os.dir(@DIR))!
	if args == ['self-test'] {
		return test_publisher()
	}
	if args.len == 2 && args[0] == 'generate' {
		return generate(args[1])
	}
	if args == ['smoke'] {
		return smoke()
	}
	return error(usage)
}

run(os.args[1..]) or {
	eprintln(err)
	exit(1)
}
