from xbmcswift2 import Plugin
from xbmcswift2 import actions
import xbmc,xbmcaddon,xbmcvfs,xbmcgui
import re
from rpc import RPC
import requests
import random
import sqlite3
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
    if not plugin.get_setting('addons.folder'):
        dialog = xbmcgui.Dialog()
        dialog.notification("addons.ini Creator", "Set Folder",xbmcgui.NOTIFICATION_ERROR )
        xbmcaddon.Addon ('plugin.video.addons.ini.creator').openSettings()

    addons = plugin.get_storage("addons")
    for a in addons.keys():
        add = plugin.get_storage(a)
        add.clear()
    addons.clear()

    folder = plugin.get_setting("addons.folder")
    file = plugin.get_setting("addons.file")
    filename = os.path.join(folder,file)
    f = xbmcvfs.File(filename,"rb")
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

@plugin.route('/pvr_subscribe')
def pvr_subscribe():
    plugin.set_setting("pvr.subscribe","true")
    xbmc.executebuiltin('Container.Refresh')

@plugin.route('/pvr_unsubscribe')
def pvr_unsubscribe():
    plugin.set_setting("pvr.subscribe","false")
    xbmc.executebuiltin('Container.Refresh')

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

@plugin.route('/clear')
def clear():
    folders = plugin.get_storage('folders')
    folders.clear()

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
        if path in folders:
            fancy_label = "[COLOR yellow][B]%s[/B][/COLOR] " % label
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Unsubscribe', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_folder, id=id, path=path))))
        else:
            fancy_label = "[B]%s[/B]" % label
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Subscribe', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_folder, id=id, path=path))))
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

@plugin.route('/pvr')
def pvr():
    path = xbmc.translatePath("special://profile/Database/TV29.db")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM channels')
    clients = {}
    channels = {}
    for row in c:
        name = row["sChannelName"]
        id = row["iUniqueId"]
        client = row["iClientId"]
        clients[client] = ""
        channels[id] = (name,client)

    path = xbmc.translatePath("special://profile/Database/Addons20.db")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    for client in clients:
        c.execute('SELECT addonID FROM addon WHERE id = ?', [client])
        row = c.fetchone()
        id = row["addonID"]
        clients[client] = id
    c.close()

    items = []
    for id in sorted(channels, key=lambda x: channels[x][0]):
        (name,client) = channels[id]
        addon = clients[client]
        url = "pvr://channels/tv/All channels/%s_%s.pvr" % (addon,id)
        items.append(
        {
            'label': name,
            'path': url,
            'is_playable': True,
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

    pvr = plugin.get_setting('pvr.subscribe')
    context_items = []
    label = "PVR"
    if pvr == "true":
        fancy_label = "[COLOR yellow][B]%s[/B][/COLOR] " % label
        context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Unsubscribe', 'XBMC.RunPlugin(%s)' % (plugin.url_for(pvr_unsubscribe))))
    else:
        fancy_label = "[B]%s[/B]" % label
        context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Subscribe', 'XBMC.RunPlugin(%s)' % (plugin.url_for(pvr_subscribe))))
    items.append(
    {
        'label': fancy_label,
        'path': plugin.url_for('pvr'),
        'thumbnail':get_icon_path('tv'),
        'context_menu': context_items,
    })

    addons = sorted(addons, key=lambda addon: remove_formatting(addon['name']).lower())
    for addon in addons:
        label = addon['name']
        id = addon['addonid']
        path = "plugin://%s" % id
        context_items = []
        if id in ids:
            fancy_label = "[COLOR yellow][B]%s[/B][/COLOR] " % label
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Unsubscribe', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_folder, id=id, path=path))))
        else:
            fancy_label = "[B]%s[/B]" % label
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Subscribe', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_folder, id=id, path=path))))
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
    if not plugin.get_setting('addons.folder'):
        dialog = xbmcgui.Dialog()
        dialog.notification("addons.ini Creator", "Set Folder",xbmcgui.NOTIFICATION_ERROR )
        xbmcaddon.Addon ('plugin.video.addons.ini.creator').openSettings()

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

    if plugin.get_setting("pvr.subscribe") == "true":
        streams["plugin.video.addons.ini.creator"] = {}
        items = pvr()
        for item in items:
            name = item["label"]
            url = item["path"]
            streams["plugin.video.addons.ini.creator"][name] = url

    folder = plugin.get_setting("addons.folder")
    file = plugin.get_setting("addons.file")
    filename = os.path.join(folder,file)
    f = xbmcvfs.File(filename,"wb")

    for id in sorted(streams):
        line = "[%s]\n" % id
        f.write(line.encode("utf8"))
        channels = streams[id]
        for channel in sorted(channels):
            url = channels[channel]
            line = "%s=%s\n" % (channel,url)
            f.write(line.encode("utf8"))
    f.close()



@plugin.route('/')
def index():
    items = []

    items.append(
    {
        'label': "Subscribe",
        'path': plugin.url_for('subscribe'),
        'thumbnail':get_icon_path('tv'),
    })
    items.append(
    {
        'label': "Create",
        'path': plugin.url_for('update'),
        'thumbnail':get_icon_path('tv'),
    })
    items.append(
    {
        'label': "Play",
        'path': plugin.url_for('player'),
        'thumbnail':get_icon_path('tv'),
    })
    items.append(
    {
        'label': "Clear Subscriptions",
        'path': plugin.url_for('clear'),
        'thumbnail':get_icon_path('tv'),
    })
    return items

if __name__ == '__main__':
    plugin.run()
    if big_list_view == True:
        view_mode = int(plugin.get_setting('view_mode'))
        plugin.set_view_mode(view_mode)