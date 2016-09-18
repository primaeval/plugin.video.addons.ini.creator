from xbmcswift2 import Plugin
from xbmcswift2 import actions
import xbmc,xbmcaddon,xbmcvfs,xbmcgui
import re
from rpc import RPC
import requests
import random

from datetime import datetime,timedelta
import time
#import urllib
import HTMLParser
import xbmcplugin
#import xml.etree.ElementTree as ET
#import sqlite3
import os
#import shutil
#from rpc import RPC
from types import *

plugin = Plugin()
big_list_view = False

def log2(v):
    xbmc.log(repr(v))

def log(v):
    xbmc.log(re.sub(',',',\n',repr(v)))

def get_icon_path(icon_name):
    addon_path = xbmcaddon.Addon().getAddonInfo("path")
    return os.path.join(addon_path, 'resources', 'img', icon_name+".png")


def remove_formatting(label):
    label = re.sub(r"\[/?[BI]\]",'',label)
    label = re.sub(r"\[/?COLOR.*?\]",'',label)
    return label

@plugin.route('/addon/<id>')
def addon(id):
    addon = plugin.get_storage(id)
    items = []
    for name in sorted(addon):
        url = addon[name]
        items.append(
        {
            'label': name,
            'path': url,
            'thumbnail':get_icon_path('tv'),
            'is_playable':True,
        })
    return items

@plugin.route('/player')
def player():
    addons = plugin.get_storage("addons")
    for a in addons.keys():
        add = plugin.get_storage(a)
        add.clear()
    addons.clear()

    name = plugin.get_setting('addons.file')
    f = xbmcvfs.File(name,"rb")
    lines = f.read().splitlines()

    addon = None
    for line in lines:
        if line.startswith('['):
            a = line.strip('[]')
            addons[a] = a
            addon = plugin.get_storage(a)
            addon.clear()
        elif "=" in line:
            (name,url) = line.split('=',1)
            if url and addon is not None:
                addon[name] = url

    items = []
    for id in sorted(addons):
        items.append(
        {
            'label': id,
            'path': plugin.url_for('addon',id=id),
            'thumbnail':get_icon_path('tv'),
        })
    return items

@plugin.route('/play/<url>')
def play(url):
    xbmc.executebuiltin('PlayMedia(%s)' % url)

@plugin.route('/add_folder/<id>/<path>')
def add_folder(id,path):
    folders = plugin.get_storage('folders')
    #ids = plugin.get_storage('ids')
    folders[path] = id
    #ids[id] = id
    xbmc.executebuiltin('Container.Refresh')

@plugin.route('/remove_folder/<id>/<path>')
def remove_folder(id,path):
    folders = plugin.get_storage('folders')
    del folders[path]
    xbmc.executebuiltin('Container.Refresh')

@plugin.route('/folder/<id>/<path>')
def folder(id,path):
    folders = plugin.get_storage('folders')
    response = RPC.files.get_directory(media="files", directory=path, properties=["thumbnail"])
    files = response["files"]
    dirs = dict([[remove_formatting(f["label"]), f["file"]] for f in files if f["filetype"] == "directory"])
    links = {}
    thumbnails = {}
    for f in files:
        if f["filetype"] == "file":
            label = remove_formatting(f["label"])
            file = f["file"]
            while (label in links):
                label = "%s." % label
            links[label] = file
            thumbnails[label] = f["thumbnail"]

    items = []

    for label in sorted(dirs):
        path = dirs[label]
        context_items = []
        context_items.append(('Subscribe', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_folder, id=id, path=path))))
        context_items.append(('Unsubscribe', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_folder, id=id, path=path))))
        if path in folders:
            fancy_label = "[COLOR yellow][B]%s[/B][/COLOR] " % label
        else:
            fancy_label = "[B]%s[/B]" % label
        items.append(
        {
            'label': fancy_label,
            'path': plugin.url_for('folder',id=id, path=path),
            'thumbnail': get_icon_path('tv'),
            'context_menu': context_items,
        })

    for label in sorted(links):
        items.append(
        {
            'label': label,
            'path': plugin.url_for('play',url=links[label]),
            'thumbnail': thumbnails[label],
        })
    return items

@plugin.route('/subscribe')
def subscribe():
    folders = plugin.get_storage('folders')
    ids = {}
    for folder in folders:
        id = folders[folder]
        ids[id] = id
    all_addons = []
    for type in ["xbmc.addon.video", "xbmc.addon.audio"]:
        response = RPC.addons.get_addons(type=type,properties=["name", "thumbnail"])
        if "addons" in response:
            found_addons = response["addons"]
            all_addons = all_addons + found_addons

    seen = set()
    addons = []
    for addon in all_addons:
        if addon['addonid'] not in seen:
            addons.append(addon)
        seen.add(addon['addonid'])

    items = []
    addons = sorted(addons, key=lambda addon: remove_formatting(addon['name']).lower())
    for addon in addons:
        label = addon['name']
        id = addon['addonid']
        path = "plugin://%s" % id
        context_items = []
        context_items.append(('Subscribe', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_folder, id=id, path=path))))
        context_items.append(('Unsubscribe', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_folder, id=id, path=path))))
        if id in ids:
            fancy_label = "[COLOR yellow][B]%s[/B][/COLOR] " % label
        else:
            fancy_label = "[B]%s[/B]" % label
        items.append(
        {
            'label': fancy_label,
            'path': plugin.url_for('folder',id=id, path=path),
            'thumbnail': get_icon_path('tv'),
            'context_menu': context_items,
        })
    return items

@plugin.route('/update')
def update():
    folders = plugin.get_storage('folders')
    streams = {}

    for folder in folders:
        path = folder
        id = folders[folder]
        if not id in streams:
            streams[id] = {}
        response = RPC.files.get_directory(media="files", directory=path, properties=["thumbnail"])
        files = response["files"]
        links = {}
        thumbnails = {}
        for f in files:
            if f["filetype"] == "file":
                label = remove_formatting(f["label"])
                file = f["file"]
                while (label in links):
                    label = "%s." % label
                links[label] = file
                thumbnails[label] = f["thumbnail"]
                streams[id][label] = file

    path = plugin.get_setting("addons.folder")
    filename = os.path.join(path,"addons.ini")
    f = xbmcvfs.File(filename,"wb")
    for id in streams:
        line = "[%s]\n" % id
        f.write(line.encode("utf8"))
        channels = streams[id]
        for channel in channels:
            url = channels[channel]
            line = "%s=%s\n" % (channel,url)
            f.write(line.encode("utf8"))
    f.close()



@plugin.route('/')
def index():
    items = []
    items.append(
    {
        'label': "Play",
        'path': plugin.url_for('player'),
        'thumbnail':get_icon_path('tv'),
    })
    items.append(
    {
        'label': "Subscribe",
        'path': plugin.url_for('subscribe'),
        'thumbnail':get_icon_path('tv'),
    })
    items.append(
    {
        'label': "Update",
        'path': plugin.url_for('update'),
        'thumbnail':get_icon_path('tv'),
    })
    return items

if __name__ == '__main__':
    plugin.run()
    if big_list_view == True:
        view_mode = int(plugin.get_setting('view_mode'))
        plugin.set_view_mode(view_mode)