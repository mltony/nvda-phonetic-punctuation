# -*- coding: UTF-8 -*-
#A part of the Earcons and Speech rules addon for NVDA
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
from config.configFlags import ReportLineIndentation
import languageHandler
import shutil
import globalCommands

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
    """
    We convert a string into Masked string to prevent rules from acting on it.
    This is useful when we have processed some punctuation marks, such as a comma,
    and would like to feed it to the synth, and avoid any other rules from acting upon it.
    So we temporarily mask the comma, and unmask it at the end.
    """
    
    def __init__(self, s):
        self.s = s

class AudioRule:
    jsonFields = "comment pattern ruleType wavFile builtInWavFile tone duration enabled caseSensitive startAdjustment endAdjustment prosodyName prosodyOffset prosodyMultiplier volume passThrough frenzyType frenzyValue minNumericValue maxNumericValue prosodyMinOffset prosodyMaxOffset replacementPattern suppressStateClutter applicationFilterRegex windowTitleRegex urlRegex".split()
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
        suppressStateClutter=False,
        applicationFilterRegex="",
        windowTitleRegex="",
        urlRegex="",
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
        self.suppressStateClutter = suppressStateClutter
        self.applicationFilterRegex = applicationFilterRegex
        self.windowTitleRegex = windowTitleRegex
        self.urlRegex = urlRegex

        self.regexp = re.compile(self.pattern)
        self._applicationFilterRegex = re.compile(applicationFilterRegex)
        self._windowTitleRegex = re.compile(windowTitleRegex)
        self._urlRegex = re.compile(urlRegex)
        self.speechCommand, self.postSpeechCommand = self.getSpeechCommand()

    def getDisplayName(self):
        if self.getFrenzyType() in [FrenzyType.TEXT, FrenzyType.CHARACTER]:
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
        elif self.ruleType in [audioRuleNoop]:
            return "Noop"
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
        if self.frenzyValue is None or len(self.frenzyValue) == 0:
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
            classClass = getProsodyClass(self.prosodyName)
            if self.prosodyOffset is not None:
                # We shouldn't set offset to zero because it means restore defaults and confuses our nested prosody commands algorithm.
                offset = self.prosodyOffset or 0.001
                preCommand = classClass(offset=self.prosodyOffset)
            else:
                preCommand = classClass(multiplier=self.prosodyMultiplier)
            postCommand = classClass()
            return preCommand, postCommand
        elif self.ruleType in [audioRuleTextSubstitution]:
            if self.replacementPattern is None:
                raise ValueError
            return self.replacementPattern, None
        elif self.ruleType in [audioRuleTextSubstitution, audioRuleNumericProsody, audioRuleNoop]:
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
            offset = self.prosodyMinOffset + (self.prosodyMaxOffset - self.prosodyMinOffset) * (numericValue - self.minNumericValue) / (self.maxNumericValue - self.minNumericValue)
            if offset == 0:
                offset = 0.001
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
characterRules = None
allProsodies = None
rulesFileName = os.path.join(globalVars.appArgs.configPath, "earconsAndSpeechRules.json")
ppRulesFileName = os.path.join(globalVars.appArgs.configPath, "phoneticPunctuationRules.json")
defaultRulesFileName = os.path.join(os.path.dirname(__file__), "defaultEarconsAndSpeechRules.json")
def reloadRules():
    global rulesByFrenzy, characterRules, allProsodies
    initialAttempt = rulesByFrenzy == None
    if initialAttempt and not os.path.exists(rulesFileName):
        # 1. Check if phonetic punctuation rules file exists - if so - then we must have just updated.
        # In this case, migrate from pp and show a dialog box.
        # or, alternatively:
        # 2. copy default rules file.
        if os.path.exists(ppRulesFileName):
            shutil.copy(ppRulesFileName, rulesFileName)
            os.replace(ppRulesFileName, ppRulesFileName + ".bak")
            wx.CallAfter(
                gui.messageBox,
                _(
                    "Phonetic punctuation add-on has been renamed to Earcons and Speech Rules.\n"
                    "We have automatically migrated all your phonetic punctuation rules to Earcons and Speech Rules add-on, so no further action is required.\n"
                    "Please feel free to explore add-on settings to discover new features.\n"
                ),
                _("Earcons and Speech Rules add-on"),
                wx.OK|wx.ICON_INFORMATION,
            )
        else:
            shutil.copy(defaultRulesFileName, rulesFileName)
        
    rulesConfig = open(rulesFileName, "r").read()
    rulesByFrenzy = {
        frenzy: []
        for frenzy in FrenzyType
    }
    allProsodies = set()
    errors = []
    for ruleDict in json.loads(rulesConfig):
        try:
            rule = AudioRule(**ruleDict)
        except Exception as e:
            errors.append(e)
        else:
            rulesByFrenzy[rule.getFrenzyType()].append(rule)
            if rule.enabled and rule.ruleType == audioRuleProsody:
                allProsodies.add(rule.prosodyName)
    if len(errors) > 0:
        log.exception(f"Failed to load {len(errors)} audio rules; last exception:", errors[-1])
    frenzy.updateRules()
    characterRules = {
        rule.pattern: rule
        for rule in rulesByFrenzy[FrenzyType.CHARACTER]
        if rule.enabled
    }

