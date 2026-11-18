// Translate mixed registry XML into the ABI declarations consumed by the emitter.
module coregen

import encoding.xml
import registryxml

fn leading_text(node xml.XMLNode) string {
	mut text := ''
	for child in node.children {
		if child is xml.XMLNode {
			break
		}
		if child is string {
			text += child
		}
	}
	return text
}

fn field_parts(node xml.XMLNode, name string) (string, string) {
	mut value := ''
	mut tail := ''
	mut found := false
	for child in node.children {
		if child is xml.XMLNode {
			if found {
				break
			}
			if child.name == name {
				value = registryxml.declaration_text(child).trim_space()
				found = true
			}
		} else if found && child is string {
			tail += child
		}
	}
	return value, tail
}

fn declaration_suffix(node xml.XMLNode, members_only bool) string {
	mut suffix := ''
	mut found := false
	mut include := false
	for child in node.children {
		if child is xml.XMLNode {
			if found {
				include = !members_only || child.name == 'enum'
				if include {
					suffix += registryxml.declaration_text(child)
				}
			} else if child.name == 'name' {
				found = true
				include = true
			}
		} else if include && child is string {
			suffix += child
		}
	}
	return suffix
}

fn array_dimensions(text string) []string {
	mut result := []string{}
	mut remaining := text
	for {
		open := remaining.index('[') or { break }
		remaining = remaining[open + 1..]
		end := remaining.index(']') or { break }
		name := remaining[..end]
		if name != '' && name.bytes().all(identifier_byte(it)) {
			result << name
		}
		remaining = remaining[end + 1..]
	}
	return result
}

fn protect_bounds(expression string) (string, string) {
	if expression == '' {
		return '', ''
	}
	if expression.bytes().any(it in [u8(`+`), `,`, `(`, `)`, `!`]) {
		mut parser := DependencyExpression{
			text:    expression
			protect: true
		}
		condition := parser.parse() or { ExpressionValue{} }
		if parser.index == expression.len && condition.c_text != '' {
			return '#if ${condition.c_text}\n', '#endif // ${condition.c_text}\n'
		}
	}
	return '#ifdef ${expression}\n', '#endif // ${expression}\n'
}

fn read_aggregate(node xml.XMLNode, name string, protect string, requirements Requirements) Aggregate {
	if alias := node.attributes['alias'] {
		return Aggregate{
			name:  name
			alias: alias
		}
	}
	expression := node.attributes['protect'] or { protect }
	begin, end := protect_bounds(expression)
	mut members := []Member{}
	for member in registryxml.children(node, 'member') {
		kind, type_tail := field_parts(member, 'type')
		member_name, name_tail := field_parts(member, 'name')
		deprecated := if requirements.deprecated_members[declaration_key(name, member_name)] {
			'true'
		} else {
			member.attributes['deprecated']
		}
		members << Member{
			name:               member_name
			c_type:             kind
			suffix:             type_tail.trim_space()
			dimensions:         array_dimensions(declaration_suffix(member, true))
			literal_dimensions: name_tail.count('[')
			deprecation:        deprecated
		}
	}
	return Aggregate{
		name:          name
		category:      node.attributes['category']
		deprecated:    node.attributes['deprecated']
		extends:       node.attributes['structextends']
		protect_begin: begin
		protect_end:   end
		members:       members
	}
}

fn read_callback(node xml.XMLNode, name string, type_order int) Callback {
	protos := registryxml.children(node, 'proto')
	mut parameters := []CallbackParameter{}
	if protos.len == 0 {
		for child in node.children {
			if child is xml.XMLNode && child.name == 'type' {
				parameters << CallbackParameter{
					c_type: registryxml.declaration_text(child)
				}
			} else if child is string && parameters.len > 0 {
				last := parameters.len - 1
				prev := parameters[last]
				parameters[last] = CallbackParameter{
					c_type: prev.c_type
					suffix: prev.suffix + child
				}
			}
		}
		return Callback{
			name:        name
			return_type: leading_text(node)
			legacy:      true
			parameters:  parameters
			type_order:  type_order
		}
	}
	for param in registryxml.children(node, 'param') {
		kind, suffix := field_parts(param, 'type')
		text := registryxml.declaration_text(param)
		parameters << CallbackParameter{
			name:        registryxml.child_text(param, 'name')
			c_type:      kind
			suffix:      suffix
			constant:    leading_text(param).contains('const')
			indirection: text.contains('*') || text.contains('[')
		}
	}
	kind, suffix := field_parts(protos[0], 'type')
	return Callback{
		name:        name
		return_type: kind
		suffix:      suffix
		parameters:  parameters
		type_order:  type_order
	}
}

fn read_command(node xml.XMLNode, name string, type_order int) !Command {
	mut parameters := []Parameter{}
	for param in registryxml.children(node, 'param') {
		kind, suffix := field_parts(param, 'type')
		param_name := registryxml.child_text(param, 'name')
		dimensions := array_dimensions(declaration_suffix(param, false))
		if dimensions.len > 1 {
			return error('${name} has a multidimensional parameter ${param_name}')
		}
		parameters << Parameter{
			name:       param_name
			c_type:     kind
			suffix:     suffix.trim_space()
			array_size: if dimensions.len == 1 { dimensions[0] } else { '' }
			constant:   leading_text(param).contains('const')
			optional:   param.attributes['optional']
			no_auto:    param.attributes['noautovalidity'] == 'true'
		}
	}
	return Command{
		name:        name
		return_type: nested_text(node, 'proto', 'type')
		parameters:  parameters
		type_order:  type_order
	}
}

fn registry_value(entry EnumInput) RegistryValue {
	num := if 'extends' in entry.node.attributes && entry.extension != '' {
		entry.node.attributes['extnumber'] or { entry.number.str() }
	} else {
		entry.node.attributes['extnumber']
	}
	return RegistryValue{
		literal:          entry.node.attributes['value']
		bit_position:     entry.node.attributes['bitpos']
		extension_number: num
		offset:           entry.node.attributes['offset']
		negative:         'dir' in entry.node.attributes
		alias:            entry.node.attributes['alias']
	}
}

fn read_group(name string, alias string, group xml.XMLNode, requirements Requirements) EnumGroup {
	v_name := remove_prefix(name)
	if alias != '' {
		return EnumGroup{
			name:  v_name
			alias: alias
		}
	}
	bitwidth := (group.attributes['bitwidth'] or { '32' }).int()
	items := requirements.groups[name]
	mut required := map[string]bool{}
	for entry in items {
		key := entry.node.attributes['name']
		if key !in requirements.removed && (entry.extension == ''
			|| (requirements.selected[entry.extension]
			&& requirements.required[declaration_key('enum', key)])) {
			required[key] = true
			if original := entry.node.attributes['alias'] {
				required[original] = true
			}
		}
	}
	mut seen := map[string]bool{}
	mut entries := []EnumEntry{}
	for entry in items {
		key := entry.node.attributes['name']
		if key in seen || key in requirements.removed {
			continue
		}
		seen[key] = true
		entries << EnumEntry{
			name:       key
			value:      registry_value(entry)
			deprecated: entry.node.attributes['deprecated']
			protected:  'protect' in entry.node.attributes
			extended:   'extends' in entry.node.attributes
			required:   required[key]
		}
	}
	return EnumGroup{
		name:     v_name
		bitwidth: bitwidth
		wide:     group.attributes['type'] == 'bitmask' && bitwidth > 32
		entries:  entries
	}
}
