#!/usr/bin/env python3 -i
#
# MIT License
#
# Copyright Anton Oreskin | https://gosudev.de
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.



# This file is invoked by passing a generator parameter `vulkan.v` or `vulkan_video.v`.
# It produces `src/vulkan.v` or `src/vulkan_video.v`, which then can be copied to your local .vmodules/vulkan directory.

import re
import string

from generator import (GeneratorOptions,
                       MissingGeneratorOptionsConventionsError,
                       MissingGeneratorOptionsError, MissingRegistryError,
                       OutputGenerator, noneStr, 
                       write)

class VGeneratorOptions(GeneratorOptions):
    """VGeneratorOptions - subclass of GeneratorOptions.

    Adds options used by VOutputGenerator objects during C language header
    generation."""

    def __init__(self,
                 prefixText='',
                 genFuncPointers=True,
                 protectFile=True,
                 protectFeature=True,
                 protectProto=None,
                 protectProtoStr=None,
                 protectExtensionProto=None,
                 protectExtensionProtoStr=None,
                 apicall='',
                 apientry='',
                 apientryp='',
                 indentFuncProto=True,
                 indentFuncPointer=False,
                 alignFuncParam=0,
                 genEnumBeginEndRange=False,
                 genAliasMacro=False,
                 genStructExtendsComment=True,
                 aliasMacro='',
                 misracstyle=False,
                 misracppstyle=False,
                 **kwargs
                 ):
        """Constructor.
        Additional parameters beyond parent class:

        - prefixText - list of strings to prefix generated header with
        (usually a copyright statement + calling convention macros)
        - protectFile - True if multiple inclusion protection should be
        generated (based on the filename) around the entire header
        - protectFeature - True if #ifndef..#endif protection should be
        generated around a feature interface in the header file
        - genFuncPointers - True if function pointer typedefs should be
        generated
        - protectProto - If conditional protection should be generated
        around prototype declarations, set to either '#ifdef'
        to require opt-in (#ifdef protectProtoStr) or '#ifndef'
        to require opt-out (#ifndef protectProtoStr). Otherwise
        set to None.
        - protectProtoStr - #ifdef/#ifndef symbol to use around prototype
        declarations, if protectProto is set
        - protectExtensionProto - If conditional protection should be generated
        around extension prototype declarations, set to either '#ifdef'
        to require opt-in (#ifdef protectExtensionProtoStr) or '#ifndef'
        to require opt-out (#ifndef protectExtensionProtoStr). Otherwise
        set to None
        - protectExtensionProtoStr - #ifdef/#ifndef symbol to use around
        extension prototype declarations, if protectExtensionProto is set
        - apicall - string to use for the function declaration prefix,
        such as APICALL on Windows
        - apientry - string to use for the calling convention macro,
        in typedefs, such as APIENTRY
        - apientryp - string to use for the calling convention macro
        in function pointer typedefs, such as APIENTRYP
        - indentFuncProto - True if prototype declarations should put each
        parameter on a separate line
        - indentFuncPointer - True if typedefed function pointers should put each
        parameter on a separate line
        - alignFuncParam - if nonzero and parameters are being put on a
        separate line, align parameter names at the specified column
        - genEnumBeginEndRange - True if BEGIN_RANGE / END_RANGE macros should
        be generated for enumerated types
        - genAliasMacro - True if the OpenXR alias macro should be generated
        for aliased types (unclear what other circumstances this is useful)
        - genStructExtendsComment - True if comments showing the structures
        whose pNext chain a structure extends are included before its
        definition
        - aliasMacro - alias macro to inject when genAliasMacro is True
        - misracstyle - generate MISRA C-friendly headers
        - misracppstyle - generate MISRA C++-friendly headers"""

        GeneratorOptions.__init__(self, **kwargs)

        self.prefixText = prefixText
        """list of strings to prefix generated header with (usually a copyright statement + calling convention macros)."""

        self.genFuncPointers = genFuncPointers
        """True if function pointer typedefs should be generated"""

        self.protectFile = protectFile
        """True if multiple inclusion protection should be generated (based on the filename) around the entire header."""

        self.protectFeature = protectFeature
        """True if #ifndef..#endif protection should be generated around a feature interface in the header file."""

        self.protectProto = protectProto
        """If conditional protection should be generated around prototype declarations, set to either '#ifdef' to require opt-in (#ifdef protectProtoStr) or '#ifndef' to require opt-out (#ifndef protectProtoStr). Otherwise set to None."""

        self.protectProtoStr = protectProtoStr
        """#ifdef/#ifndef symbol to use around prototype declarations, if protectProto is set"""

        self.protectExtensionProto = protectExtensionProto
        """If conditional protection should be generated around extension prototype declarations, set to either '#ifdef' to require opt-in (#ifdef protectExtensionProtoStr) or '#ifndef' to require opt-out (#ifndef protectExtensionProtoStr). Otherwise set to None."""

        self.protectExtensionProtoStr = protectExtensionProtoStr
        """#ifdef/#ifndef symbol to use around extension prototype declarations, if protectExtensionProto is set"""

        self.apicall = apicall
        """string to use for the function declaration prefix, such as APICALL on Windows."""

        self.apientry = apientry
        """string to use for the calling convention macro, in typedefs, such as APIENTRY."""

        self.apientryp = apientryp
        """string to use for the calling convention macro in function pointer typedefs, such as APIENTRYP."""

        self.indentFuncProto = indentFuncProto
        """True if prototype declarations should put each parameter on a separate line"""

        self.indentFuncPointer = indentFuncPointer
        """True if typedefed function pointers should put each parameter on a separate line"""

        self.alignFuncParam = alignFuncParam
        """if nonzero and parameters are being put on a separate line, align parameter names at the specified column"""

        self.genEnumBeginEndRange = genEnumBeginEndRange
        """True if BEGIN_RANGE / END_RANGE macros should be generated for enumerated types"""

        self.genAliasMacro = genAliasMacro
        """True if the OpenXR alias macro should be generated for aliased types (unclear what other circumstances this is useful)"""

        self.genStructExtendsComment = genStructExtendsComment
        """True if comments showing the structures whose pNext chain a structure extends are included before its definition"""

        self.aliasMacro = aliasMacro
        """alias macro to inject when genAliasMacro is True"""

        self.misracstyle = misracstyle
        """generate MISRA C-friendly headers"""

        self.misracppstyle = misracppstyle
        """generate MISRA C++-friendly headers"""

        self.codeGenerator = True
        """True if this generator makes compilable code"""


