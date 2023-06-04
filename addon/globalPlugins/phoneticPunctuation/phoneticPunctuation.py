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
import sre_constants
import struct
import textInfos
import threading
from threading import Thread
import time
import tones
import ui
import wave
import wx

from .utils import *
from .commands import *

defaultRules = """
[
    {
        "builtInWavFile": "3d\\help.wav",
        "caseSensitive": true,
        "comment": "String too long, to prevent synth from hanging.",
        "duration": 50,
        "enabled": true,
        "endAdjustment": 0,
        "pattern": "(?<=^.{5000}).+(?=.{100}$)",
        "ruleType": "builtInWave",
        "startAdjustment": 0,
        "tone": 500,
        "wavFile": ""
    },
    {
        "builtInWavFile": "3d\\voice-mail.wav",
        "caseSensitive": true,
        "comment": "Timestamp 1: I0113 11:25:50.843000 52 file.py:63] Message",
        "duration": 50,
        "enabled": true,
        "endAdjustment": 300,
        "pattern": "^[A-Z][0-9.: ]+[-a-zA-Z0-9:._]+\\]",
        "ruleType": "builtInWave",
        "startAdjustment": 0,
        "tone": 500,
        "wavFile": ""
    },
    {
        "builtInWavFile": "3d\\voice-mail.wav",
        "caseSensitive": true,
        "comment": "Timestamp 2: 2020-01-16 14:43:35,208 module.build INFO: Message, or without INFO",
        "duration": 50,
        "enabled": true,
        "endAdjustment": 300,
        "pattern": "^\\d\\d\\d\\d-\\d\\d-\\d\\d \\d\\d:\\d\\d:\\d\\d,\\d+ \\S+ (INFO|WARN|WARNING|DEBUG|ERROR)?:?",
        "ruleType": "builtInWave",
        "startAdjustment": 0,
        "tone": 500,
        "wavFile": ""
    },
    {
        "builtInWavFile": "3d\\voice-mail.wav",
        "caseSensitive": true,
        "comment": "Timestamp 3: [16:09:16] Message",
        "duration": null,
        "enabled": true,
        "endAdjustment": 300,
        "pattern": "^\\[\\d\\d:\\d\\d:\\d\\d\\]",
        "ruleType": "builtInWave",
        "startAdjustment": 0,
        "tone": null,
        "wavFile": ""
    },
    {
        "builtInWavFile": "3d\\voice-mail.wav",
        "caseSensitive": true,
        "comment": "Timestamp 4: [INFO    ][2020-01-22 11:01:18,624][file.py:390  ] - message",
        "duration": 50,
        "enabled": true,
        "endAdjustment": 300,
        "pattern": "^\\[(INFO|DEBUG|WARN|WARNING|ERROR)\\s*\\]\\[[-0-9:, ]+\\]\\[[-a-zA-Z0-9.:_ ]+\\][- ]*",
        "ruleType": "builtInWave",
        "startAdjustment": 0,
        "tone": 500,
        "wavFile": ""
    },
    {
        "builtInWavFile": "3d\\item.wav",
        "caseSensitive": false,
        "comment": "",
        "duration": 50,
        "enabled": true,
        "endAdjustment": 100,
        "pattern": "!",
        "ruleType": "builtInWave",
        "startAdjustment": 0,
        "tone": 500,
        "wavFile": ""
    },
    {
        "builtInWavFile": "classic\\ask-short-question.wav",
        "caseSensitive": true,
        "comment": "",
        "duration": 50,
        "enabled": true,
        "endAdjustment": 300,
        "pattern": "@",
        "ruleType": "builtInWave",
        "startAdjustment": 0,
        "tone": 500,
        "wavFile": ""
    },
    {
        "builtInWavFile": "punctuation\\Backslash.wav",
        "caseSensitive": true,
        "comment": "]",
        "duration": 361,
        "enabled": true,
        "endAdjustment": 0,
        "pattern": "\\\\",
        "ruleType": "builtInWave",
        "startAdjustment": 0,
        "tone": 500,
        "wavFile": ".\\Backslash.wav"
    },
    {
        "builtInWavFile": "punctuation\\LeftParen.wav",
        "caseSensitive": true,
        "comment": "(",
        "duration": 50,
        "enabled": true,
        "endAdjustment": 0,
        "pattern": "\\(",
        "ruleType": "builtInWave",
        "startAdjustment": 0,
        "tone": 500,
        "wavFile": ""
    },
    {
        "builtInWavFile": "punctuation\\RightParen.wav",
        "caseSensitive": true,
        "comment": ")",
        "duration": 50,
        "enabled": true,
        "endAdjustment": 0,
        "pattern": "\\)",
        "ruleType": "builtInWave",
        "startAdjustment": 0,
        "tone": 500,
        "wavFile": ""
    },
    {
        "builtInWavFile": "punctuation\\LeftBracket.wav",
        "caseSensitive": true,
        "comment": "[",
        "duration": 50,
        "enabled": true,
        "endAdjustment": 0,
        "pattern": "\\[",
        "ruleType": "builtInWave",
        "startAdjustment": 0,
        "tone": 500,
        "wavFile": "H:\\Downloads\\PhonPuncTest2\\LeftBracket-.wav"
    },
    {
        "builtInWavFile": "punctuation\\RightBracket.wav",
        "caseSensitive": true,
        "comment": "]",
        "duration": 50,
        "enabled": true,
        "endAdjustment": 0,
        "pattern": "\\]",
        "ruleType": "builtInWave",
        "startAdjustment": 0,
        "tone": 500,
        "wavFile": "H:\\Downloads\\PhonPuncTest2\\RightBracket-.wav"
    },
    {
        "builtInWavFile": "3d\\ellipses.wav",
        "caseSensitive": false,
        "comment": "...",
        "duration": 50,
        "enabled": true,
        "endAdjustment": 0,
        "pattern": "\\.{3,}",
        "ruleType": "builtInWave",
        "startAdjustment": 0,
        "tone": 500,
        "wavFile": ""
    },
    {
        "builtInWavFile": "chimes\\close-object.wav",
        "caseSensitive": true,
        "comment": ".",
        "duration": 50,
        "enabled": true,
        "endAdjustment": 50,
        "pattern": "\\.(?!\\d)",
        "ruleType": "builtInWave",
        "startAdjustment": 0,
        "tone": 500,
        "wavFile": ""
    },
    {
        "builtInWavFile": "chimes\\delete-object.wav",
        "caseSensitive": false,
        "comment": "",
        "duration": 50,
        "enabled": true,
        "endAdjustment": 100,
        "pattern": ",",
        "ruleType": "builtInWave",
        "startAdjustment": 5,
        "tone": 500,
        "wavFile": ""
    },
    {
        "builtInWavFile": "chimes\\yank-object.wav",
        "caseSensitive": false,
        "comment": "?",
        "duration": 50,
        "enabled": true,
        "endAdjustment": 0,
        "pattern": "\\?",
        "ruleType": "builtInWave",
        "startAdjustment": 0,
        "tone": 500,
        "wavFile": ""
    },
    {
        "builtInWavFile": "3d\\window-resize.wav",
        "caseSensitive": true,
        "comment": "",
        "duration": 50,
        "enabled": true,
        "endAdjustment": 0,
        "pattern": "^blank$",
        "ruleType": "builtInWave",
        "startAdjustment": 0,
        "tone": 500,
        "wavFile": ""
    },
    {
        "builtInWavFile": "punctuation\\LeftBrace.wav",
        "caseSensitive": true,
        "comment": "{",
        "duration": 50,
        "enabled": true,
        "endAdjustment": 0,
        "pattern": "\\{",
        "ruleType": "builtInWave",
        "startAdjustment": 0,
        "tone": 500,
        "wavFile": ""
    },
    {
        "builtInWavFile": "punctuation\\RightBrace.wav",
        "caseSensitive": true,
        "comment": "}",
        "duration": 50,
        "enabled": true,
        "endAdjustment": 0,
        "pattern": "\\}",
        "ruleType": "builtInWave",
        "startAdjustment": 0,
        "tone": 500,
        "wavFile": ""
    },
    {
        "builtInWavFile": "",
        "caseSensitive": true,
        "comment": "Capital",
        "duration": 50,
        "enabled": false,
        "endAdjustment": 0,
        "pattern": "(\\b|(?<=[_a-z]))[A-Z][a-z]+(\\b|(?=[_A-Z]))",
        "prosodyMultiplier": null,
        "prosodyName": "Pitch",
        "prosodyOffset": 10,
        "ruleType": "prosody",
        "startAdjustment": 0,
        "tone": 500,
        "wavFile": ""
    },
    {
        "builtInWavFile": "",
        "caseSensitive": true,
        "comment": "ALL_CAPITAL",
        "duration": 50,
        "enabled": true,
        "endAdjustment": 0,
        "pattern": "(\\b|(?<=[_a-z]))[A-Z]{2,}(\\b|(?=_)|(?=[A-Z][a-z]))",
        "prosodyMultiplier": null,
        "prosodyName": "Pitch",
        "prosodyOffset": 20,
        "ruleType": "prosody",
        "startAdjustment": 0,
        "tone": 500,
        "wavFile": ""
    }
]
""".replace("\\", "\\\\")


