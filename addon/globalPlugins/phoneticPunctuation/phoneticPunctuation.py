# -*- coding: UTF-8 -*-
#A part of the Phonetic Punctuation addon for NVDA
#Copyright (C) 2019-2022 Tony Malykh
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
from . import commands
from . import frenzy

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
        "comment": "\",
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

class MaskedString:
    def __init__(self, s):
        self.s = s

class AudioRule:
    jsonFields = "comment pattern ruleType wavFile builtInWavFile tone duration enabled caseSensitive startAdjustment endAdjustment prosodyName prosodyOffset prosodyMultiplier volume passThrough frenzyType frenzyValue minNumericValue maxNumericValue prosodyMinOffset prosodyMaxOffset replacementPattern".split()
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
        passThrough=False,
        frenzyType=FrenzyType.TEXT.name,
        frenzyValue="",
        minNumericValue=1,
        maxNumericValue=5,
        prosodyMinOffset=-10,
        prosodyMaxOffset=10,
        replacementPattern=None,
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
        self.passThrough = passThrough
        if isinstance(frenzyType, FrenzyType):
            self.frenzyType = frenzyType.name
        else:
            self.frenzyType = frenzyType
        if isinstance(frenzyValue, Enum):
            self.frenzyValue = frenzyValue.name
        else:
            self.frenzyValue = frenzyValue
        self.minNumericValue = minNumericValue
        self.maxNumericValue = maxNumericValue
        self.prosodyMinOffset = prosodyMinOffset
        self.prosodyMaxOffset = prosodyMaxOffset
        self.replacementPattern = replacementPattern
        self.regexp = re.compile(self.pattern)
        self.speechCommand, self.postSpeechCommand = self.getSpeechCommand()

    def getDisplayName(self):
        if self.getFrenzyType() == FrenzyType.TEXT:
            return self.comment or self.pattern
        else:
            return f"{FRENZY_NAMES_SINGULAR[self.getFrenzyType()]}:{self.getFrenzyValueStr()}"

    def getReplacementDescription(self):
        if self.ruleType == audioRuleWave:
            return f"Wav: {self.wavFile}"
        elif self.ruleType == audioRuleBuiltInWave:
            return self.builtInWavFile
        elif self.ruleType == audioRuleBeep:
            return f"Beep: {self.tone}@{self.duration}"
        elif self.ruleType == audioRuleProsody:
            return f"Prosody: {self.prosodyName}:{self.prosodyOffset}:{self.prosodyMultiplier}"
        elif self.ruleType in [audioRuleTextSubstitution]:
            return f"TextSubstitution: '{self.replacementPattern}'"
        elif self.ruleType in [audioRuleNumericProsody]:
            return "DynamicNumericProsody"
        else:
            raise ValueError()

    def asDict(self):
        return {k:v for k,v in self.__dict__.items() if k in self.jsonFields}
        
    def getFrenzyType(self):
        if len(self.frenzyType) == 0:
            return None
        return getattr(FrenzyType, self.frenzyType)
    
    def getFrenzyValue(self):
        if self.frenzyValue is None:
            return None
        if len(self.frenzyValue) == 0:
            return None
        type = self.getFrenzyType()
        s = self.frenzyValue
        if type == FrenzyType.ROLE:
            return getattr(controlTypes.Role, s)
        elif type in [FrenzyType.STATE, FrenzyType.NEGATIVE_STATE]:
            return getattr(controlTypes.State, s)
        elif type == FrenzyType.FORMAT:
            return getattr(TextFormat, s)
        elif type == FrenzyType.NUMERIC_FORMAT:
            return getattr(NumericTextFormat, s)
        elif type == FrenzyType.OTHER_RULE:
            return getattr(OtherRule, s)
        else:
            raise ValueError

    def getFrenzyValueStr(self):
        if len(self.frenzyValue) == 0:
            return None
        type = self.getFrenzyType()
        s = self.frenzyValue
        if type == FrenzyType.ROLE:
            return controlTypes.role._roleLabels[getattr(controlTypes.Role, s)]
        elif type in [FrenzyType.STATE, FrenzyType.NEGATIVE_STATE]:
            return controlTypes.state._stateLabels[getattr(controlTypes.State, s)]
        elif type == FrenzyType.FORMAT:
            return TEXT_FORMAT_NAMES[self.getFrenzyValue()]
        elif type == FrenzyType.NUMERIC_FORMAT:
            return NUMERIC_TEXT_FORMAT_NAMES[self.getFrenzyValue()]
        elif type == FrenzyType.OTHER_RULE:
            return OTHER_RULE_NAMES[self.getFrenzyValue()]
        else:
            raise ValueError

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
                # We shouldn't set offset to zero because it means restore defaults and confuses our nested prosody commands algorithm.
                offset = self.prosodyOffset or 0.001
                preCommand = classClass(offset=self.prosodyOffset)
            else:
                preCommand = classClass(multiplier=self.prosodyMultiplier)
            postCommand = classClass()
            return preCommand, postCommand
        elif self.ruleType in [audioRuleTextSubstitution, audioRuleNumericProsody]:
            return None, None
        else:
            raise ValueError()

    def getNumericSpeechCommand(self, numericValue):
        if self.ruleType == audioRuleNumericProsody:
            className = self.prosodyName
            className = className[0].upper() + className[1:] + 'Command'
            classClass = getattr(speech.commands, className)
            if (
                self.minNumericValue is None or
                self.maxNumericValue is None or 
                self.prosodyMinOffset is None or 
                self.prosodyMaxOffset  is None
            ):
                raise ValueError
            numericValue = max(self.minNumericValue, min(self.maxNumericValue, numericValue))
            offset = self.prosodyMinOffset + (self.prosodyMaxOffset - self.prosodyMinOffset) * (numericValue - self.minNumericValue) / (self.maxNumericValue - self.minNumericValue) or 0.001
            preCommand = classClass(offset=offset)
            postCommand = classClass()
            return preCommand, postCommand
        elif self.ruleType == audioRuleTextSubstitution:
            if self.replacementPattern is None:
                raise ValueError
            preCommand = self.replacementPattern.format(numericValue)
            return preCommand, None
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
            index2 = match.start(0)
            yield s[index:index2]
            yield self.speechCommand
            if self.passThrough:
                # returning masked string to avoid other rules processing this punctuation mark again
                yield MaskedString(match.group(0))
            if self.postSpeechCommand is not None:
                yield match.group(0)
                yield self.postSpeechCommand
            index = match.end(0)
        yield s[index:]


