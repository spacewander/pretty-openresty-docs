#!/usr/bin/env python
# coding: utf-8
"""
Build dash docset for OpenResty.
See https://kapeli.com/docsets for how to build docset.
"""
from __future__ import unicode_literals
from collections import namedtuple
from shutil import rmtree
from sys import stdout
from threading import Thread, Lock
import codecs
import logging
import os
import sqlite3

# pip install -r requirements.txt
from bs4 import BeautifulSoup
from requests.exceptions import HTTPError
from requests.utils import quote
import requests

Resource = namedtuple('Resource', ['filename', 'url'])
Entry = namedtuple('Entry', ['name', 'type', 'path'])
Doc = namedtuple('Doc', ['name', 'url', 'sections'])


def build_url_from_repo_name(repo, readme='README.markdown'):
    return 'https://github.com/openresty/%s/blob/master/%s' % (repo, readme)

# List all docs of projects distributed with OpenResty tar package.
# Not all docs have Chinese translation, so don't consider it now.
DOCS = [
    Doc('lua-nginx-module', build_url_from_repo_name('lua-nginx-module'),
        ['directives', 'nginx-api-for-lua']),
    Doc('lua-resty-core', build_url_from_repo_name('lua-resty-core'),
        ['api-implemented']),
    Doc('lua-resty-lrucache', build_url_from_repo_name('lua-resty-lrucache'),
        ['methods']),
    Doc('lua-resty-upload', build_url_from_repo_name('lua-resty-upload'),
        []),
    Doc('lua-resty-upstream-healthcheck',
        build_url_from_repo_name('lua-resty-upstream-healthcheck'),
        ['methods']),
    Doc('lua-resty-mysql', build_url_from_repo_name('lua-resty-mysql'),
        ['methods']),
    Doc('lua-resty-memcached', build_url_from_repo_name('lua-resty-memcached'),
        ['methods']),
    Doc('lua-resty-redis', build_url_from_repo_name('lua-resty-redis'),
        ['methods']),
    Doc('lua-resty-string', build_url_from_repo_name('lua-resty-string'), []),
    Doc('lua-upstream-nginx-module',
        build_url_from_repo_name('lua-upstream-nginx-module', 'README.md'),
        ['functions']),
    Doc('lua-redis-parser', build_url_from_repo_name('lua-redis-parser'),
        ['functions', 'constants']),
    Doc('echo-nginx-module', build_url_from_repo_name('echo-nginx-module'),
        ['content-handler-directives', 'filter-directives', 'variables']),
    Doc('xss-nginx-module',
        build_url_from_repo_name('xss-nginx-module', 'README.md'),
        ['directives']),
    Doc('resty-cli', build_url_from_repo_name('resty-cli', 'README.md'),
        []),
    Doc('array-var-nginx-module',
        build_url_from_repo_name('array-var-nginx-module', 'README.md'),
        ['directives']),
    Doc('drizzle-nginx-module',
        build_url_from_repo_name('drizzle-nginx-module'),
        ['directives', 'variables']),
    Doc('headers-more-nginx-module',
        build_url_from_repo_name('headers-more-nginx-module'),
        ['directives']),
    Doc('srcache-nginx-module',
        build_url_from_repo_name('srcache-nginx-module'),
        ['directives', 'variables']),
    Doc('encrypted-session-nginx-module',
        build_url_from_repo_name('encrypted-session-nginx-module', 'README.md'),
        ['directives']),
    Doc('rds-json-nginx-module',
        build_url_from_repo_name('rds-json-nginx-module', 'README.md'),
        ['directives']),
    Doc('redis2-nginx-module', build_url_from_repo_name('redis2-nginx-module'),
        ['directives']),
    Doc('memc-nginx-module', build_url_from_repo_name('memc-nginx-module'),
        ['memcached-commands-supported', 'directives']),
    Doc('rds-csv-nginx-module',
        build_url_from_repo_name('rds-csv-nginx-module', 'README.md'),
        ['directives']),
    Doc('set-misc-nginx-module',
        build_url_from_repo_name('set-misc-nginx-module'),
        ['directives']),
    # special cases below
    Doc('lua-resty-websocket', build_url_from_repo_name('lua-resty-websocket'),
        ['resty.websocket.server', 'resty.websocket.client',
        'resty.websocket.protocol']),
]


