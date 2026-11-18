// Index Vulkan registry declarations and select the public feature interfaces.
module coregen

import encoding.xml
import registryxml

const core_api = 'vulkan'

struct FeatureInput {
	node       xml.XMLNode
	name       string
	sort_order int
	category   int
	version    int
	number     int
	position   int
mut:
	blocks []xml.XMLNode
}

struct CoreRegistry {
	type_names    []string
	types         map[string]xml.XMLNode
	groups        map[string]xml.XMLNode
	commands      map[string]xml.XMLNode
	features      []FeatureInput
	core_features []FeatureInput
	extensions    []FeatureInput
	platforms     map[string]string
}

fn matches_core_api(apis string) bool {
	return apis == '' || core_api in apis.split(',')
}

fn filter_registry(node xml.XMLNode) xml.XMLNode {
	mut children := []xml.XMLNodeContents{cap: node.children.len}
	for item in node.children {
		if item is xml.XMLNode {
			if matches_core_api(item.attributes['api']) {
				children << filter_registry(item)
			}
		} else {
			children << item
		}
	}
	return xml.XMLNode{
		name:       node.name
		attributes: node.attributes
		children:   children
	}
}

fn nested_text(node xml.XMLNode, parent string, leaf string) string {
	for item in registryxml.children(node, parent) {
		return registryxml.child_text(item, leaf)
	}
	return ''
}

fn registry_name(node xml.XMLNode) string {
	if name := node.attributes['name'] {
		return name
	}
	direct := registryxml.child_text(node, 'name')
	if direct != '' {
		return direct
	}
	return nested_text(node, 'proto', 'name')
}

fn feature_input(node xml.XMLNode, position int) FeatureInput {
	name := node.attributes['name']
	raw_number := node.attributes['number']
	major, minor := raw_number.split_once('.') or { raw_number, '' }
	parts := name.split('_')
	vendor := if parts.len > 1 { parts[1] } else { '' }
	mut category := 0
	if node.name == 'extension' {
		category = if vendor in ['ARB', 'KHR', 'OES'] { 2 } else { 3 }
	} else if name.starts_with('VKSC') {
		category = 1
	}
	return FeatureInput{
		node:       node
		name:       name
		sort_order: node.attributes['sortorder'].int()
		category:   category
		version:    if node.name == 'feature' { major.int() * 1000 + minor.int() } else { 0 }
		number:     if node.name == 'extension' { raw_number.int() } else { 0 }
		position:   position
		blocks:     node.children.filter(it is xml.XMLNode).map(it as xml.XMLNode)
	}
}

fn interface_order(a &FeatureInput, b &FeatureInput) int {
	for pair in [[a.sort_order, b.sort_order], [a.category, b.category],
		[a.version, b.version], [a.number, b.number], [a.position, b.position]] {
		if pair[0] != pair[1] {
			return pair[0] - pair[1]
		}
	}
	return 0
}

fn feature_uses(current FeatureInput, target string, graph map[string]FeatureInput, mut visited map[string]bool) bool {
	if current.name in visited {
		return false
	}
	visited[current.name] = true
	for dependency in current.node.attributes['depends'].replace(',', '+').split('+').map(it.trim_space()) {
		if dependency == target {
			return true
		}
		if next := graph[dependency] {
			if feature_uses(next, target, graph, mut visited) {
				return true
			}
		}
	}
	return false
}

fn public_features(nodes []xml.XMLNode) []FeatureInput {
	mut graph := map[string]FeatureInput{}
	mut public := []FeatureInput{}
	mut internal := []FeatureInput{}
	for i, node in nodes {
		feature := feature_input(node, i)
		graph[feature.name] = feature
		if node.attributes['apitype'] == 'internal' {
			internal << feature
		} else {
			public << feature
		}
	}
	for feature in internal {
		for mut candidate in public {
			mut visited := map[string]bool{}
			if feature_uses(candidate, feature.name, graph, mut visited) {
				candidate.blocks << feature.blocks.filter(it.name in ['require', 'deprecate',
					'remove'])
				break
			}
		}
	}
	return public
}

fn load_core_registry(path string) !CoreRegistry {
	root := filter_registry(registryxml.read_mixed(path)!)
	mut types := map[string]xml.XMLNode{}
	mut names := []string{}
	for section in registryxml.children(root, 'types') {
		for node in registryxml.children(section, 'type') {
			name := registry_name(node)
			if name == '' || name in types {
				return error('missing or repeated Vulkan type name "${name}"')
			}
			types[name] = node
			names << name
		}
	}
	mut groups := map[string]xml.XMLNode{}
	for node in registryxml.children(root, 'enums') {
		groups[node.attributes['name']] = node
	}
	mut commands := map[string]xml.XMLNode{}
	for section in registryxml.children(root, 'commands') {
		for node in registryxml.children(section, 'command') {
			name := registry_name(node)
			if name == '' || name in commands {
				return error('missing or repeated Vulkan command name "${name}"')
			}
			commands[name] = node
		}
	}
	mut platforms := map[string]string{}
	for section in registryxml.children(root, 'platforms') {
		for node in registryxml.children(section, 'platform') {
			platforms[node.attributes['name']] = node.attributes['protect']
		}
	}
	core_features := public_features(registryxml.children(root, 'feature'))
	mut features := core_features.clone()
	mut extensions := []FeatureInput{}
	for section in registryxml.children(root, 'extensions') {
		for node in registryxml.children(section, 'extension') {
			feature := feature_input(node, features.len + extensions.len)
			extensions << feature
		}
	}
	for extension in extensions {
		if core_api in extension.node.attributes['supported'].split(',') {
			features << extension
		}
	}
	features.sort_with_compare(interface_order)
	return CoreRegistry{
		type_names:    names
		types:         types
		groups:        groups
		commands:      commands
		features:      features
		core_features: core_features
		extensions:    extensions
		platforms:     platforms
	}
}
