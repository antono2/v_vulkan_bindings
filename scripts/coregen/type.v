// Resolve core typedefs and ABI aliases in registry traversal order.
module coregen

struct RegistryType {
	name       string
	category   string
	alias      string
	c_type     string
	suffix     string
	deprecated string
}

struct TypeEvent {
	kind  string
	index int
}

struct TypeState {
mut:
	roots      map[string]string
	enums      map[string]bool
	value_at   map[string]int
	aliases    map[string]string
	type_slots map[string]string
}

fn (mut state TypeState) set_root(name string, root string, order int) {
	state.roots[name] = root
	if root in primitive_types {
		state.value_at[name] = order
	}
}

fn (mut state TypeState) resolve_alias(name string, alias string, order int) string {
	target := remove_prefix(alias)
	if target in primitive_types {
		state.set_root(name, target, order)
		return target
	}
	if mapped := platform_types[target] {
		state.set_root(name, mapped, order)
		return mapped
	}
	if root := state.roots[target] {
		state.set_root(name, root, order)
		return root
	}
	return target
}

fn (mut state TypeState) emit_typedef(decl RegistryType, known map[string]bool, order int) !string {
	name := remove_prefix(decl.name)
	if decl.category == 'include' {
		return ''
	}
	if decl.alias != '' {
		target := state.resolve_alias(name, decl.alias, order)
		return deprecation_comment(name, decl.deprecated)! + 'pub type ${name} = ${target}'
	}
	match decl.category {
		'' {
			if name == '' || !lowercase(name[0]) || name in scalar_types {
				return ''
			}
			return '@[typedef]\npub struct C.${decl.name} {}'
		}
		'handle' {
			state.set_root(name, 'voidptr', order)
			return '// Pointer to ${decl.name}_T\npub type ${name} = voidptr\n'
		}
		'basetype', 'bitmask' {
			if decl.c_type == '' {
				if decl.category == 'bitmask' || name in scalar_types || name in platform_types {
					return ''
				}
				return 'pub type ${name} = C.${decl.name}\n@[typedef]\npub struct C.${decl.name} {}\n'
			}
			target := typedef_c_type(decl.c_type, decl.suffix, known)
			if target == '' {
				return ''
			}
			return 'pub type ${name} = ${state.resolve_alias(name, target, order)}'
		}
		else {
			return error('unsupported Vulkan registry type category "${decl.category}" for ${decl.name}')
		}
	}
}

fn resolve_types(plan BindingPlan, known map[string]bool) !TypeState {
	mut state := TypeState{}
	for i, event in plan.type_events {
		// A command or callback sees only types already visited when it is recorded.
		order := i + 1
		match event.kind {
			'type' {
				decl := plan.types[event.index]
				state.type_slots[decl.name] = state.emit_typedef(decl, known, order)!
			}
			'group' {
				group := plan.groups[event.index]
				if group.alias != '' {
					target := state.resolve_alias(group.name, group.alias, order)
					state.aliases[group.name] = target
					if target in state.enums {
						state.enums[group.name] = true
						state.value_at[group.name] = order
					}
				} else if group.wide {
					state.set_root(group.name, if group.bitwidth == 64 { 'u64' } else { 'u32' },
						order)
				} else {
					state.enums[group.name] = true
					state.value_at[group.name] = order
				}
			}
			'aggregate' {
				decl := plan.structs[event.index]
				name := remove_prefix(decl.name)
				if decl.alias != '' {
					state.aliases[name] = state.resolve_alias(name, decl.alias, order)
				} else if name !in state.roots {
					state.set_root(name, 'C.${decl.name}', order)
				}
			}
			else {
				return error('unknown Vulkan type event "${event.kind}"')
			}
		}
	}
	return state
}

fn is_visited_value(name string, order int, value_at map[string]int) bool {
	seen := value_at[name] or { return false }
	return seen <= order
}
