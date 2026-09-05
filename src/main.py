#!/usr/bin/env python3
#
# Copyright 2013-2026 The Khronos Group Inc.
#
# SPDX-License-Identifier: Apache-2.0

import argparse
import inspect
import os
import pathlib
import pdb
import re
import sys
import time
import xml.etree.ElementTree as etree

script_path = pathlib.Path(__file__).resolve().parent
vk_script_path = (script_path / '../vulkandocs/scripts').resolve()
sys.path.append(str(vk_script_path))
os.chdir(vk_script_path)

from vgenerator import VGeneratorOptions, VOutputGenerator
from generator import GeneratorOptions
from reflib import logDiag, logErr, setLogFile
from reg import Registry
from apiconventions import APIConventions

startTime = None
errWarn = sys.stderr
diag = None
genOpts = {}


def startTimer(timeit: bool) -> None:
    global startTime
    if timeit:
        startTime = time.process_time()


def endTimer(timeit: bool, msg: str) -> None:
    global startTime
    if timeit and startTime is not None:
        end_time = time.process_time()
        logDiag(msg, end_time - startTime)
        startTime = None


def makeREstring(strings, default=None, strings_are_regex=False):
    """Turn a list of strings into a regexp string matching exactly those strings."""
    if strings or default is None:
        if not strings_are_regex:
            strings = [re.escape(s) for s in strings]
        return f"^({'|'.join(strings)})$"
    return default


def makeGenOpts(args):
    """Build only the V generator targets required by this project."""
    global genOpts
    genOpts = {}

    defaultExtensions = args.defaultExtensions
    extensions = args.extension
    removeExtensions = args.removeExtensions
    emitExtensions = args.emitExtensions
    features = args.feature
    protect = args.protect
    directory = args.directory

    addExtensionsPat = makeREstring(extensions, None)
    removeExtensionsPat = makeREstring(removeExtensions, None)
    emitExtensionsPat = makeREstring(emitExtensions, r'.*')
    featuresPat = makeREstring(features, r'.*')

    prefixStrings = []
    vkPrefixStrings = []
    protectFile = protect
    conventions = APIConventions()

    defaultAPIName = args.apiname if args.apiname is not None else conventions.xml_api_name
    mergeApiNames = args.mergeApiNames

    v_common = dict(
        conventions=conventions,
        directory=directory,
        genpath=None,
        profile=None,
        defaultExtensions=defaultExtensions,
        addExtensions=addExtensionsPat,
        removeExtensions=removeExtensionsPat,
        emitExtensions=emitExtensionsPat,
        prefixText=prefixStrings + vkPrefixStrings,
        genFuncPointers=False,
        protectFile=protectFile,
        protectFeature=False,
        apicall=' ',
        apientry=' ',
        apientryp='& ',
        alignFuncParam=48,
        misracstyle=False,
        misracppstyle=False,
    )
    if 'mergeInternalApis' in inspect.signature(GeneratorOptions.__init__).parameters:
        v_common['mergeInternalApis'] = not args.no_internal_api_merging

    genOpts['vulkan.v'] = [
        VOutputGenerator,
        VGeneratorOptions(
            filename='../../src/vulkan.v',
            apiname=defaultAPIName,
            mergeApiNames=mergeApiNames,
            versions=featuresPat,
            emitversions=featuresPat,
            **v_common,
        )
    ]

    genOpts['vulkan_video.v'] = [
        VOutputGenerator,
        VGeneratorOptions(
            filename='../../src/vulkan_video.v',
            apiname='vulkan_video',
            versions=None,
            emitversions=None,
            **v_common,
        )
    ]

    genOpts['vulkan_base_core.v'] = [
        VOutputGenerator,
        VGeneratorOptions(
            filename='../../src/vulkan_base.v',
            apiname='vulkanbase',
            mergeApiNames=mergeApiNames,
            versions=featuresPat,
            emitversions=featuresPat,
            **v_common,
        )
    ]


