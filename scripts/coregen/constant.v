// Emit standalone registry constants with their C ABI widths and exact strings.
module coregen

import strings

struct StandaloneConstant {
	name       string
	value      RegistryValue
	c_type     string
	deprecated string
}

fn identifier_byte(ch u8) bool {
	return ch.is_digit() || lowercase(ch) || uppercase(ch) || ch == `_`
}

fn hexadecimal_byte(ch u8) bool {
	return ch.is_digit() || (ch >= `a` && ch <= `f`) || (ch >= `A` && ch <= `F`)
}

fn number_stop(expression string, start int, hex bool) int {
	mut offset := start
	if hex {
		offset += 2
		for offset < expression.len && hexadecimal_byte(expression[offset]) {
			offset++
		}
		return offset
	}
	for offset < expression.len && expression[offset].is_digit() {
		offset++
	}
	if offset < expression.len && expression[offset] == `.` {
		offset++
		for offset < expression.len && expression[offset].is_digit() {
			offset++
		}
	}
	if offset < expression.len && expression[offset] in [u8(`e`), `E`] {
		mut exponent := offset + 1
		if exponent < expression.len && expression[exponent] in [u8(`+`), `-`] {
			exponent++
		}
		first_digit := exponent
		for exponent < expression.len && expression[exponent].is_digit() {
			exponent++
		}
		if exponent > first_digit {
			offset = exponent
		}
	}
	return offset
}

fn strip_c_numeric_suffixes(expression string) string {
	mut output := strings.new_builder(expression.len)
	mut index := 0
	for index < expression.len {
		ch := expression[index]
		starts_decimal := ch == `.` && index + 1 < expression.len
			&& expression[index + 1].is_digit()
		if (ch.is_digit() || starts_decimal)
			&& (index == 0 || !identifier_byte(expression[index - 1])) {
			hex := index + 2 < expression.len && ch == `0`
				&& expression[index + 1] in [u8(`x`), `X`]
				&& hexadecimal_byte(expression[index + 2])
			number_end := number_stop(expression, index, hex)
			mut suffix_end := number_end
			suffix_types := if hex { 'uUlL' } else { 'uUlLfF' }
			for suffix_end < expression.len && suffix_types.contains_u8(expression[suffix_end]) {
				suffix_end++
			}
			if suffix_end == expression.len || !identifier_byte(expression[suffix_end]) {
				output.write_string(expression[index..number_end])
				index = suffix_end
				continue
			}
		}
		output.write_u8(ch)
		index++
	}
	return output.str()
}

fn strip_wrapping_parentheses(expression string) string {
	mut remaining := expression.trim_space()
	for remaining.starts_with('(') && remaining.ends_with(')') {
		mut depth := 0
		mut end := -1
		for index, ch in remaining {
			if ch == `(` {
				depth++
			} else if ch == `)` {
				depth--
				if depth == 0 {
					end = index
					break
				}
			}
		}
		if end != remaining.len - 1 {
			break
		}
		remaining = remaining[1..end].trim_space()
	}
	return remaining
}

fn emit_constant(constant StandaloneConstant) !string {
	name := remove_prefix(constant.name.trim_space().to_lower())
	if name == '' {
		return error('incomplete Vulkan constant "${constant.name}"')
	}
	original :=
		strip_wrapping_parentheses(resolve_value(constant.value, 32, false, false)!.spelling)
	if name.ends_with('_extension_name') && original.starts_with('"') {
		return 'pub const ${name} = c${original}'
	}
	mut value := strip_wrapping_parentheses(strip_c_numeric_suffixes(original)).to_lower()
	prefix := if constant.c_type != '' && original.contains('~') { '~' } else { '' }
	if prefix == '~' && value.starts_with('~') {
		operand := value[1..].trim_space()
		if operand != '' && (operand.bytes().all(it.is_digit())
			|| (operand.starts_with('0x') && operand.len > 2
			&& operand[2..].bytes().all(hexadecimal_byte(it)))) {
			value = operand
		}
	}
	value = remove_prefix(value)
	if constant.c_type != '' {
		kind := scalar_types[constant.c_type] or {
			return error('unsupported constant type ${constant.c_type} for ${constant.name}')
		}
		value = '${prefix}${kind}(${value})'
	}
	return 'pub const ${name} = ${value}'
}
