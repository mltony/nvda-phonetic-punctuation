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

from .phoneticPunctuationGui import RulesDialog
from . import phoneticPunctuation as pp
from . import utils

utils.initConfiguration()
pp.reloadRules()
addonHandler.initTranslation()

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    scriptCategory = _("Phonetic Punctuation")

    def __init__(self, *args, **kwargs):
        super(GlobalPlugin, self).__init__(*args, **kwargs)
        self.createMenu()
        self.injectMonkeyPatches()

    def createMenu(self):
        gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(RulesDialog)

    def terminate(self):
        self.restoreMonkeyPatches()
        gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(RulesDialog)

    def injectMonkeyPatches(self):
        pp.injectMonkeyPatches()

    def  restoreMonkeyPatches(self):
        pp.restoreMonkeyPatches()

    @script(description='Toggle phonetic punctuation.', gestures=['kb:NVDA+Alt+p'])
    def script_togglePp(self, gesture):
        enabled = utils.getConfig("enabled")
        enabled = not enabled
        utils.setConfig("enabled", enabled)
        if enabled:
            msg = _("Phonetic punctuation on")
        else:
            msg = _("Phonetic punctuation off")
        ui.message(msg)