audioRuleBuiltInWave = "builtInWave"
audioRuleWave = "wave"
audioRuleBeep = "beep"
audioRuleProsody = "prosody"
audioRuleTypes = [
    audioRuleBuiltInWave,
    audioRuleWave,
    audioRuleBeep,
    audioRuleProsody,
]

class AudioRule:
    jsonFields = "comment pattern ruleType wavFile builtInWavFile tone duration enabled caseSensitive startAdjustment endAdjustment prosodyName prosodyOffset prosodyMultiplier volume".split()
    def __init__(
        self,
        comment,
        pattern,
        ruleType,
        wavFile=None,
        builtInWavFile=None,
        startAdjustment=0,
        endAdjustment=0,
        tone=None,
        duration=None,
        enabled=True,
        caseSensitive=True,
        prosodyName=None,
        prosodyOffset=None,
        prosodyMultiplier=None,
        volume=100,
    ):
        self.comment = comment
        self.pattern = pattern
        self.ruleType = ruleType
        self.wavFile = wavFile
        self.builtInWavFile = builtInWavFile
        self.startAdjustment = startAdjustment
        self.endAdjustment = endAdjustment
        self.tone = tone
        self.duration = duration
        self.enabled = enabled
        self.caseSensitive = caseSensitive
        self.prosodyName = prosodyName
        self.prosodyOffset = prosodyOffset
        self.prosodyMultiplier = prosodyMultiplier
        self.volume = volume
        self.regexp = re.compile(self.pattern)
        self.speechCommand, self.postSpeechCommand = self.getSpeechCommand()

    def getDisplayName(self):
        return self.comment or self.pattern

    def getReplacementDescription(self):
        if self.ruleType == audioRuleWave:
            return f"Wav: {self.wavFile}"
        elif self.ruleType == audioRuleBuiltInWave:
            return self.builtInWavFile
        elif self.ruleType == audioRuleBeep:
            return f"Beep: {self.tone}@{self.duration}"
        elif self.ruleType == audioRuleProsody:
            return f"Prosody: {self.prosodyName}:{self.prosodyOffset}:{self.prosodyMultiplier}"
        else:
            raise ValueError()

    def asDict(self):
        return {k:v for k,v in self.__dict__.items() if k in self.jsonFields}

    def getSpeechCommand(self):
        if self.ruleType in [audioRuleBuiltInWave, audioRuleWave]:
            if self.ruleType == audioRuleBuiltInWave:
                wavFile = os.path.join(getSoundsPath(), self.builtInWavFile)
            else:
                wavFile = self.wavFile
            return PpWaveFileCommand(
                wavFile,
                startAdjustment=self.startAdjustment,
                endAdjustment=self.endAdjustment,
                volume=self.volume,
            ), None
        elif self.ruleType == audioRuleBeep:
            return PpBeepCommand(self.tone, self.duration, left=self.volume, right=self.volume), None
        elif self.ruleType == audioRuleProsody:
            className = self.prosodyName
            className = className[0].upper() + className[1:] + 'Command'
            classClass = getattr(speech.commands, className)
            if self.prosodyOffset is not None:
                preCommand = classClass(offset=self.prosodyOffset)
            else:
                preCommand = classClass(multiplier=self.prosodyMultiplier)
            postCommand = classClass()
            return preCommand, postCommand
            
        else:
            raise ValueError()

    def processString(self, s, *args, **kwargs):
        if not self.enabled:
            yield s
            return
        for command in self.processStringInternal(s, *args, **kwargs):
            if isinstance(command, str):
                if len(command) > 0:
                    yield command
            else:
                yield command

    def processStringInternal(self, s, symbolLevel, language):
        index = 0
        for match in self.regexp.finditer(s):
            if (
                not speech.isBlank(match.group(0))
                and speech.isBlank(speech.processText(language,match.group(0), symbolLevel))
            ):
                # Current punctuation level indicates that punctuation mark matched will not be pronounced, therefore skipping it.
                continue
            yield s[index:match.start(0)]
            yield self.speechCommand
            if self.postSpeechCommand is not None:
                yield match.group(0)
                yield self.postSpeechCommand
            index = match.end(0)
        yield s[index:]


