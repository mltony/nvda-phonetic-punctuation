# -*- coding: UTF-8 -*-
#A part of the Phonetic Punctuation addon for NVDA
#Copyright (C) 2019 Tony Malykh
#This file is covered by the GNU General Public License.
#See the file COPYING.txt for more details.

import addonHandler
import api
import bisect
import config
import controlTypes
import ctypes
import globalPluginHandler
import gui
import json
import NVDAHelper
from NVDAObjects.window import winword
import operator
import re
import sayAllHandler
from scriptHandler import script, willSayAllResume
import speech
import struct
import textInfos
import tones
import ui
import wx

debug = True
if debug:
    f = open("C:\\Users\\tony\\Dropbox\\1.txt", "w")
def mylog(s):
    if debug:
        print >>f, str(s)
        f.flush()

def myAssert(condition):
    if not condition:
        raise RuntimeError("Assertion failed")

def hook(*args, **kwargs):
    tones.beep(500, 50)
    mylog("Hook!")

def interceptSpeech():
    def makeInterceptFunc(targetFunc):
        def wrapperFunc(*args, **kwargs):
            hook(*args, **kwargs)
            targetFunc(*args, **kwargs)
        return wrapperFunc
    speech.speak = makeInterceptFunc(speech.speak)

interceptSpeech    ()

addonHandler.initTranslation()
class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    scriptCategory = _("Phonetic Punctuation")

    def __init__(self, *args, **kwargs):
        super(GlobalPlugin, self).__init__(*args, **kwargs)
        self.createMenu()

    def createMenu(self):
        pass


    def terminate(self):
        pass


