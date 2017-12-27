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
    size = len(entries)
    if size == 0:
        return
    entries = sorted(entries, key=lambda x: x[2])
    entries_in_previous_doc = []
    current_doc = entries[0][2].split('#')[0]
    start = 0
    for i in range(size + 1):
        if i < size:
            doc_name, _ = entries[i][2].split('#')
            # Only print when new doc is met or the last doc is met
            if doc_name == current_doc:
                continue
            entries_in_previous_doc = entries[start:i]
            start = i
        else:
            entries_in_previous_doc = entries[start:]
        print("%s: %d" % (os.path.splitext(current_doc)[0],
                          len(entries_in_previous_doc)))
        max_len = [0, 0, 0]
        for entry in entries_in_previous_doc:
            for j, e in enumerate(entry):
                max_len[j] = max(max_len[j], len(e))
        format_str = '\t' + '\t'.join(('%%-%ds' % length)
                                      for length in max_len)
        for entry in entries_in_previous_doc:
            print(format_str % entry)
        print('')
        current_doc = doc_name


if __name__ == '__main__':
    argc = len(sys.argv)
    if (argc == 2 or argc == 3) and sys.argv[1] not in ('-h', '--help'):
        if argc == 3:
            old = get_entries(sys.argv[1])
            new = get_entries(sys.argv[2])
            diff(old, new)
        else:
            entries = get_entries(sys.argv[1])
            diff(set(), entries)
    else:
        print("Diff entries with given sqlite3 db")
        print("Usage: %s [old_sqlite.db] new_sqlite.db")
