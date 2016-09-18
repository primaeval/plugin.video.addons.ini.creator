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
    xbmc.executebuiltin('PlayMedia(%s,1)' % url)

@plugin.route('/folder/<path>')
def folder(path):
    response = RPC.files.get_directory(media="files", directory=path, properties=["thumbnail"])
    files = response["files"]
    dirs = dict([[f["label"], f["file"]] for f in files if f["filetype"] == "directory"])
    links = {}
    thumbnails = {}
    for f in files:
        if f["filetype"] == "file":
            label = f["label"]
            label = re.sub(r'\[[BI]\]','',label)
            label = re.sub(r'\[/?COLOR.*?\]','',label)
            file = f["file"]
            while (label in links):
                label = "%s." % label
            links[label] = file
            thumbnails[label] = f["thumbnail"]

    items = []

    for label in sorted(dirs):
        items.append(
        {
            'label': label,
            'path': plugin.url_for('folder',path=dirs[label]),
            'thumbnail': get_icon_path('tv'),
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
        path = "plugin://%s" % addon['addonid']
        items.append(
        {
            'label': addon['name'],
            'path': plugin.url_for('folder',path=path),
            'thumbnail': addon['thumbnail'],
        })
    return items

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
    return items

if __name__ == '__main__':
    plugin.run()
    if big_list_view == True:
        view_mode = int(plugin.get_setting('view_mode'))
        plugin.set_view_mode(view_mode)