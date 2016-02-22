#!/usr/bin/env python
# coding: utf-8
"""
Build dash docset for OpenResty.
See https://kapeli.com/docsets for how to build docset.
"""
from collections import namedtuple
import codecs
import os
import sqlite3
import urllib

# pip install -r requirements.txt
from bs4 import BeautifulSoup
from requests.exceptions import HTTPError
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
        ['memcached_commands_supported', 'directives']),
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


def get_file_from_url(url):
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
    else:
        return 'Function'


def parse_doc_from_html(html, metadata):
    """
    Parse the document part of html page according to the metadata.
    Return:
    1. a list of Entries
    2. a list of Resources
    3. a html snippet with anchor added, resource urls rewritten, useless parts removed
    """
    soup = BeautifulSoup(html, 'html.parser')

    # rewrite all css url to './Assets/' and extract them as list of Resources
    resources = []
    rewritten_head = ''
    for stylesheet in soup.findAll('link', rel='stylesheet'):
        css = stylesheet['href'].rpartition('/')[-1]
        resources.append(Resource(filename=css, url=stylesheet['href']))
        stylesheet['href'] = css
        rewritten_head += str(stylesheet)

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
                # use '#' to separate api name and its module
                entry_name = namespace + '#' + next(tag.stripped_strings)
                tag_anchor = next(tag.children)
                entry_path = base_path + tag_anchor['href']
                entries.append(Entry(
                    name=entry_name, type=section_type, path=entry_path))
                # insert an anchor to support table of contents
                anchor = soup.new_tag('a')
                anchor['name'] = '//apple_ref/%s/%s' % (
                    section_type, urllib.quote_plus(entry_name))
                anchor['class'] = 'dashAnchor'
                tag_anchor.insert_before(anchor)

    if metadata.name == 'lua-resty-websocket':
        for section in metadata.sections:
            section_header = soup.find(
                id=('user-content-' + section.replace('.', ''))).parent
            handle_each_section(section_header, 'Method', 'h4', section)
    else:
        for section in metadata.sections:
            section_type = get_type(section)
            section_header = soup.find(id=('user-content-' + section)).parent
            # all entries' header is one level lower than section's header
            entry_header = 'h' + str(int(section_header.name[1]) + 1)
            handle_each_section(
                section_header, section_type, entry_header, metadata.name)

    # support online redirect
    comment = '!-- Online page at %s -->' % metadata.url
    doc = """
        <!DOCTYPE html>
        <html lang='en'>%s
          <head>
            <meta charset='UTF-8'>
            %s
          </head>
          <body>
            %s
          </body>
        </html>
    """ % (comment, rewritten_head, readme)
    print(entries)
    return entries, resources, doc


def build_docset_structure():
    docset = 'OpenResty.docset'
    path = '%s/Contents/Resources/Documents' % docset
    if not os.path.isdir(path):
        os.makedirs(path)
    write_info_plist_to('%s/Contents/Info.plist' % docset)
    write_sql_schema_to('%s/Contents/Resources/docSet.dsidx' % docset)


def write_info_plist_to(fn):
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


def write_sql_schema_to(fn):
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

if __name__ == '__main__':
    # html = get_file_from_url(DOCS[-1].url)
    # with codecs.open('/home/lzx/doc/' + DOCS[-1].name, 'w', encoding='utf-8') as f:
        # f.write(html)
    with codecs.open('/home/lzx/doc/' + DOCS[-1].name) as f:
        html = f.read()
    entries, resources, doc = parse_doc_from_html(html, DOCS[-1])
    # print(doc)
    # build_docset_structure()