class VOutputGenerator(OutputGenerator):
    """Generates V-language API interfaces."""

    # File that stores the exact C code string for anything found with REPLACEMENT_CONTAINS_ARR
    # The C code can then be used in REPLACEMENT_MAP
    REPLACEMENT_MAP_FILE_PATH = "../../REPLACEMENT_MAP.txt"

    # This is an ordered list of sections in the header file.
    TYPE_SECTIONS = ['include', 'define', 'basetype', 'handle', 'enum',
                     'group', 'bitmask', 'funcpointer', 'struct']
    ALL_SECTIONS = TYPE_SECTIONS + ['commandPointer', 'command']

    # These are used to find the base alias in genGroup,
    BASE_TYPES_ARR = [
        'u32',
        'u64',
        'usize', 
        'f32', 
        'i32', 
        'int', 
        'u16', 
        'char', 
        'voidptr'
    ]

    # Map like '(VkFlags: u32), (VkAccessFlags: u32),
    # where VkAccessFlags is an alias for VkFlags in C, but V doesn't allow aliasing,
    # so we just track the base type for each alias.
    ALIAS_TO_BASE_TYPE_MAP = {}

    # Used to find things like "dstOffsets[2]" in struct member name
    ARRAY_REGEX = re.compile(r"\w+(\[\w+\])")

    # This one from nickl- on stackoverflow also takes care of
    # - '_' as first character
    # - multiple upper case characters
    # - numbers in names
    # https://stackoverflow.com/questions/1175208/elegant-python-function-to-convert-camelcase-to-snake-case
    CAMEL_TO_SNAKE_CASE_REGEX = re.compile('((?<=[a-z0-9])[A-Z]|(?!^)[A-Z](?=[a-z]))')
    # PhysicalDeviceVulkan13Features -> physical_device_vulkan1_3_features
    # PhysicalDevice16BitStorageFeatures -> physical_device16bit_storage_features
    # PhysicalDeviceVulkan13Features -> physical_device_vulkan1_3_features
    # BufferMemoryRequirementsInfo2 -> buffer_memory_requirements_info2
    # PhysicalDeviceIDProperties -> physical_device_id_properties
    # PhysicalDeviceMaintenance3Properties -> physical_device_maintenance3_properties
    # PhysicalDeviceVulkanMemoryModelFeatures -> physical_device_vulkan_memory_model_features
    # PhysicalDeviceShaderDemoteToHelperInvocationFeatures -> physical_device_shader_demote_to_helper_invocation_features
    # PhysicalDeviceTextureCompressionASTCHDRFeatures -> physical_device_texture_compression_astc_hdr_features
    
    # There is an enum StructureType in the vulkan registry.
    # Also, each struct has a field sType containing this enum.
    # This array stores enum values and sets a default value for sType, if possible
    STRUCTURE_TYPES = []
    STRUCTURE_TYPES_NUMBER_WITH_UNDERSCORE_REGEX = re.compile('(?<=[A-Z])_(?P<num_after_underscore>[0-9])')
    
    STD_VIDEO_MAKE_VERSION_REGEX = re.compile(r'#define VK_STD_VULKAN_VIDEO_CODEC(\w+)API_VERSION_(\d+)_(\d+)_(\d+)')

    # Array of enum names. To not set mut for enum types in funtion paramters
    ENUM_TYPES = []

    TYPE_MAP = {
        'size_t': 'usize',
        'void*': 'voidptr',
        '&void': 'voidptr',
        'void**': '&voidptr',
        'void': '',
        'uint8_t': 'u8',
        'uint16_t': 'u16',
        'uint32_t': 'u32',
        'uint64_t': 'u64',
        'int8_t': 'i8',
        'int16_t': 'i16',
        'int32_t': 'i32',
        'int64_t': 'i64',
        'double': 'f64',
        'byte*': '&u8',
        'char*': '&char',
        'char**': '&&char',
        'float': 'f32',
        'float*': '&f32',
        'char* const*': '&&char',
        'float64': 'f64',
        'float64*': '&f64',
    }

    REPLACEMENT_MAP = {
        '#if !defined(VK_NO_STDINT_H)\n    #include <stdint.h>\n#endif\n':
        '',
#        '#define VK_MAKE_VIDEO_STD_VERSION(major, minor, patch) \\\n    ((((uint32_t)(major)) << 22) | (((uint32_t)(minor)) << 12) | ((uint32_t)(patch)))\n':
#        'pub fn make_video_std_version(major u32, minor u32, patch u32) u32 {\n  return (major << 22) | (minor << 12) | patch\n}\n',
#        '\n#define VK_STD_VULKAN_VIDEO_CODEC_H264_DECODE_API_VERSION_1_0_0 VK_MAKE_VIDEO_STD_VERSION(1, 0, 0)\n':
#        'pub const std_vulkan_video_codec_h264_decode_api_version_1_0_0 = make_video_std_version(1, 0, 0)\n', 
#        '\n#define VK_STD_VULKAN_VIDEO_CODEC_H264_ENCODE_API_VERSION_1_0_0 VK_MAKE_VIDEO_STD_VERSION(1, 0, 0)\n':
#        'pub const std_vulkan_video_codec_h264_encode_api_version_1_0_0 = make_video_std_version(1, 0, 0)\n', 
#        '\n#define VK_STD_VULKAN_VIDEO_CODEC_H265_DECODE_API_VERSION_1_0_0 VK_MAKE_VIDEO_STD_VERSION(1, 0, 0)\n':
#        'pub const std_vulkan_video_codec_h265_decode_api_version_1_0_0 = make_video_std_version(1, 0, 0)\n', 
#        '\n#define VK_STD_VULKAN_VIDEO_CODEC_H265_ENCODE_API_VERSION_1_0_0 VK_MAKE_VIDEO_STD_VERSION(1, 0, 0)\n':
#        'pub const std_vulkan_video_codec_h265_encode_api_version_1_0_0 = make_video_std_version(1, 0, 0)\n', 
#        '\n#define VK_STD_VULKAN_VIDEO_CODEC_AV1_DECODE_API_VERSION_1_0_0 VK_MAKE_VIDEO_STD_VERSION(1, 0, 0)\n':
#        'pub const std_vulkan_video_codec_av1_decode_api_version_1_0_0 = make_video_std_version(1, 0, 0)\n', 
#        '\n#define VK_STD_VULKAN_VIDEO_CODEC_AV1_ENCODE_API_VERSION_1_0_0 VK_MAKE_VIDEO_STD_VERSION(1, 0, 0)\n':
#        'pub const std_vulkan_video_codec_av1_encode_api_version_1_0_0 = make_video_std_version(1, 0, 0)\n', 
        
        
        '\n#define VK_DEFINE_HANDLE(object) typedef struct object##_T* object;\n':
        '',
        '\n#ifndef VK_USE_64_BIT_PTR_DEFINES\n    #if defined(__LP64__) || defined(_WIN64) || (defined(__x86_64__) && !defined(__ILP32__) ) || defined(_M_X64) || defined(__ia64) || defined (_M_IA64) || defined(__aarch64__) || defined(__powerpc64__) || (defined(__riscv) && __riscv_xlen == 64)\n        #define VK_USE_64_BIT_PTR_DEFINES 1\n    #else\n        #define VK_USE_64_BIT_PTR_DEFINES 0\n    #endif\n#endif\n':
        '',
        '\n#ifndef VK_DEFINE_NON_DISPATCHABLE_HANDLE\n    #if (VK_USE_64_BIT_PTR_DEFINES==1)\n        #if (defined(__cplusplus) && (__cplusplus >= 201103L)) || (defined(_MSVC_LANG) && (_MSVC_LANG >= 201103L))\n            #define VK_NULL_HANDLE nullptr\n        #else\n            #define VK_NULL_HANDLE ((void*)0)\n        #endif\n    #else\n        #define VK_NULL_HANDLE 0ULL\n    #endif\n#endif\n#ifndef VK_NULL_HANDLE\n    #define VK_NULL_HANDLE 0\n#endif\n':
        '',
        '\n#ifndef VK_DEFINE_NON_DISPATCHABLE_HANDLE\n    #if (VK_USE_64_BIT_PTR_DEFINES==1)\n        #define VK_DEFINE_NON_DISPATCHABLE_HANDLE(object) typedef struct object##_T *object;\n    #else\n        #define VK_DEFINE_NON_DISPATCHABLE_HANDLE(object) typedef uint64_t object;\n    #endif\n#endif\n':
        '',
        # Deprecated, just replace with empty
        '// VK_MAKE_VERSION is deprecated, but no reason was given in the API XML\n// DEPRECATED: This define is deprecated. VK_MAKE_API_VERSION should be used instead.\n#define VK_MAKE_VERSION(major, minor, patch) \\\n    ((((uint32_t)(major)) << 22U) | (((uint32_t)(minor)) << 12U) | ((uint32_t)(patch)))\n':
        '',
        '// VK_VERSION_MAJOR is deprecated, but no reason was given in the API XML\n// DEPRECATED: This define is deprecated. VK_API_VERSION_MAJOR should be used instead.\n#define VK_VERSION_MAJOR(version) ((uint32_t)(version) >> 22U)\n':
        '',
        '// VK_VERSION_MINOR is deprecated, but no reason was given in the API XML\n// DEPRECATED: This define is deprecated. VK_API_VERSION_MINOR should be used instead.\n#define VK_VERSION_MINOR(version) (((uint32_t)(version) >> 12U) & 0x3FFU)\n':
        '',
        '// VK_VERSION_PATCH is deprecated, but no reason was given in the API XML\n// DEPRECATED: This define is deprecated. VK_API_VERSION_PATCH should be used instead.\n#define VK_VERSION_PATCH(version) ((uint32_t)(version) & 0xFFFU)\n':
        '',
#        '#define VK_MAKE_API_VERSION(variant, major, minor, patch) \\\n    ((((uint32_t)(variant)) << 29U) | (((uint32_t)(major)) << 22U) | (((uint32_t)(minor)) << 12U) | ((uint32_t)(patch)))\n':
#        'pub fn make_api_version(variant u32, major u32, minor u32, patch u32) u32 {\n  return (variant << 29) | (major << 22) | (minor << 12) | patch\n}\n',
#
#        '// Vulkan 1.0 version number\n#define VK_API_VERSION_1_0 VK_MAKE_API_VERSION(0, 1, 0, 0)// Patch version should always be set to 0\n':
#        'pub const api_version_1_0 = make_api_version(0, 1, 0, 0) // Patch version should always be set to 0',
#        '// Complete version of this file\n#define VK_HEADER_VERSION_COMPLETE VK_MAKE_API_VERSION(0, 1, 4, VK_HEADER_VERSION)\n':
#        'pub const header_version_complete = make_api_version(0, 1, 4, header_version)',
#        '// Complete version of this file\n#define VK_HEADER_VERSION_COMPLETE VK_MAKE_API_VERSION(0, 1, 3, VK_HEADER_VERSION)\n':
#        'pub const header_version_complete = make_api_version(0, 1, 3, header_version)',
#        '#define VK_API_VERSION_VARIANT(version) ((uint32_t)(version) >> 29U)':
#        'pub fn version_variant(version u32) u32 {\n  return version >> 29\n}',
#        '#define VK_API_VERSION_MAJOR(version) (((uint32_t)(version) >> 22U) & 0x7FU)':
#        'pub fn api_version_major(version u32) u32 {\n  return (version >> 22) & u32(0x7F)\n}',
#        '#define VK_API_VERSION_MINOR(version) (((uint32_t)(version) >> 12U) & 0x3FFU)':
#        'pub fn api_version_minor(version u32) u32 {\n  return (version >> 12) & u32(0x3FF)\n}',
#        '#define VK_API_VERSION_PATCH(version) ((uint32_t)(version) & 0xFFFU)':
#        'pub fn api_version_patch(version u32) u32 {\n  return version & u32(0xFFF)\n}',
    }

    # Contains all struct handles in vulkan.
    # They are pointers to StructName_T and their members are unknown.
    C_STRUCT_ARR = []

    C_STRUCT_ARR_WITH_VK_PREFIX = []

    # Used to find static C code, like #define VK_API_VERSION_MAJOR in appendSection
    # The exact C code is then replaced in genType
    REPLACEMENT_CONTAINS_ARR = [
        'STD_VIDEO_DECODE_H264_FIELD_ORDER_COUNT_LIST_SIZE', 
        'VK_MAKE_VIDEO_STD_VERSION(major, minor, patch)', 
        'VK_STD_VULKAN_VIDEO_CODEC_H264_DECODE_API_VERSION_1_0_0', 
        '#define VK_STD_VULKAN_VIDEO_CODEC_H264_ENCODE_API_VERSION_1_0_0 VK_MAKE_VIDEO_STD_VERSION(1, 0, 0)', 
        '#define VK_STD_VULKAN_VIDEO_CODEC_H265_DECODE_API_VERSION_1_0_0 VK_MAKE_VIDEO_STD_VERSION(1, 0, 0)', 
        'VK_STD_VULKAN_VIDEO_CODEC_AV1_DECODE_API_VERSION_1_0_0', 
        'VK_STD_VULKAN_VIDEO_CODEC_AV1_ENCODE_API_VERSION_1_0_0', 
        '#define VK_DEFINE_HANDLE',
        '\n#ifndef VK_DEFINE_NON_DISPATCHABLE_HANDLE\n    #if (VK_USE_64_BIT_PTR_DEFINES==1)\n        #if (defined(__cplusplus) && (__cplusplus >= 201103L)) || (defined(_MSVC_LANG) && (_MSVC_LANG >= 201103L))\n            #define VK_NULL_HANDLE nullptr\n        #else\n            #define VK_NULL_HANDLE ((void*)0)\n        #endif\n    #else\n        #define VK_NULL_HANDLE 0ULL\n    #endif\n#endif\n#ifndef VK_NULL_HANDLE\n    #define VK_NULL_HANDLE 0\n#endif',
        '\n#ifndef VK_USE_64_BIT_PTR_DEFINES\n    #if defined(__LP64__) || defined(_WIN64) || (defined(__x86_64__) && !defined(__ILP32__) ) || defined(_M_X64) || defined(__ia64) || defined (_M_IA64) || defined(__aarch64__) || defined(__powerpc64__) || (defined(__riscv) && __riscv_xlen == 64)\n        #define VK_USE_64_BIT_PTR_DEFINES 1\n    #else\n        #define VK_USE_64_BIT_PTR_DEFINES 0\n    #endif\n#endif',
        '\n#ifndef VK_DEFINE_NON_DISPATCHABLE_HANDLE\n    #if (VK_USE_64_BIT_PTR_DEFINES==1)\n        #define VK_DEFINE_NON_DISPATCHABLE_HANDLE(object) typedef struct object##_T *object;\n    #else\n        #define VK_DEFINE_NON_DISPATCHABLE_HANDLE(object) typedef uint64_t object;\n    #endif\n#endif',
        '#define VK_MAKE_API_VERSION(variant, major, minor, patch)',
        '#define VK_API_VERSION_1_0',
        '#define VK_HEADER_VERSION_COMPLETE',
        '#define VK_MAKE_VERSION',
        '#define VK_VERSION_MAJOR',
        '#define VK_VERSION_MINOR',
        '#define VK_VERSION_PATCH',
        '#define VK_API_VERSION_VARIANT',
        '#define VK_API_VERSION_MAJOR',
        '#define VK_API_VERSION_MINOR',
        '#define VK_API_VERSION_PATCH',
    ]
    
    # The generator fills this ARR with exact C code to write to replacement_map.txt,
    # which can then be put in REPLACEMENT_MAP above
    REPLACEMENT_EXACT_TEXT_ARR = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Internal state - accumulators for different inner block text
        self.sections = {section: [] for section in self.ALL_SECTIONS}
        self.feature_not_empty = False
        self.may_alias = None

    def beginFile(self, genOpts):
        OutputGenerator.beginFile(self, genOpts)
        if self.genOpts is None:
            raise MissingGeneratorOptionsError()
        # V module
        if self.genOpts.protectFile and self.genOpts.filename:
            write("""/*
MIT License

Copyright Anton Oreskin | https://gosudev.de


Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/""", file=self.outFile)
            write('module', 'vulkan', file=self.outFile)
            self.newline()

        # User-supplied prefix text, if any (list of strings)
        if genOpts.prefixText:
            for s in genOpts.prefixText:
                write(s, file=self.outFile)

    def endFile(self):
        # Finish V wrapper and multiple inclusion protection
        if self.genOpts is None:
            raise MissingGeneratorOptionsError()
        # Finish processing in superclass
        OutputGenerator.endFile(self)

        # Write REPLACEMENT_EXACT_TEXT_ARR to replacement_map.txt
        # This exact C code can then be (manually) put in REPLACEMENT_MAP.
        # genType will then replace the c_body with v_body
        # filepath is "../../../REPLACEMENT_MAP.txt"
        # absolute path is "~/workspace/v_vulkan_bindings/REPLACEMENT_MAP.txt"
        with open(self.REPLACEMENT_MAP_FILE_PATH, "w") as text_file:
            key_strings = ''
            for itm in self.REPLACEMENT_EXACT_TEXT_ARR:
                # Writing to file puts new lines instead of just '\n'
                key_strings = key_strings + "'" + self.escStr(itm).replace('\\', '\\\\').replace('\n',
                                                                                                 '\\n') + "':\n    '',\n    "
            text_file.write("# This mapping contains exact C code (key), which will be replaced with the corresponding V code (value). Use the key in REPLACEMENT_MAP in src/vgenerator.py.\n# genType will then replace c_body with v_body.\n# Check REPLACEMENT_CONTAINS_ARR to add another key.\n\
REPLACEMENT_MAP = {{\n    {}\n}}".format(key_strings))


    def beginFeature(self, interface, emit):
        # Start processing in superclass
        OutputGenerator.beginFeature(self, interface, emit)
        # C-specific
        # Accumulate includes, defines, types, enums, function pointer typedefs,
        # end function prototypes separately for this feature. They are only
        # printed in endFeature().
        self.sections = {section: [] for section in self.ALL_SECTIONS}
        self.feature_not_empty = False

    def _endProtectComment(self, protect_str, protect_directive='#ifdef'):
        if protect_directive is None or protect_str is None:
            raise RuntimeError('Should not call in here without something to protect')

        # Do not put comments after #endif closing blocks if this is not set
        if not self.genOpts.conventions.protectProtoComment:
            return ''
        elif 'ifdef' in protect_directive:
            return f' /* {protect_str} */'
        else:
            return f' /* !{protect_str} */'

    # For each section, join content and write to file.
    # Conditional compilation guard is placed around multiple functions.
    def endFeature(self):
        "Actually write the interface to the output file."
        if self.emit:
            if self.feature_not_empty:
                if self.genOpts is None:
                    raise MissingGeneratorOptionsError()
                if self.genOpts.conventions is None:
                    raise MissingGeneratorOptionsConventionsError()
                is_core = self.featureName and self.featureName.startswith(self.conventions.api_prefix + 'VERSION_')

                self.featureName = self.removeVk(self.featureName).lower()

                if self.genOpts.conventions.writeFeature(self.featureName, self.featureExtraProtect, self.genOpts.filename):
                    self.newline()
                    if self.genOpts.protectFeature:
                        write('#ifndef', self.featureName, file=self.outFile)

                    # If type declarations are needed by other features based on
                    # this one, it may be necessary to suppress the ExtraProtect,
                    # or move it below the 'for section...' loop.
                    if self.featureExtraProtect is not None:
                        write('#ifdef', self.featureExtraProtect, file=self.outFile)
                    self.newline()

                    self.featureName = self.removeVk(self.featureName)
                    # NOTE Anton: This can be used for programmatically checking available extensions, once conditional compilation is used
                    #write(f'// {self.featureName} is a preprocessor guard. Do not pass it to API calls.', file=self.outFile)
                    #write('const', self.featureName, '=', '1', file=self.outFile)
                    for section in self.TYPE_SECTIONS:
                        contents = self.sections[section]
                        if contents:
                            write('\n'.join(contents), file=self.outFile)
                    if self.genOpts.genFuncPointers and self.sections['commandPointer']:
                        write('\n'.join(self.sections['commandPointer']), file=self.outFile)
                        self.newline()

                    if self.sections['command']:
                        if self.genOpts.protectProto:
                            write(self.genOpts.protectProto,
                                  self.genOpts.protectProtoStr, file=self.outFile)
                        if self.genOpts.protectExtensionProto and not is_core:
                            write(self.genOpts.protectExtensionProto,
                                  self.genOpts.protectExtensionProtoStr, file=self.outFile)
                        write('\n'.join(self.sections['command']), end='', file=self.outFile)
                        if self.genOpts.protectExtensionProto and not is_core:
                            write('#endif' +
                                  self._endProtectComment(protect_directive=self.genOpts.protectExtensionProto,
                                                          protect_str=self.genOpts.protectExtensionProtoStr),
                                  file=self.outFile)
                        if self.genOpts.protectProto:
                            write('#endif' +
                                  self._endProtectComment(protect_directive=self.genOpts.protectProto,
                                                          protect_str=self.genOpts.protectProtoStr),
                                  file=self.outFile)
                        else:
                            self.newline()
                    if self.featureExtraProtect is not None:
                        write('#endif' +
                              self._endProtectComment(protect_str=self.featureExtraProtect),
                              file=self.outFile)

                    if self.genOpts.protectFeature:
                        write('#endif' +
                              self._endProtectComment(protect_str=self.featureName),
                              file=self.outFile)
        # Finish processing in superclass
        OutputGenerator.endFeature(self)

    #NOTE Anton: this is called after every feature and can be used for debugging and checking what method created a specific text
    def appendSection(self, section, text):
        "Append a definition to the specified section"

        if section is None:
            self.logMsg('error', 'Missing section in appendSection (probably a <type> element missing its \'category\' attribute. Text:', text)
            exit(1)

        # Add text to REPLACEMENT_EXACT_TEXT_ARR if it is in REPLACEMENT_CONTAINS_ARR
        # See REPLACEMENT_CONTAINS_ARR for explanation
        # Note Anton: https://github.com/vlang/v/issues/24164
        # Function parameter 3 is an array that is not known to V
        if 'pub fn cmd_set_fragment_shading_rate_enum_nv' in text or 'pub fn cmd_set_fragment_shading_rate_khr' in text:
            text = '/*' + text + '*/'
        esc_text = self.escStr(text)
        for starts_with in self.REPLACEMENT_CONTAINS_ARR:
            if text.__contains__(starts_with):
                self.REPLACEMENT_EXACT_TEXT_ARR.append(esc_text)

        if esc_text in self.REPLACEMENT_MAP:
            text = self.REPLACEMENT_MAP[esc_text]

        self.sections[section].append(text)
        self.feature_not_empty = True

    def genCType(self, typeinfo, name, alias):
        "Generate type."
        OutputGenerator.genType(self, typeinfo, name, alias)
        typeElem = typeinfo.elem

        # Vulkan:
        # Determine the category of the type, and the type section to add
        # its definition to.
        # 'funcpointer' is added to the 'struct' section as a workaround for
        # internal issue #877, since structures and function pointer types
        # can have cross-dependencies.
        category = typeElem.get('category')
        if category == 'funcpointer':
            section = 'struct'
        else:
            section = category

        if category in ('struct', 'union'):
            # If the type is a struct type, generate it using the
            # special-purpose generator.
            self.genStruct(typeinfo, name, alias, keep_vk_member_name = True)
        else:
            if self.genOpts is None:
                raise MissingGeneratorOptionsError()

            body = self.deprecationComment(typeElem)

            # OpenXR: this section was not under 'else:' previously, just fell through
            if alias:
                # If the type is an alias, just emit a typedef declaration
                body += 'typedef ' + alias + ' ' + name + ';\n'
            else:
                # Replace <apientry /> tags with an APIENTRY-style string
                # (from self.genOpts). Copy other text through unchanged.
                # If the resulting text is an empty string, do not emit it.
                body += noneStr(typeElem.text)
                for elem in typeElem:
                    if elem.tag == 'apientry':
                        body += self.genOpts.apientry + noneStr(elem.tail)
                    else:
                        body += noneStr(elem.text) + noneStr(elem.tail)
                if category == 'define' and self.misracppstyle():
                    body = body.replace("(uint32_t)", "static_cast<uint32_t>")
            if body:
                # Add extra newline after multi-line entries.
                if '\n' in body[0:-1]:
                    body += '\n'
                # We just need to c_body, to compare against a list of replacements in genType,
                return section, body

    def genVType(self, typeinfo, name, alias):
        "Generate type."
        OutputGenerator.genType(self, typeinfo, name, alias)
        typeElem = typeinfo.elem

        # Vulkan:
        # Determine the category of the type, and the type section to add
        # its definition to.
        # 'funcpointer' is added to the 'struct' section as a workaround for
        # internal issue #877, since structures and function pointer types
        # can have cross-dependencies.
        category = typeElem.get('category')
        if category == 'funcpointer':
            section = 'struct'
        else:
            section = category

        if category in ('struct', 'union'):
            # If the type is a struct type, generate it using the
            # special-purpose generator.
            self.genStruct(typeinfo, name, alias, keep_vk_member_name = True)
        else:
            if self.genOpts is None:
                raise MissingGeneratorOptionsError()

            body = self.deprecationComment(typeElem)

            v_name = ''
            v_value = v_name
            v_type  = ''
            v_text = ''  # something like 'const' or 'type'
            v_is_handle = False
            v_is_function_pointer = name.startswith('PFN_')
            v_params = []

            # OpenXR: this section was not under 'else:' previously, just fell through
            if alias:
                # If the type is an alias, make sure not to alias an alias
                name,  alias = self.v_translate_c_name_to_basetype(name, alias)
                body += 'pub type ' + name + ' = ' + alias + '\n'
            else:
                # Replace <apientry /> tags with an APIENTRY-style string
                # (from self.genOpts). Copy other text through unchanged.
                # If the resulting text is an empty string, do not emit it.
                for elem in typeElem:
                    if elem.tag == 'apientry':
                        body += self.genOpts.apientry + noneStr(elem.tail)
                    elif elem.tag == 'type':
                        if noneStr(elem.text) == 'VK_DEFINE_HANDLE':
                            v_type = '&{}'.format('C.Vk' + name)
                            v_is_handle = True
                        elif noneStr(elem.text) == 'VK_DEFINE_NON_DISPATCHABLE_HANDLE':
                            # Note: Not sure if we want 64 bit pointers for opaque types, instead of voidptr
                            # v_type = 'u64(&{})'.format(name)
                            # self.C_STRUCT_ARR.append(name)
                            v_type = '&{}'.format('C.' + name)
                            v_is_handle = True
                        else:
                            v_type = noneStr(elem.text)
                            param_name = (noneStr(elem.tail)
                                          .replace(',', '')
                                          .replace(' ', '')
                                          .replace(')', '')
                                          .replace(';', '')
                                          # No const type here, but handled later for const_ function parameters
                                          .replace('\nconst', '')
                                          .strip()
                                          )

                            if v_type in self.TYPE_MAP:
                                v_type = self.TYPE_MAP[v_type]

                            v_type = self.removeVk(v_type)

                            if 'PFN_' in name and '*' in body:
                                v_params[0] = (v_params[0][0], 'voidptr')

                            if '*' in param_name:
                                ptr_count = param_name.count('*')
                                # NOTE Anton: Removing const, as it just signals that the pointer won't be changed by vulkan
                                param_name = param_name.replace('*', '').replace('const', '').strip()
                                if v_type in self.C_STRUCT_ARR:
                                    for _ in range(ptr_count):
                                        v_type = '&' + v_type 
                                else:
                                    for _ in range(ptr_count):
                                        v_type = '&' + v_type 
                                # In case of 'void*', v_type will be just '&', as void was replaced with empty string by TYPE_MAP
                                if v_type.replace('&', '') == '':
                                    v_type = 'voidptr'
                            elif v_type in self.C_STRUCT_ARR:
                                pass

                            v_type = self.removeVk(v_type)
                            v_name = self.removeVk(v_name)
                            param_name = self.removeVk(param_name)

                            # Name and type are appended to v_params in separate runs of the for loop,
                            # but always in order, so that we can simply assume the last tuple contains
                            # the current v_name
                            if v_is_function_pointer and len(v_params) > 0:
                                last_tuple = v_params[len(v_params) - 1]
                                if last_tuple[0] is not None and last_tuple[1] is not None:
                                    v_params.append((param_name, v_type))
                                else:
                                    v_params[len(v_params) - 1] = (last_tuple[0], v_type)
                            else:
                                v_params.append((param_name, v_type))
                        v_text = 'type'
                    elif elem.tag == 'name':
                        v_name = name
                        v_name = self.removeVk(v_name)
                        if v_is_handle:
                            self.C_STRUCT_ARR.append(v_name)
                            self.C_STRUCT_ARR_WITH_VK_PREFIX.append(v_name)
                        if v_is_function_pointer and len(v_params) > 0:
                            last_tuple = v_params[len(v_params) - 1]
                            if last_tuple[0] is not None and last_tuple[1] is not None:
                                v_params.append((v_name, ''))
                            else:
                                v_params[len(v_params) - 1] = (v_name, last_tuple[1])
                        else:
                            v_params.append((v_name, ''))
                        v_text = 'type'
                    if category == 'define' and self.misracppstyle():
                        body = body.replace("(uint32_t)", "static_cast<uint32_t>")
                    else:
                        # NOTE: Never reached
                        v_value = noneStr(elem.text) + noneStr(elem.tail).replace(';', '')
                        v_text = 'type'
            v_type = self.removeVk(v_type)
            v_name = self.removeVk(v_name)
            v_value = self.removeVk(v_value)

            # V doesn't allow for non basetype (u32, u64) alias,
            # so add the current type to ALIAS_TO_BASE_TYPE_MAP
            if v_text == 'type' and v_type in self.BASE_TYPES_ARR:
                self.ALIAS_TO_BASE_TYPE_MAP[v_name] = v_type
            if v_is_handle:
                body = '// Pointer to {}_T\npub type {} = voidptr'.format(name, v_name)
                self.ALIAS_TO_BASE_TYPE_MAP[v_name] = 'voidptr'
            elif v_is_function_pointer:
                v_params_str = ''
                is_first_iteration = True
                for param in v_params:
                    # Ignore index 0, which contains function name and return type
                    if is_first_iteration:
                        is_first_iteration = False
                        continue
                    v_params_str += '\n  {},'.format( param[1])
                # Remove tailing ','
                v_params_str = v_params_str[:-1]
                body = 'pub type {} = fn ({}) {}'.format(v_name, v_params_str, v_params[0][1])
                # V bug where fn type definitons can not be multiple lines
                # TODO: Double check and create an issue on V github
                body = ' '.join(body.split('\n'))
            elif v_text and v_name and v_type:
                # V doesn't allow for non basetype (u32, u64, ...) alias,
                # so find the root basetype and assign that instead.
                # This is also needed for setting mut on function calls later
                if v_type in self.BASE_TYPES_ARR:
                    self.ALIAS_TO_BASE_TYPE_MAP[v_name] = v_type
                else:
                    if v_type in self.ALIAS_TO_BASE_TYPE_MAP:
                        v_type = self.ALIAS_TO_BASE_TYPE_MAP[v_type]
                        self.ALIAS_TO_BASE_TYPE_MAP[v_name] = v_type
                v_name, v_type = self.v_translate_c_name_to_basetype(v_name,  v_type)
                if v_type == 'MAKE_API_VERSION':
                    body = 'pub const {} = {}'.format(v_name.lower(),  v_value.lower().replace('vk_header_version', 'header_version'))
                else:
                    body = 'pub {} {} = {}'.format(v_text, v_name, v_type)
            elif v_value and v_text and not category == 'basetype':
                body = 'pub {} {} = {}'.format(v_text, v_value, v_name)
            # Handle OHNativeWindow and other basetypes. The actual OHNativeWindow type is defined in some other header.
            # Currently (2025) only &OHNativeWindow is used and is created by a vulkan function.
            elif v_value and v_text and category == 'basetype':
                body = 'pub type ' + v_value + ' = C.' + v_value + '\n@[typedef]\npub struct C.' + v_value + ' {}'
            else:
                if category == 'include' or category == 'define':
                    #NOTE: Since video structs are translated to V in vulkan_video.v,
                    #these #include are not needed anymore
                    return
                elif category == 'bitmask' or category == 'handle':
                    if alias and name:
                        name,  alias = self.v_translate_c_name_to_basetype(name, alias)
                        body = 'pub type {} = {}'.format(name, alias)
                else:
                    #NOTE Anton: never reached, but feel free to check in future for new types
                    print('Omitting body:\n' + body + '\n')
