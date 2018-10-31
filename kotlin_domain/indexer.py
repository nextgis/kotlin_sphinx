# -*- coding: utf-8 -*-
################################################################################
# Project:  Kotlin to sphinx
# Purpose:  Kotlin KDoc to sphinx documentation generator
# Author:   Dmitry Barishnikov, dmitry.baryshnikov@nextgis.ru
################################################################################
# Copyright (C) 2018, NextGIS <info@nextgis.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
################################################################################

import re
import os
import fnmatch
import io

# member patterns
func_pattern = re.compile(r'\s*(?P<scope>private\s+|public\s+|open\s+|internal\s+)?(?P<type>fun)\s+(?P<template><T>)?\s*(?P<name>[a-zA-Z_][a-zA-Z0-9_.]*\b)(?P<rest>[^{]*)')
init_pattern = re.compile(r'\s*(?P<scope>private\s+|public\s+|open\s+|internal\s+)?(?P<type>init?)\s*(?P<rest>[^{]*)')
var_pattern = re.compile(r'\s*(?P<add_scope>private\s*\(set\)\s+|private\s*\(get\)\s+)?(?P<scope>private\s+|public\s+|open\s+|internal\s+)?(final\s+)?(?P<type>var\s+|val\s+)(?P<name>[a-zA-Z_][a-zA-Z0-9_]*\b)(?P<rest>[^{]*)(?P<computed>\s*{\s*)?')
case_pattern = re.compile(r'\s*(?P<name>[a-zA-Z_][a-zA-Z0-9_]*\b)(\s*\(\s*(?P<raw_value>.*)\s*\)\s*)?')

# signatures
def class_sig(name=r'[a-zA-Z_][a-zA-Z0-9_]*'):
    return re.compile(r'\s*(?P<scope>private\s+|public\s+|open\s+|internal\s+)?(final\s+)?(?P<struct>class|object)\s+(?!fun)(?P<name>' + name + r'\b)(\s*:\s*(?P<type>[^{]*))*')


def enum_class_sig(name=r'[a-zA-Z_][a-zA-Z0-9_]*'):
    return re.compile(r'\s*(?P<scope>private\s+|public\s+|open\s+|internal\s+)?(final\s+)?(?P<struct>enum\s+class)\s+(?P<name>' + name + r'\b)(\s*:\s*(?P<type>[^{]*))*')


def data_class_sig(name=r'[a-zA-Z_][a-zA-Z0-9_]*'):
    return re.compile(r'\s*(?P<scope>private\s+|public\s+|open\s+|internal\s+)?(final\s+)?(?P<struct>data\s+class)\s+(?P<name>' + name + r'\b)(\s*:\s*(?P<type>[^{]*))*')


def interface_sig(name=r'[a-zA-Z_][a-zA-Z0-9_]*'):
    return re.compile(r'\s*(?P<scope>private\s+|public\s+|open\s+|internal\s+)?(?P<struct>interface)\s+(?P<name>' + name + r'\b)(\s*:\s*(?P<type>[^{]*))*')


def extension_sig(name=r'[a-zA-Z_][a-zA-Z0-9_]*'):
    return re.compile(r'\s*(?P<scope>private\s+|public\s+|open\s+|internal\s+)?(?P<struct>extension)\s+(?P<name>' + name + r'\b)(\s*:\s*(?P<type>[^{]*))*(\s*where\s+(?P<where>[^{]*))?')

# brace balancing for determining in which depth we are
string_pattern = re.compile(r'"(?:[^"\\]*(?:\\.)?)*"')
line_comment_pattern = re.compile(r'(// .*$)')
comment_pattern = re.compile(r'/\*(?:.)*\*/')
author_pattern  = re.compile(r'^\s*@author\s*(?P<desc>.*)')
example_pattern  = re.compile(r'^\s*@sample\s*(?P<desc>.*)')
returns_pattern  = re.compile(r'^\s*@return\s*(?P<desc>.*)')
seealso_pattern  = re.compile(r'^\s*@see\s*(?P<desc>.*)')
since_pattern  = re.compile(r'^\s*@since\s*(?P<desc>.*)')
throws_pattern  = re.compile(r'^\s*@throws\s*(?P<desc>.*)')
param_pattern   = re.compile(r'^\s*@param(\s*|\[)(?P<param>[0-9A-Za-z]*)(\s*|\])\s+(?P<desc>.*)')
property_pattern = re.compile(r'^\s*@property(\s*|\[)(?P<param>[0-9A-Za-z]*)(\s*|\])\s+(?P<desc>.*)')

typical_patterns = {
    "author":author_pattern,"example":example_pattern,
    "returns":returns_pattern, "see":seealso_pattern,"since":since_pattern,
    "throws":throws_pattern
}
codeblock_pattern = re.compile(r'```')

