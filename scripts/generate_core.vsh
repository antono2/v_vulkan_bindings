// Generate the core Vulkan module from the Khronos XML registry.
import flag
import os
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
	// Keep older CI and local command lines usable through the migration.
	parser.string('python', 0, '', 'legacy option retained for compatibility')
	if parser.bool('help', `h`, false, 'show help') {
		println(parser.usage())
		return
	}
	if parser.finalize()!.len != 0 {
		return error(parser.usage())
	}
	plan := coregen.native_binding_plan(registry)!
	license := os.read_file(os.join_path(root, 'LICENSE'))!.replace('\r\n', '\n')
	source := coregen.emit_bindings(plan, license)!
	os.write_file(output, source)!
}

generate(os.args[1..]) or {
	eprintln(err)
	exit(1)
}
