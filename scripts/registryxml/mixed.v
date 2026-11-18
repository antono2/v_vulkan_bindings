// Preserve the spaces between mixed-content C tokens in the core registry.
module registryxml

import encoding.xml
import os
import strconv
import strings

const whitespace_marker = '\ufff9'

pub fn read_mixed(path string) !xml.XMLNode {
	source := os.read_file(path)!
	if source.contains(whitespace_marker) {
		return error('unexpected registry text marker in ${path}')
	}
	input := preserve_text(source)!
	document := xml.XMLDocument.from_string(compact_attribute_separators(input))!
	if document.root.name != 'registry' {
		return error('expected a Vulkan registry in ${path}')
	}
	return unescape_node(document.root)
}

fn markup_end(input string, start int) !int {
	for delimiters in [['<!--', '-->'], ['<![CDATA[', ']]>'],
		['<?', '?>']] {
		open, close := delimiters[0], delimiters[1]
		if start + open.len <= input.len && input[start..start + open.len] == open {
			end := input.index_after(close, start + open.len) or {
				return error('unclosed registry markup')
			}
			return end + close.len
		}
	}
	mut quote := u8(0)
	mut bracket_depth := 0
	for i in start + 1 .. input.len {
		ch := input[i]
		if quote != 0 {
			if ch == quote {
				quote = 0
			}
		} else if ch == `"` || ch == 39 {
			quote = ch
		} else if ch == `[` {
			bracket_depth++
		} else if ch == `]` {
			bracket_depth--
		} else if ch == `>` && bracket_depth == 0 {
			return i + 1
		}
	}
	return error('unclosed registry tag')
}

fn preserve_text(source string) !string {
	mut output := strings.new_builder(source.len)
	mut offset := 0
	mut depth := 0
	for offset < source.len {
		if source[offset] == `<` {
			end := markup_end(source, offset)!
			tag := source[offset..end]
			if tag.starts_with('</') {
				depth--
			} else if !tag.starts_with('<!') && !tag.starts_with('<?') && !tag.ends_with('/>') {
				depth++
			}
			output.write_string(tag)
			offset = end
		} else {
			end := source.index_after('<', offset) or { source.len }
			text := source[offset..end]
			if depth > 0 && text.trim_space() != text {
				// The standard reader trims each child text segment before returning it.
				output.write_string(whitespace_marker + text + whitespace_marker)
			} else {
				output.write_string(text)
			}
			offset = end
		}
	}
	return output.str()
}

fn unescape_node(node xml.XMLNode) !xml.XMLNode {
	mut attributes := map[string]string{}
	for key, value in node.attributes {
		attributes[key] = unescape(value)!
	}
	mut content := []xml.XMLNodeContents{cap: node.children.len}
	for child in node.children {
		match child {
			string {
				text := child.replace(whitespace_marker, '')
				content << unescape(text)!
			}
			xml.XMLNode {
				content << unescape_node(child)!
			}
			else {
				content << child
			}
		}
	}
	return xml.XMLNode{
		name:       node.name
		attributes: attributes
		children:   content
	}
}

fn unescape(text string) !string {
	if !text.contains('&') {
		return text
	}
	if !text.contains('&#') {
		return xml.unescape_text(text)
	}
	mut result := strings.new_builder(text.len)
	mut offset := 0
	for offset < text.len {
		start := text.index_after('&', offset) or { break }
		end := text.index_after(';', start + 1) or { return error('unclosed registry entity') }
		result.write_string(text[offset..start])
		entity := text[start + 1..end]
		if entity.starts_with('#') {
			hex := entity.starts_with('#x')
			base := if hex { 16 } else { 10 }
			value := strconv.parse_uint(entity[if hex { 2 } else { 1 }..], base, 32)!
			if value == 0 || value > 0x10ffff || (value >= 0xd800 && value <= 0xdfff) {
				return error('invalid registry character reference')
			}
			result.write_rune(rune(value))
		} else {
			result.write_string(xml.unescape_text(text[start..end + 1])!)
		}
		offset = end + 1
	}
	result.write_string(text[offset..])
	return result.str()
}