rulesDialogOpen = False
rules = []
rulesFileName = os.path.join(globalVars.appArgs.configPath, "phoneticPunctuationRules.json")
def reloadRules():
    global rules
    try:
        rulesConfig = open(rulesFileName, "r").read()
    except FileNotFoundError:
        rulesConfig = defaultRules
    mylog("Loading rules:")
    if len(rulesConfig) == 0:
        mylog("No rules config found, using default one.")
        rulesConfig = defaultRules
    mylog(rulesConfig)
    rules = []
    for ruleDict in json.loads(rulesConfig):
        try:
            rules.append(AudioRule(**ruleDict))
        except Exception as e:
            log.error("Failed to load audio rule", e)

originalSpeechSpeechSpeak = None
originalSpeechCancel = None
originalTonesInitialize = None

def isAppBlacklisted():
    focus = api.getFocusObject()
    appName = focus.appModule.appName
    if appName.lower() in getConfig("applicationsBlacklist").lower().strip().split(","):
        return True
    return False

def preSpeak(speechSequence, symbolLevel=None, *args, **kwargs):
    if isAppBlacklisted() != True and getConfig("enabled") and not rulesDialogOpen:
        if symbolLevel is None:
            symbolLevel=config.conf["speech"]["symbolLevel"]
        newSequence = speechSequence
        for rule in rules:
            newSequence = processRule(newSequence, rule, symbolLevel)
        newSequence = postProcessSynchronousCommands(newSequence, symbolLevel)
        #mylog("Speaking!")
        mylog(str(newSequence))
    else:
        newSequence = speechSequence
    return originalSpeechSpeechSpeak(newSequence, symbolLevel=symbolLevel, *args, **kwargs)

