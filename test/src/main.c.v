/*
  Creates a Vulkan Instance.
  v -cc gcc run test
*/

module main

import vulkan as vk


#flag linux -I$env('VULKAN_SDK')/include
#flag linux -I$env('VULKAN_SDK')/include/vulkan
#flag linux -I$env('VULKAN_SDK')/include/volk
#flag linux -L$env('VULKAN_SDK')/lib
#flag windows -I$env('VULKAN_SDK')/Include
#flag windows -I$env('VULKAN_SDK')/Include/vulkan
#flag windows -L$env('VULKAN_SDK')/Lib
#flag windows -I$env('VULKAN_SDK')/Include/Volk

//#include "vulkan.h"
#define VOLK_IMPLEMENTATION

#include "volk.h"

fn C.volkInitialize() vk.Result
fn C.volkLoadInstance(vk.Instance)
fn C.volkLoadDevice(vk.Device)


@[heap]
struct App {
pub mut:
	vk_instance vk.Instance
	share_data  []string // some data to share between main() and glfw callback functions
}

fn init_app() App {
	new_app := App{
		vk_instance: unsafe { nil }
		share_data:  []
	}
	return new_app
}

fn main() {
	C.volkInitialize()
	
	mut app := init_app()
	defer {
		unsafe {
			free(app.vk_instance)
		}
	}

	enabled_layer_names := [c'VK_LAYER_KHRONOS_validation']

	create_info := vk.InstanceCreateInfo{
		sType:                      vk.StructureType.instance_create_info
		pNext:                      unsafe { nil }
		flags:                      0
		pApplicationInfo:           &vk.ApplicationInfo{
			sType:              vk.StructureType.application_info
			pNext:              unsafe { nil }
			pApplicationName:   c'Vulkan in V'
			applicationVersion: 1
			pEngineName:        c'Not an Engine'
			engineVersion:      1
			apiVersion:         vk.header_version_complete
		}
		ppEnabledLayerNames:      enabled_layer_names.data
		enabledLayerCount:        u32(enabled_layer_names.len)
		ppEnabledExtensionNames:  unsafe { nil }
		enabledExtensionCount:    0
	}
	create_instance_result := vk.create_instance(&create_info, unsafe{ nil }, &app.vk_instance)
	if create_instance_result != vk.Result.success {
		println('Could not create vulkan instance. VkResult: ${create_instance_result}')
		panic("Test create vulkan instance failed.")
	}
}
