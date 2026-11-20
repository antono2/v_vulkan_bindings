// Stage the generated bindings and the exact C headers used to compile them.
import os
import rand
import semver

const header_root = 'c/vendor/include'
const header_groups = ['vulkan', 'vk_video']
const usage = 'Usage: stage_generated_release.vsh prepare TAG | install-check | install-compat TAG | install-proposal | --self-test'

struct Copy {
	source string
	target string
}

struct Headers {
	source string
	target string
	names  []string
}

fn regular_file(path string) ! {
	if !os.is_file(path) || os.is_link(path) {
		return error('Expected a regular file at ${path}')
	}
}

fn header_plans(source_root string, target_root string) ![]Headers {
	mut plans := []Headers{}
	for name in header_groups {
		source := os.join_path(source_root, name)
		target := os.join_path(target_root, name)
		if os.is_link(source) || os.is_link(target) {
			return error('Expected header directories at ${source} and ${target}')
		}
		names := os.ls(source)!.filter(it.ends_with('.h')).sorted()
		if names.len == 0 {
			return error('No C headers in ${source}')
		}
		for file in names {
			regular_file(os.join_path(source, file))!
		}
		plans << Headers{source, target, names}
	}
	return plans
}

fn replace_file(path string, bytes []u8) ! {
	temporary := path + '.stage-' + rand.uuid_v4()
	defer { os.rm(temporary) or {} }
	os.write_file_array(temporary, bytes)!
	os.chmod(temporary, 0o644)!
	os.rename(temporary, path)!
}

fn copy_files(files []Copy) ! {
	for file in files {
		regular_file(file.source)!
	}
	for file in files {
		replace_file(file.target, os.read_bytes(file.source)!)!
	}
}

fn install_headers(plans []Headers) ! {
	for group in plans {
		os.mkdir_all(group.target)!
		for name in group.names {
			replace_file(os.join_path(group.target, name), os.read_bytes(os.join_path(group.source,
				name))!)!
		}
	}
	for group in plans {
		for name in os.ls(group.target)! {
			if name.ends_with('.h') && name !in group.names {
				os.rm(os.join_path(group.target, name))!
			}
		}
	}
}

fn revision(checkout string) !string {
	result := os.exec(['git', '-C', checkout, 'rev-parse', 'HEAD'])
	if result.exit_code != 0 {
		return error('Could not resolve the Vulkan-Headers commit: ${result.output.trim_space()}')
	}
	return result.output.trim_space()
}

fn validate_metadata(tag string, commit string) ! {
	version := semver.from(tag.trim_string_left('v'))!
	if 'v${version}' != tag || version.prerelease != '' || version.metadata != '' {
		return error('Expected a stable Vulkan registry tag: ${tag}')
	}
	if commit.len != 40 || !commit.bytes().all((it >= `0` && it <= `9`) || (it >= `a` && it <= `f`)) {
		return error('Expected the full Vulkan-Headers commit')
	}
}

fn prepare(root string, metadata_root string, tag string, commit string) ! {
	validate_metadata(tag, commit)!
	plans := header_plans(os.join_path(root, 'vulkanheaders', 'include'), os.join_path(root,
		'published', header_root))!
	install_headers(plans)!
	replace_file(os.join_path(metadata_root, 'VERSION'), (tag + '\n').bytes())!
	replace_file(os.join_path(metadata_root, 'REGISTRY_COMMIT'), (commit + '\n').bytes())!
}

fn bindings(artifact string, target string) []Copy {
	return ['vulkan.v', 'vulkan_video.v'].map(Copy{os.join_path(artifact, 'src', it), os.join_path(target,
		it)})
}

fn install_proposal(root string) ! {
	regular_file(os.join_path(root, 'c', 'volk.c.v'))!
	artifact := os.join_path(root, 'generated')
	version := os.join_path(artifact, 'VERSION')
	commit := os.join_path(artifact, 'REGISTRY_COMMIT')
	regular_file(version)!
	regular_file(commit)!
	validate_metadata(os.read_file(version)!.trim_right('\n'),
		os.read_file(commit)!.trim_right('\n'))!
	plans := header_plans(os.join_path(artifact, 'published', header_root), os.join_path(root,
		header_root))!
	mut files := bindings(artifact, root)
	for name in ['VERSION', 'REGISTRY_COMMIT'] {
		files << Copy{os.join_path(artifact, name), os.join_path(root, name)}
	}
	copy_files(files)!
	install_headers(plans)!
}