def onPostNvdaStartup():
    if any([len(rule.urlRegex) > 0 for rule in rulesByFrenzy[FrenzyType.TEXT]]) and not isURLResolutionAvailable():
        wx.CallAfter(
            gui.messageBox,
            _(
                "Error initializing some text rules of Earcons and Speech Rules add-on since they contain URL filter.\n"
                "URL detection feature requires BrowserNav v2.6.2 or later add-on to be installed.\n"
                "However it is either not installed, or failed to initialize.\n"
                "Please install the latest BrowserNav add-on from add-on store and restart NVDA.\n"
                "In the mean time all text rules with URL filter will be disabled.\n"
            ),
            _("Earcons and speech rules add-on Error"),
            wx.ICON_ERROR | wx.OK,
        )
        return

core.postNvdaStartup.register(onPostNvdaStartup)

originalSpeechSpeechSpeak = None
originalSpeechCancel = None
originalProcessSpeechSymbols = None
originalTonesInitialize = None
def preSpeak(speechSequence, symbolLevel=None, *args, **kwargs):
    global speechCancelledFlag
    if isPhoneticPunctuationEnabled():
        if symbolLevel is None:
            symbolLevel=config.conf["speech"]["symbolLevel"]
        newSequence = speechSequence
        appName, windowTitle, url = getCurrentContext()
        for rule in rulesByFrenzy[FrenzyType.TEXT]:
            if len(rule.applicationFilterRegex) > 0 and not rule._applicationFilterRegex.search(appName):
                continue
            if len(rule.windowTitleRegex) > 0 and not rule._windowTitleRegex.search(windowTitle):
                continue
            if (
                len(rule.urlRegex) > 0 
                and (
                    url is None
                    or not rule._urlRegex.search(url)
                )
            ):
                continue
            newSequence = processRule(newSequence, rule, symbolLevel)
        resetProsodiesSequence = []
        if speechCancelledFlag:
            resetProsodiesSequence = resetProsodies([])
            speechCancelledFlag = False
        newSequence = postProcessSynchronousCommands(newSequence, symbolLevel)
        newSequence = resetProsodiesSequence + newSequence
        #mylog("Speaking!")
        mylog(str(newSequence))
    else:
        newSequence = speechSequence
    newSequence = newSequence + [' '] # Otherwise v2024.2 throws weird Braille Exception + 
    return originalSpeechSpeechSpeak(newSequence, symbolLevel=symbolLevel, *args, **kwargs)

speechCancelledFlag = False
def preCancelSpeech(*args, **kwargs):
    global speechCancelledFlag
    speechCancelledFlag = True
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
        log.error("Error while reloading Earcons and Speech Rules", e)
    return result