def balance_braces(line, brace_count):
    if line.startswith("//"): return brace_count
    line = string_pattern.sub("", line)
    line = comment_pattern.sub("", line)
    line = line_comment_pattern.sub("", line)
    open_braces = line.count('{')
    close_braces = line.count('}')
    braces = brace_count + open_braces - close_braces
    return braces

def balance_bracket(line):
    if line.startswith("//"): return 0
    line = string_pattern.sub("", line)
    line = comment_pattern.sub("", line)
    line = line_comment_pattern.sub("", line)
    open_brackets = line.count('(')
    close_brackets = line.count(')')
    return open_brackets - close_brackets

# fetch documentation block
def get_doc_block(content, line):

    # search upwards for documentation lines
    doc_block = []
    block_detected = False

    for i in reversed(content[:line+1]):
        l = i.rstrip()
        startsComment = False
        endsComment = False
        if l.endswith("*/"):
            endsComment = True
            l = l[:-2]
            block_detected = True
        if l.strip().startswith("/**"):
            startsComment = True
            l = l.strip()[3:]
        elif l.startswith("/*"):
            return [] #not a doc comment

        if not block_detected: #don't go searching arbitrarily far back
            break

        #insert on top
        if not (startsComment and l == ""):
            doc_block.insert(0,l)

        if startsComment:
            break
    return doc_block

def clearName(name, replace = '_'):
    return re.sub( '\s+', replace, name ).strip()

def doc_line_to_rst(doc_line):
    return doc_line[0]

def doc_block_to_rst(doc_block):
    # sphinx requires a newline between documentation and directives
    # but Kotlin does not
    global was_doc
    was_doc = True

    def emit_doc():
        global was_doc
        if not was_doc:
            was_doc = True
            return True
        return False

    def emit_directive():
        global was_doc
        if was_doc:
            was_doc = False
            return True
        return False

    code_mode = False

    for l in doc_block:
        l = l.strip()
        if l and l[0] == '*':
            l = l[1:]

        if codeblock_pattern.match(l):
            if not code_mode:
                code_mode = True
                yield '.. code-block:: kotlin'
                yield ''
                continue
            else:
                code_mode = False
                continue
        if code_mode:
            yield '    ' + l
            continue

        match = param_pattern.match(l)
        if match:
            match = match.groupdict()
            # if emit_directive(): yield ''
            yield ':parameter ' + match['param'] + ': ' + match['desc']
            continue

        match = property_pattern.match(l)
        if match:
            match = match.groupdict()
            # if emit_directive(): yield ''
            yield ':property ' + match['param'] + ': ' + match['desc']
            continue

        c = False #continue if required
        for name,pattern in typical_patterns.items():
            match = pattern.match(l)
            if match:
                match = match.groupdict()
                # if emit_directive(): yield ''
                yield ':' + name + ': ' + match['desc']
                c = True
                break
        if c: continue

        if not was_doc and l != "":
            yield "    " + l
            continue

        #if we've got here, assume it's doc
        if emit_doc(): yield ''
        yield l.strip()

class KotlinFileIndex(object):

    symbol_signatures = [class_sig(), enum_class_sig(), data_class_sig(), extension_sig(), interface_sig()]

    def __init__(self, search_path):
        self.index = []

        # find all files
        self.files = []
        for path in search_path:
            for root, dirnames, filenames in os.walk(path):
                for filename in fnmatch.filter(filenames, '*.kt'):
                    self.files.append(os.path.join(root, filename))

        for file in self.files:
            print("Indexing kotlin file: %s" % file)
            symbol_stack = []
            braces = 0
            with io.open(file, mode="r", encoding="utf-8") as fp:
                content = fp.readlines()
                for (index, line) in enumerate(content):
                    braces = balance_braces(line, braces)
                    # track boxed context
                    for pattern in self.symbol_signatures:
                        match = pattern.match(line)
                        if match:
                            match = match.groupdict()

                            struct = match['struct'].strip()
                            scope = 'public'
                            if 'scope' in match and match['scope']:
                                scope = match['scope'].strip()

                            if scope == 'open':
                                scope = 'public'

                            item = {
                                'file': file,
                                'line': index,
                                'depth': 1 if braces == 0 else braces,
                                'type': clearName(struct, ' '),
                                'scope': scope,
                                'name': match['name'].strip(),
                                'docstring': get_doc_block(content, index - 1),
                                'param': match['type'].strip() if match['type'] else None,
                                'where': match['where'].strip() if 'where' in match and match['where'] else None,
                                'children': [],
                                'raw': line
                            }

                            if len(symbol_stack) > 0 and braces > symbol_stack[-1]['depth']:
                                symbol_stack[-1]['children'].append(item)
                            else:
                                symbol_stack.append(item)

                            # find members
                            start = index
                            if line.rstrip()[-1] == '{':
                                start = index + 1
                            else:
                                for i in range(index + 1, len(content)):
                                    l = content[i].lstrip()
                                    if len(l) > 0 and l[0] == '{':
                                        start = i
                                        break
                            if braces != 0:
                                item['members'] = KotlinObjectIndex(content, start, item['type'])

            self.index.extend(symbol_stack)

    def by_file(self, index=None):
        result = {}

        if not index:
            index = self.index

        for item in index:
            if item['file'] not in result:
                result[item['file']] = []
            result[item['file']].append(item)

        return result

    @staticmethod
    def documentation(item, indent="    ", noindex=False, nodocstring=False, location=False):
        if item['param']:
            line = '.. kotlin:' + item['type'] + ':: ' + item['name'] + ' : ' + item['param']
        else:
            line = '.. kotlin:' + item['type'] + ':: ' + item['name']

        if item['where']:
            line += ' where ' + item['where']

        yield line

        if noindex:
            yield indent + ':noindex:'
        yield ''

        if not nodocstring:
            for line in doc_block_to_rst(item['docstring']):
                yield indent + line
            # yield ''

