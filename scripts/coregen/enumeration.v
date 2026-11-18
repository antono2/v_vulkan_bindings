// Emit registry enums and 64-bit flag constants.
module coregen

import strconv
import strings

struct EnumEntry {
	name       string
	value      RegistryValue
	deprecated string
	protected  bool
	extended   bool
	required   bool
}

struct EnumGroup {
	name     string
	alias    string
	bitwidth int
	wide     bool
	entries  []EnumEntry
}

fn enum_field(group string, original string) string {
	mut normalized := strings.new_builder(original.len)
	for i, ch in original {
		if ch == `_` && i > 0 && i + 1 < original.len && uppercase(original[i - 1])
			&& original[i + 1].is_digit() {
			continue
		}
		normalized.write_u8(ch)
	}
	full_name := remove_prefix(normalized.str()).to_lower()
	mut name := full_name
	mut words := wrapper_name(group).split('_')
	for end := words.len; end > 0; end-- {
		prefix := words[..end].join('_')
		if name.starts_with(prefix) {
			name = name[prefix.len..].trim_string_left('_')
			break
		}
	}
	for i, word in words {
		if word == 'bits' {
			words[i] = 'bit'
		}
	}
	for start in 0 .. words.len {
		suffix := words[start..].join('_')
		if name.ends_with(suffix) {
			name = name[..name.len - suffix.len].trim_string_right('_')
			break
		}
		with_khr := suffix + '_khr'
		if name.ends_with(with_khr) {
			name = name[..name.len - with_khr.len].trim_string_right('_')
			break
		}
	}
	if name == '' {
		return full_name
	}
	if name == 'or' {
		return 'or_'
	}
	return if name[0].is_digit() { '_${name}' } else { name }
}

fn maximum_field(group string) string {
	mut start := group.len
	for start > 0 && uppercase(group[start - 1]) {
		start--
	}
	if group.len - start < 2 {
		return 'max_enum'
	}
	return 'max_enum_${group[start..].to_lower()}'
}

fn emit_small_enum(group EnumGroup) !string {
	mut signed := false
	mut concrete := []EnumEntry{}
	mut has_max := false
	for entry in group.entries {
		if entry.required && entry.protected {
			continue
		}
		resolved := resolve_value(entry.value, group.bitwidth, true, false)!
		if resolved.number != '' {
			number := strconv.parse_int(resolved.number, 10, 32) or {
				return error('${group.name}.${entry.name} exceeds the C enum range')
			}
			if !entry.extended && number < 0 && !wrapper_name(group.name).contains('flag_bits') {
				signed = true
			}
		}
		// V enum members need unique discriminants. Registry aliases are useful
		// for matching StructureType defaults, but are not separate enum values.
		if entry.required && resolved.number != '' {
			concrete << entry
			has_max = has_max || resolved.spelling in ['0x7FFFFFFF', '0xFFFFFFFF']
		}
	}
	storage := if signed { '' } else { ' as u32' }
	cast := if signed { 'int' } else { 'u32' }
	mut lines := ['pub enum ${group.name}${storage} {']
	for entry in concrete {
		comment := deprecation_comment(entry.name, entry.deprecated)!
		if comment != '' {
			lines << comment.trim_space()
		}
		field := enum_field(group.name, entry.name)
		spelling := resolve_value(entry.value, group.bitwidth, false, false)!.spelling
		value := if spelling.starts_with('0x') { '${cast}(${spelling})' } else { spelling }
		lines << '${field} = ${value}'
	}
	if !has_max {
		lines << '${maximum_field(group.name)} = max_int'
	}
	lines << '}'
	return lines.join('\n')
}

fn emit_wide_flags(group EnumGroup) !string {
	kind := if group.bitwidth == 64 { 'u64' } else { 'u32' }
	mut lines := ['// Flag bits for ${group.name}', 'pub type ${group.name} = ${kind}']
	for entry in group.entries {
		resolved := resolve_value(entry.value, group.bitwidth, true, true)!
		if resolved.number != '' {
			strconv.parse_uint(resolved.number, 10, 64) or {
				return error('${group.name}.${entry.name} exceeds the unsigned flag range')
			}
		}
		if !entry.required {
			continue
		}
		comment := deprecation_comment(entry.name, entry.deprecated)!
		if comment != '' {
			lines << comment.trim_space()
		}
		name := remove_prefix(entry.name.to_lower())
		value := remove_prefix(strip_c_numeric_suffixes(resolved.spelling)).to_lower()
		literal_kind := if resolved.spelling.contains('ULL') {
			'u64'
		} else if resolved.spelling.contains('U') {
			'u32'
		} else {
			''
		}
		if literal_kind == '' || value.starts_with('vk') {
			lines << 'pub const ${name} = ${value}'
		} else {
			prefix := if resolved.spelling.contains('~') { '~' } else { '' }
			lines << 'pub const ${name} = ${prefix}${literal_kind}(${value})'
		}
	}
	return lines.join('\n') + '\n'
}

fn emit_group(group EnumGroup, alias string) !string {
	if group.alias != '' {
		return 'pub type ${group.name} = ${alias}'
	}
	if group.wide {
		if group.bitwidth > 64 {
			return error('unsupported bit width ${group.bitwidth} for ${group.name}')
		}
		return emit_wide_flags(group)
	}
	if group.bitwidth > 32 {
		return error('unsupported bit width ${group.bitwidth} for ${group.name}')
	}
	return emit_small_enum(group)
}