fn self_test() ! {
	root := os.join_path(os.temp_dir(), 'vulkan-release-' + rand.uuid_v4())
	os.mkdir(root)!
	defer { os.rmdir_all(root) or {} }
	artifact := os.join_path(root, 'generated')
	os.mkdir_all(os.join_path(artifact, 'src'))!
	os.write_file(os.join_path(artifact, 'src', 'vulkan.v'), '// core\n')!
	os.write_file(os.join_path(artifact, 'src', 'vulkan_video.v'), '// video\n')!
	for name in header_groups {
		source := os.join_path(artifact, 'vulkanheaders', 'include', name)
		os.mkdir_all(source)!
		os.write_file(os.join_path(source, 'fresh.h'), name)!
		target := os.join_path(root, header_root, name)
		os.mkdir_all(target)!
		os.write_file(os.join_path(target, 'obsolete.h'), 'old')!
		os.write_file(os.join_path(target, 'README'), 'keep')!
	}
	commit := '0123456789abcdef0123456789abcdef01234567'
	prepare(artifact, artifact, 'v1.4.369', commit)!
	copy_files(bindings(artifact, os.join_path(artifact, 'published')))!
	assert os.read_file(os.join_path(artifact, 'published', 'vulkan_video.v'))! == '// video\n'
	os.write_file(os.join_path(root, 'c', 'volk.c.v'), '// pinned Volk\n')!
	last_header := os.join_path(artifact, 'published', header_root, 'vk_video', 'fresh.h')
	os.rm(last_header)!
	if _ := install_proposal(root) {
		return error('Staged an incomplete artifact')
	}
	assert !os.exists(os.join_path(root, 'VERSION'))
	assert os.is_file(os.join_path(root, header_root, 'vulkan', 'obsolete.h'))
	os.write_file(last_header, 'vk_video')!
	registry_commit := os.join_path(artifact, 'REGISTRY_COMMIT')
	os.write_file(registry_commit, 'invalid\n')!
	if _ := install_proposal(root) {
		return error('Staged an artifact with invalid registry metadata')
	}
	assert !os.exists(os.join_path(root, 'vulkan.v'))
	os.write_file(registry_commit, commit + '\n')!
	for _ in 0 .. 2 {
		install_proposal(root)!
	}
	assert os.read_file(os.join_path(root, 'VERSION'))! == 'v1.4.369\n'
	assert os.read_file(os.join_path(root, 'REGISTRY_COMMIT'))! == commit + '\n'
	assert os.read_file(os.join_path(root, 'vulkan.v'))! == '// core\n'
	for name in header_groups {
		target := os.join_path(root, header_root, name)
		assert os.read_file(os.join_path(target, 'fresh.h'))! == name
		assert os.read_file(os.join_path(target, 'README'))! == 'keep'
		assert !os.exists(os.join_path(target, 'obsolete.h'))
	}
	println('Release staging checks passed.')
}

fn run(args []string) ! {
	root := os.getwd()
	if args == ['--self-test'] {
		self_test()!
	} else if args == ['install-check'] {
		copy_files(bindings(root, os.join_path(root, 'published')))!
	} else if args == ['install-proposal'] {
		install_proposal(root)!
	} else if args.len == 2 && args[0] in ['prepare', 'install-compat'] {
		metadata_root := if args[0] == 'prepare' { root } else { os.join_path(root, 'published') }
		prepare(root, metadata_root, args[1], revision(os.join_path(root, 'vulkanheaders'))!)!
		if args[0] == 'install-compat' {
			copy_files(bindings(root, metadata_root))!
		}
	} else {
		return error(usage)
	}
}

run(os.args[1..]) or {
	eprintln(err)
	exit(1)
}
