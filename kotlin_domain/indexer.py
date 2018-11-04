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
func_pattern = re.compile(r'\s*(?P<scope>private\s+|public\s+|open\s+|internal\s+|protected\s+)?(?P<type>fun)\s+(?P<template><T>)?\s*(?P<name>[a-zA-Z_][a-zA-Z0-9_.]*\b)(?P<rest>[^{]*)')
init_pattern = re.compile(r'\s*(?P<scope>private\s+|public\s+|open\s+|internal\s+|protected\s+)?(?P<type>(init|constructor|firstconstructor))\s*(?P<rest>[^{]*)')
var_pattern = re.compile(r'\s*(?P<scope>private\s+|public\s+|open\s+|internal\s+|protected\s+)?(?P<type>var\s+|val\s+)(?P<name>[a-zA-Z_][a-zA-Z0-9_]*\b)(?P<rest>[^{]*)(?P<computed>\s*{\s*)?')
case_pattern = re.compile(r'\s*case:\s+(?P<name>[a-zA-Z_][a-zA-Z0-9_]*\b)(\s*\(\s*(?P<raw_value>[a-zA-Z0-9_]*)\s*\)\s*)?')

# signatures
def class_sig(name=r'[a-zA-Z_][a-zA-Z0-9_]*'):
    return re.compile(r'\s*(?P<scope>private\s+|public\s+|open\s+|internal\s+|protected\s+)?(final\s+|inline\s+|sealed\s+)?(?P<struct>class|object)\s+(?!fun)(?P<name>' + name + r'\b)(\s*:\s*(?P<type>[^{]*))*(?P<rest>[^{]*)')

def fun_sig(name=r'[a-zA-Z_][a-zA-Z0-9_]*'):
    return re.compile(r'\s*(?P<scope>private\s+|public\s+|open\s+|internal\s+|protected\s+)?(final\s+)?(?P<struct>fun)\s+(?P<name>' + name + r'\b)(\s*:\s*(?P<type>[^{]*))*(?P<rest>[^{]*)')


def enum_class_sig(name=r'[a-zA-Z_][a-zA-Z0-9_]*'):
    return re.compile(r'\s*(?P<scope>private\s+|public\s+|open\s+|internal\s+|protected\s+)?(final\s+)?(?P<struct>enum\s+class)\s+(?P<name>' + name + r'\b)(\s*:\s*(?P<type>[^{]*))*(?P<rest>[^{]*)')


def data_class_sig(name=r'[a-zA-Z_][a-zA-Z0-9_]*'):
    return re.compile(r'\s*(?P<scope>private\s+|public\s+|open\s+|internal\s+|protected\s+)?(final\s+)?(?P<struct>data\s+class)\s+(?!fun)(?P<name>' + name + r'\b)(\s*:\s*(?P<type>[^{]*))*(?P<rest>[^{]*)')


def interface_sig(name=r'[a-zA-Z_][a-zA-Z0-9_]*'):
    return re.compile(r'\s*(?P<scope>private\s+|public\s+|open\s+|internal\s+|protected\s+)?(?P<struct>interface)\s+(?P<name>' + name + r'\b)(\s*:\s*(?P<type>[^{]*))*(?P<rest>[^{]*)')


def extension_sig(name=r'[a-zA-Z_][a-zA-Z0-9_]*'):
    return re.compile(r'\s*(?P<scope>private\s+|public\s+|open\s+|internal\s+|protected\s+)?(?P<struct>extension)\s+(?P<name>' + name + r'\b)(\s*:\s*(?P<type>[^{]*))*(?P<rest>[^{]*)')

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
param_pattern   = re.compile(r'^\s*@param(\s*|\[)(?P<param>[0-9A-Za-z_]*)(\s*|\])\s+(?P<desc>.*)')
property_pattern = re.compile(r'^\s*@property(\s*|\[)(?P<param>[0-9A-Za-z_]*)(\s*|\])\s+(?P<desc>.*)')

typical_patterns = {
    "author":author_pattern,"example":example_pattern,
    "returns":returns_pattern, "see":seealso_pattern,"since":since_pattern,
    "throws":throws_pattern
}
codeblock_pattern = re.compile(r'```')

stop_words = [
    'public', 'private', 'open', 'internal', 'data class', 'interface', 'enum',
    'fun', 'var', 'val', 'companion', 'object', 'class',
]

