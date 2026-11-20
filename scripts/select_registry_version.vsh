// Resolve which Vulkan registry release should be proposed.
import net.http
import os
import semver
import time

const docs_remote = 'https://github.com/KhronosGroup/Vulkan-Docs.git'
const published_version_url = 'https://raw.githubusercontent.com/antono2/vulkan/master/VERSION'
const tag_prefix = 'refs/tags/'
const process_poll = 20 * time.millisecond

struct Selection {
	requested string
	changed   bool
	branch    string
}

fn stable_version(tag string) !semver.Version {
	if !tag.starts_with('v') {
		return error('Expected a stable registry tag')
	}
	version := semver.from(tag[1..])!
	if version.prerelease != '' || version.metadata != '' || version.str() != tag[1..] {
		return error('Expected a stable registry tag')
	}
	return version
}

fn latest_tag(refs string) !string {
	mut latest := ''
	mut newest := semver.Version{}
	for line in refs.split_into_lines() {
		_, ref := line.split_once('\t') or { continue }
		if !ref.starts_with(tag_prefix) {
			continue
		}
		tag := ref[tag_prefix.len..]
		version := stable_version(tag) or { continue }
		if latest == '' || newest < version {
			latest = tag
			newest = version
		}
	}
	if latest == '' {
		return error('Vulkan-Docs has no stable registry tag')
	}
	return latest
}

fn select_version(current string, requested string, force bool) !Selection {
	published := stable_version(current) or {
		return error('Invalid published version: ${current}')
	}
	target := stable_version(requested) or {
		return error('Invalid requested version: ${requested}')
	}
	if target < published {
		return error('Refusing to replace published registry ${current} with older ${requested}')
	}
	if current == requested && force {
		return Selection{requested, true, 'compat/generated-${requested}'}
	}
	return Selection{requested, current != requested, 'generated/${requested}'}
}

fn registry_refs() !string {
	git := os.find_abs_path_of_executable('git')!
	mut child := os.new_process(git)
	defer { child.close() }
	child.set_args(['ls-remote', '--tags', '--refs', docs_remote])
	child.set_redirect_stdio()
	child.run()
	mut refs := ''
	mut diagnostics := ''
	for child.is_alive() {
		refs += child.stdout_read()
		diagnostics += child.stderr_read()
		time.sleep(process_poll)
	}
	refs += child.stdout_slurp()
	diagnostics += child.stderr_slurp()
	child.wait()
	if child.code != 0 {
		return error('Could not read Vulkan-Docs tags: ${diagnostics.trim_space()}')
	}
	return refs
}

fn self_test() ! {
	refs := 'a\trefs/tags/v1.4.90\nb\trefs/tags/v1.4.301\nc\trefs/tags/v1.5.0-rc.1\n' +
		'd\trefs/tags/v1.4.302+local\ne\trefs/tags/v1.4.300\nf\trefs/heads/v9.0.0\n'
	assert latest_tag(refs)! == 'v1.4.301'
	assert select_version('v1.4.9', 'v1.4.10', false)! == Selection{'v1.4.10', true, 'generated/v1.4.10'}
	assert select_version('v1.4.10', 'v1.4.10', false)! == Selection{'v1.4.10', false, 'generated/v1.4.10'}
	assert select_version('v1.4.10', 'v1.4.10', true)! == Selection{'v1.4.10', true, 'compat/generated-v1.4.10'}
	for current, requested in {
		'v1.4.301': 'v1.4.90'
		'v1.4':     'v1.4.301'
		'v1.4.300': 'v1.4.301-rc.1'
	} {
		if _ := select_version(current, requested, true) {
			return error('Accepted invalid version selection: ${current} → ${requested}')
		}
	}
	if _ := latest_tag('a\trefs/tags/v1.5.0-rc.1\n') {
		return error('Selected a prerelease tag')
	}
	println('Registry version selection checks passed.')
}

fn run(args []string) ! {
	if args == ['--self-test'] {
		self_test()!
		return
	}
	if args.len != 0 {
		return error('Usage: select_registry_version.vsh [--self-test]')
	}
	url := os.getenv_opt('TARGET_VERSION_URL') or { published_version_url }
	reply := http.get(url)!
	if reply.status_code != 200 {
		return error('Could not read published registry version (HTTP ${reply.status_code})')
	}
	current := reply.body.trim_right('\n')
	mut requested := os.getenv('REQUESTED_VERSION')
	if requested == '' {
		requested = latest_tag(registry_refs()!)!
	}
	selection := select_version(current, requested, os.getenv('FORCE_REGENERATE') == 'true')!
	if output := os.getenv_opt('GITHUB_OUTPUT') {
		mut stream := os.open_append(output)!
		defer { stream.close() }
		stream.write_string('requested=${selection.requested}\nchanged=${selection.changed}\nbranch=${selection.branch}\n')!
	}
	println('Current: ${current}; requested: ${selection.requested}; update required: ${selection.changed}; branch: ${selection.branch}')
}

run(os.args[1..]) or {
	eprintln(err)
	exit(1)
}