#                    return section, body
                    return

            if body:
                # Add extra newline after multi-line entries.
                if '\n' in body[0:-1]:
                    body += '\n'
                return section, body

    def genProtectString(self, protect_str):
        """Generate protection string.

        Protection strings are the strings defining the OS/Platform/Graphics
        requirements for a given API command.  When generating the
        language header files, we need to make sure the items specific to a
        graphics API or OS platform are properly wrapped in #ifs."""
        protect_if_str = ''
        protect_end_str = ''
        if not protect_str:
            return (protect_if_str, protect_end_str)

        if ',' in protect_str:
            protect_list = protect_str.split(',')
            protect_defs = ('defined(%s)' % d for d in protect_list)
            protect_def_str = ' && '.join(protect_defs)
            protect_if_str = '#if %s\n' % protect_def_str
            protect_end_str = '#endif // %s\n' % protect_def_str
        else:
            protect_if_str = '#ifdef %s\n' % protect_str
            protect_end_str = '#endif // %s\n' % protect_str

        return (protect_if_str, protect_end_str)

    def typeMayAlias(self, typeName):
        if not self.may_alias:
            if self.registry is None:
                raise MissingRegistryError()
            # First time we have asked if a type may alias.
            # So, populate the set of all names of types that may.

            # Everyone with an explicit mayalias="true"
            self.may_alias = set(typeName
                                 for typeName, data in self.registry.typedict.items()
                                 if data.elem.get('mayalias') == 'true')

            # Every type mentioned in some other type's parentstruct attribute.
            polymorphic_bases = (otherType.elem.get('parentstruct')
                                 for otherType in self.registry.typedict.values())
            self.may_alias.update(set(x for x in polymorphic_bases
                                      if x is not None))
        return typeName in self.may_alias

    def genStruct(self, typeinfo, typeName, alias,  keep_vk_member_name = False):
        """Generate struct (e.g. C "struct" type).

        This is a special case of the <type> tag where the contents are
        interpreted as a set of <member> tags instead of freeform C
        C type declarations. The <member> tags are just like <param>
        tags - they are a declaration of a struct or union member.
        Only simple member declarations are supported (no nested
        structs etc.)

        If alias is not None, then this struct aliases another; just
        generate a typedef of that alias."""
        OutputGenerator.genStruct(self, typeinfo, typeName, alias)

        if self.genOpts is None:
            raise MissingGeneratorOptionsError()

        typeElem = typeinfo.elem
        typeNameOrig = typeName
        typeName = self.removeVk(typeName)
        body = self.deprecationComment(typeElem)

        if alias:
            typeName,  alias = self.v_translate_c_name_to_basetype(typeName, alias)
            body = 'pub type ' + typeName + ' = ' + alias + '\n'
        else:
            (protect_begin, protect_end) = self.genProtectString(typeElem.get('protect'))
            if protect_begin:
                body += protect_begin

            if self.genOpts.genStructExtendsComment:
                structextends = typeElem.get('structextends')
                body += '// ' + typeName + ' extends ' + structextends + '\n' if structextends else ''

            body += 'pub type ' + typeName + ' = ' + 'C.'+ typeNameOrig + '\n'
            if typeElem.get('category') == 'struct':
                body += '@[typedef]\npub struct '
            else:
                body += '@[typedef]\npub union '

            # This is an OpenXR-specific alternative where aliasing refers
            # to an inheritance hierarchy of types rather than C-level type
            # aliases.
            if self.genOpts.genAliasMacro and self.typeMayAlias(typeName):
                body += self.genOpts.aliasMacro

            body +=  'C.'+ typeNameOrig + ' {\n'
            if typeName not in self.ALIAS_TO_BASE_TYPE_MAP:
                self.ALIAS_TO_BASE_TYPE_MAP[typeName] = 'C.'+ typeNameOrig
                
            targetLen = self.getMaxCParamTypeLength(typeinfo)
            body += 'pub mut:\n'
            for member in typeElem.findall('.//member'):
                body += self.deprecationComment(member, indent = 4)
                body += self.makeVParamDecl(typeName, member, targetLen + 4, do_struct_members = True,  keep_vk_member_name = keep_vk_member_name)
                body += '\n'
            body += '}\n'
            if protect_end:
                body += protect_end

        self.appendSection('struct', body)

    def genGroup(self, groupinfo, groupName, alias=None):
        """Generate groups (e.g. C "enum" type).

        These are concatenated together with other types.

        If alias is not None, it is the name of another group type
        which aliases this type; just generate that alias."""
        OutputGenerator.genGroup(self, groupinfo, groupName, alias)
        groupElem = groupinfo.elem

        # After either enumerated type or alias paths, add the declaration
        # to the appropriate section for the group being defined.
        if groupElem.get('type') == 'bitmask':
            section = 'bitmask'
        else:
            section = 'group'

        groupName = self.removeVk(groupName)

        # NOTE Anton: In order to Replace C code instead of V code with REPLACEMENT_MAP,
        # we need to generate C code
        # Same is done in genGroup, genStruct, genType
        if alias:
            cbody = 'typedef ' + alias + ' ' + groupName + ';\n'
            if cbody in self.REPLACEMENT_MAP:
                cbody = self.REPLACEMENT_MAP[cbody]
                self.appendSection(section, cbody)
            else:
                groupName,  alias = self.v_translate_c_name_to_basetype(groupName, alias)
                body = 'pub type ' + groupName + ' = ' + alias + '\n'
                # Store enum name and alias. To ignore when setting mut for enum function paramters
                if alias in self.ENUM_TYPES:
                  self.ENUM_TYPES.append(groupName)

                self.appendSection(section, body)
        else:
            if self.genOpts is None:
                raise MissingGeneratorOptionsError()
            # Note: set keep_vk_member_name to True to keep vk enum member names like VK_DYNAMIC_STATE_PATCH_CONTROL_POINTS_EXT
            (section, body) = self.buildEnumVDecl(self.genOpts.genEnumBeginEndRange, groupinfo, groupName, keep_vk_member_name=False)
            self.appendSection(section, '\n' + body)

    def genEnum(self, enuminfo, name, alias):
        """Generate the C declaration for a constant (a single <enum> value).

        <enum> tags may specify their values in several ways, but are usually
        just integers."""
        # c'...string...' error on alias. Ignore them
        # https://github.com/vlang/v/issues/24235
        if enuminfo.elem.attrib.get('deprecated') == 'aliased':
           # return
           pass

        OutputGenerator.genEnum(self, enuminfo, name, alias)
        body = self.deprecationComment(enuminfo.elem)
        body += self.buildConstantVDecl(enuminfo, name, alias)
        self.appendSection('enum', body)

    def buildConstantVDecl(self, enuminfo, name, alias):
        """Generate the C declaration for a constant (a single <enum>
        value).

        <enum> tags may specify their values in several ways, but are
        usually just integers or floating-point numbers."""

        (_, strVal) = self.enumToValue(enuminfo.elem, False)

        # Generate const x = u32(123)
        prefix = ''
        v_type = ''
        v_name = name

        # Only replace U,L,... in types like (~0ULL), not in names like 'vk_google_hlsl_functionality_1_extension_name'
        if strVal.lower().startswith('vk') or strVal.startswith('0x'):
            v_value = strVal
        else:
            v_value = (strVal.replace('~', '')
                             .replace('U', '')
                             .replace('L', '')
                             .replace('F', '')
                             .replace('(', '')
                             .replace(')', ''))

        if enuminfo.elem.get('type') and not alias:
            typeStr = enuminfo.elem.get('type')
            if typeStr in self.TYPE_MAP:
                v_type = self.TYPE_MAP[typeStr]
            else:
                print("Could not find matching V type for " + typeStr)
            if '~' in strVal:
                prefix = '~'

        v_name = v_name.lower().strip()
        # Don't .lower() the value for exact strings, like
        # pub const vk_khr_maintenance_1_extension_name = "VK_KHR_maintenance1"
        # But .lower() the value for references to vk_khr_external_memory_capabilities_extension_name, like
        # pub const vk_khr_maintenance1_extension_name = vk_khr_maintenance_1_extension_name
        if not v_name.lower().endswith("_extension_name") or not v_value.startswith('"'):
            v_value = v_value.lower()
        if v_name.lower().endswith("_extension_name") and v_value.startswith('"'):
            v_value = 'c'+ v_value # Use c strings c'text'

        v_name = self.removeVk(v_name)
        v_value = self.removeVk(v_value)

        if prefix:
            body = 'pub const ' + v_name.ljust(33) + ' = ' + prefix + v_type + "(" + v_value + ")"
        elif not v_type.strip():
            body = 'pub const ' + v_name.ljust(33) + ' = ' + prefix + v_type.strip() + v_value
        else:
            body = 'pub const ' + v_name.ljust(33) + ' = ' + prefix + v_type.strip() + "(" + v_value + ")"

        return body

    def genCmd(self, cmdinfo, name, alias):
        "Command generation"
        OutputGenerator.genCmd(self, cmdinfo, name, alias)

        if self.genOpts is None:
            raise MissingGeneratorOptionsError()
        prefix = ''
        decls = self.makeVDecls(cmdinfo.elem)
        self.appendSection('command', prefix + decls[0] + '\n')
        if self.genOpts.genFuncPointers:
            self.appendSection('commandPointer', decls[1])

    def misracstyle(self):
        return self.genOpts.misracstyle

    def misracppstyle(self):
        return self.genOpts.misracppstyle

    # Remove Vk... from variable names, as they are all in the vulkan name space already
    def removeVk(self, v_name_or_value: string) -> str:
        if v_name_or_value.lower() in ['vk_true', 'vk_false']:
            return v_name_or_value[2:] #_true _false
        if v_name_or_value.lower().startswith('vk_'):
            v_name_or_value = v_name_or_value[3:]
        if v_name_or_value.lower().startswith('vk'):
            v_name_or_value = v_name_or_value[2:]
        return v_name_or_value

    # V doesn't allow for non basetype (u32, u64) aliases,
    # so find the root basetype and assign that instead.
    # Returns basetype if found, the unchanged alias if not found
    def v_translate_c_name_to_basetype(self, name = None, alias = None) -> (str, str):
        alias = self.removeVk(alias)
        name = self.removeVk(name)
        ptr_count = alias.count('&')
        if alias in self.BASE_TYPES_ARR:
            self.ALIAS_TO_BASE_TYPE_MAP[name] = alias
        elif alias in self.C_STRUCT_ARR:
            alias = 'voidptr'
        # &C.VkCommandBuffer -> CommandBuffer
        elif self.removeVk(alias.lstrip('&')) in self.C_STRUCT_ARR:
            for _ in range(ptr_count):
                alias = '&' + alias 
            alias = 'C.Vk' + alias
            self.ALIAS_TO_BASE_TYPE_MAP[name] = alias
        else:
            if alias in self.ALIAS_TO_BASE_TYPE_MAP:
                alias = self.ALIAS_TO_BASE_TYPE_MAP[alias]
                self.ALIAS_TO_BASE_TYPE_MAP[name] = alias

        return name,  alias
    
    # TODO: remove, as only called once
    def v_translate_type_basetype(self,  type) -> str:
        if type in self.C_STRUCT_ARR_WITH_VK_PREFIX:
            return 'voidptr'
