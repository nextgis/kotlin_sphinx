# -*- coding: utf-8 -*-
################################################################################
# Project:  Kotlin to sphinx
# Purpose:  Kotlin KDoc to sphinx documentation
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
"""
    sphinx.domains.kotlin
    ~~~~~~~~~~~~~~~~~~~~~~

    The Kotlin domain.

    :author:  Dmitry Baryshnikov, dmitry.baryshnikov@nextgis.com
    :copyright: Copyright 2018 NextGIS, info@nextgis.com
    :license: This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import re

from docutils import nodes
from docutils.parsers.rst import directives

from sphinx import addnodes
from sphinx.roles import XRefRole
from sphinx.locale import l_
from sphinx.domains import Domain, ObjType, Index
from sphinx.directives import ObjectDescription
from sphinx.util.nodes import make_refnode
from sphinx.util.docfields import Field, GroupedField, TypedField

kotlin_reserved = set(['Double', 'Float', 'Long', 'Int', 'Short', 'Byte', 'Char',
    'Boolean', 'ByteArray', 'ShortArray', 'IntArray',
    'UByte', 'UShort', 'UInt', 'ULong',
    'UByteArray', 'UShortArray', 'UIntArray', 'ULongArray', 'UIntProgression',
    'UIntRange', 'ULongRange', 'ULongProgression', 'String',
])

def formExternalUrl(type):
# https://kotlinlang.org/api/latest/jvm/stdlib/kotlin/-u-int/index.html
# https://kotlinlang.org/api/latest/jvm/stdlib/kotlin/-double/index.html
    out = 'https://kotlinlang.org/api/latest/jvm/stdlib/kotlin/'
    for char in type:
        if char.isupper():
            out += '-' + char.lower()
        else:
            out += char
    return out + '/index.html'

def _iteritems(d):
    for k in d:
        yield k, d[k]


class KotlinObjectDescription(ObjectDescription):
    option_spec = {
        'noindex': directives.flag,
    }

    def add_target_and_index(self, name_cls_add, sig, signode):
        fullname, signature, add_to_index = name_cls_add
        if 'noindex' in self.options or not add_to_index:
            return

        # for char in '<>()[]:, ?!':
        #     signature = signature.replace(char, "-")

        # note target
        if fullname not in self.state.document.ids:
            signode['ids'].append(signature)
            self.state.document.note_explicit_target(signode)
            self.env.domaindata['kotlin']['objects'][fullname] = (self.env.docname, self.objtype, signature)
        else:
            objects = self.env.domaindata['kotlin']['objects']
            self.env.warn(
                self.env.docname,
                'duplicate object description of %s, ' % fullname +
                'other instance in ' +
                self.env.doc2path(objects[fullname][0]),
                self.lineno)


class KotlinClass(KotlinObjectDescription):

    def handle_signature(self, sig, signode):
        container_class_name = self.env.temp_data.get('kotlin:class')

        # split on : -> first part is class name, second part is superclass list
        parts = [x.strip() for x in sig.split(':', 1)]

        # if the class name contains a < then there is a generic type attachment
        if '<' in parts[0]:
            class_name, generic_type = parts[0].split('<')
            generic_type = generic_type[:-1]
        else:
            class_name = parts[0]
            generic_type = None

        # did we catch a 'where' ?
        type_constraint = None
        class_parts = None
        if ' ' in class_name:
            class_parts = class_name.split(' ')
        elif '\t' in class_name:
            class_parts = class_name.split('\t')

        if class_name.count('.'):
            class_name = class_name.split('.')[-1]

        # if we have more than one part this class has super classes / protocols
        super_classes = None
        if len(parts) > 1:
            super_classes = [x.strip() for x in parts[1].split(',')]

        # Add class name
        objTypeFixed = self.objtype.replace('_', ' ')
        signode += addnodes.desc_addname(objTypeFixed, objTypeFixed + ' ')
        signode += addnodes.desc_name(class_name, class_name)

        # if we had super classes add annotation
        if super_classes:
            children = []
            for c in super_classes:
                prefix = ', ' if c != super_classes[0] else ''
                ref = addnodes.pending_xref('', reftype='type', refdomain='kotlin', reftarget=c, refwarn=True)
                ref += nodes.Text(prefix + c)
                children.append(ref)
            signode += addnodes.desc_type('', ' : ', *children)

        # add type constraint
        if type_constraint:
            signode += addnodes.desc_type(type_constraint, ' ' + type_constraint)

        add_to_index = True
        if self.objtype == 'extension' and not super_classes:
            add_to_index = False

        if container_class_name:
            class_name = container_class_name + '.' + class_name
        return self.objtype + ' ' + class_name, self.objtype + ' ' + class_name, add_to_index

    def before_content(self):
        if self.names:
            parts = self.names[0][1].split(" ")
            if len(parts) > 1:
                self.env.temp_data['kotlin:class'] = " ".join(parts[1:])
            else:
                env.temp_data['kotlin:class'] = self.names[0][1]
            self.env.temp_data['kotlin:class_type'] = self.objtype
            self.clsname_set = True

    def after_content(self):
        if self.clsname_set:
            self.env.temp_data['kotlin:class'] = None
            self.env.temp_data['kotlin:class_type'] = None


class KotlinClassmember(KotlinObjectDescription):

    doc_field_types = [
        TypedField('parameter', label=l_('Parameters'),
                   names=('param', 'parameter', 'arg', 'argument'),
                   typerolename='obj', typenames=('paramtype', 'type')),
        GroupedField('errors', label=l_('Throws'), rolename='obj',
                     names=('raises', 'raise', 'exception', 'except', 'throw', 'throws'),
                     can_collapse=True),
        Field('returnvalue', label=l_('Returns'), has_arg=False,
              names=('returns', 'return')),
    ]

    def _parse_parameter_list(self, parameter_list):
        parameters = []
        parens = {'[]': 0, '()': 0, '<>': 0}
        last_split = 0
        for i, c in enumerate(parameter_list):
            for key, value in parens.items():
                if c == key[0]:
                    value += 1
                    parens[key] = value
                if c == key[1]:
                    value -= 1
                    parens[key] = value

            skip_comma = False
            for key, value in parens.items():
                if value != 0:
                    skip_comma = True

            if c == ',' and not skip_comma:
                parameters.append(parameter_list[last_split:i].strip())
                last_split = i + 1
        parameters.append(parameter_list[last_split:].strip())

        result = []
        for parameter in parameters:
            name, rest = [x.strip() for x in parameter.split(':', 1)]
            name_parts = name.split(' ', 1)
            if len(name_parts) > 1:
                name = name_parts[0]
                variable_name = name_parts[1]
            else:
                name = name_parts[0]
                variable_name = name_parts[0]
            equals = rest.rfind('=')
            if equals >= 0:
                default_value = rest[equals + 1:].strip()
                param_type = rest[:equals].strip()
            else:
                default_value = None
                param_type = rest
            result.append({
                "name": name,
                "variable_name": variable_name,
                "type": param_type,
                "default": default_value
            })
        return result

    def handle_signature(self, sig, signode):
        container_class_name = self.env.temp_data.get('kotlin:class')
        container_class_type = self.env.temp_data.get('kotlin:class_type')

        # split into method name and rest
        first_anglebracket = sig.find('<')
        first_paren = sig.find('(')
        if first_anglebracket >= 0 and first_paren > first_anglebracket:
            split_point = sig.find('>')+1
        else:
            split_point = first_paren

        # calculate generics
        if first_anglebracket >= 0:
            sp = sig[first_anglebracket:]
            np = sp.find('>')
            generics = sp[:np+1]
        else:
            generics = None

        method_name = sig[0:split_point]

        # find method specialization
        angle_bracket = method_name.find('<')
        if angle_bracket >= 0:
            method_name = method_name[:angle_bracket]

        rest = sig[split_point:]

        # split parameter list
        parameter_list = None
        depth = 0
        for i, c in enumerate(rest):
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
            if depth == 0:
                parameter_list = rest[1:i]
                rest = rest[i + 1:]
                break

        if parameter_list is not None and len(parameter_list) > 0:
            parameters = self._parse_parameter_list(parameter_list)
        else:
            parameters = []

        # check if it throws
        throws = rest.find('throws') >= 0

        # check for return type
        return_type = None
        arrow = rest.find('->')
        if arrow >= 0:
            return_type = rest[arrow + 2:].strip()

        # build signature and add nodes
        signature = ''
        if self.objtype == 'static_fun':
            signode += addnodes.desc_addname("static", "static fun ")
        elif self.objtype == 'class_method':
            signode += addnodes.desc_addname("class", "class fun ")
        elif self.objtype != 'init':
            signode += addnodes.desc_addname("fun", "fun ")

        if self.objtype == 'init':
            signode += addnodes.desc_name('init', 'init')
            signature += 'init('
            for p in parameters:
                if p['name'] == p['variable_name']:
                    signature += p['name'] + ':'
                else:
                    signature += p['name'] + ' ' + p['variable_name'] + ':'
            signature += ')'
        else:
            signode += addnodes.desc_name(method_name, method_name)
            signature += method_name
            signature += '('
            for p in parameters:
                if p['name'] == p['variable_name']:
                    signature += p['name'] + ':'
                else:
                    signature += p['name'] + ' ' + p['variable_name'] + ':'
            signature += ')'

        if generics:
            signode += addnodes.desc_addname(generics,generics)

        params = []
        sig = ''
        for p in parameters:
            if p['name'] == p['variable_name']:
                param = p['name'] + ': ' # + p['type']
                sig += p['name'] + ':'
            else:
                param = p['name'] + ' ' + p['variable_name'] + ':' # + p['type']
                sig += p['name'] + ' ' + p['variable_name'] + ':'
            #if p['default']:
            #    param += ' = ' + p['default']

            paramNode = addnodes.desc_parameter(param, param)
            paramXref = addnodes.pending_xref('', refdomain='kotlin', reftype='type', reftarget=p['type'])
            paramXref += nodes.Text(p['type'], p['type'])
            paramNode += paramXref
            if p['default']:
                paramNode += nodes.Text(' = ' + p['default'], ' = ' + p['default'])
            params.append(paramNode)
        signode += addnodes.desc_parameterlist(sig, "", *params)

        title = signature
        if throws:
            signode += addnodes.desc_annotation("throws", "throws")
            # signature += "throws"

        if return_type:
            paramNode = addnodes.desc_returns('', '')
            paramXref = addnodes.pending_xref('', refdomain='kotlin', reftype='type', reftarget=return_type)
            paramXref += nodes.Text(return_type, return_type)
            paramNode += paramXref
            signode += paramNode
            # signode += addnodes.desc_returns(return_type, return_type)
            #signature += "-" + return_type

        #if container_class_type == 'protocol':
        #    signature += "-protocol"

        #if self.objtype == 'static_method':
        #    signature += '-static'
        #elif self.objtype == 'class_method':
        #    signature += '-class'

        if container_class_name:
            return (container_class_name + '.' + title), (container_class_name + '.' + signature), True
        return title, signature, True


class KotlinEnumCase(KotlinObjectDescription):

    def handle_signature(self, sig, signode):
        container_class_name = self.env.temp_data.get('kotlin:class')
        enum_case = None
        assoc_value = None
        raw_value = None

        # split on ( -> first part is case name
        parts = [x.strip() for x in sig.split('(', 1)]
        enum_case = parts[0].strip()
        if len(parts) > 1:
            parts = parts[1].rsplit('=', 1)
            assoc_value = parts[0].strip()
            if len(parts) > 1:
                raw_value = parts[1].strip()
            if assoc_value == "":
                assoc_value = None
            else:
                assoc_value = "(" + assoc_value
        else:
            parts = [x.strip() for x in sig.split('=', 1)]
            enum_case = parts[0].strip()
            if len(parts) > 1:
                raw_value = parts[1].strip()

        # Add class name
        signode += addnodes.desc_name(enum_case, enum_case)
        if assoc_value:
            signode += addnodes.desc_type(assoc_value, assoc_value)
        if raw_value:
            signode += addnodes.desc_addname(raw_value, " = " + raw_value)

        if container_class_name:
            enum_case = container_class_name + '.' + enum_case
        return enum_case, enum_case, True


var_sig = re.compile(r'^\s*(?P<name>[a-zA-Z_][a-zA-Z0-9_]*\b)(\s*:\s*(?P<type>[a-zA-Z_[(][a-zA-Z0-9_<>[\]()?!:, \t-\.]*))?(\s*=\s*(?P<value>[^{]*))?')


class KotlinClassIvar(KotlinObjectDescription):

    doc_field_types = [
        Field('defaultvalue', label=l_('Default'), has_arg=False,
              names=('defaults', 'default')),
    ]

    def handle_signature(self, sig, signode):
        container_class_name = self.env.temp_data.get('kotlin:class')

        match = var_sig.match(sig)
        if not match:
            self.env.warn(
                self.env.docname,
                'invalid variable/constant documentation string "%s", ' % sig,
                self.lineno)
            return

        match = match.groupdict()

        if self.objtype == 'var':
            signode += addnodes.desc_addname("var", "var ")
        elif self.objtype == 'val':
            signode += addnodes.desc_addname("val", "val ")

        name = match['name'].strip()
        signature = name
        signode += addnodes.desc_name(name, name)
        if match['type']:
            typ = match['type'].strip()
            #signature += '-' + typ
            # signode += addnodes.desc_type(typ, " : " + typ)
            # Add ref
            typeNode = addnodes.desc_type(' : ', ' : ')
            typeXref = addnodes.pending_xref('', refdomain='kotlin', reftype='type', reftarget=typ)
            typeXref += nodes.Text(typ, typ)
            typeNode += typeXref
            signode += typeNode


        if match['value'] and len(match['value']) > 0:
            value = match['value'].strip()
            signode += addnodes.desc_addname(value, " = " + value)
        elif match['value']:
            signode += addnodes.desc_addname('{ ... }', ' = { ... }')

        #signature += "-" + self.objtype

        if container_class_name:
            name = container_class_name + '.' + name
            signature = container_class_name + '.' + signature

        return name, signature, True


class KotlinXRefRole(XRefRole):

    def __init__(self,tipe):
        super(KotlinXRefRole, self).__init__()
        self.tipe = tipe

    def process_link(self, env, refnode, has_explicit_title, title, target):
        if "." in target:
            return title, target
        return title, self.tipe+" "+target


type_order = ['class', 'data_class', 'enum_class', 'protocol', 'extension']

class KotlinModuleIndex(Index):
    """
    Index subclass to provide the Kotlin module index.
    """

    name = 'modindex'
    localname = l_('Kotlin Module Index')
    shortname = l_('Index')

    @staticmethod
    def indexsorter(a):
        global type_order
        for i, t in enumerate(type_order):
            if a[0].startswith(t):
                return '{:04d}{}'.format(i, a[0])
        return a[0]

    @staticmethod
    def sigsorter(a):
        global type_order

        start = 0
        for t in type_order:
            if a[3].startswith(t):
                start = len(t) + 1
                break
        return a[3][start]

    def generate(self, docnames=None):
        global type_order
        content = []
        collapse = 0

        entries = []
        for refname, (docname, typ, signature) in _iteritems(self.domain.data['objects']):
            info = typ.replace("_", " ")
            entries.append((
                refname,
                0,
                docname,
                signature,
                info,
                '',
                ''
            ))

        entries = sorted(entries, key=self.sigsorter)
        current_list = []
        current_key = None
        for entry in entries:
            start = 0
            for t in type_order:
                if entry[3].startswith(t):
                    start = len(t) + 1
                    break

            if entry[3][start].upper() != current_key:
                if len(current_list) > 0:
                    content.append((current_key, current_list))
                current_key = entry[3][start].upper()
                current_list = []
            current_list.append(entry)
        content.append((current_key, current_list))

        result = []
        for key, entries in content:
            e = sorted(entries, key=self.indexsorter)
            result.append((key, e))

        return result, collapse


class KotlinDomain(Domain):
    """Kotlin language domain."""
    name = 'kotlin'
    label = 'Kotlin'
    object_types = {
        'function':        ObjType(l_('function'),            'function',     'obj'),
        'fun':             ObjType(l_('fun'),                 'fun',          'obj'),
        'static_fun':      ObjType(l_('static fun'),          'static_fun',   'obj'),
        'class_method':    ObjType(l_('class method'),        'class_method', 'obj'),
        'object':          ObjType(l_('object'),              'object',       'obj'),
        'class':           ObjType(l_('class'),               'class',        'obj'),
        'enum_class':      ObjType(l_('enum class'),          'enum_class',   'obj'),
        'enum_case':       ObjType(l_('enum case'),           'enum_case',    'obj'),
        'data_class':      ObjType(l_('data class'),          'data_class',   'obj'),
        'init':            ObjType(l_('initializer'),         'init',         'obj'),
        'constructor':     ObjType(l_('constructor'),         'constructor',  'obj'),
        'protocol':        ObjType(l_('protocol'),            'protocol',     'obj'),
        'extension':       ObjType(l_('extension'),           'extension',    'obj'),
        'default_impl':    ObjType(l_('default implementation'),'default_impl','obj'),
        'val':             ObjType(l_('constant'),            'val',          'obj'),
        'var':             ObjType(l_('variable'),            'var',          'obj'),
    }

    directives = {
        'function':        KotlinClassmember,
        'fun':             KotlinClassmember,
        'static_fun':      KotlinClassmember,
        'class_method':    KotlinClassmember,
        'object':          KotlinClass,
        'class':           KotlinClass,
        'enum_class':      KotlinClass,
        'enum_case':       KotlinEnumCase,
        'data_class':      KotlinClass,
        'init':            KotlinClassmember,
        'constructor':     KotlinClassmember,
        'protocol':        KotlinClass,
        'extension':       KotlinClass,
        'default_impl':    KotlinClass,
        'val':             KotlinClassIvar,
        'var':             KotlinClassIvar,
    }

    roles = {
        'function':      KotlinXRefRole("function"),
        'fun':           KotlinXRefRole("fun"),
        'static_fun':    KotlinXRefRole("static_fun"),
        'object':        KotlinXRefRole("object"),
        'class':         KotlinXRefRole("class"),
        'enum_class':    KotlinXRefRole("enum_class"),
        'enum_case':     KotlinXRefRole("enum_case"),
        'data_class':    KotlinXRefRole("data_class"),
        'init':          KotlinXRefRole("init"),
        'constructor':   KotlinXRefRole("constructor"),
        'class_method':  KotlinXRefRole("class_method"),
        'protocol':      KotlinXRefRole("protocol"),
        'extension':     KotlinXRefRole("extension"),
        'default_impl':  KotlinXRefRole("default_impl"),
        'val':           KotlinXRefRole("let"),
        'var':           KotlinXRefRole("var"),
    }
    initial_data = {
        'objects': {},  # fullname -> docname, objtype
    }
    indices = [
        KotlinModuleIndex,
    ]

    def clear_doc(self, docname):
        for fullname, (fn, _, _) in list(self.data['objects'].items()):
            if fn == docname:
                del self.data['objects'][fullname]

    def resolve_xref(self, env, fromdocname, builder,
                     typ, target, node, contnode):
        if target.endswith('?') or target.endswith('!'):
            test_target = target[:-1]
        elif target.startswith('[') and target.endswith(']'):
            test_target = target[1:-1]
        else:
            test_target = target

        point_pos = test_target.find('.')
        if point_pos != -1:
            test_target = test_target[point_pos:]

        for refname, (docname, type, signature) in _iteritems(self.data['objects']):
            for to in type_order:
                if refname == to + ' ' + test_target:
                    node = make_refnode(builder, fromdocname, docname, signature, contnode, test_target)
                    return node
        if test_target in kotlin_reserved:
            node = nodes.reference(test_target, test_target)
            node['refuri'] = formExternalUrl(test_target)
            node['reftitle'] = test_target

            return node

        return None

    def get_objects(self):
        for refname, (docname, type, signature) in _iteritems(self.data['objects']):
            yield (refname, refname, type, docname, refname, 1)

def make_index(app,*args):
    from .autodoc import build_index
    build_index(app)

def setup(app):
    app.add_domain(KotlinDomain)
    # app.add_config_value('kotlin_search_path', ['../src'], 'env')
