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

import argparse
import os
from indexer import KotlinFileIndex, KotlinObjectIndex

parser = argparse.ArgumentParser(description='Create reStructured text documentation from Kotlin code.')
parser.add_argument('source_path', type=str, help='Path to Kotlin files')
parser.add_argument('documentation_path', type=str, help='Path to generate the documentation in')
parser.add_argument('--private', dest='private', action='store_true', help='Include private and internal members', required=False, default=False)
parser.add_argument('--overwrite', dest='overwrite', action='store_true', help='Overwrite existing documentation', required=False, default=False)
parser.add_argument('--undoc-members', dest='undoc', action='store_true', help='Include members without documentation block', required=False, default=False)
parser.add_argument('--no-members', dest='members', action='store_false', help='Do not include member documentation', required=False, default=True)
parser.add_argument('--no-index', dest='noindex', action='store_true', help='Do not add anything to the index', required=False, default=False)
parser.add_argument('--no-index-members', dest='noindex_members', action='store_true', help='Do not add members to the index, just the toplevel items', required=False, default=False)

# TODO: https://kotlinlang.org/api/latest/jvm/stdlib/kotlin/-string/index.html
# TODO: https://kotlinlang.org/api/latest/jvm/stdlib/kotlin/-unit/index.html

def main():
    args = parser.parse_args()
    source_path = os.path.abspath(args.source_path)
    file_index = KotlinFileIndex([source_path])

    try:
        os.makedirs(args.documentation_path)
    except:
        pass

    # check for overwrite
    for file, members in file_index.by_file().items():
        destfile = get_dest_file(file, args.source_path, args.documentation_path)
        if os.path.exists(destfile) and not args.overwrite:
            print("""ERROR: {} already exists, to overwrite existing
                     documentation use the '--overwrite' flag""".format(file))
            exit(1)

    for file, members in file_index.by_file().items():
        destfile = get_dest_file(file, args.source_path, args.documentation_path)
        print("Writing documentation for '{}'...".format(os.path.relpath(file, source_path)))
        try:
            os.makedirs(os.path.dirname(destfile))
        except:
            pass
        with open(destfile, "w") as fp:
            heading = 'Documentation for {}'.format(os.path.relpath(file, source_path))
            fp.write(heading + '\n')
            fp.write(('=' * len(heading)) + '\n\n\n')
            document(members, args, file, fp, '')


def get_dest_file(filename, search_path, doc_path):
    rel = os.path.relpath(filename, search_path)
    return os.path.join(doc_path, rel)[:-3] + '.rst'

def document(members, args, file, fp, indent):
    for member in members:
        add = True
        if args.undoc is False and len(member['docstring']) == 0:
            add = False
        if args.private is False and member['scope'] != 'public':
            add = False
        if not add:
            # print 'Skip documentation for ' + member['name']
            continue

        doc = KotlinFileIndex.documentation(
            member,
            indent=indent,
            nodocstring=args.undoc,
            noindex=args.noindex
        )
        for line in doc:
            content = indent + line + "\n"
            fp.write(content)

        if args.members:
            document_member(member, args, file, fp, indent)
        fp.write('\n')


def document_member(parent, args, file, fp, indent):
    if 'members' not in parent:
        return
    for member in parent['members'].index:
        add = True
        
        # Always document enum cases
        if args.undoc is False and len(member['docstring']) == 0 and member['type'] != 'enum_case':
            add = False
        if args.private is False and member['scope'] != 'public':
            add = False
        if not add:
            continue

        doc = KotlinObjectIndex.documentation(
            member,
            indent=indent,
            nodocstring=False,
            noindex=(args.noindex or args.noindex_members)
        )
        for line in doc:
            content = indent + '   ' + line + "\n"
            fp.write(content)

    document(parent['children'], args, file, fp, indent + '   ')


if __name__ == "__main__":
    main()
