// Translate registry version defines while keeping the binding's public names and masks.
module coregen

struct RegistryDefine {
	name string
	text string
}

// These helpers mirror the public binding API. In particular the legacy
// version_minor uses a 12-bit mask, while api_version_minor uses 10 bits.
const version_helpers = {
	'VK_MAKE_VERSION':           'pub fn make_version(major u32, minor u32, patch u32) u32 {
		return (major << 22) | (minor << 12) | patch
	}'
	'VK_VERSION_MAJOR':          'pub fn version_major(version u32) u32 {
		return version >> 22
	}'
	'VK_VERSION_MINOR':          'pub fn version_minor(version u32) u32 {
		return (version >> 12) & 0xFFF
	}'
	'VK_VERSION_PATCH':          'pub fn version_patch(version u32) u32 {
		return version & 0xFFF
	}'
	'VK_MAKE_API_VERSION':       'pub fn make_api_version(variant u32, major u32, minor u32, patch u32) u32 {
		return (variant << 29) | (major << 22) | (minor << 12) | patch
	}'
	'VK_API_VERSION_VARIANT':    'pub fn version_variant(version u32) u32 {
		return version >> 29
	}'
	'VK_API_VERSION_MAJOR':      'pub fn api_version_major(version u32) u32 {
		return (version >> 22) & u32(0x7F)
	}'
	'VK_API_VERSION_MINOR':      'pub fn api_version_minor(version u32) u32 {
		return (version >> 12) & u32(0x3FF)
	}'
	'VK_API_VERSION_PATCH':      'pub fn api_version_patch(version u32) u32 {
		return version & u32(0xFFF)
	}'
	'VK_MAKE_VIDEO_STD_VERSION': 'pub fn make_video_std_version(major u32, minor u32, patch u32) u32 {
		return (major << 22) | (minor << 12) | patch
	}'
}

fn emit_define(decl RegistryDefine) !string {
	name := decl.name
	if helper := version_helpers[name] {
		return helper
	}
	if name == 'VK_HEADER_VERSION' {
		for line in decl.text.split_into_lines() {
			fields := line.fields()
			if fields.len >= 3 && fields[0] == '#define' && fields[1] == name
				&& fields[2].bytes().all(it.is_digit()) {
				return 'pub const header_version = ${fields[2]}'
			}
		}
		return error('missing numeric Vulkan header version')
	}
	if name.starts_with('VK_API_VERSION') || name.starts_with('VKSC_API_VERSION')
		|| name == 'VK_HEADER_VERSION_COMPLETE' {
		tag := 'VK_MAKE_API_VERSION('
		start := decl.text.index(tag) or { return '' }
		call := decl.text[start + tag.len..]
		arguments, rest := call.split_once(')') or {
			return error('missing closing parenthesis in ${name}')
		}
		mut values := arguments.split(',').map(it.trim_space())
		if values.len != 4 {
			return error('${name} has ${values.len} version components')
		}
		for mut value in values {
			if value == 'VK_HEADER_VERSION' {
				value = 'header_version'
			}
		}
		return
			'pub const ${remove_prefix(name).to_lower()} = make_api_version(${values.join(', ')})' +
			rest.trim_right(' \t\n\r')
	}
	if name.starts_with('VK_STD_VULKAN_VIDEO_CODEC_') {
		_, suffix := name.split_once('_API_VERSION_') or { return '' }
		values := suffix.split('_')
		if values.len == 3 && values.all(it != '' && it.bytes().all(it.is_digit())) {
			return 'pub const ${remove_prefix(name).to_lower()} = make_video_std_version(${values.join(', ')})'
		}
	}
	// C preprocessor and handle macros are compiled by the Vulkan headers.
	return ''
}
