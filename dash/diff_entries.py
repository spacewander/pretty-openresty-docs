#!/usr/bin/env python
# coding: utf-8

# Diff entries from two sqlite3 db
import os
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
    entries_in_previous_doc = []
    current_doc = entries[0][2].split('#')[0]
    start = 0
    for i in range(0, len(entries)):
        doc_name, _ = entries[i][2].split('#')
        if doc_name != current_doc:
            entries_in_previous_doc = entries[start:i]
            start = i
            print("%s: %d" % (
                os.path.splitext(current_doc)[0], len(entries_in_previous_doc)))
            for e in entries_in_previous_doc:
                print('\t%s' % e[0])
            print('')
            current_doc = doc_name
    entries_in_previous_doc = entries[start:]
    print("%s: %d" % (
        os.path.splitext(current_doc)[0], len(entries_in_previous_doc)))
    for e in entries_in_previous_doc:
        print('\t%s' % e[0])
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
