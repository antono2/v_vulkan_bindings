// Traverse the selected Vulkan features in dependency and declaration order.
module coregen

import encoding.xml
import registryxml

struct CoreTraversal {
	registry     CoreRegistry
	requirements Requirements
mut:
	plan    BindingPlan
	emitted map[string]bool
}

fn add_slot(mut sections map[string][]DeclarationSlot, section string, kind string, name string) {
	sections[section] << DeclarationSlot{
		kind: kind
		name: name
	}
}

fn (mut traversal CoreTraversal) record_type(node xml.XMLNode, name string, protect string, mut sections map[string][]DeclarationSlot) {
	category := node.attributes['category']
	alias := node.attributes['alias']
	match category {
		'struct', 'union' {
			traversal.plan.type_events << TypeEvent{'aggregate', traversal.plan.structs.len}
			traversal.plan.structs << read_aggregate(node, name, protect, traversal.requirements)
			add_slot(mut sections, 'struct', 'aggregate', name)
		}
		'enum' {
			target := if alias == '' { name } else { alias }
			group := traversal.registry.groups[target] or { return }
			traversal.plan.type_events << TypeEvent{'group', traversal.plan.groups.len}
			traversal.plan.groups << read_group(name, alias, group, traversal.requirements)
			section := if group.attributes['type'] == 'bitmask' { 'bitmask' } else { 'group' }
			add_slot(mut sections, section, 'group', remove_prefix(name))
		}
		'funcpointer' {
			traversal.plan.callbacks << read_callback(node, name, traversal.plan.type_events.len)
			add_slot(mut sections, 'struct', 'callback', name)
		}
		'define' {
			traversal.plan.defines << RegistryDefine{
				name: name
				text: registryxml.declaration_text(node)
			}
			add_slot(mut sections, 'define', 'define', name)
		}
		else {
			kind, suffix := field_parts(node, 'type')
			traversal.plan.type_events << TypeEvent{'type', traversal.plan.types.len}
			traversal.plan.types << RegistryType{
				name:       name
				category:   category
				alias:      alias
				c_type:     kind
				suffix:     suffix
				deprecated: node.attributes['deprecated']
			}
			section := if category == '' { 'struct' } else { category }
			add_slot(mut sections, section, 'type', name)
		}
	}
}

fn (mut traversal CoreTraversal) emit(ref Reference, protect string, mut sections map[string][]DeclarationSlot) ! {
	key := declaration_key(ref.kind, ref.name)
	if key in traversal.emitted || !traversal.requirements.required[key] {
		return
	}
	node := traversal.registry.resolve(ref, traversal.requirements) or { return }
	traversal.emitted[key] = true
	alias := node.attributes['alias']
	if alias != '' {
		traversal.emit(Reference{ref.kind, alias}, '', mut sections)!
	}
	if ref.kind == 'type' {
		if required := node.attributes['requires'] {
			traversal.emit(Reference{'type', required}, '', mut sections)!
		}
	}
	match ref.kind {
		'type' {
			for dependency in descendants(node, 'type') {
				traversal.emit(Reference{'type', dependency}, '', mut sections)!
			}
			for dependency in descendants(node, 'enum') {
				traversal.emit(Reference{'enum', dependency}, '', mut sections)!
			}
			traversal.record_type(node, ref.name, protect, mut sections)
			if bitvalues := node.attributes['bitvalues'] {
				traversal.emit(Reference{'type', bitvalues}, '', mut sections)!
			}
		}
		'enum' {
			entry := traversal.requirements.enums[ref.name]
			traversal.plan.constants << StandaloneConstant{
				name:       ref.name
				value:      registry_value(entry)
				c_type:     if alias == '' { node.attributes['type'] } else { '' }
				deprecated: node.attributes['deprecated']
			}
			add_slot(mut sections, 'enum', 'constant', ref.name)
		}
		'command' {
			signature := traversal.registry.command_signature(node)
			for dependency in descendants(signature, 'type') {
				traversal.emit(Reference{'type', dependency}, '', mut sections)!
			}
			traversal.plan.commands << read_command(signature, ref.name,
				traversal.plan.type_events.len)!
			add_slot(mut sections, 'command', 'command', ref.name)
		}
		else {}
	}
}

fn (mut traversal CoreTraversal) emit_feature(feature FeatureInput) ! {
	mut sections := map[string][]DeclarationSlot{}
	for block in feature.blocks.filter(it.name == 'require') {
		for kind in ['type', 'enum', 'command'] {
			for node in registryxml.children(block, kind) {
				if kind == 'enum' && 'extends' in node.attributes {
					continue
				}
				traversal.emit(Reference{kind, node.attributes['name']},
					node.attributes['protect'], mut sections)!
			}
		}
	}
	if sections.len == 0 {
		return
	}
	platform := feature.node.attributes['platform']
	define := traversal.registry.platforms[platform]
	if platform != '' && define == '' {
		return error('missing Vulkan platform guard for ${platform}')
	}
	traversal.plan.features << RegistryFeature{
		name:            feature.name
		platform:        if platform == '' { '' } else { 'vulkan_${platform}' }
		platform_define: define
		protect:         feature.node.attributes['protect']
		sections:        sections
	}
}

pub fn native_binding_plan(path string) !BindingPlan {
	registry := load_core_registry(path)!
	mut requirements := registry_requirements(registry)
	requirements.select(registry)!
	mut traversal := CoreTraversal{
		registry:     registry
		requirements: requirements
		plan:         BindingPlan{
			type_names: registry.type_names
		}
	}
	for feature in registry.features {
		traversal.emit_feature(feature)!
	}
	return traversal.plan
}