def preCancelSpeech(*args, **kwargs):
    localCurrentChain = currentChain
    if localCurrentChain is not None:
        localCurrentChain.terminate()
    originalSpeechCancel(*args, **kwargs)

def preTonesInitialize(*args, **kwargs):
    result = originalTonesInitialize(*args, **kwargs)
    try:
        reloadRules()
    except Exception as e:
        log.error("Error while reloading phonetic punctuation rules", e)
    return result

def injectMonkeyPatches():
    global originalSpeechSpeechSpeak, originalSpeechCancel, originalTonesInitialize
    originalSpeechSpeechSpeak = speech.speech.speak
    speech.speech.speak = preSpeak
    originalSpeechCancel = speech.speech.cancelSpeech
    speech.speech.cancelSpeech = preCancelSpeech
    originalTonesInitialize = tones.initialize
    tones.initialize = preTonesInitialize

def  restoreMonkeyPatches():
    global originalSpeechSpeechSpeak, originalSpeechCancel, originalTonesInitialize
    speech.speech.speak = originalSpeechSpeechSpeak
    speech.speech.cancelSpeech = originalSpeechCancel
    tones.initialize = originalTonesInitialize


def processRule(speechSequence, rule, symbolLevel):
    language=speech.getCurrentLanguage()
    newSequence = []
    for command in speechSequence:
        if isinstance(command, str):
            newSequence.extend(rule.processString(command, symbolLevel, language))
        else:
            newSequence.append(command)
    return newSequence

def postProcessSynchronousCommands(speechSequence, symbolLevel):
    language=speech.getCurrentLanguage()
    speechSequence = [element for element in speechSequence
        if not isinstance(element, str)
        or not speech.isBlank(speech.processText(language,element,symbolLevel))
    ]

    newSequence = []
    for (isSynchronous, values) in itertools.groupby(speechSequence, key=lambda x: isinstance(x, PpSynchronousCommand)):
        if isSynchronous:
            chain = PpChainCommand(list(values))
            duration = chain.getDuration()
            newSequence.append(chain)
            newSequence.append(speech.commands.BreakCommand(duration))
        else:
            newSequence.extend(values)
    newSequence = eloquenceFix(newSequence, language, symbolLevel)
    return newSequence

def eloquenceFix(speechSequence, language, symbolLevel):
    """
    With some versions of eloquence driver, when the entire utterance has been replaced with audio icons, and therefore there is nothing else to speak,
    the driver for some reason issues the callback command after the break command, not before.
    To work around this, we detect this case and remove break command completely.
    """
    nonEmpty = [element for element in speechSequence
        if  isinstance(element, str)
        and not speech.isBlank(speech.processText(language,element,symbolLevel))
    ]
    if len(nonEmpty) > 0:
        return speechSequence
    indicesToRemove = []
    for i in range(1, len(speechSequence)):
        if  (
            isinstance(speechSequence[i], speech.commands.BreakCommand)
            and isinstance(speechSequence[i-1], PpChainCommand)
        ):
            indicesToRemove.append(i)
    return [speechSequence[i] for i in range(len(speechSequence)) if i not in indicesToRemove]