highLevelSpeakFunctionNames = {
    speech.speech: [
        #'speakMessage',
        #'speakSsml',
        #'speakSpelling',
        #'speakObjectProperties',
        #'speakObject',
        #'speakText',
        #'speakPreselectedText',
        #'speakSelectionMessage',
        'speakTextInfo',
    ],
    globalCommands.GlobalCommands: [
        #'script_navigatorObject_current',
        #'script_reportCurrentFocus',
    ],
}
originalHighLevelSpeakFunctions = {}
pdbg = False
def monkeyPatchRestoreProsodyInAllHighLevelSpeakFunctions():
    def createFunctor(targetFunction, functionName):
        def functor(*args, **kwargs):
            global pdbg
            if functionName == 'speakTextInfo':
                info = args[0]
                if 'd' == info.text:
                    tones.beep(500, 50)
                    pdbg = True
                    frenzy.pdbg = True
            if isPhoneticPunctuationEnabled():
                # Sending a string containing a single whitespace.
                # For some reason if the string is empty, this causes a weird exception in braille.py.
                #originalSpeechSpeechSpeak(resetProsodies([' ']))
                pass
            result = targetFunction(*args, **kwargs)
            if pdbg:
                pdbg = False
                frenzy.pdbg = False
            return result
        return functor
    
    for module, functionNames in highLevelSpeakFunctionNames.items():
        originalHighLevelSpeakFunctions[module] = {}
        for functionName in functionNames:
            function = getattr(module, functionName)
            originalHighLevelSpeakFunctions[module][functionName] = function
            replacementFunctor = createFunctor(function, functionName)
            setattr(module, functionName, replacementFunctor)
            if module == speech.speech:
                setattr(speech, functionName, replacementFunctor)

def monkeyUnpatchRestoreProsodyInAllHighLevelSpeakFunctions():
    for module, d in originalHighLevelSpeakFunctions.items():
        for functionName, originalFunction in d.items():
            setattr(module, functionName, originalFunction)
            if module == speech.speech:
                setattr(speech, functionName, originalFunction)
    
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
    
    global original_processSpeechSymbol
    original_processSpeechSymbol = characterProcessing.processSpeechSymbol
    characterProcessing.processSpeechSymbol = new_processSpeechSymbol
    global original_getIndentationSpeech
    original_getIndentationSpeech = speech.speech.getIndentationSpeech
    speech.speech.getIndentationSpeech = new_getIndentationSpeech
    global original_getSelectionMessageSpeech
    original_getSelectionMessageSpeech = speech.speech._getSelectionMessageSpeech
    speech.speech._getSelectionMessageSpeech = new_getSelectionMessageSpeech
    
    #monkeyPatchRestoreProsodyInAllHighLevelSpeakFunctions()

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
    
    characterProcessing.processSpeechSymbol = original_processSpeechSymbol
    speech.speech.getIndentationSpeech = original_getIndentationSpeech
    speech.speech._getSelectionMessageSpeech = original_getSelectionMessageSpeech
    
    #monkeyUnpatchRestoreProsodyInAllHighLevelSpeakFunctions()


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
    """
    This function groups together adjacent earcons.
    For some reason if we issue multiple adjacent wave commands, then either some of them don't get triggered at all,
    or there are extra silence in between.
    To work around that we replace adjacent earcons with a single PPChainCommand,
    that is clever enough to play all earcons with the right timing.
    Then we apply some more tweaks to fix other glitches.
    We also connect earcons separated by some meaningless commands together into a single chain.
    Examples of meaningless commands are LangChain commands or empty strings.
    """
    language=speech.getCurrentLanguage()
    def isEmptyString(command):
        return isinstance(command, str) and speech.isBlank(speech.processText(language,command,symbolLevel))
    newSequence = []
    excludeIndices = set()
    for i, command in enumerate(speechSequence):
        if i in excludeIndices:
            continue
        if isinstance(command, PpSynchronousCommand):
            chain = [command]
            for j in range(i+1, len(speechSequence)):
                cj = speechSequence[j]
                if isinstance(cj, PpSynchronousCommand):
                    chain.append(cj)
                    excludeIndices.add(j)
                elif isEmptyString(cj):
                    excludeIndices.add(j)
                elif isinstance(cj, (speech.commands.LangChangeCommand, MaskedString, speech.commands.BaseProsodyCommand)):
                    pass
                else:
                    break
            chainCommand = PpChainCommand(chain)
            duration = chainCommand.getDuration()
            newSequence.append(chainCommand)
            newSequence.append(speech.commands.BreakCommand(duration))
        elif not isEmptyString(command):
            newSequence.append(command)
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