rulesByFrenzy = None
rulesFileName = os.path.join(globalVars.appArgs.configPath, "phoneticPunctuationRules.json")
def reloadRules():
    global rulesByFrenzy
    try:
        rulesConfig = open(rulesFileName, "r").read()
    except FileNotFoundError:
        rulesConfig = defaultRules
    mylog("Loading rules:")
    if len(rulesConfig) == 0:
        mylog("No rules config found, using default one.")
        rulesConfig = defaultRules
    mylog(rulesConfig)
    
    rulesByFrenzy = {
        frenzy: []
        for frenzy in FrenzyType
    }
    errors = []
    for ruleDict in json.loads(rulesConfig):
        try:
            rule = AudioRule(**ruleDict)
        except Exception as e:
            errors.append(e)
        else:
            rulesByFrenzy[rule.getFrenzyType()].append(rule)
    if len(errors) > 0:
        log.error(f"Failed to load {len(errors)} audio rules; last exception:", errors[-1])
    frenzy.updateRules()

originalSpeechSpeechSpeak = None
originalSpeechCancel = None
originalProcessSpeechSymbols = None
originalTonesInitialize = None

api.ps = []
def preSpeak(speechSequence, symbolLevel=None, *args, **kwargs):
    api.ps.append(speechSequence)
    if isPhoneticPunctuationEnabled():
        if symbolLevel is None:
            symbolLevel=config.conf["speech"]["symbolLevel"]
        newSequence = speechSequence
        for rule in rulesByFrenzy[FrenzyType.TEXT]:
            newSequence = processRule(newSequence, rule, symbolLevel)
        newSequence = postProcessSynchronousCommands(newSequence, symbolLevel)
        #mylog("Speaking!")
        mylog(str(newSequence))
    else:
        newSequence = speechSequence
    newSequence = newSequence + [' '] # Otherwise v2024.2 throws weird Braille Exception + 
    return originalSpeechSpeechSpeak(newSequence, symbolLevel=symbolLevel, *args, **kwargs)

def preCancelSpeech(*args, **kwargs):
    if isPhoneticPunctuationEnabled():
        localCurrentChain = commands.currentChain
        if localCurrentChain is not None:
            localCurrentChain.terminate()
    originalSpeechCancel(*args, **kwargs)
    

