#!/usr/bin/python3 -i
#
# Copyright 2013-2023 The Khronos Group Inc.
#
# SPDX-License-Identifier: Apache-2.0

import os
import re

from generator import (GeneratorOptions,
                       MissingGeneratorOptionsConventionsError,
                       MissingGeneratorOptionsError, MissingRegistryError,
                       OutputGenerator, noneStr, regSortFeatures, write)

from cgenerator import CGeneratorOptions, COutputGenerator

from itertools import groupby


class VGeneratorOptionsBK(GeneratorOptions):
    """VGeneratorOptionsBK - subclass of GeneratorOptions.

    Adds options used by VOutputGeneratorBK objects during V language header
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
        - misracstyle - generate MISRA V-friendly headers
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
        """generate MISRA V-friendly headers"""

        self.misracppstyle = misracppstyle
        """generate MISRA C++-friendly headers"""

        self.codeGenerator = True
        """True if this generator makes compilable code"""


class VOutputGeneratorBK(OutputGenerator):
    """Generates V-language API interfaces."""

    # This is an ordered list of sections in the header file.
    TYPE_SECTIONS = ['include', 'define', 'basetype', 'handle', 'enum',
                     'group', 'bitmask', 'funcpointer', 'struct']
    ALL_SECTIONS = TYPE_SECTIONS + ['commandPointer', 'command']
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
        # 'const* char*': '&char',
        'char* const*': '&&char',
        'float64': 'f64',
        'float64*': '&f64',
        'StdVideoH265LevelIdc': 'u32',
        'HMONITOR': 'voidptr',
        'MTLDevice_id': 'voidptr',
        'MTLCommandQueue_id': 'voidptr',
        'MTLBuffer_id': 'voidptr',
        'MTLTexture_id': 'voidptr',
        'zx_handle_t': 'voidptr',
        'GgpFrameToken': 'u64',
        'GgpStreamDescriptor': 'voidptr',
        'MTLSharedEvent_id': 'voidptr',
        'IOSurfaceRef': 'voidptr', # NOTE Anton: not sure if to include header or just this
        # 'VkBuildAccelerationStructureFlagsNV': 'C.VkFlags',
        'VkBuildAccelerationStructureFlagsNV': 'Flags',
        'Window': 'voidptr',
        'xcb_window_t': 'voidptr',
        'xcb_visualid_t': 'voidptr',
        'VisualID': 'voidptr',
        'Display': 'C.DisplayKHR',
        'RROutput': 'u32',
        'HANDLE': 'voidptr',
        'DWORD': 'u32',
        'LPCWSTR': 'string',
        'HWND': 'voidptr',
        'HINSTANCE': 'voidptr',
        'SECURITY_ATTRIBUTES': '',
        'pLayerPrefix': 'char',
        'pMessage': 'char',
#        'CAMetalLayer': '',
#        '_screen_window': '',
#        '_screen_context': '',
#        '_screen_buffer': '',
#        'IDirectFB': '',
#        'IDirectFBSurface': '',
#        'pCallbackData': '',
#        'pName': '',
#        'VkRemoteAddressNV': '',
#        'AHardwareBuffer': '',
#        'ANativeWindow': '',
#        'wl_display': '',
#        'wl_surface': '',
#        'xcb_connection_t': '',
    }

    # This constains all struct names, which are coming from C.
    # They are simply prepended with "C." in vulkan.v
    # Elements are added dynamically, except the static std video headers in include/video
    C_STRUCT_ARR = [
        "StdVideoDecodeH265PictureInfoFlags",
        "StdVideoDecodeH265PictureInfo",
        "StdVideoDecodeH265ReferenceInfoFlags",
        "StdVideoDecodeH265ReferenceInfo",
        "StdVideoEncodeH264WeightTableFlags",
        "StdVideoEncodeH264WeightTable",
        "StdVideoEncodeH264SliceHeaderFlags",
        "StdVideoEncodeH264PictureInfoFlags",
        "StdVideoEncodeH264ReferenceInfoFlags",
        "StdVideoEncodeH264ReferenceListsInfoFlags",
        "StdVideoEncodeH264RefListModEntry",
        "StdVideoEncodeH264RefPicMarkingEntry",
        "StdVideoEncodeH264ReferenceListsInfo",
        "StdVideoEncodeH264PictureInfo",
        "StdVideoEncodeH264ReferenceInfo",
        "StdVideoEncodeH264SliceHeader",
        "StdVideoH264SpsVuiFlags",
        "StdVideoH264HrdParameters",
        "StdVideoH264SequenceParameterSetVui",
        "StdVideoH264SpsFlags",
        "StdVideoH264ScalingLists",
        "StdVideoH264SequenceParameterSet",
        "StdVideoH264PpsFlags",
        "StdVideoH264PictureParameterSet",
        "StdVideoH264LevelIdc",
        "StdVideoH264ProfileIdc",
        "StdVideoDecodeH264PictureInfoFlags",
        "StdVideoDecodeH264PictureInfo",
        "StdVideoDecodeH264ReferenceInfoFlags",
        "StdVideoDecodeH264ReferenceInfo",
        "StdVideoEncodeH265WeightTableFlags",
        "StdVideoEncodeH265WeightTable",
        "StdVideoEncodeH265SliceSegmentHeaderFlags",
        "StdVideoEncodeH265SliceSegmentHeader",
        "StdVideoEncodeH265ReferenceListsInfoFlags",
        "StdVideoEncodeH265ReferenceListsInfo",
        "StdVideoEncodeH265PictureInfoFlags",
        "StdVideoEncodeH265LongTermRefPics",
        "StdVideoEncodeH265PictureInfo",
        "StdVideoEncodeH265ReferenceInfoFlags",
        "StdVideoEncodeH265ReferenceInfo",
        "StdVideoH265DecPicBufMgr",
        "StdVideoH265SubLayerHrdParameters",
        "StdVideoH265HrdFlags",
        "StdVideoH265HrdParameters",
        "StdVideoH265VpsFlags",
        "StdVideoH265ProfileTierLevelFlags",
        "StdVideoH265ProfileTierLevel",
        "StdVideoH265ProfileIdc",
        "StdVideoH265VideoParameterSet",
        "StdVideoH265ScalingLists",
        "StdVideoH265SpsVuiFlags",
        "StdVideoH265SequenceParameterSetVui",
        "StdVideoH265PredictorPaletteEntries",
        "StdVideoH265SpsFlags",
        "StdVideoH265ShortTermRefPicSetFlags",
        "StdVideoH265ShortTermRefPicSet",
        "StdVideoH265LongTermRefPicsSps",
        "StdVideoH265SequenceParameterSet",
        "StdVideoH265PpsFlags",
        "StdVideoH265PictureParameterSet",
    ]

    # Since exact strings are used in REPLACEMENT_MAP,
    # this is used to find the strings to replace later and put them in a file replacement_map.txt
    REPLACEMENT_CONTAINS_ARR = [
        '#include "vk_platform.h"',
        '#define VK_DEFINE_HANDLE',
        '\n#ifndef VK_DEFINE_NON_DISPATCHABLE_HANDLE\n    #if (VK_USE_64_BIT_PTR_DEFINES==1)\n        #if (defined(__cplusplus) && (__cplusplus >= 201103L)) || (defined(_MSVC_LANG) && (_MSVC_LANG >= 201103L))\n            #define VK_NULL_HANDLE nullptr\n        #else\n            #define VK_NULL_HANDLE ((void*)0)\n        #endif\n    #else\n        #define VK_NULL_HANDLE 0ULL\n    #endif\n#endif\n#ifndef VK_NULL_HANDLE\n    #define VK_NULL_HANDLE 0\n#endif',
        '\n#ifndef VK_USE_64_BIT_PTR_DEFINES\n    #if defined(__LP64__) || defined(_WIN64) || (defined(__x86_64__) && !defined(__ILP32__) ) || defined(_M_X64) || defined(__ia64) || defined (_M_IA64) || defined(__aarch64__) || defined(__powerpc64__) || (defined(__riscv) && __riscv_xlen == 64)\n        #define VK_USE_64_BIT_PTR_DEFINES 1\n    #else\n        #define VK_USE_64_BIT_PTR_DEFINES 0\n    #endif\n#endif',
        '\n#ifndef VK_DEFINE_NON_DISPATCHABLE_HANDLE\n    #if (VK_USE_64_BIT_PTR_DEFINES==1)\n        #define VK_DEFINE_NON_DISPATCHABLE_HANDLE(object) typedef struct object##_T *object;\n    #else\n        #define VK_DEFINE_NON_DISPATCHABLE_HANDLE(object) typedef uint64_t object;\n    #endif\n#endif',
        '#define VK_MAKE_API_VERSION(variant, major, minor, patch)',
        '#define VK_API_VERSION_1_0',
        '#define VK_HEADER_VERSION ',
        '#define VK_HEADER_VERSION_COMPLETE',
        '#define VK_API_VERSION_VARIANT',
        '#define VK_API_VERSION_MAJOR',
        '#define VK_API_VERSION_MINOR',
        '#define VK_API_VERSION_PATCH',
        '#ifdef __OBJC__\n@class',
        '#ifdef __OBJC__\n@protocol',
    ]

    CGEN = None

    REPLACEMENT_EXACT_TEXT_ARR = []

    # This map is used to replace the whole body text in 'def genType'.
    # The map key is the original C header code, which is generated first and then checked if a replacement matches
    REPLACEMENT_MAP = {
        # '#include "vk_platform.h"': '#flag -I @VMODROOT/. \n#include "vk_platform.h"\n#include "vk_video/vulkan_video_codec_h264std.h"\n#include "vk_video/vulkan_video_codec_h264std_decode.h"\n#include "vk_video/vulkan_video_codec_h265std.h"\n#include "vk_video/vulkan_video_codec_h265std_decode.h"\n#include "vk_video/vulkan_video_codec_h264std_encode.h"\n#include "vk_video/vulkan_video_codec_h265std_encode.h"\n',
        # VK_DEFINE_HANDLE and others will be simply replaced with '&object' and 'u64(&object)'
        '\n#define VK_DEFINE_HANDLE(object) typedef struct object##_T* object;\n':
            '',
        '\n#ifndef VK_DEFINE_NON_DISPATCHABLE_HANDLE\n    #if (VK_USE_64_BIT_PTR_DEFINES==1)\n        #if (defined(__cplusplus) && (__cplusplus >= 201103L)) || (defined(_MSVC_LANG) && (_MSVC_LANG >= 201103L))\n            #define VK_NULL_HANDLE nullptr\n        #else\n            #define VK_NULL_HANDLE ((void*)0)\n        #endif\n    #else\n        #define VK_NULL_HANDLE 0ULL\n    #endif\n#endif\n#ifndef VK_NULL_HANDLE\n    #define VK_NULL_HANDLE 0\n#endif':
            '',
        '\n#ifndef VK_USE_64_BIT_PTR_DEFINES\n    #if defined(__LP64__) || defined(_WIN64) || (defined(__x86_64__) && !defined(__ILP32__) ) || defined(_M_X64) || defined(__ia64) || defined (_M_IA64) || defined(__aarch64__) || defined(__powerpc64__) || (defined(__riscv) && __riscv_xlen == 64)\n        #define VK_USE_64_BIT_PTR_DEFINES 1\n    #else\n        #define VK_USE_64_BIT_PTR_DEFINES 0\n    #endif\n#endif\n':
            '',
        '\n#ifndef VK_DEFINE_NON_DISPATCHABLE_HANDLE\n    #if (VK_USE_64_BIT_PTR_DEFINES==1)\n        #if (defined(__cplusplus) && (__cplusplus >= 201103L)) || (defined(_MSVC_LANG) && (_MSVC_LANG >= 201103L))\n            #define VK_NULL_HANDLE nullptr\n        #else\n            #define VK_NULL_HANDLE ((void*)0)\n        #endif\n    #else\n        #define VK_NULL_HANDLE 0ULL\n    #endif\n#endif\n#ifndef VK_NULL_HANDLE\n    #define VK_NULL_HANDLE 0\n#endif\n':
            '',
        '\n#ifndef VK_DEFINE_NON_DISPATCHABLE_HANDLE\n    #if (VK_USE_64_BIT_PTR_DEFINES==1)\n        #define VK_DEFINE_NON_DISPATCHABLE_HANDLE(object) typedef struct object##_T *object;\n    #else\n        #define VK_DEFINE_NON_DISPATCHABLE_HANDLE(object) typedef uint64_t object;\n    #endif\n#endif\n':
            '',
        '#define VK_MAKE_API_VERSION(variant, major, minor, patch) \\\n    ((((uint32_t)(variant)) << 29U) | (((uint32_t)(major)) << 22U) | (((uint32_t)(minor)) << 12U) | ((uint32_t)(patch)))\n':
            'pub fn make_api_version(variant u32, major u32, minor u32, patch u32) u32 {\n  return variant << 29 | major << 22 | minor << 12 | patch\n}\n',
        '// Vulkan 1.0 version number\n#define VK_API_VERSION_1_0 VK_MAKE_API_VERSION(0, 1, 0, 0)// Patch version should always be set to 0\n':
            'pub const api_version_1_0 = make_api_version(0, 1, 0, 0) // Patch version should always be set to 0',
        '// Version of this file\n#define VK_HEADER_VERSION ':
            'pub const header_version = ',
        '// Complete version of this file\n#define VK_HEADER_VERSION_COMPLETE VK_MAKE_API_VERSION(0, 1, 3, VK_HEADER_VERSION)\n':
            'pub const header_version_complete = make_api_version(0, 1, 3, header_version)',
        '#define VK_API_VERSION_VARIANT(version) ((uint32_t)(version) >> 29U)':
            'pub fn version_variant(version u32) u32 {\n  return version >> 29\n}',
        '#define VK_API_VERSION_MAJOR(version) (((uint32_t)(version) >> 22U) & 0x7FU)':
            'pub fn api_version_major(version u32) u32 {\n  return version >> 22 & u32(0x7F)\n}',
        '#define VK_API_VERSION_MINOR(version) (((uint32_t)(version) >> 12U) & 0x3FFU)':
            'pub fn api_version_minor(version u32) u32 {\n  return version >> 12 & u32(0x3FF)\n}',
        '#define VK_API_VERSION_PATCH(version) ((uint32_t)(version) & 0xFFFU)':
            'pub fn api_version_patch(version u32) u32 {\n  return version & u32(0xFFF)\n}',
        '// Vulkan 1.3 version number\n#define VK_API_VERSION_1_3 VK_MAKE_API_VERSION(0, 1, 3, 0)// Patch version should always be set to 0\n':
            '// Vulkan 1.3 version number\npub const api_version_1_3 = make_api_version(0, 1, 3, 0)// Patch version should always be set to 0\n',
        '// Vulkan 1.2 version number\n#define VK_API_VERSION_1_2 VK_MAKE_API_VERSION(0, 1, 2, 0)// Patch version should always be set to 0\n':
            '// Vulkan 1.2 version number\npub const api_version_1_2 = make_api_version(0, 1, 2, 0)// Patch version should always be set to 0\n',
        '// Vulkan 1.1 version number\n#define VK_API_VERSION_1_1 VK_MAKE_API_VERSION(0, 1, 1, 0)// Patch version should always be set to 0\n':
            '// Vulkan 1.1 version number\npub const api_version_1_1 = make_api_version(0, 1, 1, 0)// Patch version should always be set to 0\n',
        # TODO: Double check if we need a compile parameter -Dparam for __OBJC__ and what to do about metal
        '#ifdef __OBJC__\n@class CAMetalLayer;\n#else\ntypedef void CAMetalLayer;\n#endif\n':
            '',
        '#ifdef __OBJC__\n@class CAMetalLayer;\n#else\ntypedef void \n':
            '',
        '#ifdef __OBJC__\n@protocol MTLDevice;\ntypedef id<MTLDevice> MTLDevice_id;\n#else\ntypedef void* MTLDevice_id;\n#endif\n':
            '',
        '#ifdef __OBJC__\n@protocol MTLDevice;\ntypedef id<MTLDevice> MTLDevice_id;\n#else\ntypedef void* \n':
            '',
        '#ifdef __OBJC__\n@protocol MTLCommandQueue;\ntypedef id<MTLCommandQueue> MTLCommandQueue_id;\n#else\ntypedef void* MTLCommandQueue_id;\n#endif\n':
            '',
        '#ifdef __OBJC__\n@protocol MTLCommandQueue;\ntypedef id<MTLCommandQueue> MTLCommandQueue_id;\n#else\ntypedef void* \n':
            '',
        '#ifdef __OBJC__\n@protocol MTLBuffer;\ntypedef id<MTLBuffer> MTLBuffer_id;\n#else\ntypedef void* MTLBuffer_id;\n#endif\n':
            '',
        '#ifdef __OBJC__\n@protocol MTLBuffer;\ntypedef id<MTLBuffer> MTLBuffer_id;\n#else\ntypedef void* \n':
            '',
        '#ifdef __OBJC__\n@protocol MTLTexture;\ntypedef id<MTLTexture> MTLTexture_id;\n#else\ntypedef void* MTLTexture_id;\n#endif\n':
            '',
        '#ifdef __OBJC__\n@protocol MTLTexture;\ntypedef id<MTLTexture> MTLTexture_id;\n#else\ntypedef void* \n':
            '',
        '#ifdef __OBJC__\n@protocol MTLSharedEvent;\ntypedef id<MTLSharedEvent> MTLSharedEvent_id;\n#else\ntypedef void* MTLSharedEvent_id;\n#endif\n':
            '',
        '#ifdef __OBJC__\n@protocol MTLSharedEvent;\ntypedef id<MTLSharedEvent> MTLSharedEvent_id;\n#else\ntypedef void* \n':
            '',
    }
    # so the key is whatever the body contains at the end of 'genType'.
    # Means that changes to the v code will require remapping...

    # These are used to find the base alias in genGroup,
    # because Vlang doesn't allow non basetype type aliases
    BASE_TYPES_ARR = [
        'u32',
        'u64',
    ]
    # Map like '(VkFlags: u32) (VkAccessFlags: u32),
    # where VkAccessFlags is aliased to VkFlags in C
    # More mappings are added dynamically
    ALIAS_TO_BASE_TYPE_MAP = {}

    # Used to find things like "dstOffsets[2]" in struct member name
    ARRAY_REGEX = re.compile(r"\w+(\[\w+\])")

    # CAMEL_TO_SNAKE_CASE_REGEX = re.compile(r'(?<!^)(?=[A-Z])')
    # This one from nickl- on stackoverflow also takes care of
    # - '_' as first character
    # - multiple upper case characters
    # - numbers in names
    # https://stackoverflow.com/questions/1175208/elegant-python-function-to-convert-camelcase-to-snake-case
    CAMEL_TO_SNAKE_CASE_REGEX = re.compile('((?<=[a-z0-9])[A-Z]|(?!^)[A-Z](?=[a-z]))')

    FIX_TYPOS_MAP = {
        'VK_MAX_GOBA_PRIORITY_SIZE_KHR': 'VK_MAX_GLOBAL_PRIORITY_SIZE_KHR',
        #'vk_googe_hs_nctionaity_1_extension_name': 'vk_googe_hs_nctionaity_1_extension_name'
    }

    DONT_CONVERT_TO_SNAKE_CASE_ARR = [
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Internal state - accumulators for different inner block text
        self.sections = {section: [] for section in self.ALL_SECTIONS}
        self.feature_not_empty = False
        self.may_alias = None
        self.CGEN = COutputGenerator(self)

    def beginFile(self, genOpts):
        OutputGenerator.beginFile(self, genOpts)
        if self.genOpts is None:
            raise MissingGeneratorOptionsError()
        # V-specific
        #
        # Multiple inclusion protection & C++ wrappers.
        if self.genOpts.protectFile and self.genOpts.filename:
            headerSym = self.genOpts.filename
            # write('module', headerSym, file=self.outFile)
            # write('module', headerSym.replace('.v', ''), file=self.outFile)
            write('module vulkan', file=self.outFile)

            self.newline()

        # User-supplied prefix text, if any (list of strings)
        if genOpts.prefixText:
            for s in genOpts.prefixText:
                write(s, file=self.outFile)

        # # C++ extern wrapper - after prefix lines so they can add includes.
        # self.newline()
        # write('#ifdef __cplusplus', file=self.outFile)
        # write('extern "C" {', file=self.outFile)
        # write('#endif', file=self.outFile)
        # self.newline()

    def endFile(self):
        # V-specific
        # Finish C++ wrapper and multiple inclusion protection
        if self.genOpts is None:
            raise MissingGeneratorOptionsError()
        # self.newline()
        # write('#ifdef __cplusplus', file=self.outFile)
        # write('}', file=self.outFile)
        # write('#endif', file=self.outFile)
        # if self.genOpts.protectFile and self.genOpts.filename:
        #     self.newline()
        #     write('#endif', file=self.outFile)
        # Finish processing in superclass
        OutputGenerator.endFile(self)

        # Write REPLACEMENT_EXACT_TEXT_ARR to replacement_map.txt
        # This is to store the exact C code to (manually) put in REPLACEMENT_MAP.
        # It is then used in genType to replace c_body with v_body
        with open("replacement_map.txt", "w") as text_file:
            key_strings = ''
            for itm in self.REPLACEMENT_EXACT_TEXT_ARR:
                # Oh shit son, writing to file puts in new lines instead of just '\n'
                key_strings = key_strings + "'" + self.escStr(itm).replace('\\', '\\\\').replace('\n',
                                                                                                 '\\n') + "':\n    '',\n    "
            text_file.write("REPLACEMENT_MAP = {{\n    {}\n}}".format(key_strings))

    def beginFeature(self, interface, emit):
        # Start processing in superclass
        OutputGenerator.beginFeature(self, interface, emit)
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

    def endFeature(self):
        "Actually write the interface to the output file."
        # V-specific
        if self.emit:
            if self.feature_not_empty:
                if self.genOpts is None:
                    raise MissingGeneratorOptionsError()
                if self.genOpts.conventions is None:
                    raise MissingGeneratorOptionsConventionsError()
                is_core = self.featureName and self.featureName.startswith(self.conventions.api_prefix + 'VERSION_')
                if self.genOpts.conventions.writeFeature(self.featureExtraProtect, self.genOpts.filename):
                    self.newline()
                    # TODO: Can be removed / reinserted when Vlang supports $ compile time code on root/module level
                    # https://github.com/vlang/v/issues/20420
#                    if self.genOpts.protectFeature:
#                        write('#ifndef', self.featureName, file=self.outFile)

                    # If type declarations are needed by other features based on
                    # this one, it may be necessary to suppress the ExtraProtect,
                    # or move it below the 'for section...' loop.
                    if self.featureExtraProtect is not None:
                        # TODO: Can be removed / reinserted when Vlang supports $ compile time code on root/module level
                        # https://github.com/vlang/v/issues/20420
                        pass
#                        write('#ifdef', self.featureExtraProtect, file=self.outFile)
                    self.newline()

                    # Generate warning of possible use in IDEs
                    write(f'// {self.featureName} is a preprocessor guard. Do not pass it to API calls.',
                          file=self.outFile)
                    # write('#define', self.featureName, '1', file=self.outFile)
                    # NOTE Anton: Removing Vk... from variable names, as they are all in the vulkan name space already
                    self.featureName = self.removeVk(self.featureName)

                    write('const', self.featureName.lower(), '=', '1', file=self.outFile)
                    for section in self.TYPE_SECTIONS:
                        contents = self.sections[section]
                        if contents:
                            write('\n'.join(contents), file=self.outFile)

                    if self.genOpts.genFuncPointers and self.sections['commandPointer']:
                        write('\n'.join(self.sections['commandPointer']), file=self.outFile)
                        self.newline()

                    if self.sections['command']:
                        # NOTE Anton: Removing functions behind VK_NO_PROTOTYPES, as their symbols aren't found
                        # in graphics card drivers for dynamic linking.
                        # TODO: Can be removed when Vlang supports $ compile time code on root/module level
                        # https://github.com/vlang/v/issues/20420
                        # if self.genOpts.protectProto and self.genOpts.protectProtoStr == 'VK_NO_PROTOTYPES':
                        #     return

                        if self.genOpts.protectProto:
                            write(self.genOpts.protectProto,
                                  self.genOpts.protectProtoStr, file=self.outFile)
                        if self.genOpts.protectExtensionProto and not is_core:
                            write(self.genOpts.protectExtensionProto,
                                  self.genOpts.protectExtensionProtoStr, file=self.outFile)
                        write('\n'.join(self.sections['command']), end='', file=self.outFile)
                        if self.genOpts.protectExtensionProto and not is_core:
                            # TODO: Can be removed / reinserted when Vlang supports $ compile time code on root/module level
                            # https://github.com/vlang/v/issues/20420
                            pass
#                            write('#endif' +
#                                  self._endProtectComment(protect_directive=self.genOpts.protectExtensionProto,
#                                                          protect_str=self.genOpts.protectExtensionProtoStr),
#                                  file=self.outFile)
                        if self.genOpts.protectProto:
                            # TODO: Can be removed / reinserted when Vlang supports $ compile time code on root/module level
                            # https://github.com/vlang/v/issues/20420
                            pass
#                            write('} // VK_NO_PROTOTYPES' +
#                                  self._endProtectComment(protect_directive=self.genOpts.protectProto,
#                                                          protect_str=self.genOpts.protectProtoStr),
#                                  file=self.outFile)
                        else:
                            self.newline()

                    if self.featureExtraProtect is not None:
                        # TODO: Can be removed / reinserted when Vlang supports $ compile time code on root/module level
                        # https://github.com/vlang/v/issues/20420
                        pass
#                        write('#endif' +
#                              self._endProtectComment(protect_str=self.featureExtraProtect),
#                              file=self.outFile)

                    if self.genOpts.protectFeature:
                        # TODO: Can be removed / reinserted when Vlang supports $ compile time code on root/module level
                        # https://github.com/vlang/v/issues/20420
                        pass
#                        write('#endif' +
#                              self._endProtectComment(protect_str=self.featureName),
#                              file=self.outFile)
        # Finish processing in superclass
        OutputGenerator.endFeature(self)

    def escStr(self, text) -> str:
        # NOTE Anton: Idk man. If text contains `\` before new line, the mapping isn't found. This fixes it
        return text.replace(r'\\', '\\\\').replace(r'\n', '\\n')

    # NOTE Anton: Removing Vk... from variable names, as they are all in the vulkan name space already
    def removeVk(self, v_name_or_value) -> str:
        # TODO: No idea why 'vk_false' is replaced with '_false'. Temporary solution
        if v_name_or_value.lower() in ['vk_true', 'vk_false']:
            return v_name_or_value
        if v_name_or_value.lower().startswith('vk_') and not v_name_or_value[3:].lower() in ['true', 'false']:
            v_name_or_value = v_name_or_value[3:]
        if v_name_or_value.lower().startswith('vk') and not v_name_or_value[2:].lower() in ['true', 'false']:
            v_name_or_value = v_name_or_value[2:]
        if v_name_or_value.lower().startswith('c.vk') and not v_name_or_value[4:].lower() in ['true', 'false']:
            v_name_or_value = 'C.' + v_name_or_value[4:]
        return v_name_or_value

    def appendSection(self, section, text):
        "Append a definition to the specified section"

        if section is None:
            self.logMsg('error',
                        'Missing section in appendSection (probably a <type> element missing its \'category\' attribute. Text:',
                        text)
            exit(1)

        # Add text to REPLACEMENT_CONTAINS_ARR if it contains ...
        esc_text = self.escStr(text)
        for starts_with in self.REPLACEMENT_CONTAINS_ARR:
            if text.__contains__(starts_with):
                self.REPLACEMENT_EXACT_TEXT_ARR.append(esc_text)

        if esc_text in self.REPLACEMENT_MAP:
            text = self.REPLACEMENT_MAP[esc_text]
        # TODO: This is dumb and should have been handled before these commands even get here, BUT
        # another map to remember alias functions or a custom "reg.py" are the only other solutions coming to mind right now
        prototype_functions = ['vkGetRayTracingCaptureReplayShaderGroupHandlesKHR', 'vkCmdTraceRaysIndirectKHR', 'vkGetRayTracingShaderGroupStackSizeKHR', 'vkCmdSetRayTracingPipelineStackSizeKHR', 'vkCmdDrawMeshTasksEXT', 'vkCmdDrawMeshTasksIndirectEXT', 'vkCmdDrawMeshTasksIndirectCountEXT', 'vkCreateAndroidSurfaceKHR', 'vkCreateWin32SurfaceKHR','vkGetPhysicalDeviceWin32PresentationSupportKHR','vkGetPhysicalDeviceVideoCapabilitiesKHR','vkGetPhysicalDeviceVideoFormatPropertiesKHR','vkCreateVideoSessionKHR','vkDestroyVideoSessionKHR','vkGetVideoSessionMemoryRequirementsKHR','vkBindVideoSessionMemoryKHR', 'vkCreateVideoSessionParametersKHR', 'vkUpdateVideoSessionParametersKHR', 'vkDestroyVideoSessionParametersKHR', 'vkCmdBeginVideoCodingKHR', 'vkCmdEndVideoCodingKHR', 'vkCmdControlVideoCodingKHR','vkCmdDecodeVideoKHR','vkCmdBeginRenderingKHR','vkCmdEndRenderingKHR','vkGetPhysicalDeviceFeatures2KHR','vkGetPhysicalDeviceProperties2KHR','vkGetPhysicalDeviceFormatProperties2KHR','vkGetPhysicalDeviceImageFormatProperties2KHR','vkGetPhysicalDeviceQueueFamilyProperties2KHR','vkGetPhysicalDeviceMemoryProperties2KHR','vkGetPhysicalDeviceSparseImageFormatProperties2KHR','vkGetDeviceGroupPeerMemoryFeaturesKHR','vkCmdSetDeviceMaskKHR','vkCmdDispatchBaseKHR','vkTrimCommandPoolKHR','vkEnumeratePhysicalDeviceGroupsKHR','vkGetPhysicalDeviceExternalBufferPropertiesKHR','vkGetMemoryWin32HandleKHR','vkGetMemoryWin32HandlePropertiesKHR','vkGetMemoryFdKHR','vkGetMemoryFdPropertiesKHR','vkGetPhysicalDeviceExternalSemaphorePropertiesKHR', 'vkImportSemaphoreWin32HandleKHR','vkGetSemaphoreWin32HandleKHR','vkImportSemaphoreFdKHR','vkGetSemaphoreFdKHR','vkCmdPushDescriptorSetKHR','vkCmdPushDescriptorSetWithTemplateKHR','vkCreateDescriptorUpdateTemplateKHR','vkDestroyDescriptorUpdateTemplateKHR','vkUpdateDescriptorSetWithTemplateKHR','vkCreateRenderPass2KHR','vkCmdBeginRenderPass2KHR','vkCmdNextSubpass2KHR','vkCmdEndRenderPass2KHR','vkGetSwapchainStatusKHR','vkGetPhysicalDeviceExternalFencePropertiesKHR','vkImportFenceWin32HandleKHR','vkGetFenceWin32HandleKHR', 'vkImportFenceFdKHR', 'vkGetFenceFdKHR','vkEnumeratePhysicalDeviceQueueFamilyPerformanceQueryCountersKHR','vkGetPhysicalDeviceQueueFamilyPerformanceQueryPassesKHR','vkAcquireProfilingLockKHR','vkReleaseProfilingLockKHR','vkGetImageMemoryRequirements2KHR','vkGetBufferMemoryRequirements2KHR','vkGetBufferMemoryRequirements2KHR','vkGetImageSparseMemoryRequirements2KHR','vkCreateSamplerYcbcrConversionKHR','vkDestroySamplerYcbcrConversionKHR','vkBindBufferMemory2KHR','vkBindImageMemory2KHR','vkGetDescriptorSetLayoutSupportKHR','vkCmdDrawIndirectCountKHR','vkCmdDrawIndexedIndirectCountKHR','vkGetSemaphoreCounterValueKHR','vkWaitSemaphoresKHR','vkSignalSemaphoreKHR','vkGetPhysicalDeviceFragmentShadingRatesKHR','vkCmdSetFragmentShadingRateKHR','vkWaitForPresentKHR','vkGetBufferDeviceAddressKHR','vkGetBufferOpaqueCaptureAddressKHR','vkGetDeviceMemoryOpaqueCaptureAddressKHR','vkCreateDeferredOperationKHR','vkDestroyDeferredOperationKHR','vkGetDeferredOperationMaxConcurrencyKHR','vkGetDeferredOperationResultKHR','vkDeferredOperationJoinKHR','vkGetPipelineExecutablePropertiesKHR','vkGetPipelineExecutableStatisticsKHR','vkGetPipelineExecutableInternalRepresentationsKHR','vkMapMemory2KHR','vkUnmapMemory2KHR','vkGetPhysicalDeviceVideoEncodeQualityLevelPropertiesKHR', 'vkGetEncodedVideoSessionParametersKHR','vkCmdEncodeVideoKHR','vkCmdSetEvent2KHR','vkCmdResetEvent2KHR','vkCmdWaitEvents2KHR','vkCmdPipelineBarrier2KHR','vkCmdWriteTimestamp2KHR','vkQueueSubmit2KHR','vkCmdWriteBufferMarker2AMD', 'vkGetQueueCheckpointData2NV','vkCmdCopyBuffer2KHR','vkCmdCopyImage2KHR','vkCmdCopyBufferToImage2KHR','vkCmdCopyImageToBuffer2KHR','vkCmdBlitImage2KHR','vkCmdResolveImage2KHR','vkCmdTraceRaysIndirect2KHR','vkGetDeviceBufferMemoryRequirementsKHR','vkGetDeviceImageMemoryRequirementsKHR','vkGetDeviceImageSparseMemoryRequirementsKHR','vkCmdBindIndexBuffer2KHR','vkGetRenderingAreaGranularityKHR','vkGetDeviceImageSubresourceLayoutKHR','vkGetImageSubresourceLayout2KHR','vkGetPhysicalDeviceCooperativeMatrixPropertiesKHR','vkCreateDebugReportCallbackEXT','vkDestroyDebugReportCallbackEXT','vkDebugReportMessageEXT','vkDebugMarkerSetObjectTagEXT','vkDebugMarkerSetObjectNameEXT','vkCmdDebugMarkerBeginEXT','vkCmdDebugMarkerEndEXT','vkCmdDebugMarkerInsertEXT', 'vkCmdBindTransformFeedbackBuffersEXT','vkCmdBeginTransformFeedbackEXT','vkCmdEndTransformFeedbackEXT','vkCmdBeginQueryIndexedEXT','vkCmdEndQueryIndexedEXT','vkCmdDrawIndirectByteCountEXT','vkCreateCuModuleNVX','vkCreateCuFunctionNVX','vkDestroyCuModuleNVX','vkDestroyCuFunctionNVX','vkCmdCuLaunchKernelNVX','vkGetImageViewHandleNVX','vkGetImageViewAddressNVX','vkCmdDrawIndirectCountAMD','vkCmdDrawIndexedIndirectCountAMD','vkGetShaderInfoAMD','vkCreateStreamDescriptorSurfaceGGP','vkGetPhysicalDeviceExternalImageFormatPropertiesNV','vkGetMemoryWin32HandleNV','vkCreateViSurfaceNN','vkCmdBeginConditionalRenderingEXT','vkCmdEndConditionalRenderingEXT','vkCmdSetViewportWScalingNV','vkReleaseDisplayEXT','vkAcquireXlibDisplayEXT','vkGetRandROutputDisplayEXT','vkGetPhysicalDeviceSurfaceCapabilities2EXT','vkDisplayPowerControlEXT','vkDisplayPowerControlEXT','vkRegisterDeviceEventEXT','vkRegisterDisplayEventEXT','vkGetSwapchainCounterEXT','vkGetRefreshCycleDurationGOOGLE','vkGetPastPresentationTimingGOOGLE','vkCmdSetDiscardRectangleEXT','vkCmdSetDiscardRectangleEnableEXT','vkCmdSetDiscardRectangleModeEXT','vkSetHdrMetadataEXT','vkCreateIOSSurfaceMVK','vkCreateMacOSSurfaceMVK','vkSetDebugUtilsObjectNameEXT','vkSetDebugUtilsObjectTagEXT','vkQueueBeginDebugUtilsLabelEXT','vkQueueEndDebugUtilsLabelEXT','vkQueueInsertDebugUtilsLabelEXT','vkCmdBeginDebugUtilsLabelEXT','vkCmdEndDebugUtilsLabelEXT','vkCmdInsertDebugUtilsLabelEXT','vkCreateDebugUtilsMessengerEXT','vkDestroyDebugUtilsMessengerEXT','vkSubmitDebugUtilsMessageEXT','vkGetAndroidHardwareBufferPropertiesANDROID','vkGetMemoryAndroidHardwareBufferANDROID','vkCreateExecutionGraphPipelinesAMDX','vkGetExecutionGraphPipelineScratchSizeAMDX','vkGetExecutionGraphPipelineNodeIndexAMDX','vkCmdInitializeGraphScratchMemoryAMDX','vkCmdDispatchGraphAMDX','vkCmdDispatchGraphIndirectAMDX','vkCmdDispatchGraphIndirectCountAMDX','vkCmdSetSampleLocationsEXT','vkGetPhysicalDeviceMultisamplePropertiesEXT','vkGetImageDrmFormatModifierPropertiesEXT','vkCreateValidationCacheEXT','vkDestroyValidationCacheEXT','vkMergeValidationCachesEXT','vkGetValidationCacheDataEXT','vkCmdBindShadingRateImageNV','vkCmdSetViewportShadingRatePaletteNV', 'vkCmdSetCoarseSampleOrderNV','vkCreateAccelerationStructureNV', 'vkDestroyAccelerationStructureNV','vkGetAccelerationStructureMemoryRequirementsNV','vkBindAccelerationStructureMemoryNV','vkCmdBuildAccelerationStructureNV','vkCmdCopyAccelerationStructureNV','vkCmdTraceRaysNV','vkCreateRayTracingPipelinesNV','vkGetRayTracingShaderGroupHandlesKHR', 'vkGetRayTracingShaderGroupHandlesNV', 'vkGetAccelerationStructureHandleNV','vkCmdWriteAccelerationStructuresPropertiesNV', 'vkCompileDeferredNV','vkGetMemoryHostPointerPropertiesEXT','vkCmdWriteBufferMarkerAMD','vkGetPhysicalDeviceCalibrateableTimeDomainsEXT','vkGetCalibratedTimestampsEXT','vkCmdDrawMeshTasksNV','vkCmdDrawMeshTasksIndirectNV','vkCmdDrawMeshTasksIndirectCountNV','vkCmdSetExclusiveScissorEnableNV','vkCmdSetExclusiveScissorNV','vkCmdSetCheckpointNV','vkGetQueueCheckpointDataNV','vkInitializePerformanceApiINTEL','vkUninitializePerformanceApiINTEL','vkCmdSetPerformanceMarkerINTEL','vkCmdSetPerformanceStreamMarkerINTEL', 'vkCmdSetPerformanceOverrideINTEL', 'vkAcquirePerformanceConfigurationINTEL', 'vkReleasePerformanceConfigurationINTEL','vkQueueSetPerformanceConfigurationINTEL','vkGetPerformanceParameterINTEL','vkSetLocalDimmingAMD','vkCreateImagePipeSurfaceFUCHSIA','vkCreateMetalSurfaceEXT','vkGetBufferDeviceAddressEXT','vkGetPhysicalDeviceToolPropertiesEXT','vkGetPhysicalDeviceCooperativeMatrixPropertiesNV','vkGetPhysicalDeviceSupportedFramebufferMixedSamplesCombinationsNV','vkGetPhysicalDeviceSurfacePresentModes2EXT','vkAcquireFullScreenExclusiveModeEXT','vkReleaseFullScreenExclusiveModeEXT','vkGetDeviceGroupSurfacePresentModes2EXT','vkCmdSetLineStippleEXT','vkResetQueryPoolEXT','vkCmdSetCullModeEXT','vkCmdSetFrontFaceEXT','vkCmdSetPrimitiveTopologyEXT','vkCmdSetViewportWithCountEXT','vkCmdSetScissorWithCountEXT','vkCmdBindVertexBuffers2EXT', 'vkCmdSetDepthTestEnableEXT','vkCmdSetDepthWriteEnableEXT','vkCmdSetDepthCompareOpEXT','vkCmdSetDepthBoundsTestEnableEXT','vkCmdSetStencilTestEnableEXT','vkCmdSetStencilOpEXT','vkCopyMemoryToImageEXT','vkCopyImageToMemoryEXT','vkCopyImageToImageEXT','vkTransitionImageLayoutEXT','vkGetImageSubresourceLayout2EXT', 'vkReleaseSwapchainImagesEXT','vkGetGeneratedCommandsMemoryRequirementsNV','vkCmdPreprocessGeneratedCommandsNV','vkCmdExecuteGeneratedCommandsNV','vkCmdBindPipelineShaderGroupNV','vkCreateIndirectCommandsLayoutNV','vkDestroyIndirectCommandsLayoutNV','vkCmdSetDepthBias2EXT','vkAcquireDrmDisplayEXT','vkGetDrmDisplayEXT','vkCreatePrivateDataSlotEXT','vkDestroyPrivateDataSlotEXT','vkSetPrivateDataEXT','vkGetPrivateDataEXT','vkCreateCudaModuleNV', 'vkGetCudaModuleCacheNV','vkCreateCudaFunctionNV','vkDestroyCudaModuleNV','vkDestroyCudaFunctionNV','vkCmdCudaLaunchKernelNV','vkExportMetalObjectsEXT','vkGetDescriptorSetLayoutSizeEXT','vkGetDescriptorSetLayoutBindingOffsetEXT','vkGetDescriptorEXT','vkCmdBindDescriptorBuffersEXT','vkCmdSetDescriptorBufferOffsetsEXT', 'vkCmdBindDescriptorBufferEmbeddedSamplersEXT','vkGetBufferOpaqueCaptureDescriptorDataEXT','vkGetImageOpaqueCaptureDescriptorDataEXT','vkGetImageViewOpaqueCaptureDescriptorDataEXT','vkGetSamplerOpaqueCaptureDescriptorDataEXT','vkGetAccelerationStructureOpaqueCaptureDescriptorDataEXT','vkCmdSetFragmentShadingRateEnumNV','vkGetDeviceFaultInfoEXT','vkAcquireWinrtDisplayNV','vkGetWinrtDisplayNV','vkCreateDirectFBSurfaceEXT', 'vkGetPhysicalDeviceDirectFBPresentationSupportEXT','vkCmdSetVertexInputEXT','vkGetMemoryZirconHandleFUCHSIA','vkGetMemoryZirconHandlePropertiesFUCHSIA','vkImportSemaphoreZirconHandleFUCHSIA','vkGetSemaphoreZirconHandleFUCHSIA','vkCreateBufferCollectionFUCHSIA','vkSetBufferCollectionImageConstraintsFUCHSIA','vkSetBufferCollectionBufferConstraintsFUCHSIA','vkDestroyBufferCollectionFUCHSIA','vkGetBufferCollectionPropertiesFUCHSIA','vkGetDeviceSubpassShadingMaxWorkgroupSizeHUAWEI','vkCmdSubpassShadingHUAWEI','vkCmdBindInvocationMaskHUAWEI', 'vkGetMemoryRemoteAddressNV','vkGetPipelinePropertiesEXT','vkCmdSetPatchControlPointsEXT','vkCmdSetRasterizerDiscardEnableEXT','vkCmdSetDepthBiasEnableEXT','vkCmdSetLogicOpEXT','vkCmdSetPrimitiveRestartEnableEXT','vkCreateScreenSurfaceQNX','vkGetPhysicalDeviceScreenPresentationSupportQNX', 'vkCmdSetColorWriteEnableEXT','vkCmdDrawMultiEXT','vkCmdDrawMultiIndexedEXT','vkCreateMicromapEXT','vkDestroyMicromapEXT','vkCmdBuildMicromapsEXT','vkBuildMicromapsEXT','vkCopyMicromapEXT','vkCopyMicromapToMemoryEXT','vkCopyMemoryToMicromapEXT', 'vkWriteMicromapsPropertiesEXT','vkCmdCopyMicromapEXT','vkCmdCopyMicromapToMemoryEXT','vkCmdCopyMemoryToMicromapEXT','vkCmdWriteMicromapsPropertiesEXT','vkGetDeviceMicromapCompatibilityEXT','vkGetMicromapBuildSizesEXT','vkCmdDrawClusterHUAWEI',
'vkCmdDrawClusterIndirectHUAWEI',
'vkSetDeviceMemoryPriorityEXT',
'vkGetDescriptorSetLayoutHostMappingInfoVALVE',
'vkGetDescriptorSetHostMappingVALVE',
'vkCmdCopyMemoryIndirectNV',
'vkCmdCopyMemoryToImageIndirectNV',
'vkCmdDecompressMemoryNV',
'vkCmdDecompressMemoryIndirectCountNV',
'vkGetPipelineIndirectMemoryRequirementsNV',
'vkCmdUpdatePipelineIndirectBufferNV',
                               'vkGetPipelineIndirectDeviceAddressNV',
                               'vkCmdSetTessellationDomainOriginEXT',
                               'vkCmdSetDepthClampEnableEXT',
                               'vkCmdSetPolygonModeEXT',
                               'vkCmdSetRasterizationSamplesEXT',
                               'vkCmdSetSampleMaskEXT',
                               'vkCmdSetAlphaToCoverageEnableEXT',
                               'vkCmdSetAlphaToOneEnableEXT',
                               'vkCmdSetLogicOpEnableEXT',
                               'vkCmdSetColorBlendEnableEXT',
                               'vkCmdSetColorBlendEquationEXT',
                               'vkCmdSetColorWriteMaskEXT',
                               'vkCmdSetRasterizationStreamEXT',
                               'vkCmdSetConservativeRasterizationModeEXT',
                               'vkCmdSetExtraPrimitiveOverestimationSizeEXT',
                               'vkCmdSetDepthClipEnableEXT',
                               'vkCmdSetSampleLocationsEnableEXT',
                               'vkCmdSetColorBlendAdvancedEXT',
                               'vkCmdSetProvokingVertexModeEXT',
                               'vkCmdSetLineRasterizationModeEXT',
                               'vkCmdSetLineStippleEnableEXT',
                               'vkCmdSetDepthClipNegativeOneToOneEXT',
                               'vkCmdSetViewportWScalingEnableNV',
                               'vkCmdSetViewportSwizzleNV',
                               'vkCmdSetCoverageToColorEnableNV',
                               'vkCmdSetCoverageToColorLocationNV',
                               'vkCmdSetCoverageModulationModeNV',
                               'vkCmdSetCoverageModulationTableEnableNV',
                               'vkCmdSetCoverageModulationTableNV',
                               'vkCmdSetShadingRateImageEnableNV',
                               'vkCmdSetRepresentativeFragmentTestEnableNV',
                               'vkCmdSetCoverageReductionModeNV',
                               'vkGetShaderModuleIdentifierEXT',
                               'vkGetShaderModuleCreateInfoIdentifierEXT',
                               'vkGetPhysicalDeviceOpticalFlowImageFormatsNV',
                               'vkCreateOpticalFlowSessionNV',
                               'vkDestroyOpticalFlowSessionNV',
                               'vkBindOpticalFlowSessionImageNV',
                               'vkCmdOpticalFlowExecuteNV',
                               'vkCreateShadersEXT',
                               'vkDestroyShaderEXT',
                               'vkGetShaderBinaryDataEXT',
                               'vkCmdBindShadersEXT',
                               'vkGetFramebufferTilePropertiesQCOM',
                               'vkGetDynamicRenderingTilePropertiesQCOM',
                               'vkSetLatencySleepModeNV',
                               'vkLatencySleepNV',
                               'vkSetLatencyMarkerNV',
                               'vkGetLatencyTimingsNV',
                               'vkQueueNotifyOutOfBandNV',
                               'vkCmdSetAttachmentFeedbackLoopEnableEXT',
                               'vkGetScreenBufferPropertiesQNX',
                               'vkCreateAccelerationStructureKHR',
                               'vkDestroyAccelerationStructureKHR',
                               'vkCmdBuildAccelerationStructuresKHR',
                               'vkCmdBuildAccelerationStructuresIndirectKHR',
                               'vkBuildAccelerationStructuresKHR',
                               'vkCopyAccelerationStructureKHR',
                               'vkCopyAccelerationStructureToMemoryKHR',
                               'vkCopyMemoryToAccelerationStructureKHR',
                               'vkWriteAccelerationStructuresPropertiesKHR',
                               'vkCmdCopyAccelerationStructureKHR',
                               'vkCmdCopyAccelerationStructureToMemoryKHR',
                               'vkCmdCopyMemoryToAccelerationStructureKHR',
                               'vkGetAccelerationStructureDeviceAddressKHR',
                               'vkCmdWriteAccelerationStructuresPropertiesKHR',
                               'vkGetDeviceAccelerationStructureCompatibilityKHR',
                               'vkGetAccelerationStructureBuildSizesKHR',
                               'vkCmdTraceRaysKHR',
                               'vkCreateRayTracingPipelinesKHR'
                               ]
        if not any(prototype_function in text for prototype_function in prototype_functions):
            self.sections[section].append(text)
            self.feature_not_empty = True
        else:
            x = "qwe"

    def genType(self, typeinfo, name, alias):
        body = ''
        section = ''
        cur_type = self.genCType(typeinfo, name, alias)
        if cur_type is None or not cur_type or cur_type[1].startswith('// DEPRECATED:'):
            return
        c_section, c_body = cur_type

        # Add text to REPLACEMENT_CONTAINS_ARR if it contains something from REPLACEMENT_CONTAINS_ARR
        # Later used to find exactly matching C Code and replace it with V code
        esc_text = self.escStr(c_body)
        for contains_str in self.REPLACEMENT_CONTAINS_ARR:
            if contains_str in c_body:
                self.REPLACEMENT_EXACT_TEXT_ARR.append(esc_text)

        cur_type = self.genVType(typeinfo, name, alias)
        if cur_type is None or not cur_type:
            return
        v_section, v_body = cur_type

        if c_body in self.REPLACEMENT_MAP:
            body = self.REPLACEMENT_MAP[c_body]
            section = c_section
        else:
            body = v_body
            section = v_section

        # Custom convert '#define VK_HEADER_VERSION 272'
        # to 'pub const VK_HEADER_VERSION = 272'
        # in order to keep the number independent.
        text_starts_with = '// Version of this file\n#define VK_HEADER_VERSION '
        if c_body.startswith(text_starts_with):
            if text_starts_with in self.REPLACEMENT_MAP:
                body = self.REPLACEMENT_MAP[text_starts_with] + c_body.replace(text_starts_with, '')

        self.appendSection(section, body)

    def genCType(self, typeinfo, name, alias) -> (str, str):
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
            # self.genStruct(typeinfo, name, alias)
            return self.genStruct(typeinfo, name, alias)
        else:
            if self.genOpts is None:
                raise MissingGeneratorOptionsError()
            # OpenXR: this section was not under 'else:' previously, just fell through
            if alias:
                # If the type is an alias, just emit a typedef declaration
                body = 'typedef ' + alias + ' ' + name + ';\n'
            else:
                # Replace <apientry /> tags with an APIENTRY-style string
                # (from self.genOpts). Copy other text through unchanged.
                # If the resulting text is an empty string, do not emit it.
                body = noneStr(typeElem.text)
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
                # self.appendSection(section, body)
                return section, body

    def genVType(self, typeinfo, name, alias) -> (str, str):
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
            # self.genStruct(typeinfo, name, alias)
            return self.genStruct(typeinfo, name, alias)
        else:
            if self.genOpts is None:
                raise MissingGeneratorOptionsError()
            v_name = ''
            v_value = name
            v_text = ''  # something like 'const' or 'type'
            v_type = ''
            v_is_handle = False
            v_is_function_pointer = name.startswith('PFN_')
            # Array of tuples of function parameters [('name', 'type')]
            v_params = []
            # body = ''
            body = noneStr(typeElem.text)
            # OpenXR: this section was not under 'else:' previously, just fell through
            if alias:
                # If the type is an alias, make sure to not alias an alias
                alias = self.v_translate_alias_to_basetype(name, alias)

                # NOTE Anton: Removing Vk... from variable names, as they are all in the vulkan name space already
                name = self.removeVk(name)
                body = 'pub type ' + name + ' = ' + alias + '\n'
            else:
                # Replace <apientry /> tags with an APIENTRY-style string
                # (from self.genOpts). Copy other text through unchanged.
                # If the resulting text is an empty string, do not emit it.
                # body = noneStr(typeElem.text)

                for elem in typeElem:
                    if elem.tag == 'apientry':
                        body += self.genOpts.apientry + noneStr(elem.tail)
                    elif elem.tag == 'type':
                        #NOTE Anton: v_type is not needed for empty C structs, but keep the logic for now
                        if noneStr(elem.text) == 'VK_DEFINE_HANDLE':
                            # self.C_STRUCT_ARR.append(name)
                            v_type = '&{}'.format('C.' + name)
                            v_is_handle = True
                        elif noneStr(elem.text) == 'VK_DEFINE_NON_DISPATCHABLE_HANDLE':
                            # TODO: 64 bit pointer?
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
                                          # We don't have const in the same sense in Vlang
                                          .replace('\nconst', '')
                                          .strip()
                                          )

                            if v_type in self.TYPE_MAP:
                                v_type = self.TYPE_MAP[v_type]

                            # NOTE Anton: Removing Vk... from variable names, as they are all in the vulkan name space already
                            v_type = self.removeVk(v_type)

                            if 'PFN_' in name and '*' in body:
                                #v_type = 'voidptr'
                                v_params[0] = (v_params[0][0], 'voidptr')

                            if '*' in param_name:
                                # NOTE Anton: Removing const, as it just signals that the pointer won't be changed by vulkan
                                param_name = param_name.replace('*', '').replace('const', '').strip()
                                # if v_type in self.TYPE_MAP:
                                #     v_type = '&' + self.TYPE_MAP[v_type]
                                if v_type in self.C_STRUCT_ARR:
                                    v_type = '&C.' + v_type
                                else:
                                    v_type = '&'+v_type
                                # In case of 'void*', v_type will be just '&', as void was replaced with empty string by TYPE_MAP
                                if v_type == '&':
                                    v_type = 'voidptr'
                            elif v_type in self.C_STRUCT_ARR:
                                v_type = 'C.' + v_type

                            # NOTE Anton: Removing Vk... from variable names, as they are all in the vulkan name space already
                            v_type = self.removeVk(v_type)
                            v_name = self.removeVk(v_name)
                            param_name = self.removeVk(param_name)

                            # Name and type are appended to v_params in separate runs of the for loop,
                            # but always in order, so that we can simply assume the last tuple contains
                            # the current v_name
                            if v_is_function_pointer and len(v_params) > 0:
                                last_tuple = v_params[len(v_params) - 1]
                                # if last_tuple[0] is not None and last_tuple[1] is not None:
                                #     v_params.append((param_name, v_type))
                                if last_tuple[0] is not None and last_tuple[1] is not None:
                                    v_params.append((param_name, v_type))
                                else:
                                    v_params[len(v_params) - 1] = (last_tuple[0], v_type)
                            else:
                                v_params.append((param_name, v_type))
                        v_text = 'type'
                    elif elem.tag == 'name':
                        # v_name = noneStr(elem.text) + noneStr(elem.tail).replace(';', '').replace(')', '')
                        v_name = name
                        v_name = self.removeVk(v_name)
                        if v_is_handle:
                            self.C_STRUCT_ARR.append(v_name)
                            v_name = 'C.' + v_name
                            #v_name = v_name
                        if v_is_function_pointer and len(v_params) > 0:
                            last_tuple = v_params[len(v_params) - 1]
                            if last_tuple[0] is not None and last_tuple[1] is not None:
                                v_params.append((v_name, ''))
                            else:
                                v_params[len(v_params) - 1] = (v_name, last_tuple[1])
                        else:
                            v_params.append((v_name, ''))
                        v_text = 'type'
                    else:
                        # NOTE Anton: This is never reached
                        # body += noneStr(elem.text) + noneStr(elem.tail)
                        v_value = noneStr(elem.text) + noneStr(elem.tail).replace(';', '')
                        v_text = 'const'
                # if category == 'define' and self.misracppstyle():
                #     body = body.replace("(uint32_t)", "static_cast<uint32_t>")

            # NOTE Anton: V doesn't allow for upper case function names and const variables
            # Lowers 'pub type VK_HEADER_VERSION' and 'pub type VkBool32'
            # if not v_is_handle:
            #     v_name = v_name.lower()

            # NOTE Anton: Removing Vk... from variable names, as they are all in the vulkan name space already
            v_type = self.removeVk(v_type)
            v_name = self.removeVk(v_name)
            v_value = self.removeVk(v_value)


            # Vlang doesn't allow for non basetype (u32, u64) aliases,
            # so add the current type alias to BASE_TYPE_MAP
            if v_text == 'type' and v_type in self.BASE_TYPES_ARR:
                self.ALIAS_TO_BASE_TYPE_MAP[v_name] = v_type

            if v_is_handle:
                body = 'pub type {} = voidptr'.format(v_name)
                # placeholder = 0
            elif v_is_function_pointer:
                v_params_str = ''
                is_first_iteration = True
                for param in v_params:
                    # The name, type at 0 are function name and return type
                    if is_first_iteration:
                        is_first_iteration = False
                        continue
                    v_params_str += '\n  {} {},'.format(param[0].ljust(33), param[1])
                # Remove tailing ','
                v_params_str = v_params_str[:-1]
                body = 'pub type {} = fn ({}) {}'.format(v_name, v_params_str, v_params[0][1])
                # NOTE Anton: Vlang bug where fn type definitons can't be multiple lines
                # TODO: Create an issue on Vlang github
                body = ' '.join(body.split('\n'))
            elif v_text and v_name and v_type:
                # Vlang doesn't allow for non basetype (u32, u64) aliases,
                # so find the root basetype and assign that instead of alias
                if v_type in self.BASE_TYPES_ARR:
                    self.ALIAS_TO_BASE_TYPE_MAP[v_name] = v_type
                else:
                    if v_type in self.ALIAS_TO_BASE_TYPE_MAP:
                        v_type = self.ALIAS_TO_BASE_TYPE_MAP[v_type]
                        self.ALIAS_TO_BASE_TYPE_MAP[name] = v_type

                body = 'pub {} {} = {}'.format(v_text, v_name, v_type)
            elif v_value and v_text and not category == 'basetype':
                # TODO: Handle ANativeWindow and other basetypes. For now just ignore with 'not basetype'
                body = 'pub {} {} = {}'.format(v_text, v_value, v_name)
            else:
                print('Omitting body:\n' + body + '\n')
                return

            if '\n' in body[0:-1]:
                body += '\n'

            if body:
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

        # NOTE Anton: code path never reached; test with a graphics API or OS platform
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

    def genStruct(self, typeinfo, typeName, alias) -> (str, str):
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
        # NOTE Anton: Removing Vk... from variable names, as they are all in the vulkan name space already
        typeName = self.removeVk(typeName)

        if alias:
            alias = self.v_translate_alias_to_basetype(typeName, alias)
            body = 'pub type ' + typeName + ' = ' + alias + '\n'
        else:
            body = ''
            (protect_begin, protect_end) = self.genProtectString(typeElem.get('protect'))
            if protect_begin:
                body += protect_begin

            if self.genOpts.genStructExtendsComment:
                structextends = typeElem.get('structextends')
                body += '// ' + typeName + ' extends ' + structextends + '\n' if structextends else ''

            cur_category = typeElem.get('category')
            if cur_category == 'struct':
                body += 'pub struct '
            else:
                body += 'pub union '
            # else:
            #     body += 'pub type ' + typeName + ' = ' + alias + '\n'

            # This is an OpenXR-specific alternative where aliasing refers
            # to an inheritance hierarchy of types rather than C-level type
            # aliases.
            if self.genOpts.genAliasMacro and self.typeMayAlias(typeName):
                body += ' ' + self.genOpts.aliasMacro

            if cur_category == 'struct' or cur_category == 'union':
                body += typeName + ' {\n'

            targetLen = self.getMaxVParamNameLength(typeinfo)
            body += 'pub mut:\n'
            for member in typeElem.findall('.//member'):
                body += self.makeVParamDecl(member, targetLen + 4)
                body += '\n'
            body += '} ' + '\n'
            if protect_end:
                body += protect_end

        return 'struct', body

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

        # NOTE Anton: Removing Vk... from variable names, as they are all in the vulkan name space already
        groupName = self.removeVk(groupName)

        # NOTE Anton: In order to Replace C code instead of V code with REPLACEMENT_MAP,
        # we need to generate C code
        # Same is done in genCmd, genEnum, genGroup, genStruct, genType
        if alias:
            cbody = 'typedef ' + alias + ' ' + groupName + ';\n'
            if cbody in self.REPLACEMENT_MAP:
                cbody = self.REPLACEMENT_MAP[cbody]
                self.appendSection(section, cbody)
            else:
                alias = self.v_translate_alias_to_basetype(groupName, alias)

                body = 'pub type ' + groupName + ' = ' + alias + '\n'
                self.appendSection(section, body)
        else:
            if self.genOpts is None:
                raise MissingGeneratorOptionsError()

            (section, body) = self.buildEnumVDecl(self.genOpts.genEnumBeginEndRange, groupinfo, groupName)
            self.appendSection(section, '\n' + body)

    def genEnum(self, enuminfo, name, alias):
        """Generate the C declaration for a constant (a single <enum> value).

        <enum> tags may specify their values in several ways, but are usually
        just integers."""

        OutputGenerator.genEnum(self, enuminfo, name, alias)

        body = self.buildConstantVDecl(enuminfo, name, alias)
        self.appendSection('enum', body)

    def buildConstantVDecl(self, enuminfo, name, alias):
        """Generate the C declaration for a constant (a single <enum>
        value).

        <enum> tags may specify their values in several ways, but are
        usually just integers or floating-point numbers."""

        (_, strVal) = self.enumToValue(enuminfo.elem, False)

        # if self.misracppstyle() and enuminfo.elem.get('type') and not alias:
        #     # Generate e.g.: static constexpr uint32_t x = ~static_cast<uint32_t>(1U);
        #     # This appeases MISRA "underlying type" rules.
        #     typeStr = enuminfo.elem.get('type');
        #     invert = '~' in strVal
        #     number = strVal.strip("()~UL")
        #     if typeStr != "float":
        #         number += 'U'
        #     strVal = "~" if invert else ""
        #     strVal += "static_cast<" + typeStr + ">(" + number + ")"
        #     body = 'static constexpr ' + typeStr.ljust(9) + name.ljust(33) + ' {' + strVal + '};'
        # elif enuminfo.elem.get('type') and not alias:
        #     # Generate e.g.: #define x (~0ULL)
        #     typeStr = enuminfo.elem.get('type');
        #     invert = '~' in strVal
        #     paren = '(' in strVal
        #     number = strVal.strip("()~UL")
        #     if typeStr != "float":
        #         if typeStr == "uint64_t":
        #             number += 'ULL'
        #         else:
        #             number += 'U'
        #     strVal = "~" if invert else ""
        #     strVal += number
        #     if paren:
        #         strVal = "(" + strVal + ")";
        #     # body = '#define ' + name.ljust(33) + ' ' + strVal;
        #     body = 'const ' + name.ljust(33) + ' = ' + strVal;
        # else:
        #     # body = '#define ' + name.ljust(33) + ' ' + strVal
        #     body = 'const ' + name.ljust(33) + ' = ' + strVal

        # Generate e.g.: const x = u32()
        prefix = ''
        v_type = ''
        v_name = name

        # Only replace U,L,... in types like (~0ULL), not in names like 'vk_google_hlsl_functionality_1_extension_name'
        if strVal.lower().startswith('vk'):
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
                print("Couldn't find matching V type for " + typeStr)
            if '~' in strVal:
                prefix = '~'
        # NOTE Anton: V doesn't allow for upper case function names and const variables
        # Remove .lower() once upper case is supported
        # NOTE Anton: Some typos in the source vk.xml, so we just fix them here
        if v_name in self.FIX_TYPOS_MAP:
            v_name = self.FIX_TYPOS_MAP[v_name]
        if v_value in self.FIX_TYPOS_MAP:
            v_value = self.FIX_TYPOS_MAP[v_value]

        # v_name = self.CAMEL_TO_SNAKE_CASE_REGEX.sub('_', v_name).lower().strip()
        # v_value = self.CAMEL_TO_SNAKE_CASE_REGEX.sub('_', v_value).lower()
        v_name = v_name.lower().strip()

        # Don't .lower() the value for exact strings, like
        # pub const vk_khr_maintenance_1_extension_name = "VK_KHR_maintenance1"
        # But .lower() the value for references to vk_khr_external_memory_capabilities_extension_name, like
        # pub const vk_khr_maintenance1_extension_name = vk_khr_maintenance_1_extension_name
        if not v_name.lower().endswith("_extension_name") or not v_value.startswith('"'):
            v_value = v_value.lower()

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
        # NOTE Anton: Removing functions behind VK_NO_PROTOTYPES (checked by alias exists, I guess),
        # as their symbols aren't found in graphics card drivers for dynamic linking.
        # TODO: Can be removed when Vlang supports $ compile time code on root/module level
        # https://github.com/vlang/v/issues/20420
        # TODO: Find out how to check for functions guarded by 'VK_NO_PROTOTYPES' without a static list
        #if alias is not None or name in ['vkGetRayTracingCaptureReplayShaderGroupHandlesKHR', 'vkCmdTraceRaysIndirectKHR', 'vkGetRayTracingShaderGroupStackSizeKHR', 'vkCmdSetRayTracingPipelineStackSizeKHR', 'vkCmdDrawMeshTasksEXT', 'vkCmdDrawMeshTasksIndirectEXT', 'vkCmdDrawMeshTasksIndirectCountEXT']:
        #    return

        OutputGenerator.genCmd(self, cmdinfo, name, alias)

        # if alias:
        #     prefix = '// ' + name + ' is an alias of command ' + alias + '\n'
        # else:
        #     prefix = ''
        if self.genOpts is None:
            raise MissingGeneratorOptionsError()

        prefix = ''

        decls = self.makeVDecls(cmdinfo.elem)
        self.appendSection('command', prefix + decls[0] + '\n')

        if self.genOpts.genFuncPointers:
            self.appendSection('commandPointer', decls[1])

    def misracstyle(self):
        return self.genOpts.misracstyle;

    def misracppstyle(self):
        return self.genOpts.misracppstyle;

    # Vlang doesn't allow for non basetype (u32, u64) aliases,
    # so find the root basetype and assign that instead.
    # Returns basetype if found, the unchanged alias if not found
    def v_translate_alias_to_basetype(self, name, alias) -> str:
        # NOTE Anton: Removing Vk... from variable names, as they are all in the vulkan name space already
        alias = self.removeVk(alias)
        name = self.removeVk(name)

        if alias in self.BASE_TYPES_ARR:
            self.ALIAS_TO_BASE_TYPE_MAP[name] = alias
        else:
            if alias in self.ALIAS_TO_BASE_TYPE_MAP:
                alias = self.ALIAS_TO_BASE_TYPE_MAP[alias]
                self.ALIAS_TO_BASE_TYPE_MAP[name] = alias

        return alias

    def v_camel_to_snake_case(self, v_name) -> str:
        return self.CAMEL_TO_SNAKE_CASE_REGEX.sub(r'_\1', v_name).lower()

    def makeVParamDecl(self, param, aligncol, only_types=False, only_names=False):
        """Return a string which is an indented, formatted
        declaration for a `<param>` or `<member>` block (e.g. function parameter
        or structure/union member).

        - param - Element (`<param>` or `<member>`) to format
        - aligncol - if non-zero, attempt to align the nested `<type>` element
          at this column"""
        if self.genOpts is None:
            raise MissingGeneratorOptionsError()
        if self.genOpts.conventions is None:
            raise MissingGeneratorOptionsConventionsError()
        indent = '    '
        # paramdecl = indent
        prefix = noneStr(param.text)
        v_type = ''
        v_name = ''

        for elem in param:
            text = noneStr(elem.text)
            tail = noneStr(elem.tail)
            text_plus_tail = text + tail.strip()

            if elem.tag == 'type':
                # Translate C type to V type
                if text_plus_tail in self.TYPE_MAP:
                    v_type = self.TYPE_MAP[text_plus_tail]
                else:
                    # if type is not mapped to V, it's mostly something like 'VkDeviceQueueCreateInfo*',
                    # so just replace * with & and move it to the left
                    v_type = text_plus_tail
                    # NOTE Anton: Removing Vk... from variable names, as they are all in the vulkan name space already
                    v_type = self.removeVk(v_type)

                    if '*' in v_type:
                        #NOTE Anton: Removing const, as it just signals that the pointer won't be changed by vulkan
                        v_type_without_pointer = v_type.replace('*', '').replace('const', '').strip()
                        if v_type_without_pointer in self.TYPE_MAP:
                            v_type = '&' + self.TYPE_MAP[v_type_without_pointer]
                            # In case of 'void*', v_type will be just '&', as void was replaced with empty string by TYPE_MAP
                            if v_type == '&':
                                v_type = 'voidptr'
                        elif v_type_without_pointer in self.C_STRUCT_ARR:
                            v_type = '&C.' + v_type_without_pointer
                        else:
                            v_type = '&' + v_type_without_pointer
                    elif v_type in self.C_STRUCT_ARR:
                        v_type = 'C.' + v_type
                    # In struct members function pointers get an "?" to make them nullable
                    elif v_type.lower().startswith("pfn_"):
                        # v_type = "?" + v_type
                        v_type = v_type + ' = unsafe { nil }'
            elif elem.tag == 'enum':
                v_name = v_name + text_plus_tail
                # v_name = self.removeVk(v_name)
            else:
                v_name = prefix + text_plus_tail
                # NOTE Anton: Removing Vk... from variable names, as they are all in the vulkan name space already
                v_name = self.removeVk(v_name)

            if self.should_insert_may_alias_macro and self.genOpts.conventions.is_voidpointer_alias(elem.tag, text,
                                                                                                    tail):
                # OpenXR-specific macro insertion - but not in apiinc for the spec
                tail = self.genOpts.conventions.make_voidpointer_alias(tail)

            # Clear prefix for subsequent iterations
            prefix = ''

        # paramdecl = paramdecl + prefix
        array_match = self.ARRAY_REGEX.match(v_name)
        if array_match:
            v_name = v_name.replace(array_match.group(1), '')
            # NOTE Anton: Remove lower() once Vlang allows for upper case members
            # https://github.com/vlang/v/issues/20420
            v_type = '[' + self.removeVk(array_match.group(1).lower().replace('[', '').replace(']', '')) + ']' + v_type
            #v_type = array_match.group(1).lower() + v_type
            # NOTE Anton: Vlang doesn't allow function parameters with static array length, like [2]SomeEnum,
            # instead we write []SomeEnum
            ##v_type = '[]{}'.format(v_type)

        # NOTE Anton: V doesn't allow for upper case function names and const variables
        # v_name = v_name.lower()
        # NOTE Anton: 'module' and 'type' are reserved keywords in V
        if v_name == 'module':
            v_name = 'vkmodule'
        if v_name == 'type':
            v_name = 'vktype'

        # Note Anton: C supports custom types like 'uint32_t instanceCustomIndex:24;'
        # We just remove the number of bits, as these types all fit into u32
        if ':' in v_name:
            v_name = v_name.split(':')[0]

        # Note Anton: Remove lower() once Vlang allows for upper case members
        # https://github.com/vlang/v/issues/20420
        v_name = self.v_camel_to_snake_case(v_name)
        if only_types:
            paramdecl = indent + v_type
        elif only_names:
            paramdecl = indent + v_name
        else:
            paramdecl = indent + v_name.ljust(aligncol - 1) + ' ' + v_type

        # if aligncol == 0:
        #     # Squeeze out multiple spaces other than the indentation
        #     paramdecl = indent + ' '.join(paramdecl.split())
        return paramdecl

    def getVParamNameLength(self, param):
        """Return the length of the type field is an indented, formatted
        declaration for a `<param>` or `<member>` block (e.g. function parameter
        or structure/union member).

        - param - Element (`<param>` or `<member>`) to identify"""
        if self.genOpts is None:
            raise MissingGeneratorOptionsError()
        if self.genOpts.conventions is None:
            raise MissingGeneratorOptionsConventionsError()

        # Allow for missing <name> tag
        newLen = 0
        paramdecl = '    ' + noneStr(param.text)
        # paramdecl = noneStr(param.text) + '    '
        for elem in param:
            text = noneStr(elem.text)
            tail = noneStr(elem.tail)

            if self.should_insert_may_alias_macro and self.genOpts.conventions.is_voidpointer_alias(elem.tag, text,
                                                                                                    tail):
                # OpenXR-specific macro insertion
                tail = self.genOpts.conventions.make_voidpointer_alias(tail)
            if elem.tag == 'name':
                # Align at specified column, if possible
                newLen = len(paramdecl.rstrip())
                self.logMsg('diag', 'Identifying length of', elem.text, 'as', newLen)
            paramdecl += text + tail

        return newLen

    def getMaxVParamNameLength(self, info):
        """Return the length of the longest type field for a member/parameter.

        - info - TypeInfo or CommandInfo.
        """
        lengths = (self.getVParamNameLength(member)
                   for member in info.getMembers())
        return max(lengths)

    def buildEnumVDecl(self, expand, groupinfo, groupName):
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
            except ValueError as ve:
                self.logMsg('error', 'Invalid value for bitwidth attribute (', groupElem.get('bitwidth'), ') for ',
                            groupName, ' - must be an integer value\n')
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

        # Used to store all options, as in `$if option ? {`
        # '' is for enums without a protect option
        protect_options = [None]
        enums = groupinfo.elem.findall('enum')
        for elem in enums:
            protect = elem.get('protect')
            if protect is not None:
                if protect not in protect_options:
                    protect_options.append(protect)

        protect_options_used = len(protect_options) > 1
        # TODO: Can be removed when Vlang supports $ compile time code on root/module level
        # https://github.com/vlang/v/issues/20420
        # remove this, so that all protect options are processed
        protect_options_used = False

        if usedefine or usebitmask:
            # Validate the bitwidth and generate values appropriately
            if bitwidth > 64:
                self.logMsg('error', 'Invalid value for bitwidth attribute (', groupElem.get('bitwidth'),
                            ') for bitmask type ', groupName, ' - must be less than or equal to 64\n')
                exit(1)
            else:
                body = ''
                section = ''
                first_iteration = True
                # Iterate over reversed to process without protection last
                # and append '$else' instead of '$else $if'
                for protect_option in reversed(protect_options):
                    # TODO: Can be removed when Vlang supports $ compile time code on root/module level
                    # https://github.com/vlang/v/issues/20420
                    # remove this check, so that all protect options are processed
                    if protect_option is not None:
                        continue

                    if first_iteration and protect_option is not None:
                        body += '$if {} ? {{\n'.format(protect_option)
                    elif protect_option is None and protect_options_used:
                        body += '$else {\n'
                    else:
                        if protect_options_used:
                            body += '$else $if {} ? {{\n'.format(protect_option)
                    (cur_section, cur_body) = self.buildEnumVDecl_BitmaskOrDefine(groupinfo, groupName, bitwidth,
                                                                                  usedefine, protect_option)
                    body += cur_body + '\n'
                    if protect_options_used:
                        body += '}\n'
                    # NOTE Anton: Assuming there aren't multiple sections per '$if option ? {'
                    section = cur_section
                    first_iteration = False
                return section, body

        else:
            # Validate the bitwidth and generate values appropriately
            if bitwidth > 32:
                self.logMsg('error', 'Invalid value for bitwidth attribute (', groupElem.get('bitwidth'),
                            ') for enum type ', groupName, ' - must be less than or equal to 32\n')
                exit(1)
            else:
                body = ''
                section = ''
                first_iteration = True
                # Iterate over reversed to process without protection last
                # and append '$else' instead of '$else $if'
                for protect_option in reversed(protect_options):
                    # TODO: Can be removed when Vlang supports $ compile time code on root/module level
                    # https://github.com/vlang/v/issues/20420
                    # remove this check, so that all protect options are processed
                    if protect_option is not None:
                        continue

                    if first_iteration and protect_option is not None:
                        body += '$if {} ? {{\n'.format(protect_option)
                    elif protect_option is None and protect_options_used:
                        body += '$else {\n'
                    else:
                        if protect_options_used:
                            body += '$else $if {} ? {{\n'.format(protect_option)
                    (cur_section, cur_body) = self.buildEnumVDecl_Enum(expand, groupinfo, groupName, protect_option)
                    body += cur_body + '\n'
                    if protect_options_used:
                        body += '}\n'
                    # NOTE Anton: Assuming there aren't multiple sections per '$if option ? {'
                    section = cur_section
                return section, body

    def buildEnumVDecl_BitmaskOrDefine(self, groupinfo, groupName, bitwidth, usedefine, protect_option):
        """Generate the C declaration for an "enum" that is actually a
        set of flag bits"""
        groupElem = groupinfo.elem
        flagTypeName = groupElem.get('name')

        # NOTE Anton: Removing Vk... from variable names, as they are all in the vulkan name space already
        flagTypeName = self.removeVk(flagTypeName)

        # Prefix
        body = "// Flag bits for " + flagTypeName + "\n"

        # if bitwidth == 64:
        #     body += "typedef VkFlags64 %s;\n" % flagTypeName;
        # else:
        #     body += "typedef VkFlags %s;\n" % flagTypeName;
        if bitwidth == 64:
            body += "pub type %s = u64\n" % flagTypeName
            # Vlang doesn't allow for non basetype (u32, u64) aliases,
            # so add the current type alias to BASE_TYPE_MAP
            self.ALIAS_TO_BASE_TYPE_MAP[flagTypeName] = 'u64'
        else:
            body += "pub type %s = u32\n" % flagTypeName
            self.ALIAS_TO_BASE_TYPE_MAP[flagTypeName] = 'u32'

        # Maximum allowable value for a flag (unsigned 64-bit integer)
        maxValidValue = 2 ** (64) - 1
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
                # pub const VK_PIPELINE_STAGE_2_RAY_TRACING_SHADER_BIT_NV VkPipelineStageFlagBits2 = VK_PIPEINE_STAGE_2_RAY_TRACING_SHADER_BIT_KHR
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
                self.logMsg('error', 'Allowable range for flag types in C is [', minValidValue, ',', maxValidValue,
                            '], but', name, 'flag has a value outside of this (', strVal, ')\n')
                exit(1)

            decl = self.genRequirements(name, mustBeFound=False)

            if self.isEnumRequired(elem):
                protect = elem.get('protect')
                if protect is not None and protect != protect_option:
                    continue

                # usedefine = False, self.misracstyle() = False
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
                    #v_name = self.CAMEL_TO_SNAKE_CASE_REGEX.sub('_', v_name).lower()
                    v_name = v_name.lower()
                    # NOTE Anton: Removing Vk... from variable names, as they are all in the vulkan name space already
                    v_value = self.removeVk(v_value)
                    v_name = self.removeVk(v_name)
                    v_type = self.removeVk(v_type)

                    v_value = v_value.lower()

                    # decl += "static const {} {} = {};\n".format(flagTypeName, name, strVal)
                    if couldnt_convert_strVal:
                        # decl += "pub const {} {} = {}\n".format(v_name, flagTypeName, prefix + v_type + v_value)
                        val_concat = prefix + v_type #+ v_value
                        # TODO typos fixes in val_concat with some replacement map
                        # NOTE Anton: remove .lower() once Vlang supports upper case names
                        #val_concat = self.CAMEL_TO_SNAKE_CASE_REGEX.sub('_', val_concat).lower()
                        val_concat = val_concat.lower()

                        decl += "pub const {} = {}\n".format(v_name, val_concat)
                    else:
                        if v_value.lower().startswith("vk"):
                            decl += "pub const {} = {}\n".format(v_name, v_value)
                        else:
                            decl += "pub const {} = {}\n".format(v_name, prefix + v_type + '(' + v_value + ')')

                if numVal is not None:
                    body += decl
                else:
                    aliasText += decl

            # if protect_option is not None:
            #     # body += '#endif\n'
            #     body += '}\n'

        # Now append the non-numeric enumerant values
        # TODO: Double check if pub const can be aliased
        body += aliasText

        # Postfix

        return ("bitmask", body)

    def buildEnumVDecl_Enum(self, expand, groupinfo, groupName, protect_option):
        """Generate the V declaration for an enumerated type"""
        groupElem = groupinfo.elem

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

        # Prefix
        # body = ["typedef enum %s {" % groupName]
        # NOTE Anton: Removing Vk... from variable names, as they are all in the vulkan name space already
        if groupName.lower().startswith('vk') and not groupName[2:].lower() in ['true', 'false']:
            groupName = groupName[2:]

        body = ["pub enum %s {" % groupName]

        # @@ Should use the type="bitmask" attribute instead
        isEnum = ('FLAG_BITS' not in expandPrefix)

        # Allowable range for a C enum - which is that of a signed 32-bit integer
        maxValidValue = 2 ** (32 - 1) - 1
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
            # Note Anton: V doesn't allow for upper case enum member names
            # name = self.CAMEL_TO_SNAKE_CASE_REGEX.sub('_', name).lower()
            name = name.lower()
            # NOTE Anton: Removing Vk... from variable names, as they are all in the vulkan name space already
            # if name.lower().startswith('vk_') and not name[3:].lower() in ['true', 'false']:
            #     name = name[3:]
            name = self.removeVk(name)

            # Extension enumerants are only included if they are required
            if self.isEnumRequired(elem):
                decl = ''

                protect = elem.get('protect')
                if protect is not None and protect != protect_option:
                    continue

                # Indent requirements comment, if there is one
                requirements = self.genRequirements(name, mustBeFound=False)
                if requirements != '':
                    requirements = '  ' + requirements
                decl += requirements
                # decl += '    {} = {},'.format(name, strVal)
                decl += '    {} = int({})'.format(name, strVal)

                if numVal is not None:
                    body.append(decl)
                else:
                    aliasText.append(decl)

            # Range check for the enum value
            if numVal is not None and (numVal > maxValidValue or numVal < minValidValue):
                self.logMsg('error', 'Allowable range for C enum types is [', minValidValue, ',', maxValidValue,
                            '], but', name, 'has a value outside of this (', strVal, ')\n')
                exit(1)

            # Do not track min/max for non-numbers (numVal is None)
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

        # Now append the non-numeric enumerant values
        # Now don't do that for V
        # body.extend(aliasText)

        # Generate min/max value tokens - legacy use case.
        if isEnum and expand:
            body.extend((f'    {expandPrefix}_BEGIN_RANGE{expandSuffix} = {minName},',
                         f'    {expandPrefix}_END_RANGE{expandSuffix} = {maxName},',
                         f'    {expandPrefix}_RANGE_SIZE{expandSuffix} = ({maxName} - {minName} + 1),'))

        # Generate a range-padding value to ensure the enum is 32 bits, but
        # only in code generators, so it does not appear in documentation
        if (self.genOpts.codeGenerator or
            self.conventions.generate_max_enum_in_docs):
            # body.append(f'    {expandPrefix}_MAX_ENUM{expandSuffix} = 0x7FFFFFFF')
            # Note Anton: V doesn't allow for upper case enum member names
            # expandPrefix = self.CAMEL_TO_SNAKE_CASE_REGEX.sub('_', expandPrefix).lower()
            # expandSuffix = self.CAMEL_TO_SNAKE_CASE_REGEX.sub('_', expandSuffix).lower()
            expandPrefix = expandPrefix.lower()
            # NOTE Anton: Removing Vk... from variable names, as they are all in the vulkan name space already
            # if expandPrefix.startswith('vk_') and not expandPrefix[3:].lower() in ['true', 'false']:
            #     expandPrefix = expandPrefix[3:]
            expandPrefix = self.removeVk(expandPrefix)

            expandSuffix = expandSuffix.lower()
            body.append(f'    {expandPrefix}_max_enum{expandSuffix} = int(0x7FFFFFFF)')

        # Postfix
        # body.append("} %s;" % groupName)
        body.append("}")

        # Determine appropriate section for this declaration
        if groupElem.get('type') == 'bitmask':
            section = 'bitmask'
        else:
            section = 'group'

        return (section, '\n'.join(body))

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
        # tdecl = 'typedef '
        tdecl = 'type '
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
        # declaration. Otherwise, append its contents and tail contents.
        for elem in proto:
            text = noneStr(elem.text)
            tail = noneStr(elem.tail)
            text_plus_tail = text + tail.strip()

            # if elem.tag == 'name':
            #     pdecl += self.makeVProtoName(text, tail)
            #     tdecl += self.makeVTypedefName(text, tail)
            # else:
            #     pdecl += text + tail
            #     tdecl += text + tail
            if elem.tag == 'type':
                # Translate C type to V type
                v_type = text_plus_tail
                if v_type in self.TYPE_MAP:
                    v_type = self.TYPE_MAP[v_type]
                else:
                    # NOTE Anton: Removing Vk... from variable names, as they are all in the vulkan name space already
                    # if v_type.lower().startswith('vk') and not v_type[2:].lower() in ['true', 'false']:
                    #     v_type = v_type[2:]
                    v_type = self.removeVk(v_type)

                    # if type is not mapped to V, it's mostly something like 'VkDeviceQueueCreateInfo*',
                    # so just replace * with & and move it to the left
                    if '*' in v_type:
                        v_type_non_pointer = v_type.replace('*', '')
                        if v_type_non_pointer in self.TYPE_MAP:
                            v_type = '&' + self.TYPE_MAP[v_type_non_pointer]
                        elif v_type_non_pointer in self.C_STRUCT_ARR:
                            v_type = '&C.' + v_type_non_pointer
                        else:
                            v_type = '&' + v_type_non_pointer
                    elif v_type in self.C_STRUCT_ARR:
                        v_type = 'C.' + v_type

            else:
                v_name = text_plus_tail

        array_match = self.ARRAY_REGEX.match(v_name)
        if array_match:
            v_name = v_name.replace(array_match.group(1), '')
            #v_type = array_match.group(1) + v_type
            v_type = '[' + self.removeVk(array_match.group(1).lower().replace('[', '').replace(']', '')) + ']' + v_type
            # NOTE Anton: Vlang doesn't allow function parameters with static array length, like [2]SomeEnum,
            # instead we write []SomeEnum
            ##v_type = '[]{}'.format(v_type)


        # NOTE Anton: V doesn't allow for upper case function names and const variables
        # v_name = self.CAMEL_TO_SNAKE_CASE_REGEX.sub('_', v_name).lower()
        v_name_original = v_name
        v_name_upper_case = v_name[0].upper()+v_name[1:]
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
        # Indented parameters
        indentdecl = ''
        if n > 0:
            indentdecl = '(\n'
            indentdecl += ',\n'.join(self.makeVParamDecl(p, self.genOpts.alignFuncParam, True)
                                     for p in params)
            # indentdecl += ');'
            indentdecl += ')'
        else:
            # indentdecl = '(void);'
            indentdecl = '()'
        # # Non-indented parameters
        paramdecl = '('  # TODO: remove paramdecl, as it's not used for V

        # Generate V wrapper function and append
        v_wrapper = 'pub fn '
        # NOTE Anton: Removing Vk... from user space functions, as they will be called like
        # vulkan.some_function anyway
        v_name_no_vk = self.removeVk(v_name)
        v_wrapper += v_name_no_vk
        if n > 0:
            v_function_params = '(\n'
            v_function_params += ',\n'.join(self.makeVParamDecl(p, self.genOpts.alignFuncParam, False)
                                            for p in params)
            v_function_params += ')'
        else:
            v_function_params = '()'
        v_wrapper += v_function_params + ' ' + v_type + " {\n"
        # TODO: Write fn body
        v_type_stripped = v_type.strip()
        v_function_param_names = ""
        if n > 0:
            v_function_param_names = '(\n'
            v_function_param_names += ',\n'.join(self.makeVParamDecl(p, self.genOpts.alignFuncParam, False, True)
                                            for p in params)
            v_function_param_names += ')'
        else:
            v_function_param_names = '()'


        #loader_str = '{}(dl_loader.get_sym("{}") or { println("Couldn\'t load sym for {}: ${err}") return })'.format(v_name_upper_case, v_name_upper_case, v_name_upper_case)
        loader_str = ''

        #loader_str = v_name_upper_case + '(dl_loader.loader.get_sym("' + v_name_upper_case + '"))'

        if v_type_stripped == '':
            # loader_str = 'mut dl_loader := loader.get_or_create_dynamic_lib_loader(\n        key: "vulkan"\n        env_path: ""\n        paths: ["libvulkan.so.1", "vulkan-1.dll"]\n    ) or {\n        println("modules/vulkan/vulkan.v: Couldn\'t get or create dynamic lib loader: ${err}")\n        return\n    }\n    defer { dl_loader.unregister() }\n    f := ' + v_name_upper_case + '(dl_loader.get_sym(\'' + v_name_original + '\'\n    ) or { \n        println("Couldn\'t load sym for \'' + v_name_original + '\': ${err}")\n        return \n    })\n'
            ##loader_str = '  f := ' + v_name_upper_case + '((*loader_p).get_sym(\'' + v_name_original + '\'\n    ) or { \n        println("Couldn\'t load symbol for \'' + v_name_original + '\': ${err}")\n        return \n    })\n'
            ##v_wrapper += '    {}    f{}'.format(loader_str, v_function_param_names)
            v_wrapper += '    C.' + v_name_original + '{}'.format(' '.join(v_function_param_names.split('\n')))
        # elif v_type_stripped == 'VkResult':
        elif v_type_stripped == 'Result':
            # loader_str = 'mut dl_loader := loader.get_or_create_dynamic_lib_loader(\n        key: "vulkan"\n        env_path: ""\n        paths: ["libvulkan.so.1", "vulkan-1.dll"]\n    ) or {\n        println("modules/vulkan/vulkan.v: Couldn\'t get or create dynamic lib loader: ${err}")\n        return Result.error_unknown\n    }\n    defer { dl_loader.unregister() }\n    f := ' + v_name_upper_case + '(dl_loader.get_sym(\'' + v_name_original + '\'\n    ) or { \n        println("Couldn\'t load sym for \'' + v_name_original + '\': ${err}")\n        return Result.error_unknown\n    })\n'
            ##loader_str = '  f := ' + v_name_upper_case + '((*loader_p).get_sym(\'' + v_name_original + '\'\n    ) or { \n        println("Couldn\'t load symbol for \'' + v_name_original + '\': ${err}")\n        return Result.error_unknown\n    })\n'
            ##v_wrapper += '    {}    return f{}'.format(loader_str, v_function_param_names)
            v_wrapper += '    return C.' + v_name_original + '{}'.format(' '.join(v_function_param_names.split('\n')))
        else:
            # loader_str = 'mut dl_loader := loader.get_or_create_dynamic_lib_loader(key: "vulkan"\n        env_path: ""\n        paths: ["libvulkan.so.1", "vulkan-1.dll"]\n    ) or {\n        panic("modules/vulkan/vulkan.v: Couldn\'t get or create dynamic lib loader: ${err}")\n        }\n    defer { dl_loader.unregister() }\n    f := ' + v_name_upper_case + '(dl_loader.get_sym("' + v_name_original + '"\n    ) or { \n        panic("Couldn\'t load sym for \'' + v_name_original + '\': ${err}") })\n'
            ##loader_str = '  f := ' + v_name_upper_case + '((*loader_p).get_sym("' + v_name_original + '"\n    ) or { \n        panic("Couldn\'t load symbol for \'' + v_name_original + '\': ${err}") })\n'
            ##v_wrapper += '    {}    return f{}'.format(loader_str, v_function_param_names)
            v_wrapper += '    return C.' + v_name_original + '{}'.format(' '.join(v_function_param_names.split('\n')))
        v_wrapper += '\n'
        v_wrapper += "}\n"

        # return [pdecl + indentdecl, tdecl + paramdecl]
        return ['fn C.' + v_name_original + indentdecl + ' ' + v_type + '\n' + v_wrapper, tdecl + paramdecl]
        #return ['type {} = fn {} {}\n\n{}'.format(v_name_upper_case, indentdecl, v_type, v_wrapper), tdecl + paramdecl]
        #return ['type {} = fn {} {}\n\n{}'.format(v_name_upper_case, ' '.join(indentdecl.split('\n')), v_type, v_wrapper), tdecl + paramdecl]
        ##return [ 'type {} = fn {} {}\n\n{}'.format(v_name_upper_case, ' '.join(indentdecl.split('\n')), v_type, v_wrapper), tdecl + paramdecl ]
        #return [ 'fn C.{}{}\n    {}\n{}'.format(v_name_original, ' '.join(indentdecl.split('\n')), v_type, v_wrapper), tdecl + paramdecl ]

