// Rehearse the compatibility workflow against an isolated local Git remote.
import os
import rand

const history = 'v1.3.290'
const current = 'v1.4.368'
const first_ref = 'refs/tags/v1.0.1+vcompat.1'
const second_ref = 'refs/tags/v1.0.2+vcompat.1'

fn command(args []string) !string {
	result := os.exec(args)
	if result.exit_code != 0 {
		return error(result.output)
	}
	return result.output.trim_space()
}

fn git(repo string, args []string) !string {
	mut full := ['git', '-C', repo, '-c', 'user.name=Fixture', '-c',
		'user.email=fixture@example.invalid']
	full << args
	return command(full)
}

fn file(path string, contents string) ! {
	os.mkdir_all(os.dir(path))!
	os.write_file(path, contents)!
}

fn commit(repo string, message string) ! {
	git(repo, ['add', '.'])!
	git(repo, ['commit', '-qm', message])!
}

fn publisher(mode string, manifest string) []string {
	return [@VEXE, 'run', 'scripts/publish_compatibility_tags.vsh', mode, manifest]
}

fn check() ! {
	root := os.join_path(os.temp_dir(), 'compatibility-fixture-' + rand.uuid_v4())
	os.mkdir(root)!
	defer { os.rmdir_all(root) or {} }
	previous := os.getwd()
	os.chdir(root)!
	defer { os.chdir(previous) or {} }
	os.setenv('COMPATIBILITY_REVISION', '1', true)
	os.unsetenv('VULKAN_SDK')
	os.setenv('GITHUB_OUTPUT', os.join_path(root, 'outputs'), true)
	for script in ['publish_compatibility_tags.vsh', 'stage_generated_release.vsh'] {
		source := os.join_path(@DIR, '..', '..', 'scripts', script)
		file(os.join_path('scripts', script), os.read_file(source)!)!
	}
	for kind in ['core', 'video'] {
		name := if kind == 'core' { 'vulkan.v' } else { 'vulkan_video.v' }
		file('scripts/generate_${kind}.vsh',
			"import os\nos.write_file('src/${name}', 'module vulkan\\n') or { panic(err) }\n")!
	}
	os.mkdir('src')!
	file('test/main.v', 'module main\nimport antono2.vulkan\nfn main() { assert vulkan.fixture }\n')!
	for repo in ['vulkandocs', 'vulkanheaders'] {
		os.mkdir(repo)!
		git(repo, ['init', '-q'])!
		for tag in [history, current] {
			file(os.join_path(repo, 'include', 'vulkan', 'vulkan_core.h'), tag)!
			file(os.join_path(repo, 'include', 'vk_video', 'codec.h'), tag)!
			commit(repo, tag)!
			git(repo, ['tag', tag])!
		}
	}
	os.mkdir('seed')!
	git('seed', ['init', '-q', '--initial-branch=master'])!
	file('seed/VERSION', history + '\n')!
	file('seed/v.mod', "Module { name: 'vulkan', version: '1.0.0' }\n")!
	file('seed/fixture.v', 'module vulkan\npub const fixture = true\n')!
	file('seed/c/volk.c.v', 'module c\n')!
	file('seed/c/vendor/include/vulkan/obsolete.h', '')!
	commit('seed', 'Historical package')!
	git('seed', ['tag', 'v1.0.1'])!
	file('seed/VERSION', current + '\n')!
	commit('seed', 'Current package')!
	git('seed', ['tag', 'v1.0.2'])!
	command(['git', 'clone', '-q', '--bare', 'seed', 'remote.git'])!
	command(['git', 'clone', '-q', 'remote.git', 'published'])!
	base := git('remote.git', ['rev-parse', 'master'])!

	command(publisher('prepare', 'manifest'))!
	assert os.read_lines('manifest')! == [first_ref, second_ref]
	assert os.read_file('outputs')! == 'count=2\n'
	assert git('remote.git', ['tag', '--list', '*+vcompat.*'])! == ''
	file('invalid', first_ref + '\nrefs/heads/master\n')!
	assert os.exec(publisher('push', 'invalid')).exit_code != 0
	assert git('remote.git', ['tag', '--list', '*+vcompat.*'])! == ''

	git('remote.git', ['update-ref', second_ref, base])!
	collision := os.exec(publisher('push', 'manifest'))
	assert collision.exit_code != 0 && collision.output.contains('already exists'), collision.output
	assert git('remote.git', ['tag', '--list', '*+vcompat.*'])! == 'v1.0.2+vcompat.1'
	git('remote.git', ['update-ref', '-d', second_ref, base])!
	command(publisher('push', 'manifest'))!
	for index, ref in [first_ref, second_ref] {
		tag := [history, current][index]
		assert git('remote.git', ['cat-file', '-t', ref])! == 'tag'
		assert git('remote.git', ['show', ref + ':VERSION'])! == tag
		assert git('remote.git', ['show', ref + ':REGISTRY_COMMIT'])! == git('vulkanheaders', [
			'rev-parse',
			tag + '^{commit}',
		])!
		assert git('remote.git', ['show', ref + ':c/vendor/include/vulkan/vulkan_core.h'])! == tag
		assert git('remote.git', ['show', ref + ':c/vendor/include/vk_video/codec.h'])! == tag
	}
	assert git('remote.git', ['rev-parse', 'master'])! == base
	command(publisher('prepare', 'rerun'))!
	assert os.read_file('rerun')! == ''
	assert os.read_file('outputs')! == 'count=2\ncount=0\n'
	println('Compatibility publication, atomic rejection, and no-op rerun passed.')
}

check() or {
	eprintln(err)
	exit(1)
}