prosodyStacks = collections.defaultdict(lambda: [])
prosodyOffsets = collections.defaultdict(lambda: 0)
def fixProsodyCommands(sequence):
    """
    Prosody commands in NVDA don't support nesting natively.
    E.g., if you increase pitch by 10, and then increase pitch by 10 again, these numbers don't add up.
    The latter pitch command will simply override the former one.
    That is not desired behavior; we would like pitch offsets to be additive.
    We can't deal with multiplicative  prosody commands, so we just don't support them here.
    Adjusting prosody offsets in this function so that they support nesting.
    """
    global prosodyStacks, prosodyOffsets
    prosodySettings = {}
    def findProsodySetting(cls):
        nonlocal prosodySettings
        try:
            return prosodySettings[cls]
        except KeyError:
            pass
        clsName  = cls.__name__
        commandSuffix = 'Command'
        if not clsName.endswith(commandSuffix):
            raise RuntimeError(f"Unknown Prosody {clsName}")
        prosodyName = clsName[:-len(commandSuffix)].lower()
        for srs in globalVars.settingsRing.settings:
            if srs.setting.id == prosodyName:
                prosodySettings[cls] = srs
                return srs
        # Well, perhaps current synth doesn't support given prosody.
        prosodySettings[cls] = None
        return None
        
            
    result = []
    for i, command in enumerate(sequence):
        if isinstance(command, speech.commands.BaseProsodyCommand):
            cls = type(command)
            if command._multiplier != 1:
                log.error("Multiplicative prosody commands detected. This is not supported by Earcons and Speech Rules add-on.")
                return sequence
            commandOffset = command._offset
            if commandOffset == 0:
                # stack pop
                if len(prosodyStacks[cls]) == 0:
                    log.error("Stack underflow during fixProsodyCommands in Earcons and Speech Rules add-on.")
                    return sequence
                prosodyOffsets[cls] = prosodyStacks[cls][-1]
                del prosodyStacks[cls][-1]
            else:
                prosodyStacks[cls].append(prosodyOffsets[cls])
                prosodyOffsets[cls] += commandOffset
            command = copy.deepcopy(command)
            # Let's make sure the offset doesn't go beyond (0, 100) interval - otherwise synths will ignore this command.
            ps = findProsodySetting(cls)
            if ps is not None:
                maxOffset = ps.max - ps.value
                minOffset = ps.min - ps.value
                effectiveOffset = max(
                    minOffset,
                    min(
                        maxOffset,
                        prosodyOffsets[cls]
                    )
                )
            else:
                effectiveOffset = prosodyOffsets[cls]
            command._offset = effectiveOffset
            command.isDefault = command._offset == 0
        result.append(command)
    return result

def resetProsodies(sequence):
    """
    Resetting all prosodies at the beginning of each utterance so that previous speech doesn't affect this utterance.
    Here is the explanation as to why this is needed:
    If we alter a prosody, we typically also insert another command to reset that prosody back.
    However, sometimes user would cancel speech before the second prosody command has reached the synth.
    We don't want prosody to stay altered and affect the next utterance.
    NVDA appears to have some kind of logic to reset prosody, but it is unreliable and I ddin't track it down.
    So doing a poor man's prosody reset here.
    Also resetting prosodies stack.
    """
    global prosodyStacks, prosodyOffsets
    prosodyStacks.clear()
    prosodyOffsets.clear()
    if len(allProsodies) == 0:
        return sequence
    return [getProsodyClass(prosodyName)() for prosodyName in allProsodies] + sequence