#        if type.startswith('['):
#            type = 'voidptr'
#        if type.startswith('&') or type.lstrip('&') in self.C_STRUCT_ARR_WITH_VK_PREFIX:
#            type_without_amp = type[1:]
#            ptr_count = 1
#            if type_without_amp.startswith('&'):
#                type_without_amp = type_without_amp[1:]
#                ptr_count = 2
#            if type_without_amp.startswith('&'):
#                type_without_amp = type_without_amp[1:]
#                ptr_count = 3
#            type = 'voidptr'
#            for _ in range(ptr_count):
#                type = '&' + type
#        
        
        return type

    def v_camel_to_snake_case(self, v_name) -> str:
        return self.CAMEL_TO_SNAKE_CASE_REGEX.sub(r'_\1', v_name).lower()

    def find_matching_structure_type_enum(self, v_name) -> str:
        name_without_underscore_lower = v_name.replace("_", "").lower()
        for type_enum in self.STRUCTURE_TYPES:
            if type_enum.replace("_", "") == name_without_underscore_lower:
                return type_enum
        return ""

    def removeStructEnumNameFromMember(self,  structEnumName,  memberName) -> string:
        # VideoCodecOperationFlagBitsKHR.video_codec_operation_encode_h264_bit_khr
        # VideoCodecOperationFlagBitsKHR.encode_h264
        newName = memberName
        # VideoCodecOperationFlagBitsKHR
        structEnumNameSnakeCase = self.v_camel_to_snake_case(structEnumName)
        # video_codec_operation_flag_bits_khr
        words = structEnumNameSnakeCase.split('_')
        words_end = words
        prefixToRemove = "" 
        # Iterate over: [video, codec, operation, flag, bits, khr] 
        #                 -> [video, codec, operation, flag, bits]
        #                 -> [video, codec, operation, flag]
        #                      ...
        # and remove from start of enum member name
        for i in range(len(words)):
            prefixToRemove = "_".join(words)
            # Remove one word from end for next iteration
            words = words[0:-1]
            if memberName.startswith(prefixToRemove):
                newName = newName[len(prefixToRemove):]
                break
        
        # Remove starting _
        if newName != '' and newName[0] == '_':
            newName = newName[1:]

        # Iterate over: [video, codec, operation, flag, bits, khr] 
        #                 -> [codec, operation, flag, bits, khr]
        #                 -> [operation, flag, bits, khr]
        #                      ...
        # and remove from end of enum member name
        # Note: `bits` corresponds to `bit` in member name
        # Also, some member names have _khr postfix, but the enum name does not
        bits_index = next((i for i, value in enumerate(words_end) if value == 'bits'), -1)
        if (bits_index != -1):
            words_end[bits_index] = 'bit'
        for i in range(len(words_end)):
            if (i < len(words_end) and words_end[i] == 'bits'):
                words_end[i] = 'bit'
            postfixToRemove = "_".join(words_end)
            words_end = words_end[1:]
            if newName.endswith(postfixToRemove):
                newName = newName[0:-len(postfixToRemove)]
                break
            if newName.endswith(postfixToRemove + '_khr'):
                newName = newName[0:-len(postfixToRemove + '_khr')]
                break
        
        # Remove tailing _
        if newName != '' and newName[-1] == '_':
            newName = newName[0:-1]
            
        # V does not allow for member names to start with a number, so add _ back
        if newName[0:1].isnumeric():
            newName = '_' + newName
        if newName != False and newName != '':
            memberName = newName

        return memberName


    # Note Anton: the oiginal method comes from vulkandocs/scripts/generator.py
    # This handles one function parameter and depending on which kind of function definition
    # TODO: Some paramters aren't required anymore
    def makeVParamDecl(self, typeName, param, aligncol, do_c_func_params=False, do_c_to_v_func_call_params=False, do_struct_members=False, do_base_type=False, keep_vk_member_name=False, do_array_voidptr=False):
        """Return a string which is an indented, formatted
        declaration for a `<param>` or `<member>` block (e.g. function parameter
        or structure/union member).

        - param - Element (`<param>` or `<member>`) to format
        - aligncol - if non-zero, attempt to align the nested `<name>` element
          at this column"""
        if self.genOpts is None:
            raise MissingGeneratorOptionsError()
        if self.genOpts.conventions is None:
            raise MissingGeneratorOptionsConventionsError()
        indent = '    '
        paramdecl = indent
        prefix = noneStr(param.text)
        v_type = ''
        v_name = ''
        v_type_without_pointer = ''
        is_const = False
        
        for elem in param:
            text = noneStr(elem.text)
            if 'const ' in text:
                is_const = True
            tail = noneStr(elem.tail)
            text_plus_tail = text + tail.strip()
            # Note: vk.xml registry has the attribute optional = true
            # double check @[required] in V
            #optional = param.get('optional')

            if elem.tag == 'type':
                # Translate C type to V type
                if text_plus_tail in self.TYPE_MAP:
                    v_type = self.TYPE_MAP[text_plus_tail]
                else:
                    # if type is not mapped to V, it's mostly something like 'VkDeviceQueueCreateInfo*',
                    # so just replace * with & and move it to the left
                    v_type = text_plus_tail
                    v_type = self.removeVk(v_type)
                    ptr_count = v_type.count('*')

                    if '*' in v_type:
                        #NOTE Anton: Removing const, as it just signals that the pointer won't be changed by vulkan.
                        # Also, convert * to & and keep count
                        v_type_without_pointer =  v_type.replace('const ', '').replace('const', '')
                        v_type_without_pointer = v_type_without_pointer.replace('*', '').strip()
                        if v_type_without_pointer in self.TYPE_MAP:
                            # In case of 'void', TYPE_MAP will return empty string
                            if self.TYPE_MAP[v_type_without_pointer] == '':
                                v_type = ('&'*(ptr_count-1)) + 'voidptr'
                            else:
                                v_type = ('&'*(ptr_count)) + self.TYPE_MAP[v_type_without_pointer]
                        else:
                            if v_type_without_pointer in self.ALIAS_TO_BASE_TYPE_MAP:
                                if self.ALIAS_TO_BASE_TYPE_MAP[v_type_without_pointer].startswith('C.'):
                                    #v_type = ('&'*(pointer_count-1)) + v_type_without_pointer
                                    v_type = ('&'*(ptr_count)) + v_type_without_pointer
                                else:
                                    v_type = ('&'*ptr_count) + v_type_without_pointer

                            else:
                                v_type = ('&'*ptr_count)  + v_type_without_pointer
                    elif v_type in self.C_STRUCT_ARR:
                        pass
                    elif v_type.lower().startswith("pfn_"):
                        v_type = v_type + ' = unsafe { nil }'
            elif elem.tag == 'enum':
                v_name = v_name + text_plus_tail
            else:
                v_name = prefix + text_plus_tail
                if not keep_vk_member_name:
                    v_name = self.removeVk(v_name)
            

            if self.should_insert_may_alias_macro and self.genOpts.conventions.is_voidpointer_alias(elem.tag, text, tail):
                # OpenXR-specific macro insertion - but not in apiinc for the spec
                tail = self.genOpts.conventions.make_voidpointer_alias(tail)
            if elem.tag == 'name' and aligncol > 0:
                self.logMsg('diag', 'Aligning parameter', elem.text, 'to column', self.genOpts.alignFuncParam)
                # Align at specified column, if possible
                paramdecl = paramdecl.rstrip()
                oldLen = len(paramdecl)
                # This works around a problem where very long type names -
                # longer than the alignment column - would run into the tail
                # text.
                #paramdecl = paramdecl.ljust(aligncol - 1) + ' '
                newLen = len(paramdecl)
                self.logMsg('diag', 'Adjust length of parameter decl from', oldLen, 'to', newLen, ':', paramdecl)



            #NOTE Anton: pipeline_cache_uuid [VK_UUID_SIZE]u8
            #                  to pipeline_cache_uuid [uuid_size]u8
            array_match = self.ARRAY_REGEX.match(v_name)
            if array_match:
                v_name = v_name.replace(array_match.group(1), '')
                # Squeeze next dimension in multidimensional arrays between type and last dimension
                last_index_of_arr = v_type.rfind(']')+1
                v_type = v_type[:last_index_of_arr] + '[' + self.removeVk(array_match.group(1).lower().replace('[', '').replace(']', '')) + ']' + v_type[last_index_of_arr:]
                if do_array_voidptr:
                    v_type = 'voidptr'

            #Note Anton: module is a reserved keywords in V
            if not do_struct_members and v_name == 'module':
                v_name = 'vkmodule'
            # Note Anton: C supports custom types like 'uint32_t instanceCustomIndex:24;'
            # We just remove the number of bits, as these types all fit into u32
            if ':' in v_name:
                v_name = v_name.split(':')[0]
                
            # Note Anton: Remove lower() once V allows for upper case members
            # https://github.com/vlang/v/issues/20420
            if not keep_vk_member_name:
                v_name = self.v_camel_to_snake_case(v_name)
            # Note Anton: After adding param names for const_ prefix, `type ImageType` throws error: unknown type `vulkan.type`
            # So, change function parameter name
            if not do_struct_members and v_name == 'type':
                v_name = 'type_param'
            # TODO: Setting const_ prefix on vkCreatePipelineLayout will segfault
            # fn C.vkCreatePipelineLayout(device Device,  const_p_create_info &PipelineLayoutCreateInfo,  const_p_allocator &AllocationCallbacks,  p_pipeline_layout &PipelineLayout) Result
            #if not do_struct_members and is_const:
            #    v_name = 'const_' + v_name
            if not do_struct_members and not do_c_to_v_func_call_params:
                # Note Anton: Adding parameter name just to set a 'const_' prefix, because the type itself can not be marked
                #paramdecl = indent + v_type
                paramdecl = ' ' + v_name + ' ' + v_type
            elif do_c_to_v_func_call_params:
                paramdecl = indent + v_name
            else:
                paramdecl = indent + v_name.ljust(aligncol - 1) + ' ' + v_type
                
            if v_name == 'pNext' and v_type == 'voidptr':
                paramdecl = paramdecl + ' = unsafe{ nil }'
            # Assuming typeName is the struct name
            if do_struct_members and v_name == 'pNext' and typeName.endswith(v_type):
                paramdecl = paramdecl.replace(v_type, 'voidptr') + ' = unsafe{ nil }'
            if v_name == 'pUserData' and v_type == 'voidptr':
                paramdecl = paramdecl + ' = unsafe{ nil }'
            
            # For each item also check if its sType and can get a default value for StructureType
            if v_name == 'sType':
                # PhysicalDeviceVulkan13Features -> physical_device_vulkan1_3_features
                struct_type_enum = self.v_camel_to_snake_case(typeName).lower()
                if struct_type_enum in self.STRUCTURE_TYPES:
                    paramdecl = paramdecl + ' = StructureType.' + struct_type_enum
                else:
                    struct_type_enum = self.find_matching_structure_type_enum(typeName).lower()
                    if struct_type_enum != "":
                        paramdecl = paramdecl + ' = StructureType.' + struct_type_enum

            # Clear prefix for subsequent iterations
            if (prefix.find('const ') != -1):
                is_const = True
            prefix = ''
            
       # Set mut for function paramters that are not const, except for enum types
       # Note: Ignoring base types,
       # because mutable arguments are only allowed for arrays, interfaces, maps, pointers, structs or their aliases
        if (is_const == False and not do_struct_members):# and not do_c_to_v_func_call_params):
                type_to_check = v_type
                m = re.match(r'(?:&|\[\d*\])*(?:C\.Vk)?(.*)', type_to_check)                    
                if (m):
                    type_to_check = m.group(1)
                if (not type_to_check in self.ENUM_TYPES
                and not type_to_check in self.BASE_TYPES_ARR
                and (not type_to_check in self.ALIAS_TO_BASE_TYPE_MAP
                or not self.ALIAS_TO_BASE_TYPE_MAP[type_to_check] in self.BASE_TYPES_ARR)
                ):
                    paramdecl = 'mut' + paramdecl # TODO: When using /* mut */ error: inline comment is deprecated, please use line comment
                    pass

        if aligncol == 0:
            # Squeeze out multiple spaces other than the indentation
            #paramdecl = indent + ' '.join(paramdecl.split())
            paramdecl = ' '.join(paramdecl.split())
        return paramdecl

    # Note Anton: the oiginal method comes from vulkandocs/scripts/generator.py
    def buildEnumVDecl(self, expand, groupinfo, groupName,  keep_vk_member_name=False):
        """Generate the C declaration for an enum"""
        if self.genOpts is None:
            raise MissingGeneratorOptionsError()
        if self.genOpts.conventions is None:
            raise MissingGeneratorOptionsConventionsError()

        groupElem = groupinfo.elem

        # Determine the required bit width for the enum group.
        # 32 is the default, which generates C enum types for the values.
        bitwidth = 32

        # If the constFlagBits preference is set, 64 is the default for bitmasks
        if self.genOpts.conventions.constFlagBits and groupElem.get('type') == 'bitmask':
            bitwidth = 64

        # Check for an explicitly defined bitwidth, which will override any defaults.
        if groupElem.get('bitwidth'):
            try:
                bitwidth = int(groupElem.get('bitwidth'))
            except ValueError:
                self.logMsg('error', 'Invalid value for bitwidth attribute (', groupElem.get('bitwidth'), ') for ', groupName, ' - must be an integer value\n')
                exit(1)

        usebitmask = False
        usedefine = False

        # Bitmask flags can be generated as either "static const uint{32,64}_t" values,
        # or as 32-bit C enums. 64-bit types must use uint64_t values.
        if groupElem.get('type') == 'bitmask':
            if bitwidth > 32 or self.misracppstyle():
                usebitmask = True
            if self.misracstyle():
                usedefine = True

        if usedefine or usebitmask:
            # Validate the bitwidth and generate values appropriately
            if bitwidth > 64:
                self.logMsg('error', 'Invalid value for bitwidth attribute (', groupElem.get('bitwidth'), ') for bitmask type ', groupName, ' - must be less than or equal to 64\n')
                exit(1)
            else:
                return self.buildEnumVDecl_BitmaskOrDefine(groupinfo, groupName, bitwidth, usedefine)
        else:
            # Validate the bitwidth and generate values appropriately
            if bitwidth > 32:
                self.logMsg('error', 'Invalid value for bitwidth attribute (', groupElem.get('bitwidth'), ') for enum type ', groupName, ' - must be less than or equal to 32\n')
                exit(1)
            else:
                # Note Anton: Default path. Code jumps right to here
                return self.buildEnumVDecl_Enum(expand, groupinfo, groupName,  keep_vk_member_name=keep_vk_member_name)

    # Note Anton: the oiginal method comes from vulkandocs/scripts/generator.py
    def buildEnumVDecl_BitmaskOrDefine(self, groupinfo, groupName, bitwidth, usedefine):
        """Generate the C declaration for an "enum" that is actually a
        set of flag bits"""
        groupElem = groupinfo.elem
        flagTypeName = groupElem.get('name')

        flagTypeName = self.removeVk(flagTypeName)

        # Prefix
        body = "// Flag bits for " + flagTypeName + "\n"

        if bitwidth == 64:
            body += "pub type %s = u64\n" % flagTypeName
            # Vlang doesn't allow for non basetype (u32, u64) aliases,
            # so add the current type alias to BASE_TYPE_MAP
            self.ALIAS_TO_BASE_TYPE_MAP[flagTypeName] = 'u64'
        else:
            body += "pub type %s = u32\n" % flagTypeName
            self.ALIAS_TO_BASE_TYPE_MAP[flagTypeName] = 'u32'

        # Maximum allowable value for a flag (unsigned 64-bit integer)
        maxValidValue = 2**(64) - 1
        minValidValue = 0

        # Get a list of nested 'enum' tags.
        enums = groupElem.findall('enum')

        # Check for and report duplicates, and return a list with them
        # removed.
        enums = self.checkDuplicateEnums(enums)

        # Accumulate non-numeric enumerant values separately and append
        # them following the numeric values, to allow for aliases.
        # NOTE: this does not do a topological sort yet, so aliases of
        # aliases can still get in the wrong order.
        aliasText = ''

        # Loop over the nested 'enum' tags.
        for elem in enums:
            #deprecated = elem.get('deprecated') 
            #if deprecated is not None:
            #if deprecated == 'aliased':
            #    continue;            
            
            # Convert the value to an integer and use that to track min/max.
            # Values of form -(number) are accepted but nothing more complex.
            # Should catch exceptions here for more complex constructs. Not yet.
            (numVal, strVal) = self.enumToValue(elem, True, bitwidth, True)
            name = elem.get('name')
            
            # Convert C const value to V type
            prefix = ''
            v_type = ''
            v_name = name
            couldnt_convert_strVal = False

            if 'ULL' in strVal:
                v_type = 'u64'
            elif 'U' in strVal:
                v_type = 'u32'
            else:
                # Couldn't convert strVal to v_type, so we assume it's something like
                # pub const VK_PIPELINE_STAGE_2_RAY_TRACING_SHADER_BIT_NV = VK_PIPEINE_STAGE_2_RAY_TRACING_SHADER_BIT_KHR
                v_type = strVal
                couldnt_convert_strVal = True

            if '~' in strVal:
                prefix = '~'

            if strVal.lower().startswith('vk'):
                v_value = strVal
            else:
                v_value = (strVal.replace('~', '')
                                 .replace('U', '')
                                 .replace('L', '')
                                 .replace('F', '')
                                 .replace('(', '')
                                 .replace(')', ''))

            # Range check for the enum value
            if numVal is not None and (numVal > maxValidValue or numVal < minValidValue):
                self.logMsg('error', 'Allowable range for flag types in C is [', minValidValue, ',', maxValidValue, '], but', name, 'flag has a value outside of this (', strVal, ')\n')
                exit(1)

            decl = self.genRequirements(name, mustBeFound = False)

            if self.isEnumRequired(elem):
                protect = elem.get('protect')
                if protect is not None:
                    pass

                body += self.deprecationComment(elem, indent = 0)
                if usedefine:
                    decl += "#define {} {}\n".format(name, strVal)
                elif self.misracppstyle():
                    decl += "static constexpr {} {} {{{}}};\n".format(flagTypeName, name, strVal)
                else:
                    # Some C compilers only allow initializing a 'static const' variable with a literal value.
                    # So initializing an alias from another 'static const' value would fail to compile.
                    # Work around this by chasing the aliases to get the actual value.
                    while numVal is None:
                        alias = self.registry.tree.find("enums/enum[@name='" + strVal + "']")
                        if alias is not None:
                            (numVal, strVal) = self.enumToValue(alias, True, bitwidth, True)
                        else:
                            self.logMsg('error', 'No such alias {} for enum {}'.format(strVal, name))

                    # NOTE Anton: V doesn't allow for upper case function names and const variables
                    v_name = v_name.lower()
                    v_value = self.removeVk(v_value)
                    v_name = self.removeVk(v_name)
                    v_type = self.removeVk(v_type)

                    v_value = v_value.lower()

                    if couldnt_convert_strVal:
                        val_concat = prefix + v_type
                        val_concat = val_concat.lower()
                        decl += "pub const {} = {}\n".format(v_name, val_concat)
                    else:
                        #NOTE Anton: vk_true and vk_false are hardcoded. To keep the prefix
                        if v_value.lower().startswith("vk"):
                            decl += "pub const {} = {}\n".format(v_name, v_value)
                        else:
                            decl += "pub const {} = {}\n".format(v_name, prefix + v_type + '(' + v_value + ')')

                if numVal is not None:
                    body += decl
                else:
                    aliasText += decl

                if protect is not None:
                    pass

        # Now append the non-numeric enumerant values
        body += aliasText

        return ("bitmask", body)

    # Note Anton: the oiginal method comes from vulkandocs/scripts/generator.py
    def buildEnumVDecl_Enum(self, expand, groupinfo, groupName, keep_vk_member_name=False):
        """Generate the V declaration for an enumerated type"""
        groupElem = groupinfo.elem
        # Determine appropriate section for this declaration
        if groupElem.get('type') == 'bitmask':
            section = 'bitmask'
        else:
            section = 'group'

        # Break the group name into prefix and suffix portions for range
        # enum generation
        expandName = re.sub(r'([0-9]+|[a-z_])([A-Z0-9])', r'\1_\2', groupName).upper()
        expandPrefix = expandName
        expandSuffix = ''
        expandSuffixMatch = re.search(r'[A-Z][A-Z]+$', groupName)
        if expandSuffixMatch:
            expandSuffix = '_' + expandSuffixMatch.group()
            # Strip off the suffix from the prefix
            expandPrefix = expandName.rsplit(expandSuffix, 1)[0]

        # @@ Should use the type="bitmask" attribute instead
        isEnum = ('FLAG_BITS' not in expandPrefix)
        
        # Prefix
        groupNameOrig = groupName
        groupName = self.removeVk(groupName)
        body =[]
        # Replace used as placeholder for 'as u32' if enum doesn't contain negative values
        body.append('pub enum ' + groupNameOrig +' ThisIsAplaceholderTO_REPLACE_LATERwithEnumType{')
        
        # Store enum name and variations of it. To ignore when setting mut for function paramters
        if not groupNameOrig in self.STRUCTURE_TYPES:
            self.ENUM_TYPES.append(groupNameOrig)
        
        # Allowable range for a C enum - which is that of a signed 32-bit integer
        maxValidValue = 2**(32 - 1) - 1
        minValidValue = (maxValidValue * -1) - 1

        # Get a list of nested 'enum' tags.
        enums = groupElem.findall('enum')

        # Check for and report duplicates, and return a list with them
        # removed.
        enums = self.checkDuplicateEnums(enums)

        # Loop over the nested 'enum' tags. Keep track of the minimum and
        # maximum numeric values, if they can be determined; but only for
        # core API enumerants, not extension enumerants. This is inferred
        # by looking for 'extends' attributes.
        minName = None

        # Accumulate non-numeric enumerant values separately and append
        # them following the numeric values, to allow for aliases.
        # NOTE: this does not do a topological sort yet, so aliases of
        # aliases can still get in the wrong order.
        aliasText = []

        maxName = None
        minValue = None
        maxValue = None
        for elem in enums:
            # Convert the value to an integer and use that to track min/max.
            # Values of form -(number) are accepted but nothing more complex.
            # Should catch exceptions here for more complex constructs. Not yet.
            (numVal, strVal) = self.enumToValue(elem, True)
            name = elem.get('name')

            # Handle StructureType Enum customly to set a default s_type in structs later
            # AAAA_2323_AAAA -> AAAA2323_AAAA
            # VK_STRUCTURE_TYPE_SURFACE_CAPABILITIES_2_EXT -> VK_STRUCTURE_TYPE_SURFACE_CAPABILITIES2_EXT
            # Matching s_type = structure_type_surface_capabilities2_ext
            # To fix an issue, where the default s_type enum doesn't match the StructureType enum
            # replace '_2' with '2'
            name = self.STRUCTURE_TYPES_NUMBER_WITH_UNDERSCORE_REGEX.sub(r'\g<num_after_underscore>', name)

            # V doesn't allow for upper case enum member names
            if not keep_vk_member_name:
                name = self.removeVk(name).lower()
            
            name = self.removeStructEnumNameFromMember(groupName,  name)
            
            # Extension enumerants are only included if they are required
            if self.isEnumRequired(elem):
                decl = ''
                protect = elem.get('protect')
                if protect is not None:
                    #TODO: remove continue and implement conditional compilation, once available, on root level in V code
                    continue
                    decl += '#ifdef {}\n'.format(protect)

                decl += self.genRequirements(name, mustBeFound = False, indent = 2)
                decl += self.deprecationComment(elem, indent = 2)
                if strVal[0:2] == '0x':
                    decl += '    {} = int({})'.format(name, strVal)
                else:
                    decl += '    {} = {}'.format(name, strVal)
                # Append all items in StructureType struct. Later used to set default sType if found in STRUCTURE_TYPES
                if groupName == 'StructureType':
                    self.STRUCTURE_TYPES.append(name)
                if protect is not None:
                    decl += '\n#endif'
                if numVal is not None:
                    body.append(decl)
                else:
                    aliasText.append(decl)

            # Range check for the enum value
            if numVal is not None and (numVal > maxValidValue or numVal < minValidValue):
                self.logMsg('error', 'Allowable range for C enum types is [', minValidValue, ',', maxValidValue, '], but', name, 'has a value outside of this (', strVal, ')\n')
                exit(1)

            # Track min/max for enum numbers, not where numVal is None
            if isEnum and numVal is not None and elem.get('extends') is None:
                if minName is None:
                    minName = maxName = name
                    minValue = maxValue = numVal
                elif minValue is None or numVal < minValue:
                    minName = name
                    minValue = numVal
                elif maxValue is None or numVal > maxValue:
                    maxName = name
                    maxValue = numVal

        # Generate min/max value tokens - legacy use case.
        if isEnum and expand:
            body.extend((f'    {expandPrefix}_BEGIN_RANGE{expandSuffix} = {minName},',
                         f'    {expandPrefix}_END_RANGE{expandSuffix} = {maxName},',
                         f'    {expandPrefix}_RANGE_SIZE{expandSuffix} = ({maxName} - {minName} + 1),'))

        # Generate a range-padding value to ensure the enum is 32 bits, but
        # only in code generators, so it does not appear in documentation
        if (self.genOpts.codeGenerator or
            self.conventions.generate_max_enum_in_docs):

            # NOTE Anton: V doesn't allow for upper case enum member names
            expandPrefix = self.removeVk(expandPrefix).lower()
            expandSuffix = expandSuffix.lower()
            # NOTE Anton: Sometimes a member named `invalid` has the same value as max_int and would be duplicate
            if ((len(list(filter (lambda x : (x.find('int(0x7FFFFFFF)') != -1 or x.find('int(0xFFFFFFFF)') != -1), body))) <= 0)):
              body.append(f'    max_enum{expandSuffix} = max_int')

       # Postfix
        body.append("}")
        
        # Replace placeholder to make enum as u32 or not
        # TODO: Ticket about need to cast u32(enum) types for " | " operation to concatinate flag bits
        # error: only `==` and `!=` are defined on `enum`, use an explicit cast to `int` if needed
        ret = '\n'.join(body)
        if minValue is not None and minValue < 0:
            ret = ret.replace('ThisIsAplaceholderTO_REPLACE_LATERwithEnumType', '')
        else:
            ret = ret.replace('ThisIsAplaceholderTO_REPLACE_LATERwithEnumType', 'as u32 ')
            ret = ret.replace('int(', 'u32(')

        return (section, ret)

    def makeVDecls(self, cmd):
        """Return V prototype and function pointer typedef for a
        `<command>` Element, as a two-element list of strings.

        - cmd - Element containing a `<command>` tag"""
        if self.genOpts is None:
            raise MissingGeneratorOptionsError()
        proto = cmd.find('proto')
        params = cmd.findall('param')
        # Begin accumulating prototype and typedef strings
        pdecl = self.genOpts.apicall
        tdecl = 'typedef '
        v_type = ''
        v_name = ''

        # Insert the function return type/name.
        # For prototypes, add APIENTRY macro before the name
        # For typedefs, add (APIENTRY *<name>) around the name and
        #   use the PFN_cmdnameproc naming convention.
        # Done by walking the tree for <proto> element by element.
        # etree has elem.text followed by (elem[i], elem[i].tail)
        #   for each child element and any following text
        # Leading text
        pdecl += noneStr(proto.text)
        tdecl += noneStr(proto.text)
        # For each child element, if it is a <name> wrap in appropriate
        # declaration. Otherwise append its contents and tail contents.
        for elem in proto:
            text = noneStr(elem.text)
            tail = noneStr(elem.tail)
            text_plus_tail = text + tail.strip()

            if elem.tag == 'type':
                # Translate C type to V type
                v_type = text_plus_tail
                if v_type in self.TYPE_MAP:
                    v_type = self.TYPE_MAP[v_type]
                else:
                    v_type = self.removeVk(v_type)

                    # if type is not mapped to V type, it's mostly something like 'VkDeviceQueueCreateInfo*',
                    # so just replace * with & and move it to the left
                    ptr_count = v_type.count('*')
                    if '*' in v_type:
                        v_type_without_pointer = v_type.replace('*', '')
                        if v_type_without_pointer in self.TYPE_MAP:
                            v_type = ('&'*ptr_count)  + self.TYPE_MAP[v_type_without_pointer]
                        else:
                            v_type = ('&'*ptr_count)  + v_type_without_pointer
            else:
                v_name = text_plus_tail

        v_name_original = v_name
        v_name = self.v_camel_to_snake_case(v_name)

        pdecl = v_name
        tdecl = v_type

        if self.genOpts.alignFuncParam == 0:
            # Squeeze out multiple spaces - there is no indentation
            pdecl = ' '.join(pdecl.split())
            tdecl = ' '.join(tdecl.split())

        # Now add the parameter declaration list, which is identical
        # for prototypes and typedefs. Concatenate all the text from
        # a <param> node without the tags. No tree walking required
        # since all tags are ignored.
        # Uses: self.indentFuncProto
        # self.indentFuncPointer
        # self.alignFuncParam
        n = len(params)
        # fn C.vk ...
        if n > 0:
            c_func_def_params = '(\n'
            for p in params:
                cur_base_type = self.makeVParamDecl(v_name, p, self.genOpts.alignFuncParam, do_c_func_params=True, do_c_to_v_func_call_params=False, do_struct_members=False, do_base_type=False,  keep_vk_member_name=False)
                c_func_def_params += '{}, '.format(cur_base_type)
            c_func_def_params = c_func_def_params.rstrip(', ')
            c_func_def_params += ')'
        else:
            c_func_def_params = '()'
            
        # pub type PFN_vkGet ...
        v_wrapper = ''
        if n > 0:
            v_pub_type_pfn_param_names = '('
            for p in params:
                cur_type = self.makeVParamDecl(v_name, p, self.genOpts.alignFuncParam, do_c_func_params=True, do_c_to_v_func_call_params=False, do_struct_members=False, do_base_type=False, do_array_voidptr=False, keep_vk_member_name=False).lstrip()
                v_pub_type_pfn_param_names += '{}, '.format(cur_type)
            v_pub_type_pfn_param_names = v_pub_type_pfn_param_names.rstrip(', ')
            v_pub_type_pfn_param_names += ')'
        else:
            v_pub_type_pfn_param_names = '()'
        
        # Add PFN_func type defintion for each vk function.
        # These are not part of vulkan, but of the bindings for V
        if v_type == 'PFN_vkVoidFunction':
            v_wrapper += 'pub type PFN_{} = fn{}\n'.format(v_name_original,  v_pub_type_pfn_param_names) 
        else:
            v_wrapper += 'pub type PFN_{} = fn{} {}\n'.format(v_name_original,  v_pub_type_pfn_param_names,  v_type) 


        # pub fn get_ ...
        v_name_no_vk = self.removeVk(v_name)
        v_wrapper += '@[inline]\npub fn '
        v_wrapper += v_name_no_vk

        # C function params to basetype for C call inside V function
        if n > 0:
            v_function_params_cast_base = '(\n'
            for p in params:
                cur_base_type = self.makeVParamDecl(v_name, p, self.genOpts.alignFuncParam, do_c_func_params=True, do_c_to_v_func_call_params=False, do_struct_members=False, do_base_type=True).lstrip()
                its_an_array = False
                if cur_base_type.startswith('['):
                    its_an_array = True
                cur_base_type = self.v_translate_type_basetype(cur_base_type.lstrip())
                cur_param_name = self.makeVParamDecl(v_name, p, self.genOpts.alignFuncParam, do_c_func_params=False, do_c_to_v_func_call_params=True).lstrip()
                if its_an_array:
                    v_function_params_cast_base += '{}({}.data), '.format(cur_base_type,  cur_param_name)
                else:
                    v_function_params_cast_base += '{}({}), '.format(cur_base_type,  cur_param_name)
            v_function_params_cast_base = v_function_params_cast_base.rstrip(', ')
            
            v_function_params_cast_base += ')'

            v_function_param_names_and_types = '(\n'
            v_function_param_names_and_types += ',\n'.join(self.makeVParamDecl(v_name, p, self.genOpts.alignFuncParam, do_c_func_params=False, do_c_to_v_func_call_params=False, do_array_voidptr=False).lstrip()
                                            for p in params)
            v_function_param_names_and_types += ')'
            
            v_function_param_names = '(\n'
            v_function_param_names += ',\n'.join(self.makeVParamDecl(v_name, p, self.genOpts.alignFuncParam, do_c_func_params=False, do_c_to_v_func_call_params=True).lstrip()
                                            for p in params)
            v_function_param_names += ')'
            
        else:
            v_function_param_names = '()'
            v_function_params_cast_base = '()'
            v_function_param_names = ()


        #TODO: Add error code comment?
        #NOTE: V function with VK_NO_PROTOTYPES conditional compilation
