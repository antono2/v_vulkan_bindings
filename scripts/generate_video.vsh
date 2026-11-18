// Generate the V declarations for the Vulkan Video standard headers.
import encoding.xml
import flag
import os
import strconv
import strings

const scalar_types = {
	'uint8_t':  'u8'
	'uint16_t': 'u16'
	'uint32_t': 'u32'
	'uint64_t': 'u64'
	'int8_t':   'i8'
	'int16_t':  'i16'
	'int32_t':  'i32'
	'int64_t':  'i64'
}

struct VideoRegistry {
	types      map[string]xml.XMLNode
	enums      map[string]xml.XMLNode
	extensions []xml.XMLNode
}

fn children(node xml.XMLNode, tag string) []xml.XMLNode {
	mut result := []xml.XMLNode{}
	for item in node.children {
		if item is xml.XMLNode && item.name == tag {
			result << item
		}
	}
	return result
}

fn child_text(node xml.XMLNode, tag string) string {
	for item in children(node, tag) {
		return declaration_text(item).trim_space()
	}
	return ''
}

fn declaration_text(node xml.XMLNode) string {
	mut text := ''
	for item in node.children {
		match item {
			string {
				text += item
			}
			xml.XMLNode {
				if item.name != 'comment' {
					text += declaration_text(item)
				}
			}
			else {}
		}
	}
	return text
}

fn read_registry(path string) !VideoRegistry {
	doc := xml.XMLDocument.from_string(compact_attribute_separators(os.read_file(path)!))!
	if doc.root.name != 'registry' {
		return error('expected a Vulkan Video registry in ${path}')
	}
	mut types := map[string]xml.XMLNode{}
	mut enums := map[string]xml.XMLNode{}
	mut extensions := []xml.XMLNode{}
	for section in children(doc.root, 'types') {
		for node in children(section, 'type') {
			name := node.attributes['name'] or { child_text(node, 'name') }
			types[name] = node
		}
	}
	for group in children(doc.root, 'enums') {
		enums[group.attributes['name']] = group
	}
	for section in children(doc.root, 'extensions') {
		for extension in children(section, 'extension') {
			if 'vulkan' in extension.attributes['supported'].split(',') {
				extensions << extension
			}
		}
	}
	if types.len == 0 || enums.len == 0 || extensions.len == 0 {
		return error('incomplete Vulkan Video registry in ${path}')
	}
	extensions.sort_with_compare(fn (a &xml.XMLNode, b &xml.XMLNode) int {
		return a.attributes['number'].int() - b.attributes['number'].int()
	})
	return VideoRegistry{types, enums, extensions}
}

fn constant_name(name string) string {
	return name.to_lower().trim_string_left('vk_')
}

fn snake_name(name string) string {
	mut result := strings.new_builder(name.len)
	for i, ch in name {
		if i > 0 && ch >= `A` && ch <= `Z` {
			previous := name[i - 1]
			next_is_lower := i + 1 < name.len && name[i + 1] >= `a` && name[i + 1] <= `z`
			if previous.is_digit() || (previous >= `a` && previous <= `z`) || next_is_lower {
				result.write_u8(`_`)
			}
		}
		result.write_u8(ch)
	}
	return result.str().to_lower()
}

fn enum_member_name(group string, c_name string) string {
	mut normalized := strings.new_builder(c_name.len)
	// Match the historical registry spelling that joins a letter and the following number.
	for i, ch in c_name {
		if ch == `_` && i > 0 && i + 1 < c_name.len && c_name[i - 1] >= `A` && c_name[i - 1] <= `Z`
			&& c_name[i + 1].is_digit() {
			continue
		}
		normalized.write_u8(ch)
	}
	original := constant_name(normalized.str())
	words := snake_name(group).split('_')
	mut name := original
	for end := words.len; end > 0; end-- {
		prefix := words[..end].join('_')
		if name.starts_with(prefix) {
			name = name[prefix.len..].trim_string_left('_')
			break
		}
	}
	for start in 0 .. words.len {
		suffix := words[start..].join('_')
		if name.ends_with(suffix) {
			name = name[..name.len - suffix.len].trim_string_right('_')
			break
		}
	}
	if name == '' {
		return original
	}
	if name[0].is_digit() {
		return '_${name}'
	}
	return name
}

fn enum_declaration(group xml.XMLNode) !string {
	name := group.attributes['name']
	mut entries := []string{}
	mut seen := map[i64]bool{}
	mut signed := false
	for entry in children(group, 'enum') {
		// V enums cannot express two names for the same discriminant.
		if 'alias' in entry.attributes {
			continue
		}
		value := entry.attributes['value']
		number := strconv.parse_int(value, 0, 32) or {
			return error('unsupported value "${value}" in ${name}')
		}
		if number in seen {
			continue
		}
		seen[number] = true
		signed = signed || number < 0
		entries << '${enum_member_name(name, entry.attributes['name'])} = ${value}'
	}
	if i64(0x7fffffff) !in seen {
		entries << 'max_enum = max_int'
	}
	int_type := if signed { 'int' } else { 'u32' }
	for mut entry in entries {
		left, right := entry.split_once(' = ') or { continue }
		if right.starts_with('0x') {
			entry = '${left} = ${int_type}(${right})'
		}
	}
	storage := if signed { '' } else { ' as u32' }
	return 'pub enum ${name}${storage} {\n' + entries.join('\n') + '\n}'
}