original_processSpeechSymbol = None
def new_processSpeechSymbol(locale, symbol):
    if isPhoneticPunctuationEnabled():
        rule = characterRules.get(symbol, None)
        if rule is not None:
            return rule.getSpeechCommand()[0]
    return original_processSpeechSymbol(locale, symbol)

original_getIndentationSpeech = None
def new_getIndentationSpeech(indentation, formatConfig):
    """Retrieves the indentation speech sequence for a given string of indentation.
    @param indentation: The string of indentation.
    @param formatConfig: The configuration to use.
    """
    if not isPhoneticPunctuationEnabled():
        return original_getIndentationSpeech(indentation, formatConfig)
    speechIndentConfig = formatConfig["reportLineIndentation"] in (
        ReportLineIndentation.SPEECH,
        ReportLineIndentation.SPEECH_AND_TONES,
    )
    toneIndentConfig = (
        formatConfig["reportLineIndentation"]
        in (
            ReportLineIndentation.TONES,
            ReportLineIndentation.SPEECH_AND_TONES,
        )
        and speech.speech._speechState.speechMode == speech.speech.SpeechMode.talk
    )
    indentSequence = []
    if not indentation:
        if toneIndentConfig:
            indentSequence.append(speech.commands.BeepCommand(speech.speech.IDT_BASE_FREQUENCY, speech.speech.IDT_TONE_DURATION))
        if speechIndentConfig:
            # mltony change
            noIndentRule = frenzy.otherRules.get(OtherRule.NO_INDENT, None)
            if noIndentRule is not None:
                indentSequence.append(
                    noIndentRule.getSpeechCommand()[0]
                )
            else:
                indentSequence.append(
                    # Translators: This is spoken when the given line has no indentation.
                    _("no indent"),
                )
        return indentSequence

    # The non-breaking space is semantically a space, so we replace it here.
    indentation = indentation.replace("\xa0", " ")
    res = []
    locale = languageHandler.getLanguage()
    quarterTones = 0
    for m in speech.speech.RE_INDENTATION_CONVERT.finditer(indentation):
        raw = m.group()
        symbol = characterProcessing.processSpeechSymbol(locale, raw[0])
        count = len(raw)
        if symbol == raw[0]:
            # There is no replacement for this character, so do nothing.
            res.append(raw)
        elif count == 1:
            res.append(symbol)
        else:
            # @mltony Changed here: supporting earcons for symbols
            #res.append("{count} {symbol}".format(count=count, symbol=symbol))
            res.append(f"{count}")
            res.append(symbol)
        quarterTones += count * 4 if raw[0] == "\t" else count

    speak = speechIndentConfig
    if toneIndentConfig:
        if quarterTones <= speech.speech.IDT_MAX_SPACES:
            pitch = speech.speech.IDT_BASE_FREQUENCY * 2 ** (quarterTones / 24.0)  # 24 quarter tones per octave.
            indentSequence.append(speech.commands.BeepCommand(pitch, speech.speech.IDT_TONE_DURATION))
        else:
            # we have more than 72 spaces (18 tabs), and must speak it since we don't want to hurt the users ears.
            speak = True
    if speak:
        indentSequence.extend(res)
    return indentSequence

original_getSelectionMessageSpeech = None
def new_getSelectionMessageSpeech(
	message,
	text,
):
    """
    When we replace say space character with an earcon, then "space selected" message doesn't work well.
    Fixing that behavior.
    """
    if isPhoneticPunctuationEnabled() and not isinstance(text, str):
        # Assuming that str is an earcon rather than string
        return [
            message.replace('%s', ''),
            text,
        ]
    return original_getSelectionMessageSpeech(message, text)