def balance_braces(line, brace_count):
    if line.startswith("//"): return brace_count
    line = string_pattern.sub("", line)
    line = comment_pattern.sub("", line)
    line = line_comment_pattern.sub("", line)
    open_braces = line.count('{')
    close_braces = line.count('}')
    braces = brace_count + open_braces - close_braces
    return braces

def balance_comment(line, comment_count):
    open_braces = line.count('/*')
    close_braces = line.count('*/')
    braces = comment_count + open_braces - close_braces
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

def clear_name(name, replace = '_'):
    return re.sub( '\s+', replace, name ).strip()

def get_docstring_for_val(vnameVal, docstring):
    out = []
    startDoc = False
    for line in docstring:
        if '@property[' + vnameVal + ']' in line or '@property ' + vnameVal + ' ' in line:
            out.append(line.strip()[12 + len(vnameVal):])
            startDoc = True

        if startDoc:
            if not line or '@' in line:
                return out
            out.append(line)
    return out

def get_docstring_for_param(vnameVal, docstring):
    vnameValStrip = vnameVal.strip()
    out = []
    startDoc = False
    for line in docstring:
        if '@param[' + vnameValStrip + ']' in line or '@param ' + vnameValStrip + ' ' in line:
            out.append(line.strip()[10 + len(vnameValStrip):])
            startDoc = True

        if startDoc:
            if not line or '@' in line:
                return out
            out.append(line)
    return out

def doc_line_to_rst(doc_line):
    if doc_line:
        return doc_line[0]

def doc_block_to_rst(doc_block, is_class = False):
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
            if is_class: # Skip parameters for class
                continue
            match = match.groupdict()
            # if emit_directive(): yield ''
            yield ':parameter ' + match['param'] + ': ' + match['desc']
            continue

        if '@property' in l:
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

def is_inside_comment(test_word, line):
    pos_comment_beg = line.find('/*')
    pos_comment_end = line.find('*/')
    if pos_comment_beg == -1:
        pos_comment_beg = len(line)
    if pos_comment_end == -1:
        pos_comment_end = len(line)
    test_pos = line.find(test_word)
    return  test_pos > pos_comment_beg and test_pos < pos_comment_end

def is_stop_word_present(line, commnets = True):
    line = comment_pattern.sub("", line)
    clear_line = clear_name(line, ' ')
    for stop_word in stop_words:
        if stop_word + ' ' in clear_line:
            return True

    if commnets and '/**' in clear_line:
        return True

    return False

def analyze_class_line(index, content):
    brace_balance = 0
    comment_balance = 0
    derived_part = False
    stop_words_count = 0

    out = {}
    out['constructor'] = ''
    out['derived'] = ''
    out['derived_constructor'] = ''
    out['no_body'] = True
    out['start'] = index

    for i in range(index, len(content)):
        counter = -1
        out['start'] = i
        strip_content = content[i].strip()

        # comment_balance = balance_comment(strip_content, comment_balance)

        if brace_balance == 0: # and comment_balance == 0:
            if is_stop_word_present(strip_content):
                stop_words_count += 1

        if stop_words_count > 1:
            out['no_body'] = True
            return out

        for char in strip_content:
            counter += 1
            if brace_balance == 0 and char == ':':
                derived_part = True

            if char == '{':
                out['no_body'] = False
                return out

            if char == '(':
                brace_balance += 1
            elif char == ')':
                brace_balance -= 1
                if derived_part:
                    out['derived_constructor'] += char
                else:
                    out['constructor'] += char
                continue

            if brace_balance > 0:
                if derived_part:
                    out['derived_constructor'] += char
                else:
                    out['constructor'] += char
            elif derived_part and not out['derived_constructor']:
                out['derived'] += char

    return out

def fix_line_breaks(index, content):
    l = content[index].rstrip()

    counter = 0
    while balance_bracket(l) != 0:
        index += 1
        counter += 1
        if counter > 6:
            break
        if len(content) <= index:
            break

        l += ' ' + content[index].strip()

    return l, index

