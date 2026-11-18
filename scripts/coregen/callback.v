// Emit callback typedefs from both forms used by the Vulkan registry.
module coregen

struct Callback {
	name        string
	return_type string
	suffix      string
	legacy      bool
	parameters  []CallbackParameter
	type_order  int
}

struct CallbackParameter {
	name        string
	c_type      string
	suffix      string
	constant    bool
	indirection bool
}

fn typedef_c_type(c_type string, suffix string, known map[string]bool) string {
	base := c_type.trim_space()
	if base == 'void' {
		return if suffix.contains('*') { 'voidptr' } else { '' }
	}
	mapped := scalar_types[base] or {
		name := remove_prefix(base)
		platform_types[name] or {
			if name == '' || name in primitive_types || name in ['byte', 'char']
				|| name.starts_with('PFN_') || name in known || 'Vk' + name in known {
				name
			} else {
				'voidptr'
			}
		}
	}
	return '&'.repeat(suffix.count('*')) + mapped
}

fn legacy_callback_name(suffix string) string {
	// In the flat form the parameter name follows its <type> in mixed XML content.
	mut name := ''
	mut word := ''
	for ch in suffix.replace('const', '') {
		if ch.is_alnum() || ch == `_` {
			word += ch.ascii_str()
		} else if word != '' {
			name = word
			word = ''
		}
	}
	return if word == '' { name } else { word }
}

fn emit_callback(callback Callback, known map[string]bool, value_at map[string]int) string {
	mut parameters := []string{cap: callback.parameters.len}
	for parameter in callback.parameters {
		mut name := if callback.legacy {
			legacy_callback_name(parameter.suffix)
		} else {
			remove_prefix(parameter.name).all_before(':')
		}
		if name == '' {
			continue
		}
		c_type := typedef_c_type(parameter.c_type, parameter.suffix, known)
		field_type := if c_type == '' { 'voidptr' } else { c_type }
		if !callback.legacy {
			if name == 'module' {
				name = 'vkmodule'
			} else if name == 'type' {
				name = 'type_param'
			}
			base := field_type.trim_left('&').trim_string_left('C.Vk')
			if parameter.constant && !name.starts_with('const_') {
				name = 'const_' + name
			} else if !parameter.constant && parameter.indirection && base !in primitive_types
				&& !is_visited_value(base, callback.type_order, value_at)
				&& !name.starts_with('mut_') {
				name = 'mut_' + name
			}
		}
		parameters << '${name} ${field_type}'
	}
	raw_return := if callback.legacy {
		callback.return_type.trim_space().trim_string_left('typedef').all_before('(VKAPI_PTR')
	} else {
		callback.return_type
	}
	return_type := typedef_c_type(raw_return, callback.suffix, known)
	return_suffix := if return_type == '' { '' } else { ' ${return_type}' }
	return 'pub type ${callback.name} = fn (${parameters.join(', ')})${return_suffix}\n'
}
