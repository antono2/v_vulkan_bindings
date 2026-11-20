// Regenerate historical compatibility tags and push only fully validated tags.
import os
import rand
import semver

const usage = 'Usage: publish_compatibility_tags.vsh prepare|push MANIFEST'
const prefix = 'refs/tags/'
const published = 'published'

struct Release {
	package_tag       string
	registry_tag      string
	compatibility_tag string
}

fn command(args []string) !string {
	result := os.exec(args)
	if result.exit_code != 0 {
		return error('${args.join(' ')} failed (exit ${result.exit_code}):\n${result.output.trim_space()}')
	}
	return result.output.trim_space()
}

fn git(directory string, args []string) !string {
	mut command_args := ['git', '-C', directory]
	command_args << args
	return command(command_args)
}

fn stable_tag(tag string) bool {
	if !tag.starts_with('v') {
		return false
	}
	version := semver.from(tag[1..]) or { return false }
	return version.prerelease == '' && version.metadata == '' && 'v${version}' == tag
}

fn compatibility_revision() !string {
	value := os.getenv_opt('COMPATIBILITY_REVISION') or { '1' }
	if value == '' || value[0] == `0` || !value.bytes().all(it >= `0` && it <= `9`) {
		return error('COMPATIBILITY_REVISION must be a positive integer')
	}
	return value
}

fn plan(revision string) ![]Release {
	mut releases := []Release{}
	tags := git(published, ['tag', '--list', '--sort=version:refname'])!.split_into_lines()
	for package_tag in tags {
		if !stable_tag(package_tag) {
			continue
		}
		compatibility_tag := '${package_tag}+vcompat.${revision}'
		if compatibility_tag in tags {
			println('Already published: ${compatibility_tag}')
			continue
		}
		registry_tag := git(published, ['show', '${package_tag}:VERSION'])!
		if !stable_tag(registry_tag) {
			return error('Invalid Vulkan registry version in ${package_tag}: ${registry_tag}')
		}
		for repository in ['vulkandocs', 'vulkanheaders'] {
			git(repository, ['rev-parse', '--verify', '${prefix}${registry_tag}^{commit}'])!
		}
		releases << Release{package_tag, registry_tag, compatibility_tag}
	}
	return releases
}

fn regenerate(release Release, stage string) ! {
	println('Generating ${release.compatibility_tag} from Vulkan registry ${release.registry_tag}')
	for repo in ['vulkandocs', 'vulkanheaders'] {
		git(repo, ['checkout', '--quiet', '--detach', prefix + release.registry_tag])!
	}
	git(published, ['switch', '--detach', 'origin/master'])!
	for generator in ['generate_core.vsh', 'generate_video.vsh'] {
		command([@VEXE, 'run', os.join_path('scripts', generator)])!
	}
	command([@VEXE, 'fmt', '-w', 'src/vulkan.v', 'src/vulkan_video.v'])!
	command([@VEXE, 'run', 'scripts/stage_generated_release.vsh', 'install-compat', release.registry_tag])!
	git(published, ['diff', '--check'])!
	modules := os.join_path(stage, 'modules')
	search_path := '${modules}|@vlib|@vmodules'
	command([@VEXE, '-path', search_path, '-cc', 'gcc', '-o', os.join_path(stage, 'vulkan-smoke'),
		'test'])!
	git(published, ['add', '--', 'vulkan.v', 'vulkan_video.v', 'VERSION', 'REGISTRY_COMMIT',
		'c/vendor/include/vulkan', 'c/vendor/include/vk_video'])!
	git(published, ['-c', 'user.name=github-actions[bot]', '-c',
		'user.email=41898282+github-actions[bot]@users.noreply.github.com', 'commit', '--allow-empty',
		'-m', 'Regenerate ${release.package_tag} for current V'])!
	git(published, ['-c', 'user.name=github-actions[bot]', '-c',
		'user.email=41898282+github-actions[bot]@users.noreply.github.com', 'tag', '-a',
		release.compatibility_tag, '-m', '${release.package_tag} bindings regenerated for current V'])!
}

fn prepare(manifest string, revision string) ! {
	if os.exists(manifest) || os.is_link(manifest) {
		return error('Choose a fresh tag manifest: ${manifest}')
	}
	releases := plan(revision)!
	mut refs := []string{cap: releases.len}
	if releases.len > 0 {
		stage := os.join_path(os.temp_dir(), 'vulkan-compatibility-' + rand.uuid_v4())
		os.mkdir(stage)!
		defer { os.rmdir_all(stage) or {} }
		modules := os.join_path(stage, 'modules', 'antono2')
		os.mkdir_all(modules)!
		os.symlink(os.abs_path(published), os.join_path(modules, 'vulkan'))!
		for release in releases {
			regenerate(release, stage)!
			refs << prefix + release.compatibility_tag
		}
	}
	os.write_file(manifest, refs.map(it + '\n').join(''))!
	if path := os.getenv_opt('GITHUB_OUTPUT') {
		mut output := os.open_append(path)!
		defer { output.close() }
		output.writeln('count=${refs.len}')!
	}
	println('Prepared ${refs.len} compatibility tags.')
}

fn push(manifest string, revision string) ! {
	refs := os.read_lines(manifest)!
	suffix := '+vcompat.${revision}'
	mut seen := map[string]bool{}
	for ref in refs {
		if !ref.starts_with(prefix) || !ref.ends_with(suffix)
			|| !stable_tag(ref.trim_string_left(prefix).trim_string_right(suffix)) || ref in seen {
			return error('Invalid compatibility tag ref: ${ref}')
		}
		seen[ref] = true
		git(published, ['rev-parse', '--verify', ref + '^{tag}'])!
	}
	if refs.len > 0 {
		mut args := ['push', '--atomic', 'origin']
		args << refs
		println(git(published, args)!)
	}
}

fn run(args []string) ! {
	if args.len != 2 || args[0] !in ['prepare', 'push'] {
		return error(usage)
	}
	revision := compatibility_revision()!
	if args[0] == 'prepare' {
		prepare(args[1], revision)!
	} else {
		push(args[1], revision)!
	}
}

run(os.args[1..]) or {
	eprintln(err)
	exit(1)
}
