# -*- coding: UTF-8 -*-
#A part of the Phonetic Punctuation addon for NVDA
#Copyright (C) 2019-2022 Tony Malykh
#This file is covered by the GNU General Public License.
#See the file COPYING.txt for more details.

import addonHandler
import api
import bisect
import config
import controlTypes
import copy
import core
import ctypes
from ctypes import create_string_buffer, byref
import globalPluginHandler
import globalVars
import gui
from gui import guiHelper, nvdaControls
from gui.settingsDialogs import SettingsPanel
import itertools
import json
from logHandler import log
import NVDAHelper
from NVDAObjects.window import winword
import nvwave
import operator
import os
from queue import Queue
import re
from scriptHandler import script, willSayAllResume
import speech
import speech.commands
import struct
import textInfos
import threading
from threading import Thread
import time
import tones
import ui
import wave
import wx
from . import common

debug = False
if debug:
    f = open("C:\\Users\\tony\\od\\1.txt", "w", encoding="utf-8")
    LOG_MUTEX = threading.Lock()
def mylog(s):
    if debug:
        with LOG_MUTEX:
            print(str(s), file=f)
            f.flush()

def myAssert(condition):
    if not condition:
        raise RuntimeError("Assertion failed")

class Worker(Thread):
    """ Thread executing tasks from a given tasks queue """
    def __init__(self, tasks):
        Thread.__init__(self)
        self.tasks = tasks
        self.daemon = True
        self.start()

    def run(self):
        while True:
            func, args, kargs = self.tasks.get()
            try:
                func(*args, **kargs)
            except Exception as e:
                # An exception happened in this thread
                log.error("Error in ThreadPool ", e)
            finally:
                # Mark this task as done, whether an exception happened or not
                self.tasks.task_done()


class ThreadPool:
    """ Pool of threads consuming tasks from a queue """
    def __init__(self, num_threads):
        self.tasks = Queue(num_threads)
        for _ in range(num_threads):
            Worker(self.tasks)

    def add_task(self, func, *args, **kargs):
        """ Add a task to the queue """
        self.tasks.put((func, args, kargs))

    def map(self, func, args_list):
        """ Add a list of tasks to the queue """
        for args in args_list:
            self.add_task(func, args)

    def wait_completion(self):
        """ Wait for completion of all the tasks in the queue """
        self.tasks.join()


threadPool = ThreadPool(5)

phoneticPunctuationConfigKey = "phoneticpunctuation"
def getConfig(key):
    return config.conf[phoneticPunctuationConfigKey][key]

def setConfig(key, value):
    config.conf[phoneticPunctuationConfigKey][key] = value

def initConfiguration():
    confspec = {
        "enabled" : "boolean( default=True)",
        "rules" : "string( default='')",
        "applicationsBlacklist" : "string( default='')",
    }
    config.conf.spec[phoneticPunctuationConfigKey] = confspec

def getSoundsPath():
    globalPluginPath = os.path.abspath(os.path.dirname(__file__))
    addonPath = os.path.split(globalPluginPath)[0]
    addonPath = os.path.split(addonPath)[0]
    soundsPath = os.path.join(addonPath, "sounds")
    return soundsPath

def isAppBlacklisted():
    focus = api.getFocusObject()
    appName = focus.appModule.appName
    if appName.lower() in getConfig("applicationsBlacklist").lower().strip().split(","):
        return True
    return False

def isPhoneticPunctuationEnabled():
    return not isAppBlacklisted() and  getConfig("enabled") and not  common.rulesDialogOpen