#        if self.genOpts.protectProto:
#            v_wrapper += '@[if ' + self.genOpts.protectProtoStr + ' ?]\n'
        #NOTE: PFN_vkVoidFunction is defined as `voidptr` - pointer to a function - and has to be cast to the correct `PFN_...` by the user
        #Here handle the case where a function return type is PFN_vkVoidFunction
        if v_type == 'PFN_vkVoidFunction':
            v_type = 'voidptr'
        # Append V function params
        #v_wrapper += v_function_param_names_and_types + ' ' + v_type + " {\n"
        v_wrapper += v_function_param_names_and_types + v_type + " {\n"
        v_type_stripped = v_type.strip()

        is_protected, extension_names = self.getFeatureConditionalCompilation(v_name_original)
        #TODO remove is_protected = False or remove the if branch in case the conditional compilation isn't needed
        is_protected = False
        if is_protected:
            if len(extension_names) > 1:
                v_wrapper += '//$if {} ?{{\n'.format(' && '.join(extension_names))
                v_wrapper += '$if {} ?{{\n'.format(extension_names[len(extension_names)-1])
            else:
                v_wrapper += '$if {} ?{{\n'.format(' && '.join(extension_names))

            if v_type_stripped == '':
                v_wrapper += '    C.' + v_name_original + '{}'.format(' '.join(v_function_param_names.split('\n')))
            elif v_type_stripped == 'Result':
                v_wrapper += '    return C.' + v_name_original + '{}'.format(' '.join(v_function_param_names.split('\n')))
            else:
                v_wrapper += '    return C.' + v_name_original + '{}'.format(' '.join(v_function_param_names.split('\n')))
            v_wrapper += '} $else {'
            if v_type_stripped == '':
                v_wrapper += '    //NOTE: Please check for 0 in case {} compiler flag was not passed.\n'.format(extension_names[len(extension_names)-1])
                v_wrapper += '    return'
            elif v_type_stripped == 'Result':
                v_wrapper += '    return Result.error_extension_not_present'
            else:
                v_wrapper += '    //NOTE: Please check for 0 in case {} compiler flag was not passed.\n'.format(extension_names[len(extension_names)-1])
                v_wrapper += '    return ' + v_type + '(0)'
            v_wrapper += '\n}}\n'
            return ['fn C.' + v_name_original + c_func_def_params + ' ' + v_type + '\n' + v_wrapper, tdecl]
        else:
            # C call inside V function
            if v_type_stripped == '': # has no return type
                v_wrapper += '    C.' + v_name_original + '{}'.format(' '.join(v_function_param_names.split('\n')))
            elif v_type_stripped == 'Result': # vk.Result return type
                v_wrapper += '    return C.' + v_name_original + '{}'.format(' '.join(v_function_param_names.split('\n')))
            else: # has any other return type
                v_wrapper += '    return C.' + v_name_original + '{}'.format(' '.join(v_function_param_names.split('\n')))

            v_wrapper += '\n}\n'
            return ['@[keep_args_alive]\nfn C.' + v_name_original + c_func_def_params + ' ' + v_type + '\n' + v_wrapper, tdecl]

    # Looks up if self.featureDictionary contains a given function name (or other item) under an extension.
    # Returns the extension names under which the item was found.
    def getFeatureConditionalCompilation(self,  item_str) -> (bool, [str]):
        # self.featureDictionary.keys
        # self.featureDictionary['VK_AMD_buffer_marker'].keys ==
        # basetype, bitmask, command, define, enum, enumconstant, funcpointer, handle, include, struct, uninion
        # self.featureDictionary['VK_AMD_buffer_marker']['command'].None[0] == 'vkCmdWriteBufferMarkerAMD'
        ret_bool = False
        ret_feature_names = []

        for feature in self.featureDictionary.items():
            featureName = feature[0]
            # Only protect functions that need an extension, not a specific vulkan version
            if featureName.startswith('VK_VERSION_'):
                continue
            for featureSection in feature[1].items():
                featureSectionName = featureSection[0]
                for featureSectionItem in featureSection[1].items():
