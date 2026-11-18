// Emit V command wrappers and function pointer types from registry declarations.
module coregen

import strings

const command_marker = '// VULKAN_CORE_COMMAND_SLOT '
const group_marker = '// VULKAN_CORE_GROUP_SLOT '
const constant_marker = '// VULKAN_CORE_CONSTANT_SLOT '
const struct_marker = '// VULKAN_CORE_STRUCT_SLOT '

const primitive_types = ['bool', 'string', 'i8', 'u8', 'i16', 'u16', 'int', 'i32', 'u32', 'i64',
	'u64', 'i128', 'u128', 'rune', 'f32', 'f64', 'isize', 'usize', 'voidptr']

const scalar_types = {
	'size_t':   'usize'
	'int':      'i32'
	'void':     ''
	'uint8_t':  'u8'
	'uint16_t': 'u16'
	'uint32_t': 'u32'
	'uint64_t': 'u64'
	'int8_t':   'i8'
	'int16_t':  'i16'
	'int32_t':  'i32'
	'int64_t':  'i64'
	'double':   'f64'
	'float':    'f32'
	'float64':  'f64'
}

const platform_types = {
	'Display':             'voidptr'
	'Window':              'usize'
	'VisualID':            'usize'
	'RROutput':            'usize'
	'xcb_connection_t':    'voidptr'
	'xcb_window_t':        'u32'
	'xcb_visualid_t':      'u32'
	'wl_display':          'voidptr'
	'wl_surface':          'voidptr'
	'HINSTANCE':           'voidptr'
	'HWND':                'voidptr'
	'HANDLE':              'voidptr'
	'HMONITOR':            'voidptr'
	'LPCWSTR':             '&u16'
	'DWORD':               'u32'
	'SECURITY_ATTRIBUTES': 'voidptr'
	'GgpStreamDescriptor': 'usize'
	'GgpFrameToken':       'u64'
	'zx_handle_t':         'u32'
	'IDirectFB':           'voidptr'
	'IDirectFBSurface':    'voidptr'
	'CAMetalLayer':        'voidptr'
	'_screen_context':     'voidptr'
	'_screen_window':      'voidptr'
	'_screen_buffer':      'voidptr'
	'ubm_device':          'voidptr'
	'ubm_surface':         'voidptr'
}

struct Parameter {
	name       string
	c_type     string
	suffix     string
	array_size string
	constant   bool
	optional   string
	no_auto    bool
}

struct Command {
	name        string
	return_type string
	parameters  []Parameter
	value_types []string
}

// BindingPlan preserves the order and type availability from feature traversal.
pub struct BindingPlan {
	type_names []string
	commands   []Command
	structs    []Aggregate
	constants  []StandaloneConstant
	groups     []EnumGroup
}

struct CommandEmitter {
	known_types map[string]bool
	value_types []string
}

fn remove_prefix(name string) string {
	lower := name.to_lower()
	if lower in ['vk_true', 'vk_false'] {
		return name[2..]
	}
	if lower.starts_with('vk_') {
		return name[3..]
	}
	if lower.starts_with('vk') {
		return name[2..]
	}
	return name
}

fn uppercase(ch u8) bool {
	return ch >= `A` && ch <= `Z`
}

fn lowercase(ch u8) bool {
	return ch >= `a` && ch <= `z`
}

fn wrapper_name(name string) string {
	mut result := strings.new_builder(name.len)
	for i, ch in name {
		if i > 0 && uppercase(ch) {
			previous := name[i - 1]
			starts_word := i + 1 < name.len && lowercase(name[i + 1])
			if starts_word || previous.is_digit() || lowercase(previous) {
				result.write_u8(`_`)
			}
		}
		result.write_u8(ch)
	}
	return remove_prefix(result.str().to_lower())
}

fn (emitter CommandEmitter) parameter_type(parameter Parameter) string {
	name := remove_prefix(parameter.c_type)
	pointers := parameter.suffix.count('*')
	if parameter.c_type == 'void' && pointers > 0 {
		return '&'.repeat(pointers - 1) + 'voidptr'
	}
	mapped := scalar_types[name] or {
		platform_types[name] or {
			if name in primitive_types || name in ['char', 'byte'] || name.starts_with('PFN_')
				|| name in emitter.known_types || 'Vk' + name in emitter.known_types {
				name
			} else {
				'voidptr'
			}
		}
	}
	if name == 'byte' && pointers == 1 {
		return '&u8'
	}
	return '&'.repeat(pointers) + mapped
}

fn parameter_comment(parameter Parameter) string {
	mut details := []string{}
	if parameter.no_auto {
		details << 'See spec'
	}
	if parameter.optional == '' && parameter.no_auto {
		details << 'Required'
	} else if parameter.optional == 'true' {
		details << 'Optional, can be NULL or 0'
	} else if first, second := parameter.optional.split_once(',') {
		pointer := if first == 'false' { 'Pointer. Required' } else { 'Pointer optional' }
		value := if second.all_before(',') == 'true' {
			'0/NULL allowed'
		} else {
			'valid values required'
		}
		details << '${pointer}, but ${value}'
	}
	return details.join('. ')
}

