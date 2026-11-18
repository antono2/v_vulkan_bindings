// Parse the Vulkan registries without changing mixed C declaration text.
module registryxml

import encoding.xml
import os
import strings

pub fn read(path string) !xml.XMLNode {
	doc := xml.XMLDocument.from_string(compact_attribute_separators(os.read_file(path)!))!
	if doc.root.name != 'registry' {
		return error('expected a Vulkan registry in ${path}')
	}
	return doc.root
}

pub fn children(node xml.XMLNode, tag string) []xml.XMLNode {
	mut result := []xml.XMLNode{}
	for item in node.children {
		if item is xml.XMLNode && item.name == tag {
			result << item
		}
	}
	return result
}

pub fn child_text(node xml.XMLNode, tag string) string {
	for item in children(node, tag) {
		return declaration_text(item).trim_space()
	}
	return ''
}

pub fn declaration_text(node xml.XMLNode) string {
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
