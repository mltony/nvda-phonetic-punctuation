# -*- coding: UTF-8 -*-
#A part of the Earcons and Speech Rules addon for NVDA
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
import scriptHandler
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
from . import frenzy

utils.initConfiguration()
pp.reloadRules()
addonHandler.initTranslation()

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    scriptCategory = _("Earcons and Speech Rules")

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

    @script(description=_("Toggle Earcons and Speech Rules."), gestures=['kb:NVDA+Alt+p'])
    def script_togglePp(self, gesture):
        enabled = utils.getConfig("enabled")
        enabled = not enabled
        utils.setConfig("enabled", enabled)
        if enabled:
            msg = _("Earcons and Speech Rules on")
        else:
            msg = _("Earcons and Speech Rules off")
        ui.message(msg)

    @script(description=_("Toggle state verbosity reporting."), gestures=['kb:NVDA+Alt+['])
    def script_toggleStateVerbosity(self, gesture):
        verbose = utils.getConfig("stateVerbose")
        verbose = not verbose
        utils.setConfig("stateVerbose", verbose)
        if verbose:
            msg = _("Verbose state reporting")
        else:
            msg = _("Concise state reporting")
        ui.message(msg)
        frenzy.updateRules()

    @script(description=_("Speak current heading level."), gestures=['kb:NVDA+h'])
    def script_speakHeadingLevel(self, gesture):
        count=scriptHandler.getLastScriptRepeatCount()
        focus  = api.getFocusObject()
        if focus.treeInterceptor is not None:
            if not focus.treeInterceptor.passThrough:
                focus = focus.treeInterceptor
        info = focus.makeTextInfo(textInfos.POSITION_CARET)
        info.expand(textInfos.UNIT_CHARACTER)
        fields = info.getTextWithFields()
        levelFound = False
        for field in fields:
            if(
                isinstance(field,textInfos.FieldCommand)
                and field.command == "controlStart"
            ):
                try:
                    role = field.field['role']
                    level = field.field['level']
                except KeyError:
                    continue
                if count == 0 and role != controlTypes.Role.HEADING:
                    continue
                roleText = role.displayString
                ui.message(_("{roleText} level {level}").format(**locals()))
                levelFound = True
        if not levelFound:
            ui.message(_("Noe heading level information"))
        