def preProcessSpeechSymbols(locale, text, level):
    global rulesByFrenzy
    #mylog(f"preprocess '{text}'")
    n = len(text)
    pattern = "|".join([
        rule.pattern
        for rule in rulesByFrenzy[FrenzyType.TEXT]
        if rule.enabled and rule.passThrough
    ])
    pattern = f"({pattern})+"
    #mylog(f"pattern={pattern}")
    r = re.compile(pattern, re.UNICODE)
    if r.search(""):
        # This is very wrong, just return patched function instead
        return originalProcessSpeechSymbols(locale, text, level)
    prevIndex = 0
    result = []
    for m in r.finditer(text):
        start = m.start(0)
        end = m.end(0)
        prefix = text[prevIndex:start]
        if len(prefix) > 0 and not speech.isBlank(prefix):
            chunk = originalProcessSpeechSymbols(locale, prefix, level)
            #mylog(f"{prefix} >> {chunk}")
            result.append(chunk)
        result.append(m.group(0))
        #mylog(f"=={m.group(0)}")
        prevIndex = end
    suffix = text[prevIndex:]
    if (
        prevIndex == 0
        or (
            len(suffix) > 0 and
            not speech.isBlank(suffix)
        )
    ):
        chunk = originalProcessSpeechSymbols(locale, suffix, level)
        result.append(chunk)
    finalResult = "".join(result)
    #mylog(f"finalResult={finalResult}")
    return finalResult

def preTonesInitialize(*args, **kwargs):
    result = originalTonesInitialize(*args, **kwargs)
    try:
        reloadRules()
    except Exception as e:
        log.error("Error while reloading phonetic punctuation rules", e)
    return result

def injectMonkeyPatches():
    global originalSpeechSpeechSpeak, originalSpeechCancel, originalTonesInitialize, originalProcessSpeechSymbols
    originalSpeechSpeechSpeak = speech.speech.speak
    speech.speech.speak = preSpeak
    speech.speak = speech.speech.speak
    speech.sayAll.SayAllHandler.speechWithoutPausesInstance.speak = speech.speech.speak
    originalSpeechCancel = speech.speech.cancelSpeech
    speech.speech.cancelSpeech = preCancelSpeech
    speech.cancelSpeech = speech.speech.cancelSpeech
    originalProcessSpeechSymbols = characterProcessing.processSpeechSymbols
    characterProcessing.processSpeechSymbols = preProcessSpeechSymbols
    originalTonesInitialize = tones.initialize
    tones.initialize = preTonesInitialize
    frenzy.monkeyPatch()

def  restoreMonkeyPatches():
    global originalSpeechSpeechSpeak, originalSpeechCancel, originalTonesInitialize
    speech.speech.speak = originalSpeechSpeechSpeak
    speech.speak = speech.speech.speak
    speech.sayAll.SayAllHandler.speechWithoutPausesInstance.speak = speech.speech.speak
    speech.speech.cancelSpeech = originalSpeechCancel
    speech.cancelSpeech = speech.speech.cancelSpeech
    characterProcessing.processSpeechSymbols = originalProcessSpeechSymbols
    tones.initialize = originalTonesInitialize
    frenzy.monkeyUnpatch()


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
    speechSequence = [
        element 
        for element in speechSequence
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
    newSequence = unmaskMaskedStrings(newSequence)
    newSequence = fixProsodyCommands(newSequence)
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

def unmaskMaskedStrings(sequence):
    result = []
    for item in sequence:
        if isinstance(item, MaskedString):
            result.append(item.s)
        else:
            result.append(item)
    return result

def fixProsodyCommands(sequence):
    """
    Prosody commands in NVDA don't support nesting natively.
    E.g., if you increase pitch by 10, and then increase pitch by 10 again, these numbers don't add up.
    The latter pitch command will simply override the former one.
    That is not desired behavior; we would like pitch offsets to be additive.
    We can't deal with multiplicative  prosody commands, so we just don't support them here.
    Adjusting prosody offsets in this function so that they support nesting.
    """
    prosodyStacks = collections.defaultdict(lambda: [])
    prosodyOffsets = collections.defaultdict(lambda: 0)
    result = []
    for i, command in enumerate(sequence):
        if isinstance(command, speech.commands.BaseProsodyCommand):
            cls = type(command)
            if command._multiplier != 1:
                log.error("Multiplicative prosody commands detected. This is not supported by phonetic punctuation add-on.")
                return sequence
            commandOffset = command._offset
            if commandOffset == 0:
                # stack pop
                if len(prosodyStacks[cls]) == 0:
                    log.error("Stack underflow during fixProsodyCommands in phonetic punctuation add-on.")
                    return sequence
                prosodyOffsets[cls] = prosodyStacks[cls][-1]
                del prosodyStacks[cls][-1]
            else:
                prosodyStacks[cls].append(prosodyOffsets[cls])
                prosodyOffsets[cls] += commandOffset
            command = copy.deepcopy(command)
            command._offset = prosodyOffsets[cls]
            command.isDefault = command._offset == 0
        result.append(command)
    for cls, stack in prosodyStacks.items():
        if len(stack) != 0:
            # This is not supposed to happen really.
            # But we undo any prosody command that has not been properly closed.
            result.append(cls(offset=0))
    return result
