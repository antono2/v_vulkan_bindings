// Resolve Vulkan registry values before formatting them as V declarations.
module coregen

import strconv

// Extension-added enumerants use blocks of 1,000 values starting at 10^9.
const extension_value_base = i64(1000000000)
const extension_value_block = i64(1000)

struct RegistryValue {
	literal          string
	bit_position     string
	extension_number string
	offset           string
	negative         bool
	alias            string
}

struct ResolvedValue {
	spelling string
	number   string
}

fn unsigned_suffix(bitwidth int) string {
	return if bitwidth == 64 { 'ULL' } else { 'U' }
}

fn resolve_value(value RegistryValue, bitwidth int, numeric bool, force_suffix bool) !ResolvedValue {
	if value.literal != '' {
		suffix := if force_suffix { unsigned_suffix(bitwidth) } else { '' }
		mut number := ''
		if numeric {
			number = if value.literal.starts_with('-') {
				strconv.parse_int(value.literal, 0, 64)!.str()
			} else {
				strconv.parse_uint(value.literal, 0, 64)!.str()
			}
		}
		return ResolvedValue{value.literal + suffix, number}
	}
	if value.bit_position != '' {
		index := strconv.parse_uint(value.bit_position, 0, 6)!
		flag_value := u64(1) << index
		suffix := if bitwidth == 64 || index >= 32 {
			'ULL'
		} else if force_suffix {
			'U'
		} else {
			''
		}
		return ResolvedValue{'0x${flag_value:08x}${suffix}', flag_value.str()}
	}
	if value.offset != '' {
		offset := strconv.parse_int(value.offset, 0, 32)!
		extension := strconv.parse_int(value.extension_number, 0, 32)!
		if extension < 1 {
			return error('invalid Vulkan extension number "${value.extension_number}"')
		}
		number := extension_value_base + (extension - 1) * extension_value_block + offset
		text := if value.negative { (-number).str() } else { number.str() }
		return ResolvedValue{text, text}
	}
	if value.alias != '' {
		return ResolvedValue{value.alias, ''}
	}
	return error('registry entry has no literal, bit position, extension offset, or alias')
}