class KotlinObjectIndex(object):

    def __init__(self, content, line, typ):
        signatures = [func_pattern, init_pattern, var_pattern]
        if typ == 'enum class':
            signatures = [func_pattern, init_pattern, case_pattern]
        # elif typ == 'protocol':
        #     signatures = [func_pattern, init_pattern, proto_var_pattern]

        self.index = []
        braces = 1
        i = line
        while i < len(content):
            l = content[i].rstrip()

            counter = 0
            while balance_bracket(l) != 0:
                i = i + 1
                counter = counter + 1
                if counter > 6:
                    break
                if len(content) <= i:
                    break

                l += ' ' + content[i].strip()

            # Debug
            # if counter > 0:
            #     print l + '\n'

            i = i + 1

            # balance braces
            old_braces = braces
            braces = balance_braces(l, braces)
            if braces <= 0:
                break
            if braces > 1 and old_braces == braces:
                continue

            for pattern in signatures:
                match = pattern.match(l)
                if match:
                    match = match.groupdict()
                    scope = 'public'
                    if 'scope' in match and match['scope']:
                        scope = match['scope'].strip()

                    if scope == 'open':
                        scope = 'public'

                    doc_block_pos = l.find('/**<')
                    if doc_block_pos != -1:
                        doc_block_end = l.find('*/')
                        docstring = []
                        docstring.append(l[doc_block_pos + 4:doc_block_end].strip())
                    else:
                        docstring = get_doc_block(content, i - counter - 2)
                    if "@suppress" in docstring:
                        continue

                    if 'type' in match and match['type']:
                        typeVal = match['type'].strip()
                    if typ == 'enum class':
                        typeVal = 'case'

                    if 'name' in match and match['name']:
                        nameVal = match['name'].strip()
                    if typeVal == 'init' or typeVal == 'init?':
                        nameVal = 'init'

                    # print 'Match ' + l + '[{},{},{}]'.format(nameVal, typeVal,scope)

                    self.index.append({
                        'scope': scope,
                        'line': i,
                        'type': typeVal,
                        'name': nameVal,
                        'docstring': docstring,
                        'rest': match['rest'].strip() if 'rest' in match and match['rest'] else None,
                        'raw_value': match['raw_value'].strip() if 'raw_value' in match and match['raw_value'] else None,
                        'raw': l
                    })

    @staticmethod
    def documentation(item, indent="    ", noindex=False, nodocstring=False, location=None):
        sig = item['name']
        if item['rest']:
            if item['type'] == 'var' or item['type'] == 'val':
                pos = item['rest'].find('get()')
                if pos != -1:
                    sig += item['rest'][:pos]
                else:
                    sig += item['rest']
            else:
                sig += item['rest']

        if item['type'] == 'case':
            # enum case
            case = '- ' + sig
            if item['raw_value']:
                case += ' = ' + item['raw_value']

            if not nodocstring and item['docstring']:
                yield case + ' : ' + doc_line_to_rst(item['docstring'])
            else:
                yield case
            return

        elif item['type'] == 'var' or item['type'] == 'val':
            # variables
            yield '.. kotlin:' + item['type'] + ':: ' + sig
        else:
            if item['name'] == 'init':
                yield '.. kotlin:init:: ' + sig
            else:
                yield '.. kotlin:method:: ' + sig

        if noindex:
            yield indent + ':noindex:'
        yield ''

        if not nodocstring and item['type'] != 'case':
            for line in doc_block_to_rst(item['docstring']):
                yield indent + ' ' + line
            yield ''
