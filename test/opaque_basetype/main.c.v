// Verify that the generated opaque alias resolves to the actual C pointer typedef.
module main

import antono2.vulkan as vk

fn main() {
	assert sizeof(vk.InternalHandleNV) == sizeof(voidptr)
	println('Opaque Vulkan internal handle has pointer-sized C ABI.')
}
