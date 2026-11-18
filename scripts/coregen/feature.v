// Assemble the Vulkan module from the selected features and their declarations.
module coregen

import strings

struct RegistryFeature {
	name            string
	platform        string
	platform_define string
	protect         string
	sections        map[string][]DeclarationSlot
}

pub struct DeclarationSlot {
	kind string
	name string
}

const section_order = ['include', 'define', 'basetype', 'handle', 'enum', 'group', 'bitmask',
	'funcpointer', 'struct', 'commandPointer', 'command']

const binding_header = '// Registry-generated Vulkan declarations; native handles follow Vulkan lifetime rules.
// Regenerate in antono2/v_vulkan_bindings with scripts/generate.sh (or .ps1).
// Do not edit declarations here; change src/vgenerator.py and the registry input.
module vulkan

import vulkan.c as _

#include "c/loader_bridge.h"

// Volk owns the Vulkan loader dispatch table used by this binding. Keep the
// declarations next to the public Vulkan types, while the implementation is
// compiled exactly once in c/volk.c.v.
fn C.volkInitialize() Result
fn C.volkLoadInstance(Instance)
fn C.volkLoadDevice(Device)
'

fn store_declaration(mut output map[string]string, kind string, name string, source string) ! {
	key := '${kind}/${name}'
	if key in output {
		return error('duplicate Vulkan ${kind} ${name}')
	}
	output[key] = source
}

fn render_declarations(plan BindingPlan) !map[string]string {
	mut known := map[string]bool{}
	for name in plan.type_names {
		known[name] = true
	}
	types := resolve_types(plan, known)!
	structure_group := plan.groups.filter(it.name == 'StructureType')
	if structure_group.len != 1 || plan.commands.len == 0 || plan.structs.len == 0 {
		return error('incomplete Vulkan registry plan')
	}
	structure_types := structure_type_lookup(structure_group[0].entries.filter(it.required
		&& !it.protected).map(enum_field('StructureType', it.name)))
	mut declarations := map[string]string{}
	emitter := CommandEmitter{known, types.value_at}
	for command in plan.commands {
		store_declaration(mut declarations, 'command', command.name, emitter.emit(command) + '\n')!
	}
	for aggregate in plan.structs {
		source := emit_aggregate(aggregate, known, structure_types,
			types.aliases[remove_prefix(aggregate.name)])!
		store_declaration(mut declarations, 'aggregate', aggregate.name, source + '\n')!
	}
	for group in plan.groups {
		source := emit_group(group, types.aliases[group.name])!
		formatted := if group.alias == '' { '\n' + source } else { source + '\n' }
		store_declaration(mut declarations, 'group', group.name, formatted)!
	}
	for constant in plan.constants {
		comment := deprecation_comment(constant.name, constant.deprecated)!
		source := emit_constant(constant)!
		store_declaration(mut declarations, 'constant', constant.name, comment + source)!
	}
	for callback in plan.callbacks {
		store_declaration(mut declarations, 'callback', callback.name, emit_callback(callback,
			known, types.value_at))!
	}
	for decl in plan.defines {
		store_declaration(mut declarations, 'define', decl.name, emit_define(decl)!)!
	}
	for decl in plan.types {
		store_declaration(mut declarations, 'type', decl.name, types.type_slots[decl.name])!
	}
	return declarations
}

fn is_public_platform_constant(feature string, slot DeclarationSlot) bool {
	if slot.kind != 'constant' {
		return false
	}
	name := remove_prefix(slot.name.to_lower())
	prefix := remove_prefix(feature).to_lower() + '_'
	return name.starts_with(prefix + 'spec_version') || name.starts_with(prefix + 'extension_name')
}

fn take_declarations(mut available map[string]string, slots []DeclarationSlot) ![]string {
	mut source := []string{cap: slots.len}
	for slot in slots {
		key := '${slot.kind}/${slot.name}'
		body := available[key] or { return error('unexpected Vulkan declaration ${key}') }
		available.delete(key)
		if slot.kind != 'type' || body != '' {
			source << body
		}
	}
	return source
}

// emit_bindings renders declarations in their registry-selected feature and platform scope.
pub fn emit_bindings(plan BindingPlan, license string) !string {
	mut available := render_declarations(plan)!
	mut output := strings.new_builder(1024 * 1024)
	output.writeln('/*\n${license.trim_space()}\n*/')
	output.writeln(binding_header)
	mut platforms := map[string]bool{}
	for feature in plan.features {
		output.writeln('')
		if feature.protect != '' {
			output.writeln('#ifdef ${feature.protect}')
		}
		output.writeln('')
		if feature.platform != '' {
			mut public := feature.sections['define'].clone()
			public << feature.sections['enum'].filter(is_public_platform_constant(feature.name, it))
			if public.len > 0 {
				output.writeln(take_declarations(mut available, public)!.join('\n'))
			}
			if feature.platform !in platforms {
				output.writeln('$if ${feature.platform} ? {\n#flag -D${feature.platform_define}\n}')
				platforms[feature.platform] = true
			}
			output.writeln('$if ${feature.platform} ? {')
		}
		for section in section_order {
			mut slots := feature.sections[section]
			if feature.platform != '' {
				if section == 'define' {
					continue
				}
				if section == 'enum' {
					slots = slots.filter(!is_public_platform_constant(feature.name, it))
				}
			}
			body := take_declarations(mut available, slots)!
			if body.len != 0 {
				output.writeln(body.join('\n'))
			}
		}
		if feature.platform != '' {
			output.writeln('}')
		}
		if feature.protect != '' {
			output.writeln('#endif')
		}
	}
	if available.len != 0 {
		return error('${available.len} Vulkan declarations have no feature')
	}
	return output.str()
}