fn (emitter CommandEmitter) emit(command Command) string {
	mut c_parameters := []string{cap: command.parameters.len}
	mut pfn_parameters := []string{cap: command.parameters.len}
	mut v_parameters := []string{cap: command.parameters.len}
	mut forwarded := []string{cap: command.parameters.len}
	mut comments := []string{}
	for parameter in command.parameters {
		mut name := remove_prefix(parameter.name)
		if name == 'type' {
			name = 'type_param'
		}
		if name == 'module' {
			name = 'vkmodule'
		}
		c_type := emitter.parameter_type(parameter)
		if parameter.constant && !name.starts_with('const_') {
			name = 'const_' + name
		}
		field_type := if parameter.array_size == '' {
			c_type
		} else {
			'[${remove_prefix(parameter.array_size.to_lower())}]${c_type}'
		}
		fn_pointer_type := if parameter.array_size == '' { c_type } else { '&${c_type}' }
		base := c_type.trim_left('&').trim_string_left('C.Vk')
		mutable := !parameter.constant
			&& (parameter.suffix.contains('*') || parameter.array_size != '')
			&& base !in primitive_types && base !in emitter.value_types
		if mutable && !name.starts_with('mut_') {
			name = 'mut_${name}'
		}
		c_parameters << '${name} ${field_type}'
		pfn_parameters << '${name} ${fn_pointer_type}'
		if mutable {
			v_parameters << 'mut ${name} ${field_type}'
		} else {
			v_parameters << '${name} ${field_type}'
		}
		forwarded << name
		comment := parameter_comment(parameter)
		comments << if comment == '' { '' } else { '// ${name} ${comment}' }
	}
	mut returns := scalar_types[command.return_type] or { remove_prefix(command.return_type) }
	if returns == 'PFN_vkVoidFunction' {
		returns = 'voidptr'
	}
	return_suffix := if returns == '' { '' } else { ' ${returns}' }
	call_prefix := if returns == '' { '' } else { 'return ' }
	c_params := if c_parameters.len == 0 { '()' } else { '(\n${c_parameters.join(', ')})' }
	v_params := if v_parameters.len == 0 { '()' } else { '(\n${v_parameters.join(',\n')})' }
	c_call := if forwarded.len == 0 { '()' } else { '(\n${forwarded.join(',\n')})' }
	comment_block := comments.join('\n').trim_space()
	doc := if comment_block == '' { '' } else { comment_block + '\n' }
	return '@[keep_args_alive]\nfn C.${command.name}${c_params}${return_suffix}\n\n' + doc +
		'pub type PFN_${command.name} = fn(${pfn_parameters.join(', ')})${return_suffix}\n' +
		'@[inline]\npub fn ${wrapper_name(command.name)}${v_params}${return_suffix} {\n' +
		'    ${call_prefix}C.${command.name}${c_call}\n}'
}

// emit_bindings fills declaration slots without changing feature or platform scope.
pub fn emit_bindings(template string, plan BindingPlan) !string {
	mut output := strings.new_builder(template.len)
	mut known := map[string]bool{}
	for name in plan.type_names {
		known[name] = true
	}
	mut groups := map[string]EnumGroup{}
	for group in plan.groups {
		if group.name in groups {
			return error('duplicate Vulkan enum ${group.name}')
		}
		groups[group.name] = group
	}
	structure_group := groups['StructureType'] or {
		return error('registry did not emit StructureType')
	}
	structure_types := structure_type_lookup(structure_group.entries.filter(it.required
		&& !it.protected).map(enum_field('StructureType', it.name)))
	mut constants := map[string]StandaloneConstant{}
	for constant in plan.constants {
		if constant.name in constants {
			return error('duplicate Vulkan constant ${constant.name}')
		}
		constants[constant.name] = constant
	}
	lines := template.split('\n')
	mut command_count := 0
	mut struct_count := 0
	for index, line in lines {
		if line.starts_with(command_marker) {
			if command_count >= plan.commands.len
				|| line != command_marker + plan.commands[command_count].name {
				return error('unexpected command slot "${line}"')
			}
			command := plan.commands[command_count]
			emitter := CommandEmitter{known, command.value_types}
			output.write_string(emitter.emit(command))
			command_count++
		} else if line.starts_with(struct_marker) {
			if struct_count >= plan.structs.len
				|| line != struct_marker + plan.structs[struct_count].name {
				return error('unexpected struct slot "${line}"')
			}
			output.write_string(emit_aggregate(plan.structs[struct_count], known, structure_types)!)
			struct_count++
		} else if line.starts_with(group_marker) {
			name := line[group_marker.len..]
			group := groups[name] or { return error('unexpected enum slot "${line}"') }
			output.write_string(emit_group(group)!)
			groups.delete(name)
		} else if line.starts_with(constant_marker) {
			name := line[constant_marker.len..]
			constant := constants[name] or { return error('unexpected constant slot "${line}"') }
			output.write_string(emit_constant(constant)!)
			constants.delete(name)
		} else {
			output.write_string(line)
		}
		if index + 1 < lines.len {
			output.write_u8(`\n`)
		}
	}
	if command_count != plan.commands.len || command_count == 0 || struct_count != plan.structs.len
		|| struct_count == 0 {
		return error('Vulkan plan emitted ${command_count}/${plan.commands.len} commands and ${struct_count}/${plan.structs.len} aggregates')
	}
	if groups.len != 0 {
		return error('${groups.len} of ${plan.groups.len} Vulkan enums left in the plan')
	}
	if constants.len != 0 || plan.constants.len == 0 {
		return error('${constants.len} of ${plan.constants.len} Vulkan constants left in the plan')
	}
	return output.str()
}
