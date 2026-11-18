// Apply the Khronos Vulkan registry rules for required API declarations.
module coregen

import encoding.xml
import registryxml

struct EnumInput {
	node      xml.XMLNode
	extension string
	number    int
}

struct Reference {
	kind string
	name string
}

struct Requirements {
	selected map[string]bool
mut:
	enums              map[string]EnumInput
	groups             map[string][]EnumInput
	required           map[string]bool
	removed            map[string]bool
	deprecated_members map[string]bool
}

fn declaration_key(kind string, name string) string {
	return '${kind}/${name}'
}

fn (mut requirements Requirements) add_enum(node xml.XMLNode, feature FeatureInput) {
	name := node.attributes['name']
	group := node.attributes['extends']
	entry := EnumInput{
		node:      node
		extension: if feature.node.name == 'extension' { feature.name } else { '' }
		number:    feature.number
	}
	if name !in requirements.enums {
		requirements.enums[name] = entry
	}
	if group != '' {
		requirements.groups[group] << entry
	}
}

fn registry_requirements(registry CoreRegistry) Requirements {
	mut enums := map[string]EnumInput{}
	mut groups := map[string][]EnumInput{}
	mut selected := map[string]bool{}
	mut required := map[string]bool{}
	for name, group in registry.groups {
		for node in registryxml.children(group, 'enum') {
			item := EnumInput{
				node: node
			}
			enum_name := node.attributes['name']
			enums[enum_name] = item
			groups[name] << item
			if 'type' in group.attributes {
				required[declaration_key('enum', enum_name)] = true
			}
		}
	}
	for feature in registry.features {
		selected[feature.name] = true
	}
	mut result := Requirements{
		enums:    enums
		groups:   groups
		selected: selected
		required: required
	}
	for features in [registry.core_features, registry.extensions] {
		for feature in features {
			for block in feature.blocks.filter(it.name == 'require') {
				for node in registryxml.children(block, 'enum') {
					if 'extends' in node.attributes || 'value' in node.attributes
						|| 'bitpos' in node.attributes || 'alias' in node.attributes {
						result.add_enum(node, feature)
					}
				}
			}
		}
	}
	return result
}

fn (registry CoreRegistry) resolve(ref Reference, requirements Requirements) ?xml.XMLNode {
	match ref.kind {
		'type' {
			return registry.types[ref.name]
		}
		'command' {
			return registry.commands[ref.name]
		}
		'enum' {
			item := requirements.enums[ref.name] or { return none }
			return item.node
		}
		else {
			return none
		}
	}
}

fn descendants(node xml.XMLNode, tag string) []string {
	mut names := []string{}
	for item in node.children {
		if item is xml.XMLNode {
			if item.name == tag {
				names << registryxml.declaration_text(item).trim_space()
			} else {
				names << descendants(item, tag)
			}
		}
	}
	return names
}

fn (registry CoreRegistry) command_signature(node xml.XMLNode) xml.XMLNode {
	mut target := node
	mut visited := map[string]bool{}
	for alias := target.attributes['alias']; alias != '' && alias !in visited; alias = target.attributes['alias'] {
		visited[alias] = true
		target = registry.commands[alias] or { break }
	}
	return target
}

fn (mut requirements Requirements) mark(registry CoreRegistry, ref Reference, enabled bool, mut visited map[string]bool) {
	key := declaration_key(ref.kind, ref.name)
	if key in visited {
		return
	}
	visited[key] = true
	node := registry.resolve(ref, requirements) or { return }
	if ref.kind == 'enum' && !enabled && requirements.required[key] {
		requirements.removed[ref.name] = true
	}
	requirements.required[key] = enabled
	if ref.kind == 'enum' {
		if alias := node.attributes['alias'] {
			requirements.mark(registry, Reference{'enum', alias}, enabled, mut visited)
		}
		return
	}
	if !enabled {
		return
	}
	if ref.kind == 'type' {
		for alias in ['requires', 'alias', 'bitvalues'] {
			if dependency := node.attributes[alias] {
				requirements.mark(registry, Reference{'type', dependency}, true, mut visited)
			}
		}
		for name in descendants(node, 'enum') {
			requirements.mark(registry, Reference{'enum', name}, true, mut visited)
		}
	}
	signature := if ref.kind == 'command' { registry.command_signature(node) } else { node }
	for name in descendants(signature, 'type') {
		requirements.mark(registry, Reference{'type', name}, true, mut visited)
	}
}