def genTarget(args):
    makeGenOpts(args)

    if args.target not in genOpts:
        logErr('No generator options for unknown target:', args.target)
        return None

    createGenerator, options = genOpts[args.target]

    logDiag('* Building', options.filename)
    logDiag('* options.apiname           =', options.apiname)
    logDiag('* options.versions          =', options.versions)
    logDiag('* options.emitversions      =', options.emitversions)
    logDiag('* options.defaultExtensions =', options.defaultExtensions)
    logDiag('* options.addExtensions     =', options.addExtensions)
    logDiag('* options.removeExtensions  =', options.removeExtensions)
    logDiag('* options.emitExtensions    =', options.emitExtensions)

    gen = createGenerator(errFile=errWarn, warnFile=errWarn, diagFile=diag)
    return (gen, options)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-apiname', action='store', default=None,
                        help='Specify API to generate')
    parser.add_argument('-mergeApiNames', action='store', default=None,
                        help='Specify a comma separated list of APIs to merge into the target API')
    parser.add_argument('-defaultExtensions', action='store',
                        default=APIConventions().xml_api_name,
                        help='Specify a single class of extensions to add to targets')
    parser.add_argument('-extension', action='append', default=[],
                        help='Specify an extension or extensions to add to targets')
    parser.add_argument('-removeExtensions', action='append', default=[],
                        help='Specify an extension or extensions to remove from targets')
    parser.add_argument('-emitExtensions', action='append', default=[],
                        help='Specify an extension or extensions to emit in targets')
    parser.add_argument('-feature', action='append', default=[],
                        help='Specify a core API feature name or names to add to targets')
    parser.add_argument('-debug', action='store_true', help='Enable debugging')
    parser.add_argument('-dump', action='store_true', help='Enable dump to stderr')
    parser.add_argument('-diagfile', action='store', default=None,
                        help='Write diagnostics to specified file')
    parser.add_argument('-errfile', action='store', default=None,
                        help='Write errors and warnings to specified file instead of stderr')
    parser.add_argument('-noprotect', dest='protect', action='store_false',
                        help='Disable inclusion protection in output headers')
    parser.add_argument('-no-internal-api-merging', action='store_true',
                        help='Read registries from before internal API features were introduced')
    parser.add_argument('-registry', action='store', default='../xml/vk.xml',
                        help='Use specified registry file instead of vk.xml')
    parser.add_argument('-time', action='store_true', help='Enable timing')
    parser.add_argument('-o', action='store', dest='directory', default='.',
                        help='Create target and related files in specified directory')
    parser.add_argument('target', metavar='target', nargs='?', default='vulkan.v',
                        choices=['vulkan.v', 'vulkan_video.v', 'vulkan_base_core.v'],
                        help='Specify target')
    parser.add_argument('-quiet', action='store_true', default=True,
                        help='Suppress script output during normal execution.')
    parser.add_argument('-verbose', action='store_false', dest='quiet', default=True,
                        help='Enable script output during normal execution.')

    args = parser.parse_args()
    args.feature = [name for arg in args.feature for name in arg.split()]
    args.extension = [name for arg in args.extension for name in arg.split()]

    if args.errfile:
        errWarn = open(args.errfile, 'w', encoding='utf-8')
    else:
        errWarn = sys.stderr

    if args.diagfile:
        diag = open(args.diagfile, 'w', encoding='utf-8')
    else:
        diag = None

    if args.time:
        setLogFile(setDiag=True, setWarn=True, filename='-')

    gen, options = genTarget(args)
    reg = Registry(gen, options)

    args_registry = '../../' + args.registry
    startTimer(args.time)
    tree = etree.parse(args_registry)
    # Older registries put a funcpointer's name directly under <type>.
    # Current Khronos registry helpers expect the newer <proto><name> form,
    # but a name attribute is supported by both representations.
    for type_elem in tree.getroot().findall('types/type'):
        if (type_elem.get('category') == 'funcpointer'
                and type_elem.get('name') is None
                and type_elem.find('proto/name') is None):
            legacy_name = type_elem.findtext('name')
            if legacy_name:
                type_elem.set('name', legacy_name)
    endTimer(args.time, '* Time to make ElementTree =')

    startTimer(args.time)
    reg.loadElementTree(tree)
    endTimer(args.time, '* Time to parse ElementTree =')

    if args.dump:
        logDiag('* Dumping registry to regdump.txt')
        reg.dumpReg(filehandle=open('regdump.txt', 'w', encoding='utf-8'))

    if args.debug:
        pdb.run('reg.apiGen()')
    else:
        startTimer(args.time)
        reg.apiGen()
        endTimer(args.time, '* Time to generate ' + options.filename + ' =')

    if not args.quiet:
        logDiag('* Generated', options.filename)