def prepare_enum_class(index, content):
    out = []
    brace_balance = 0
    comment_balance = 0
    end_enum_block = False

    for i in range(index + 1, len(content)):
        strip_content = content[i].strip()

        comment_balance = balance_comment(strip_content, comment_balance)

        if brace_balance == 0 and comment_balance == 0:
            if is_stop_word_present(strip_content, False):
                end_enum_block = True

        # check comment line
        if strip_content.startswith('/**'):
            out.append(content[i])
            i += 1
            continue

        if end_enum_block:
            out.append(content[i])
        else:
            out.append('case: ' + content[i])
        i += 1

    return out

class KotlinFileIndex(object):

    symbol_signatures = [class_sig(), enum_class_sig(), data_class_sig(), extension_sig(), interface_sig(), fun_sig()]

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

                            typeVal = clear_name(struct)

                            item = {
                                'file': file,
                                'line': index,
                                'depth': 1 if braces == 0 else braces,
                                'type': typeVal,
                                'scope': scope,
                                'name': match['name'].strip() + match['rest'] if match['rest'] and typeVal == 'fun' else match['name'].strip(),
                                'docstring': get_doc_block(content, index - 1),
                                'param': match['type'].strip() if match['type'] else None,
                                'children': [],
                                'raw': line
                            }

                            if typeVal == 'fun':
                                if braces == 0 or (braces == 1 and line.find('}') == -1 and line.find('{') != -1):
                                    symbol_stack.append(item)
                                continue

                            if len(symbol_stack) > 0 and braces > symbol_stack[-1]['depth']:
                                symbol_stack[-1]['children'].append(item)
                            else:
                                symbol_stack.append(item)


                            item_details = analyze_class_line(index, content)
                            # print item['name']
                            # print item_details
                            if item_details['no_body']:
                                if item_details['constructor']:
                                    contentPlus = []
                                    contentPlus.append('/**')
                                    contentPlus.extend(item['docstring'])
                                    contentPlus.append('*/')
                                    contentPlus.append('firstconstructor' + item_details['constructor'])
                                    contentPlus.append('')
                                    item['members'] = KotlinObjectIndex(contentPlus, 0, item['type'])
                            else:
                                if item['type'] == 'enum_class':
                                    enum_item = prepare_enum_class(index, content)
                                    item['members'] = KotlinObjectIndex(enum_item, 0, item['type'])
                                elif item_details['constructor']:
                                    contentPlus = []
                                    contentPlus.append('/**')
                                    contentPlus.extend(item['docstring'])
                                    contentPlus.append('*/')
                                    contentPlus.append('firstconstructor' + item_details['constructor'])
                                    contentPlus.extend(content[item_details['start'] + 1:])
                                    item['members'] = KotlinObjectIndex(contentPlus, 0, item['type'])
                                else:
                                    item['members'] = KotlinObjectIndex(content, item_details['start'] + 1, item['type'])

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

        yield line

        if noindex:
            yield indent + ':noindex:'
        yield ''

        if not nodocstring:
            for line in doc_block_to_rst(item['docstring'], item['type'] != 'fun'):
                yield indent + line
            # yield ''