#                    print(featureName + ', ' + featureSectionName)
#                    print(featureSectionItem[1])
                    if featureSectionName == 'command' and item_str in featureSectionItem[1]:
#                        print(featureName + ':\n' + featureSectionName)
#                        print(featureSectionItem)
                        ret_bool = True
                        ret_feature_names.append(featureName)
        return ret_bool, ret_feature_names

    # Note Anton: the oiginal method comes from vulkandocs/scripts/generator.py
    def genType(self, typeinfo, name, alias):
        """Generate interface for a type

        - typeinfo - TypeInfo for a type

        Extend to generate as desired in your derived class."""
        self.validateFeature('type', name)

        body = ''
        section = ''
        cur_type = self.genCType(typeinfo, name, alias)
        if cur_type is None or not cur_type or cur_type[1].startswith('// DEPRECATED:'):
            return
        c_section, c_body = cur_type

        # Add text to REPLACEMENT_EXACT_TEXT_ARR if it contains something from REPLACEMENT_CONTAINS_ARR
        # Later used to find exactly matching C code and replace it with V code
        esc_text = self.escStr(c_body)
        for contains_str in self.REPLACEMENT_CONTAINS_ARR:
            if contains_str in c_body:
                self.REPLACEMENT_EXACT_TEXT_ARR.append(esc_text)

        cur_type = self.genVType(typeinfo, name, alias)
        if cur_type is None or not cur_type:
            #NOTE: this is where #include is usually handled. Don't need it for V
            # and typedef
