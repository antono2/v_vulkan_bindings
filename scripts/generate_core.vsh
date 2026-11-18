// Generate the core Vulkan module with the V declaration emitter.
import flag
import os
import rand
import x.json2
import coregen

fn generate(args []string) ! {
	mut parser := flag.new_flag_parser(args)
	parser.application('generate_core')
	parser.description('Generate core Vulkan bindings from the Khronos registry.')
	root := os.dir(@DIR)
	registry := parser.string('registry', 0, os.join_path(root, 'vulkandocs', 'xml', 'vk.xml'),
		'registry XML input')
	output := parser.string('output', 0, os.join_path(root, 'src', 'vulkan.v'),
		'generated V source')
	default_python := if os.user_os() == 'windows' {
		os.join_path(root, '.venv', 'Scripts', 'python.exe')
	} else {
		os.join_path(root, '.venv', 'bin', 'python')
	}
	python := parser.string('python', 0, default_python,
		'Python executable with registry helpers installed')
	if parser.bool('help', `h`, false, 'show help') {
		println(parser.usage())
		return
	}
	if parser.finalize()!.len != 0 {
		return error(parser.usage())
	}
	directory := os.join_path(os.temp_dir(), 'vulkan-core-${rand.ulid()}')
	os.mkdir(directory)!
	defer { os.rmdir_all(directory) or {} }
	source_path := os.join_path(directory, 'vulkan.v')
	plan_path := os.join_path(directory, 'declarations.json')
	result := os.exec([python, os.join_path(root, 'src', 'main.py'), '-registry', os.abs_path(registry),
		'--output-file', source_path, '--command-plan', plan_path, 'vulkan.v'])
	if result.exit_code != 0 {
		return error('Vulkan registry traversal failed\n${result.output}')
	}
	plan := json2.decode[coregen.BindingPlan](os.read_file(plan_path)!)!
	license := os.read_file(os.join_path(root, 'LICENSE'))!.replace('\r\n', '\n')
	source := coregen.emit_bindings(plan, license)!
	os.write_file(output, source)!
}

generate(os.args[1..]) or {
	eprintln(err)
	exit(1)
}
