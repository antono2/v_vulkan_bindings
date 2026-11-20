// Verify historical registry output and compile it in the selected CI lane.
import crypto.sha256
import os
import rand
import registryci

const pinned_v3 = '.ci-v-source/v'
const usage = 'Usage: check_historical_registry.vsh snapshot | powershell | registry TAG | abi | strict | historical TAG'

fn snapshot(powershell bool) ! {
	if powershell {
		registryci.command(['pwsh', '-NoProfile', '-File', 'scripts/generate.ps1', '-VCompiler',
			@VEXE])!
	} else {
		registryci.command([@VEXE, 'run', 'scripts/generate.vsh'])!
	}
	registryci.verify_files()!
	mut args := ['git', 'diff', '--exit-code', '--']
	args << registryci.generated
	registryci.command(args)!
	registryci.command(['git', 'diff', '--check'])!
}

fn verify_registry_digest(tag string) ! {
	mut expected := []string{}
	for line in os.read_lines('test/core_registry_sha256.txt')! {
		fields := line.fields()
		if fields.len == 2 && fields[1] == tag {
			expected << fields[0]
		}
	}
	if expected.len != 1 || expected[0].len != 64
		|| !expected[0].bytes().all(it.is_digit() || (it >= `a` && it <= `f`)) {
		return error('Expected one SHA-256 digest for Vulkan-Docs ${tag}')
	}
	actual := sha256.sum(os.read_bytes(registryci.core)!).hex()
	if actual != expected[0] {
		return error('${registryci.core} differs for Vulkan-Docs ${tag}. Expected ${expected[0]}, got ${actual}')
	}
	println('${registryci.core}: verified Vulkan-Docs ${tag} SHA-256')
}

fn verify_registry(tag string) ! {
	registryci.generate_current()!
	for option in ['-w', '-verify'] {
		registryci.command([@VEXE, 'fmt', option, registryci.core, registryci.video])!
	}
	verify_registry_digest(tag)!
	registryci.command(['git', 'diff', '--check'])!
}

fn abi() ! {
	modules := os.abs_path('abi-modules')
	published := os.join_path(modules, 'antono2', 'vulkan')
	for path in registryci.generated {
		os.cp(path, os.join_path(published, os.file_name(path)))!
	}
	os.cp_all('abi-headers/include', os.join_path(published, 'c/vendor/include'), true)!
	os.setenv('VMODULES', modules, true)
	registryci.command([@VEXE, '-cc', 'gcc', 'run', 'test/opaque_basetype'])!
}

fn strict(stage string) ! {
	registryci.command([pinned_v3, 'version'])!
	registryci.generate_current()!
	core_text := os.read_file(registryci.core)!
	for declaration in ['pub const khr_xlib_surface_extension_name', '$if vulkan_xlib ? {',
		'#flag -DVK_USE_PLATFORM_XLIB_KHR', '$if vulkan_win32 ? {'] {
		if !core_text.contains(declaration) {
			return error('Missing generated Vulkan declaration: ${declaration}')
		}
	}
	lines := core_text.split_into_lines()
	for name in ['PFN_vkCmdSetFragmentShadingRateKHR', 'PFN_vkCmdSetFragmentShadingRateEnumNV'] {
		if !lines.any(it.starts_with('pub type ${name} = fn')
			&& it.contains('const_combinerOps &FragmentShadingRateCombinerOpKHR')) {
			return error('Missing pointer to the combiner operation array in ${name}')
		}
	}
	video_text := os.read_file(registryci.video)!
	if !video_text.contains('pub type StdVideoH264ScalingListsScalingList4x4Array') {
		return error('Missing named H.264 scaling list array type')
	}
	for line in video_text.split_into_lines() {
		fields := line.fields()
		if line.len == 0 || !line[0].is_space() || fields.len < 2 || !fields[0][0].is_capital()
			|| !fields[0].bytes().all(it.is_alnum()) {
			continue
		}
		if fields[1].starts_with('[') {
			return error('PascalCase fixed-array fields must use named array aliases: ${line.trim_space()}')
		}
	}
	registryci.prepare_module(stage)!
	// Use the pinned compiler's own library, independent of the launcher.
	os.unsetenv('VEXE')
	registryci.command([pinned_v3, '-new-compiler', '-check', 'test/main.c.v'])!
	registryci.command([pinned_v3, '-new-compiler', '-d', 'vulkan_xlib', '-check', 'test/main.c.v'])!
}

fn historical(stage string, tag string) ! {
	registryci.command([@VEXE, 'version'])!
	registryci.command([@VEXE, 'run', 'scripts/generate.vsh', tag])!
	verify_registry_digest(tag)!
	registryci.prepare_module(stage)!
	os.write_file('published/VERSION', tag + '\n')!
	sdk := os.getenv('VULKAN_SDK')
	if sdk == '' || !os.is_dir(sdk) {
		return error('VULKAN_SDK must point to the installed SDK')
	}
	volk := os.join_path(sdk, 'include', 'volk')
	os.mkdir_all(volk)!
	for file in ['volk.h', 'volk.c'] {
		registryci.command(['curl', '--fail', '--silent', '--show-error', '--location',
			'https://raw.githubusercontent.com/zeux/volk/master/${file}', '--output',
			os.join_path(volk,
				file)])!
	}
	registryci.command([@VEXE, '-cc', 'gcc', 'run', 'test'])!
	if tag == 'v1.4.335' {
		registryci.command([@VEXE, '-d', 'vulkan_xlib', '-cc', 'gcc', 'run', 'test'])!
	}
}

fn run(args []string) ! {
	os.chdir(os.dir(@DIR))!
	if args in [['--help'], ['-h']] {
		println(usage)
		return
	}
	if args.len == 1 {
		match args[0] {
			'snapshot' { return snapshot(false) }
			'powershell' { return snapshot(true) }
			'abi' { return abi() }
			else {}
		}
	}
	if args.len == 2 && args[0] == 'registry' {
		return verify_registry(args[1])
	}
	if args != ['strict'] && !(args.len == 2 && args[0] == 'historical') {
		return error(usage)
	}
	stage := os.join_path(os.temp_dir(), 'vulkan-registry-check-' + rand.uuid_v4())
	os.mkdir(stage, mode: 0o700)!
	defer { os.rmdir_all(stage) or {} }
	if args[0] == 'strict' {
		strict(stage)!
	} else {
		historical(stage, args[1])!
	}
}

run(os.args[1..]) or {
	eprintln(err)
	exit(1)
}