#            body = c_body
#            section = c_section
#
#            self.appendSection(c_section, c_body)
            return

        v_section, v_body = cur_type

        if c_body in self.REPLACEMENT_MAP:
            body = self.REPLACEMENT_MAP[c_body]
            section = c_section
        else:
            body = v_body
            section = v_section

        # Convert '#define VK_HEADER_VERSION 123'
        # to          'pub const header_version = 123'
        if c_body.startswith('// Version of this file\n#define VK_HEADER_VERSION '):
            version_index = c_body.index('VK_HEADER_VERSION') + len('VK_HEADER_VERSION') + 1
            body = 'pub const header_version = ' + c_body[version_index:-1]
        
        # Handle some of the version functions
        if '#define VK_MAKE_VERSION(major, minor, patch)' in c_body:
            body = '''
pub fn make_version(major u32, minor u32, patch u32) u32 {
  return (major << 22) | (minor << 12) | patch
}'''
        if '#define VK_VERSION_MAJOR(version)' in c_body:
            body = '''
pub fn version_major(version u32) u32 {
  return version >> 22
}'''
        if '#define VK_VERSION_MINOR(version)' in c_body:
            body = '''
pub fn version_minor(version u32) u32 {
  return (version >> 12) & 0xFFF
}'''
        if '#define VK_VERSION_PATCH(version)' in c_body:
            body = '''
pub fn version_patch(version u32) u32 {
  return version & 0xFFF
}
'''
        if 'MAKE_API_VERSION(variant, major, minor, patch)' in c_body:
            body = '''
pub fn make_api_version(variant u32, major u32, minor u32, patch u32) u32 {
  return (variant << 29) | (major << 22) | (minor << 12) | patch
}'''
        if 'API_VERSION_VARIANT(version)' in c_body:
            body = '''pub fn version_variant(version u32) u32 {
  return version >> 29
}'''
        if 'API_VERSION_MAJOR(version)' in c_body:
            body = '''
pub fn api_version_major(version u32) u32 {
  return (version >> 22) & u32(0x7F)
}'''
        if 'API_VERSION_MINOR(version)' in c_body:
            body = '''
pub fn api_version_minor(version u32) u32 {
  return (version >> 12) & u32(0x3FF)
}'''
        if 'API_VERSION_PATCH(version)' in c_body:
            body = '''
pub fn api_version_patch(version u32) u32 {
  return version & u32(0xFFF)
}'''
        if 'VK_MAKE_VIDEO_STD_VERSION(major, minor, patch)' in c_body:
            body = '''
pub fn make_video_std_version(major u32, minor u32, patch u32) u32 {
  return (major << 22) | (minor << 12) | patch
}'''
        # TODO: Version will change and new features will be added. Handle these with regex
        if '#define VK_STD_VULKAN_VIDEO_CODEC_H264_DECODE_API_VERSION_1_0_0' in c_body:
            body = '''pub const std_vulkan_video_codec_h264_decode_api_version_1_0_0 = make_video_std_version(1, 0, 0)'''    
        if '#define VK_STD_VULKAN_VIDEO_CODEC_H264_ENCODE_API_VERSION_1_0_0' in c_body:
            body = '''pub const std_vulkan_video_codec_h264_encode_api_version_1_0_0 = make_video_std_version(1, 0, 0)'''
        if '#define VK_STD_VULKAN_VIDEO_CODEC_H265_DECODE_API_VERSION_1_0_0' in c_body:
            body = '''pub const std_vulkan_video_codec_h265_decode_api_version_1_0_0 = make_video_std_version(1, 0, 0)'''
        if '#define VK_STD_VULKAN_VIDEO_CODEC_H265_ENCODE_API_VERSION_1_0_0' in c_body:
            body = '''pub const std_vulkan_video_codec_h265_encode_api_version_1_0_0 = make_video_std_version(1, 0, 0)'''
        if '#define VK_STD_VULKAN_VIDEO_CODEC_AV1_DECODE_API_VERSION_1_0_0' in c_body:
            body = '''pub const std_vulkan_video_codec_av1_decode_api_version_1_0_0 = make_video_std_version(1, 0, 0)'''
        if '#define VK_STD_VULKAN_VIDEO_CODEC_AV1_ENCODE_API_VERSION_1_0_0' in c_body:
            body = '''pub const std_vulkan_video_codec_av1_encode_api_version_1_0_0 = make_video_std_version(1, 0, 0)'''
        if '#define VK_STD_VULKAN_VIDEO_CODEC_VP9_DECODE_API_VERSION_1_0_0' in c_body:
            body = '''pub const std_vulkan_video_codec_vp9_decode_api_version_1_0_0 = make_video_std_version(1, 0, 0)'''
        #body = self.STD_VIDEO_MAKE_VERSION_REGEX.sub(r'pub const std_vulkan_video_codec\L\1\Eapi_version_\2_\3_\4 = make_video_std_version(\2, \3, \4)',  c_body)
        
        self.appendSection(section, body)

    # NOTE Anton: If text contains `\` before new line, the mapping isn't found. This fixes it
    def escStr(self, text) -> str:
        return text.replace(r'\\', '\\\\').replace(r'\n', '\\n')

    # Note Anton: the oiginal method comes from vulkandocs/scripts/generator.py
    def deprecationComment(self, elem, indent = 0):
        """If an API element is marked deprecated, return a brief comment
           describing why.
           Otherwise, return an empty string.

          - elem - Element of the API.
            API name is determined depending on the element tag.
          - indent - number of spaces to indent the comment"""

        reason = elem.get('deprecated')

        # This is almost always the path taken.
        if reason == None:
            return ''

        # There is actually a deprecated attribute.
        padding = indent * ' '

        # Determine the API name.
        if elem.tag == 'member' or elem.tag == 'param':
            name = elem.find('.//name').text
        else:
            name = elem.get('name')

        if reason == 'aliased':
            return f'{padding}// {name} is a deprecated alias\n'
        elif reason == 'ignored':
            return f'{padding}// {name} is deprecated and should not be used\n'
        elif reason == 'true':
            return f'{padding}// {name} is deprecated, but no reason was given in the API XML\n'
        else:
            # This can be caught by schema validation
            self.logMsg('error', f"{name} has an unknown deprecation attribute value '{reason}'")
            exit(1)

    # Note Anton: the oiginal method comes from vulkandocs/scripts/generator.py
    def genRequirements(self, name, mustBeFound = True, indent = 0):
        """Generate text showing what core versions and extensions introduce
        an API. This exists in the base Generator class because it is used by
        the shared enumerant-generating interfaces (buildEnumCDecl, etc.).
        Here it returns an empty string for most generators, but can be
        overridden by e.g. DocGenerator.

        - name - name of the API
        - mustBeFound - If True, when requirements for 'name' cannot be
          determined, a warning comment is generated.
        """

        return ''