fn field_declaration(member xml.XMLNode) !(string, string) {
	c_type := child_text(member, 'type')
	field := child_text(member, 'name')
	if c_type == '' || field == '' {
		return error('invalid Vulkan Video struct member')
	}
	declaration := declaration_text(member)
	_, suffix := declaration.split_once(c_type) or { return error('missing type for ${field}') }
	pointer, array := suffix.split_once(field) or { return error('missing name for ${field}') }
	base := scalar_types[c_type] or { c_type }
	mut dimensions := ''
	mut rest := array.trim_space()
	for rest.starts_with('[') {
		close := rest.index(']') or { return error('unclosed array dimension for ${field}') }
		length := rest[1..close].trim_space()
		dimensions += '[${constant_name(length)}]'
		rest = rest[close + 1..].trim_space()
	}
	// The imported C struct retains the bitfield layout from its vendor header.
	if rest != '' && !rest.starts_with(':') {
		return error('unsupported suffix "${rest}" for ${field}')
	}
	return field, dimensions + '&'.repeat(pointer.count('*')) + base
}

fn struct_declaration(node xml.XMLNode, name string) !string {
	if alias := node.attributes['alias'] {
		return 'pub type ${name} = ${alias}'
	}
	mut aliases := []string{}
	mut fields := []string{}
	for member in children(node, 'member') {
		field, field_type := field_declaration(member)!
		if field[0] >= `A` && field[0] <= `Z` && field_type.starts_with('[') {
			// V3 interprets a PascalCase field followed by [] as an embedded type.
			alias := '${name}${field}Array'
			aliases << 'pub type ${alias} = ${field_type}'
			fields << '${field} ${alias}'
		} else {
			fields << '${field} ${field_type}'
		}
	}
	aliases << 'pub type ${name} = C.${name}'
	kind := node.attributes['category']
	return aliases.join('\n') + '\n\n@[typedef]\npub ${kind} C.${name} {\npub mut:\n' +
		fields.join('\n') + '\n}'
}

fn constant_declaration(node xml.XMLNode) !string {
	name := constant_name(node.attributes['name'])
	mut value := xml.unescape_text(node.attributes['value'])!
	if value.starts_with('"') && value.ends_with('"') {
		value = "c'${value[1..value.len - 1]}'"
	} else {
		value = constant_name(value)
	}
	if c_type := node.attributes['type'] {
		v_type := scalar_types[c_type] or { return error('unknown type ${c_type} for ${name}') }
		value = '${v_type}(${value})'
	}
	return 'pub const ${name} = ${value}'
}

fn define_declaration(node xml.XMLNode, name string) !string {
	if name == 'VK_MAKE_VIDEO_STD_VERSION' {
		return 'pub fn make_video_std_version(major u32, minor u32, patch u32) u32 {\n' +
			'return (major << 22) | (minor << 12) | patch\n}'
	}
	if child_text(node, 'type') == 'VK_MAKE_VIDEO_STD_VERSION' {
		_, call := declaration_text(node).split_once('VK_MAKE_VIDEO_STD_VERSION') or {
			return error('missing version macro for ${name}')
		}
		return 'pub const ${constant_name(name)} = make_video_std_version${call.trim_space()}'
	}
	return error('unsupported video define ${name}')
}

struct ExtensionDeclarations {
mut:
	defines   []string
	constants []string
	groups    []string
	structs   []string
}

fn emit_constant(node xml.XMLNode, mut emitted map[string]bool, mut output ExtensionDeclarations) ! {
	name := node.attributes['name']
	if name !in emitted {
		output.constants << constant_declaration(node)!
		emitted[name] = true
	}
}