def get_text_from_url(url):
    res = requests.get(url)
    if res.status_code in (200, 304):
        return res.text
    raise HTTPError(res)


def get_type(section):
    if section == 'constants':
        return 'Constant'
    elif section == 'directives':
        return 'Directive'
    elif section == 'methods':
        return 'Method'
    elif section == 'variables':
        return 'Variable'
    elif section == 'memcached-commands-supported':
        return 'Command'
    else:
        return 'Function'


def parse_doc_from_html(html, metadata):
    """
    Parse the document part of html page according to the metadata.
    Return:
    1. a list of Entries
    2. a set of Resources
    3. a html snippet with anchor added, resource urls rewritten, useless parts removed
    """
    soup = BeautifulSoup(html, 'html.parser')

    # rewrite all css url to './Assets/' and extract them as list of Resources
    resources = set()
    rewritten_head = '<title>%s</title>\n' % metadata.name
    for css in soup.findAll('link', rel='stylesheet'):
        link = css['href'].rpartition('/')[-1]
        resources.add(Resource(filename=link, url=css['href']))
        new_css = soup.new_tag('link')
        new_css['rel'] = 'stylesheet'
        new_css['href'] = link
        rewritten_head += str(new_css)

    entries = []
    readme = soup.find(id='readme')
    base_path = './%s.html' % metadata.name

    def handle_each_section(section_header, section_type, entry_header, namespace):
        for tag in section_header.next_siblings:
            # not all siblings are tags
            if not hasattr(tag, 'name'):
                continue
            if tag.name == section_header.name:
                break
            if tag.name == entry_header:
                api_name = next(tag.stripped_strings)
                tag_anchor = next(tag.children)
                entry_path = base_path + tag_anchor['href']
                entries.append(Entry(
                    name=api_name, type=section_type, path=entry_path))
                # insert an anchor to support table of contents
                anchor = soup.new_tag('a')
                anchor['name'] = '//apple_ref/cpp/%s/%s' % (
                    section_type, quote(api_name))
                anchor['class'] = 'dashAnchor'
                tag_anchor.insert_before(anchor)

    if metadata.name == 'lua-resty-websocket':
        for section in metadata.sections:
            section_path = section.replace('.', '')
            entries.append(Entry(
                name=section, type='Class', path=base_path + '#' + section_path))
            section_header = soup.find(
                id=('user-content-' + section_path)).parent
            handle_each_section(section_header, 'Method', 'h4', section)
    else:
        for section in metadata.sections:
            section_type = get_type(section)
            section_header = soup.find(id=('user-content-' + section)).parent
            # all entries' header is one level lower than section's header
            entry_header = 'h' + str(int(section_header.name[1]) + 1)
            handle_each_section(
                section_header, section_type, entry_header, metadata.name)

    # remove user-content- to enable fragment href
    start_from = len('user-content-')
    for anchor in soup.findAll('a'):
        if 'id' in anchor.attrs:
            anchor['id'] = anchor['id'][start_from:]

    # support online redirect
    comment = '<!-- Online page at %s -->' % metadata.url
    doc = """<!doctype html>
        <html>%s
          <head>
            %s
          </head>
          <body>
            %s
          </body>
        </html>""" % (comment, rewritten_head, readme)
    return entries, resources, doc


def download_resources(resources,
                       path='OpenResty.docset/Contents/Resources/Documents/'):
    for resource in resources:
        resource_path = path + resource.filename
        with open(resource_path, 'w') as f:
            f.write(get_text_from_url(resource.url))