struct DependencyExpression {
	text    string
	enabled map[string]bool
	protect bool
mut:
	index int
}

struct ExpressionValue {
	enabled  bool
	c_text   string
	operator u8
}

fn (mut expression DependencyExpression) skip_space() {
	for expression.index < expression.text.len && expression.text[expression.index].is_space() {
		expression.index++
	}
}

fn (mut expression DependencyExpression) atom() !ExpressionValue {
	expression.skip_space()
	start := expression.index
	if start >= expression.text.len {
		return error('incomplete dependency expression')
	}
	if expression.text[start] == `(` {
		expression.index++
		value := expression.parse()!
		expression.skip_space()
		if expression.index == expression.text.len || expression.text[expression.index] != `)` {
			return error('unclosed dependency expression')
		}
		expression.index++
		return value
	}
	negated := expression.protect && expression.text[expression.index] == `!`
	if negated {
		expression.index++
	}
	name_start := expression.index
	for expression.index < expression.text.len {
		ch := expression.text[expression.index]
		if !ch.is_alnum() && ch !in [u8(`_`), `:`] {
			break
		}
		expression.index++
	}
	if name_start == expression.index {
		return error('invalid dependency name')
	}
	name := expression.text[name_start..expression.index]
	if expression.protect {
		prefix := if negated { '!' } else { '' }
		return ExpressionValue{
			c_text: '${prefix}defined(${name})'
		}
	}
	return ExpressionValue{
		enabled: expression.enabled[name]
	}
}

fn (value ExpressionValue) c_operand(operator u8) string {
	if value.operator != 0 && value.operator != operator {
		return '(${value.c_text})'
	}
	return value.c_text
}

fn (mut expression DependencyExpression) parse() !ExpressionValue {
	mut result := expression.atom()!
	for {
		expression.skip_space()
		if expression.index >= expression.text.len || expression.text[expression.index] == `)` {
			return result
		}
		operator := expression.text[expression.index]
		expression.index++
		value := expression.atom()!
		if operator !in [u8(`+`), `,`] {
			return error('unsupported dependency operator')
		}
		// The registry grammar evaluates both operators from left to right.
		if expression.protect {
			infix := if operator == `+` { '&&' } else { '||' }
			result = ExpressionValue{
				c_text:   '${result.c_operand(operator)} ${infix} ${value.c_operand(operator)}'
				operator: operator
			}
		} else {
			active := if operator == `+` {
				result.enabled && value.enabled
			} else {
				result.enabled || value.enabled
			}
			result = ExpressionValue{
				enabled: active
			}
		}
	}
	return result
}

fn interface_matches(block xml.XMLNode) bool {
	return block.attributes['api'] in ['', core_api] && block.attributes['profile'] == ''
}

fn (requirements Requirements) available(block xml.XMLNode) !bool {
	depends := block.attributes['depends'].trim_space()
	if depends == '' {
		return true
	}
	mut expression := DependencyExpression{
		text:    depends
		enabled: requirements.selected
	}
	result := expression.parse()!
	if expression.index < depends.len {
		return error('incomplete evaluation of ${depends}')
	}
	return result.enabled
}

fn (mut requirements Requirements) select(registry CoreRegistry) ! {
	for feature in registry.features {
		for block in feature.blocks.filter(it.name == 'deprecate' && interface_matches(it)) {
			for member in registryxml.children(block, 'feature') {
				owner := member.attributes['struct']
				name := member.attributes['name']
				requirements.deprecated_members[declaration_key(owner, name)] = true
			}
		}
	}
	for tag in ['require', 'remove'] {
		enabled := tag == 'require'
		for feature in registry.features {
			for block in feature.blocks.filter(it.name == tag && interface_matches(it)) {
				if enabled && !requirements.available(block)! {
					continue
				}
				mut visited := map[string]bool{}
				for kind in ['type', 'enum', 'command'] {
					for node in registryxml.children(block, kind) {
						requirements.mark(registry, Reference{kind, node.attributes['name']},
							enabled, mut visited)
					}
				}
			}
		}
	}
}
