# -*- coding: UTF-8 -*-
#A part of the Phonetic Punctuation addon for NVDA
#Copyright (C) 2019-2023 Tony Malykh
#This file is covered by the GNU General Public License.
#See the file COPYING.txt for more details.

import addonHandler
import api
import bisect
import characterProcessing
import config
import collections
import controlTypes
import copy
import core
import ctypes
from ctypes import create_string_buffer, byref
from enum import Enum
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

from .common import *
from .utils import *
from .commands import *
from . import phoneticPunctuation as pp


original_getObjectPropertiesSpeech = None

def new_getObjectPropertiesSpeech(
        obj,
        reason = controlTypes.OutputReason.QUERY,
        _prefixSpeechCommand = None,
        **allowedProperties
):
    if obj is None or not isPhoneticPunctuationEnabled():
        return original_getObjectPropertiesSpeech(
            obj,reason , _prefixSpeechCommand , **allowedProperties
        )
    symbolLevel=config.conf["speech"]["symbolLevel"]
    newCommands = []
    patchedAllowedProperties = {}
    if allowedProperties.get('role', False):
        role = obj.role
        if role in roleRules and roleRules[role].enabled:
            patchedAllowedProperties['role']=False
            #allowedProperties['states']=False
            rule = roleRules[role]
            command = rule.getSpeechCommand()[0]
            #api.z=command
            #newCommands.append("hahaha")
            newCommands.append(command)
    newCommands.extend(
        original_getObjectPropertiesSpeech(
            obj,
            reason ,
            _prefixSpeechCommand ,
            **{**allowedProperties, **patchedAllowedProperties},
        )
    )
    #newCommands = pp.postProcessSynchronousCommands(newCommands, symbolLevel)
    return newCommands

def monkeyPatch():
    global original_getObjectPropertiesSpeech
    original_getObjectPropertiesSpeech = speech.speech.getObjectPropertiesSpeech
    speech.speech.getObjectPropertiesSpeech = new_getObjectPropertiesSpeech

def monkeyUnpatch():
    speech.speech.getObjectPropertiesSpeech = original_getObjectPropertiesSpeech

roleRules = None
stateRules = None
def updateRules():
    global roleRules, stateRules
    roleRules = {
        rule.getFrenzyValue(): rule
        for rule in pp.rulesByFrenzy[FrenzyType.ROLE]
    }
    stateRules = {
        rule.getFrenzyValue(): rule
        for rule in pp.rulesByFrenzy[FrenzyType.STATE]
    }