def build_docset_structure():
    path = 'OpenResty.docset/Contents/Resources/Documents'
    if os.path.isdir('OpenResty.docset'):
        rmtree('OpenResty.docset')
    os.makedirs(path)
    write_info_plist()
    write_sql_schema()


def write_info_plist(fn='OpenResty.docset/Contents/Info.plist'):
    content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key>
    <string>{0}</string>
    <key>CFBundleName</key>
    <string>{1}</string>
    <key>DocSetPlatformFamily</key>
    <string>{0}</string>
    <key>isDashDocset</key>
    <true/>
    <key>DashDocSetFamily</key>
    <string>dashtoc</string>
    <key>dashIndexFilePath</key>
    <string>{2}</string>
</dict>
</plist>""".format('openresty', 'OpenResty', 'lua-nginx-module.html')
    with open(fn, 'w') as f:
        f.write(content)


def write_sql_schema(fn='OpenResty.docset/Contents/Resources/docSet.dsidx'):
    db = sqlite3.connect(fn)
    cur = db.cursor()
    try:
        cur.execute('DROP TABLE searchIndex;')
    except Exception:
        pass
    cur.execute('CREATE TABLE searchIndex(id INTEGER PRIMARY KEY, name TEXT, type TEXT, path TEXT);')
    cur.execute('CREATE UNIQUE INDEX anchor ON searchIndex (name, type, path);')
    db.commit()
    db.close()


def insert_entries(entries,
                   fn='OpenResty.docset/Contents/Resources/docSet.dsidx'):
    db = sqlite3.connect(fn)
    cur = db.cursor()
    values = ["('%s', '%s', '%s')" % (entry.name, entry.type, entry.path) for entry in entries]
    data = ','.join(values)
    # need sqlite 3.7+ to support batch insert
    cur.execute("INSERT INTO searchIndex(name, type, path) VALUES %s" % data)
    db.commit()
    db.close()


class Worker(Thread):
    lock = Lock()
    path = 'OpenResty.docset/Contents/Resources/Documents/'

    def create_logger():
        logger = logging.getLogger(__name__.split('.')[0])
        logger.setLevel(getattr(logging, 'INFO'))
        FORMAT = '[%(levelname)s] %(threadName)s %(message)s'
        formatter = logging.Formatter(fmt=FORMAT)
        handler = logging.StreamHandler(stdout)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger
    logger = create_logger()

    @classmethod
    def info(cls, *args):
        cls.logger.info(*args)

    def __init__(self):
        super(Worker, self).__init__()
        self.resources = set()
        self.entries = []

    def run(self):
        while True:
            with Worker.lock:
                if len(DOCS) == 0:
                    return
                doc = DOCS.pop()
            Worker.info('Download Readme of %s' % doc.name)
            html = get_text_from_url(doc.url)
            doc_path = Worker.path + doc.name + '.html'
            Worker.info('Parse Readme of %s' % doc.name)
            entries, resources, text = parse_doc_from_html(html, doc)
            self.resources |= resources
            self.entries.extend(entries)
            with codecs.open(doc_path, 'w', encoding='utf-8') as f:
                f.write(text)
            Worker.info('Finish %s' % doc.name)


if __name__ == '__main__':
    build_docset_structure()
    workers = [Worker() for i in range(5)]
    for worker in workers:
        worker.start()
    entries = []
    resources = set()
    for worker in workers:
        worker.join()
        entries.extend(worker.entries)
        resources |= worker.resources
    download_resources(resources)

    # mark entries have the same names
    entry_used_time = {}
    for entry in entries:
        entry_used_time[entry.name] = entry_used_time.setdefault(entry.name, 0) + 1
    new_entries = []
    for entry in entries:
        if entry_used_time[entry.name] > 1:
            name = entry.name + '(%s)' % entry.path[2:entry.path.find('.html')]
        else:
            name = entry.name
        new_entries.append(Entry(name=name, type=entry.type, path=entry.path))
    insert_entries(new_entries)
