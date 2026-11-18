// Emit imported C structs, unions, and aliases with Vulkan's default fields.
module coregen

const opaque_platform_handles = ['MTLDevice_id', 'MTLCommandQueue_id', 'MTLBuffer_id',
	'MTLTexture_id', 'MTLSharedEvent_id', 'IOSurfaceRef']

struct Member {
	name               string
	c_type             string
	suffix             string
	dimensions         []string
	literal_dimensions int
	deprecation        string
}

struct Aggregate {
	name          string
	alias         string
	category      string
	deprecated    string
	extends       string
	protect_begin string
	protect_end   string
	members       []Member
}

struct StructureTypes {
	names      map[string]bool
	normalized map[string]string
}

fn structure_type_lookup(values []string) StructureTypes {
	mut exact := map[string]bool{}
	mut normalized := map[string]string{}
	for name in values {
		exact[name] = true
		key := name.replace('_', '').to_lower()
		if key !in normalized {
			normalized[key] = name
		}
	}
	return StructureTypes{exact, normalized}
}

fn (types StructureTypes) initializer(name string) string {
	snake := wrapper_name(name)
	if snake in types.names {
		return ' = StructureType.${snake}'
	}
	if found := types.normalized[name.replace('_', '').to_lower()] {
		return ' = StructureType.${found}'
	}
	return ''
}

fn deprecation_comment(name string, reason string) !string {
	return match reason {
		'' { '' }
		'aliased' { '// ${name} is a legacy alias\n' }
		'ignored', 'unused' { '// ${name} is legacy and not used\n' }
		'true' { '// ${name} is legacy, but no reason was given in the API XML\n' }
		else { return error('${name} has an unknown legacy attribute value "${reason}"') }
	}
}

fn emit_aggregate(aggregate Aggregate, known_types map[string]bool, structure_types StructureTypes) !string {
	name := remove_prefix(aggregate.name)
	if aggregate.alias != '' {
		return 'pub type ${name} = ${aggregate.alias}'
	}
	origin := 'C.${aggregate.name}'
	translator := CommandEmitter{
		known_types: known_types
	}
	mut prefix := deprecation_comment(aggregate.name, aggregate.deprecated)! +
		aggregate.protect_begin
	if aggregate.extends != '' {
		prefix += '// ${name} extends ${aggregate.extends}\n'
	}
	mut fields := []string{cap: aggregate.members.len}
	for member in aggregate.members {
		field := remove_prefix(member.name)
		mut kind := translator.parameter_type(Parameter{
			c_type: member.c_type
			suffix: member.suffix
		})
		mut default_value := ''
		if member.dimensions.len > 0 {
			mut order := member.dimensions.clone()
			if member.literal_dimensions > 1 {
				// Match the shipped spelling of adjacent C dimensions such as VkTransformMatrixKHR.matrix.
				first := order[0]
				order.delete(0)
				order << first
			}
			dimensions := order.map('[${remove_prefix(it.to_lower())}]').join('')
			kind = dimensions + kind
			if uppercase(field[0]) {
				// A named array type avoids V3 parsing PascalCase as an embedded field.
				alias := '${name}${field}Array'
				prefix += 'pub type ${alias} = ${kind}\n'
				kind = alias
			}
		} else if kind.starts_with('PFN_') {
			default_value = ' = unsafe { nil }'
		}
		if kind in opaque_platform_handles {
			kind = 'voidptr'
		}
		if field == 'pNext' && (kind == 'voidptr' || name.ends_with(kind)) {
			kind = 'voidptr'
			default_value = ' = unsafe { nil }'
		} else if field == 'pUserData' && kind == 'voidptr' {
			default_value = ' = unsafe { nil }'
		} else if field == 'sType' {
			default_value = structure_types.initializer(name)
		}
		deprecated := deprecation_comment(member.name, member.deprecation)!
		fields << '${deprecated}${field} ${kind}${default_value}'
	}
	return prefix +
		'pub type ${name} = ${origin}\n@[typedef]\npub ${aggregate.category} ${origin} {\npub mut:\n' +
		fields.join('\n') + '\n}\n' + aggregate.protect_end
}
