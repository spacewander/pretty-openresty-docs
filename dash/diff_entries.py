#!/usr/bin/env python
# coding: utf-8

# Diff entries from two sqlite3 db
import sqlite3
import sys

def get_entries(db_name):
    db = sqlite3.connect(db_name)
    cur = db.cursor()
    cur.execute("SELECT name, type, path from searchIndex")
    entries = cur.fetchall()
    db.commit()
    db.close()
    return set(entries)

def diff(old, new):
    add = new - old
    rem = old - new
    print("Added: %d" % len(add))
    print_merged_entries(add)
    print("Removed: %d" % len(rem))
    print_merged_entries(rem)

def print_merged_entries(entries):
    if len(entries) == 0:
        return
    entries = sorted(entries, key=lambda x: x[2])
    namespace_entries = []
    current_namespace = entries[0][2].split('#')[0][:-5]
    for i in entries:
        namespace, entry = i[2].split('#')
        namespace = namespace[:-5] # remove .html
        namespace_entries.append(entry)
        if namespace != current_namespace:
            print("%s: %d" % (current_namespace, len(namespace_entries)))
            for e in namespace_entries:
                print('\t%s' % e)
            print('')
            current_namespace = namespace
            namespace_entries = []
    print("%s: %d" % (current_namespace, len(namespace_entries)))
    for e in namespace_entries:
        print('\t%s' % e)
    print('')

if __name__ == '__main__':
    argc = len(sys.argv)
    if argc == 3:
        old = get_entries(sys.argv[1])
        new = get_entries(sys.argv[2])
        diff(old, new)
    elif argc == 2:
        entries = get_entries(sys.argv[1])
        diff(set(), entries)
    else:
        print("Diff entries with given sqlite3 db")
        print("Usage: %s [old_sqlite.db] new_sqlite.db")