fn (registry VideoRegistry) emit_type(name string, allowed map[string]bool, constants map[string]xml.XMLNode, mut emitted map[string]bool, mut output ExtensionDeclarations) ! {
	if name !in allowed || name in emitted {
		return
	}
	node := registry.types[name] or { return error('missing video type ${name}') }
	emitted[name] = true
	for attribute in ['alias', 'requires'] {
		if dependency := node.attributes[attribute] {
			registry.emit_type(dependency, allowed, constants, mut emitted, mut output)!
		}
	}
	for item in children(node, 'type') {
		registry.emit_type(declaration_text(item).trim_space(), allowed, constants, mut emitted, mut
			output)!
	}
	members := children(node, 'member')
	for member in members {
		registry.emit_type(child_text(member, 'type'), allowed, constants, mut emitted, mut output)!
	}
	// Emit array bounds when first used, matching the historical registry traversal.
	for member in members {
		for bound in children(member, 'enum') {
			if constant := constants[declaration_text(bound).trim_space()] {
				emit_constant(constant, mut emitted, mut output)!
			}
		}
	}
	match node.attributes['category'] {
		'define' {
			output.defines << define_declaration(node, name)!
		}
		'enum' {
			group := registry.enums[name] or { return error('missing video enum ${name}') }
			output.groups << enum_declaration(group)!
		}
		'struct', 'union' {
			output.structs << struct_declaration(node, name)!
		}
		'include', '' {}
		else {
			return error('unsupported video type ${name}')
		}
	}
}

fn (registry VideoRegistry) generate() !string {
	license := os.read_file(os.join_path(os.dir(@DIR), 'LICENSE'))!.trim_space()
	mut blocks := [
		'/*\n${license}\n*/\n' +
			'// Registry-generated Vulkan declarations; native handles follow Vulkan lifetime rules.\n' +
			'// Regenerate in antono2/v_vulkan_bindings with v run scripts/generate.vsh.\n' +
			'// Vulkan Video declarations are generated by scripts/generate_video.vsh.\n' +
			'module vulkan',
	]
	mut emitted := map[string]bool{}
	for extension in registry.extensions {
		requirements := children(extension, 'require')
		mut allowed := map[string]bool{}
		mut constants := map[string]xml.XMLNode{}
		for requirement in requirements {
			for item in children(requirement, 'type') {
				allowed[item.attributes['name']] = true
			}
			for item in children(requirement, 'enum') {
				constants[item.attributes['name']] = item
			}
		}
		mut output := ExtensionDeclarations{}
		for requirement in requirements {
			for item in children(requirement, 'type') {
				registry.emit_type(item.attributes['name'], allowed, constants, mut emitted, mut
					output)!
			}
			for item in children(requirement, 'enum') {
				emit_constant(item, mut emitted, mut output)!
			}
		}
		leading := output.defines.join('\n') + if output.defines.len > 0 && output.constants.len > 0 {
			'\n' + output.constants.join('\n')
		} else {
			output.constants.join('\n')
		}
		if leading != '' {
			blocks << leading
		}
		blocks << output.groups
		if output.structs.len > 0 {
			structs := output.structs.join('\n\n')
			if output.groups.len > 0 {
				last := blocks.len - 1
				blocks[last] += '\n' + structs
			} else {
				blocks << structs
			}
		}
	}
	return blocks.join('\n\n') + '\n'
}

fn run(args []string) ! {
	mut parser := flag.new_flag_parser(args)
	parser.application('generate_video')
	parser.description('Generate V declarations from the Vulkan Video XML registry.')
	path := parser.string('registry', 0, 'vulkandocs/xml/video.xml', 'registry XML input')
	output := parser.string('output', 0, 'src/vulkan_video.v', 'generated V source')
	if parser.bool('help', `h`, false, 'show this help') {
		println(parser.usage())
		return
	}
	if parser.finalize()!.len != 0 {
		return error(parser.usage())
	}
	registry := read_registry(path)!
	source := registry.generate()!
	os.write_file(output, source)!
}

// The oldest supported V XML reader expects compact attribute separators.
fn compact_attribute_separators(input string) string {
	mut output := strings.new_builder(input.len)
	mut in_tag := false
	mut quote := u8(0)
	for i := 0; i < input.len; {
		byte := input[i]
		if !in_tag && byte == `<` && i + 1 < input.len {
			mut terminator := ''
			for delimiter in [['<!--', '-->'], ['<![CDATA[', ']]>']] {
				if i + delimiter[0].len <= input.len
					&& input[i..i + delimiter[0].len] == delimiter[0] {
					terminator = delimiter[1]
					break
				}
			}
			if terminator != '' {
				end := input.index_after(terminator, i + 2) or { input.len - terminator.len }
				last := end + terminator.len
				output.write_string(input[i..last])
				i = last
				continue
			}
			in_tag = input[i + 1].is_letter() || input[i + 1] == `_` || input[i + 1] == `?`
		}
		if in_tag {
			if quote != 0 {
				if byte == quote {
					quote = 0
				}
			} else if byte == `"` || byte == 39 {
				quote = byte
			} else if byte == `>` {
				in_tag = false
			} else if byte in [u8(32), 9, 10, 13] {
				start := i
				for i < input.len && input[i] in [u8(32), 9, 10, 13] {
					i++
				}
				if (i >= input.len || input[i] != `=`) && (start == 0 || input[start - 1] != `=`) {
					output.write_string(input[start..i])
				}
				continue
			}
		}
		output.write_u8(byte)
		i++
	}
	return output.str()
}

run(os.args[1..]) or {
	eprintln(err)
	exit(1)
}