class KotlinObjectIndex(object):

    def __init__(self, content, line, typ):
        signatures = [func_pattern, init_pattern, var_pattern]
        if typ == 'enum_class':
            signatures = [case_pattern]
        # elif typ == 'protocol':
        #     signatures = [func_pattern, init_pattern, proto_var_pattern]

        self.index = []
        braces = 1
        static_braces = 0

        # Make full string from fun begin to the closed brace
        i = line
        while i < len(content):
            l, new_i = fix_line_breaks(i, content)
            counter = new_i - i
            i = new_i + 1

            # balance braces
            old_braces = braces
            braces = balance_braces(l, braces)
            if 'companion object' in clear_name(l, ' '):
                static_braces = braces
            if braces < static_braces:
                static_braces = 0

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
                        if typ != 'enum_class':
                            docstring = get_doc_block(content, i - counter - 2)
                        else:
                            docstring = []
                    if "@suppress" in docstring:
                        continue

                    typeVal = ''
                    if 'type' in match and match['type']:
                        if static_braces > 0 and static_braces <= braces:
                            typeVal = 'static_' + match['type'].strip()
                        else:
                            typeVal = match['type'].strip()

                    if typ == 'enum_class':
                        typeVal = 'enum_case'

                    nameVal = ''
                    constructorVariables = []
                    if 'name' in match and match['name']:
                        nameVal = match['name'].strip()
                    if typeVal == 'init':
                        nameVal = 'init'
                    elif typeVal == 'constructor':
                        nameVal = 'constructor'
                        if 'rest' in match and match['rest']:
                            splitPos = match['rest'].find(')') + 1
                            if splitPos != 0:
                                match['rest'] = match['rest'][:splitPos]
                    elif typeVal == 'firstconstructor':
                        nameVal = 'constructor'
                        typeVal = 'constructor'

                        docstring_new = ['Main constructor', '']
                        if 'rest' in match and match['rest']:
                            variables = match['rest'].strip()[1:-1].split(',')
                            firstVal = True
                            match['rest'] = '('
                            for variable in variables:
                                vmatch = var_pattern.match(variable)
                                if vmatch:
                                    vmatch = vmatch.groupdict()
                                    vscope = 'public'
                                    if 'scope' in vmatch and vmatch['scope']:
                                        vscope = vmatch['scope'].strip()

                                    if vscope == 'open':
                                        vscope = 'public'

                                    if vscope != 'public':
                                        continue

                                    vnameVal = vmatch['name'].strip() if 'name' in vmatch and vmatch['name'] else None
                                    vtypeVal = vmatch['type'].strip() if 'type' in vmatch and vmatch['type'] else None
                                    vrestVal = vmatch['rest'].strip() if 'rest' in vmatch and vmatch['rest'] else None
                                    constructorVariables.append({
                                        'scope': vscope,
                                        'line': i,
                                        'type': vtypeVal,
                                        'name': vnameVal,
                                        'docstring': get_docstring_for_val(vnameVal, docstring),
                                        'rest': vrestVal,
                                        'raw': variable
                                    })

                                    if firstVal:
                                        firstVal = False
                                        if vrestVal:
                                            match['rest'] += vnameVal + vrestVal
                                        else:
                                            match['rest'] += vnameVal
                                    else:
                                        if vrestVal:
                                            match['rest'] += ', ' + vnameVal + vrestVal
                                        else:
                                            match['rest'] += ', ' + vnameVal
                                else:

                                    strip_variable = variable.replace(':', '|').replace('=', '|').split('|')
                                    param_docstring = get_docstring_for_param(strip_variable[0], docstring)

                                    if firstVal:
                                        firstVal = False
                                        if strip_variable[1]:
                                            match['rest'] += strip_variable[0] + strip_variable[1]
                                        else:
                                            match['rest'] += strip_variable[0]
                                    else:
                                        if strip_variable[1]:
                                            match['rest'] += ', ' + strip_variable[0] + strip_variable[1]
                                        else:
                                            match['rest'] += ', ' + strip_variable[0]

                                    if param_docstring:
                                        docstring_new.append('@param ' + strip_variable[0] + ' ' + ''.join(param_docstring))

                            match['rest'] += ')'
                        for constructorVariable in constructorVariables:
                            if constructorVariable['docstring']:
                                docstring_new.append('@param ' + constructorVariable['name'] + ' ' + ''.join(constructorVariable['docstring']))

                        docstring = docstring_new
                    # print 'Match ' + l + '[{},{},{}]'.format(nameVal, typeVal,scope)

                    self.index.append({
                        'scope': scope,
                        'line': i - 1,
                        'type': typeVal,
                        'name': nameVal,
                        'docstring': docstring,
                        'rest': match['rest'].strip() if 'rest' in match and match['rest'] else None,
                        'raw_value': match['raw_value'].strip() if 'raw_value' in match and match['raw_value'] else None,
                        'raw': l
                    })

                    if constructorVariables:
                        self.index.extend(constructorVariables)

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

        if item['type'] == 'enum_case':
            # enum case
            case = '- ' + sig
            if item['raw_value']:
                case += ' = ' + item['raw_value']

            # Always document enum cases
            if item['docstring']:
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
            elif item['name'] == 'constructor':
                yield '.. kotlin:constructor:: ' + sig
            elif item['type'] == 'static_fun':
                yield '.. kotlin:static_fun:: ' + sig
            else:
                yield '.. kotlin:fun:: ' + sig

        if noindex:
            yield indent + ':noindex:'
        yield ''

        if not nodocstring and item['type'] != 'enum_case':
            for line in doc_block_to_rst(item['docstring']):
                yield indent + ' ' + line
            yield ''
