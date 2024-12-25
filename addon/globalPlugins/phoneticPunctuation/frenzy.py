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
from . import utils
from .commands import *
from . import phoneticPunctuation as pp
from controlTypes import OutputReason
from config.configFlags import ReportLineIndentation


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
    
    global original_getTextInfoSpeech
    original_getTextInfoSpeech = speech.speech.getTextInfoSpeech
    speech.speech.getTextInfoSpeech = new_getTextInfoSpeech
    #speech.sayAll.SayAllHandler._getTextInfoSpeech = speech.speech.getTextInfoSpeech
    
    global original_getPropertiesSpeech, original_getControlFieldSpeech
    original_getPropertiesSpeech = speech.speech.getPropertiesSpeech
    speech.speech.getPropertiesSpeech = new_getPropertiesSpeech
    original_getControlFieldSpeech = speech.speech.getControlFieldSpeech
    speech.speech.getControlFieldSpeech = new_getControlFieldSpeech
    speech.getPropertiesSpeech = speech.speech.getPropertiesSpeech
    speech.getControlFieldSpeech = speech.speech.getControlFieldSpeech
    
    global original_processAndLabelStates
    original_processAndLabelStates = controlTypes.processAndLabelStates
    controlTypes.processAndLabelStates = new_processAndLabelStates

    global original_getTextInfoSpeech_considerSpelling    
    original_getTextInfoSpeech_considerSpelling = speech.speech._getTextInfoSpeech_considerSpelling
    speech.speech._getTextInfoSpeech_considerSpelling = new_getTextInfoSpeech_considerSpelling

def monkeyUnpatch():
    speech.speech.getObjectPropertiesSpeech = original_getObjectPropertiesSpeech
    speech.speech.getTextInfoSpeech = original_getTextInfoSpeech
    #speech.sayAll.SayAllHandler._getTextInfoSpeech = speech.speech.getTextInfoSpeech
    speech.speech.getPropertiesSpeech = original_getPropertiesSpeech
    speech.speech.getControlFieldSpeech = original_getControlFieldSpeech
    
    speech.getPropertiesSpeech = speech.speech.getPropertiesSpeech
    speech.getControlFieldSpeech = speech.speech.getControlFieldSpeech
    
    controlTypes.processAndLabelStates = original_processAndLabelStates
    
    speech.speech._getTextInfoSpeech_considerSpelling = original_getTextInfoSpeech_considerSpelling


roleRules = None
stateRules = None
stateDict = None
negativeStateDict=None
formatRules = None
numericFormatRules = None
otherRules = None
def updateRules():
    global roleRules, stateRules, formatRules, numericFormatRules, otherRules, stateDict, negativeStateDict
    roleRules = {
        rule.getFrenzyValue(): rule
        for rule in pp.rulesByFrenzy[FrenzyType.ROLE]
        if rule.enabled
    }
    stateRules = {
        rule.getFrenzyValue(): rule
        for rule in pp.rulesByFrenzy[FrenzyType.STATE]
        if rule.enabled
    }
    formatRules = {
        rule.getFrenzyValue(): rule
        for rule in pp.rulesByFrenzy[FrenzyType.FORMAT]
        if rule.enabled
    }
    numericFormatRules = {
        rule.getFrenzyValue(): rule
        for rule in pp.rulesByFrenzy[FrenzyType.NUMERIC_FORMAT]
        if rule.enabled
    }
    otherRules = {
        rule.getFrenzyValue(): rule
        for rule in pp.rulesByFrenzy[FrenzyType.OTHER_RULE]
        if rule.enabled
    }
    verbose = utils.getConfig("stateVerbose")
    stateDict = {}
    for rule in pp.rulesByFrenzy[FrenzyType.STATE]:
        if                  not verbose and rule.suppressStateClutter:
            stateDict[rule.getFrenzyValue()] = ""
        elif rule.ruleType == audioRuleNoop:
            # Don't set any value - NVDA will default to builtin state announcement
            continue
        else:
            stateDict[rule.getFrenzyValue()] = rule.getSpeechCommand()[0]
    negativeStateDict = {}
    for rule in pp.rulesByFrenzy[FrenzyType.NEGATIVE_STATE]:
        if                  not verbose and rule.suppressStateClutter:
            negativeStateDict[rule.getFrenzyValue()] = ""
        elif rule.ruleType == audioRuleNoop:
            # Don't set any value - NVDA will default to builtin state announcement
            continue
        else:
            negativeStateDict[rule.getFrenzyValue()] = rule.getSpeechCommand()[0]

class FakeTextInfo:
    def __init__(self, info, formatConfig, preventSpellingCharacters):
        self.info = info
        self.formatConfig = formatConfig.copy()
        self.preventSpellingCharacters = preventSpellingCharacters
        fields = info.getTextWithFields(formatConfig)
        if False:
          for i in range(len(fields)):
            field = fields[i]
            # If we have a heading or a format change, we insert an empty string right before, so that "out of container" messages can be spoken before other formatting information
            # this is disabled for now as it has too many side effects
            if isinstance(field,textInfos.FieldCommand):
                if (
                    field.command == "formatChange"
                    or (
                        field.command == "controlStart"
                        and field.field.get('role', None) == controlTypes.Role.HEADING
                    )
                ):
                    fields.insert(i, " \n")
                    break
        self.fields = fields
    
    def setSkipSet(self, skipSet):
        self.skipSet = skipSet
        
    def setStartAndEnd(self, start, end):
        self.start, self.end = start, end

    def getTextWithFields(self, formatConfig= None):
        # We tweak indentation reporting, so it's ok that indentation reporting field value is different.
        # However for sanity check we would like to ensure that all the other fields are identical.
        try:
            self.formatConfig["reportLineIndentation"] = formatConfig["reportLineIndentation"]
        except KeyError:
            pass
        if formatConfig != self.formatConfig:
            raise ValueError
        stack = []
        info = self.info
        skipSet = self.skipSet
        start = self.start
        end = self.end
        result = []
        fields = self.fields
        controlStackDepth = 0
        for i, field in enumerate(fields[:end]):
            if i in skipSet:
                continue
            if isinstance(field,textInfos.FieldCommand):
                if field.command == "controlStart":
                    controlStackDepth += 1
                elif field.command == "controlEnd":
                    controlStackDepth -= 1
            if i < start:
                if isinstance(field,textInfos.FieldCommand):
                    if field.command == "controlStart":
                        result.append(field)
                    elif field.command == "controlEnd":
                        del result[-1]
            else:
                # If we are just closing the previous controlStart without any content - drop that controlStart instead
                if (
                    len(result) > 0
                    and isinstance(result[-1], textInfos.FieldCommand)
                    and isinstance(field,textInfos.FieldCommand)
                    and result[-1].command == "controlStart"
                    and field.command == "controlEnd"
                ):
                    del result[-1]
                else:
                        # In order to avoid single spaces being spoken in a longer line when speaking by word, line or paragraph, augment them with another character to avoid spelling symbol names.
                    if False and self.preventSpellingCharacters and isinstance(field, str):
                        field = field + '\n'
                    if isinstance(field,textInfos.FieldCommand):
                        if field.command == "controlStart":
                            if field.field['role'] == controlTypes.Role.EDITABLETEXT:
                                #field.field['role'] = controlTypes.Role.UNKNOWN
                                pass
                                
                    result.append(field)
        result += [textInfos.FieldCommand("controlEnd", field=None)] * controlStackDepth
        return result
    
    def getControlFieldSpeech(
            self,
            attrs,
            ancestorAttrs,
            fieldType,
            formatConfig = None,
            extraDetail = False,
            reason= None
    ):
        return self.info.getControlFieldSpeech(
            attrs,
            ancestorAttrs,
            fieldType,
            formatConfig,
            extraDetail,
            reason,
        )

    def getFormatFieldSpeech(
            self,
            attrs,
            attrsCache= None,
            formatConfig= None,
            reason = None,
            unit = None,
            extraDetail = False,
            initialFormat = False,
    ):
        return self.info.getFormatFieldSpeech(
            attrs,
            attrsCache,
            formatConfig,
            reason ,
            unit ,
            extraDetail ,
            initialFormat ,
        )
    @property
    def obj(self):
        return self.info.obj

def findControlEnd(fields, start):
    i = start
    stack = []
    while i < len(fields):
        field = fields[i]
        if isinstance(field,textInfos.FieldCommand):
            if field.command == "controlStart":
                stack.append(field)
            elif field.command == "controlEnd":
                del stack[-1]
        if len(stack) == 0:
            return i
        i += 1
    raise RuntimeError()


def findAllHeadings(fields):
    for i, field in enumerate(fields):
        if isinstance(field,textInfos.FieldCommand):
            if field.command == "controlStart":
                try:
                    if field.field['role'] == controlTypes.Role.HEADING:
                        yield i
                except KeyError:
                    pass

def findAllFormatFieldBrackets(fields):
    currentStartIndex = None
    for i, field in enumerate(fields):
        if isinstance(field,textInfos.FieldCommand):
            if currentStartIndex is not None:
                yield (currentStartIndex, i)
                currentStartIndex = None
            if field.command == "formatChange":
                currentStartIndex = i

def isBlankSequence(sequence):
    for grouping  in sequence:
        for s in grouping:
            if isinstance(s, str)  and not speech.speech.isBlank(s):
                return False
    return True

def computeStackAtIndex(fields, index):
    stack = []
    for field in fields[:index]:
        if isinstance(field,textInfos.FieldCommand):
            if field.command == "controlStart":
                stack.append(field)
            elif field.command == "controlEnd":
                del stack[-1]
    return stack

def computeCacheableStateAtEnd(fields):
    stringFieldIndices = [i for i, field in enumerate(fields) if isinstance(field, str)]
    if len(stringFieldIndices) == 0:
        return {}
    lastIndex = stringFieldIndices[-1]
    stack = computeStackAtIndex(fields, lastIndex)
    result = {}
    for field in stack:
        if field.field['role'] == controlTypes.Role.HEADING:
            headingLevel = field.field.get('level', None)
            if headingLevel is not None:
                result['headingLevel'] = int(headingLevel)
    
    return result

original_getTextInfoSpeech = None
api.s = []
api.b = []
def new_getTextInfoSpeech(
        info,
        useCache = True,
        formatConfig= None,
        unit = None,
        reason = OutputReason.QUERY,
        _prefixSpeechCommand= None,
        onlyInitialFields = False,
        suppressBlanks = False
):
    if not isPhoneticPunctuationEnabled():
        yield from original_getTextInfoSpeech(
            info,
            useCache ,
            formatConfig,
            unit ,
            reason ,
            _prefixSpeechCommand,
            onlyInitialFields,
            suppressBlanks,
        )
        return
    if True:
        # Computing formatConfig - identical to logic in the original function
        extraDetail = unit in (textInfos.UNIT_CHARACTER, textInfos.UNIT_WORD)
        if not formatConfig:
            formatConfig = config.conf["documentFormatting"]
        formatConfig = formatConfig.copy()
        if extraDetail:
            formatConfig["extraDetail"] = True
        # For performance reasons, when navigating by paragraph or table cell, spelling errors will not be announced.
        if unit in (textInfos.UNIT_PARAGRAPH, textInfos.UNIT_CELL) and reason == OutputReason.CARET:
            formatConfig["reportSpellingErrors"] = False
    headingLevelRule = numericFormatRules.get(NumericTextFormat.HEADING_LEVEL, None)
    fontSizeRule = numericFormatRules.get(NumericTextFormat.FONT_SIZE, None)
    processHeadings = headingLevelRule is not None
    firstHeadingCommand = None
    fakeTextInfo  = FakeTextInfo(info, formatConfig, preventSpellingCharacters=unit != textInfos.UNIT_CHARACTER)
    fields = fakeTextInfo.fields

    #skip set contains indices where heading controls start and end.
    # We will filter them out before returning from this function as we don't want built-in NVDA logic to double-process headings.
    # They also serve as boundaries for other font attribute processing as typically text formatting changes when we enter/exit a heading.
    skipSet = set()
    newCommands = collections.defaultdict(lambda: [])
    try:
        cache = info.obj.ppCache
    except AttributeError:
        cache = {}
    newCache = {}
    try:
        newCache['fontSize'] = cache['fontSize']
    except KeyError:
        pass
    if processHeadings:
        headingStarts = list(findAllHeadings(fields))
        headingEnds = [findControlEnd(fields, headingSstart) for headingSstart in headingStarts]
        nHeadings = len(headingStarts)
        # Filter out nested headings.
        # Nested headings happen on very few web pages and typically are not meaningful.
        # In theory we can handle nested headings properly, but this greatly overcomplicates the code with only marginal return.
        lastHeadingEnd = -1
        nestedHeadingIndices = set()
        for i in range(nHeadings):
            if headingStarts[i] < lastHeadingEnd:
                nestedHeadingIndices.add(i)
            lastHeadingEnd = headingEnds[i]
        skipSet.update(headingStarts)
        skipSet.update(headingEnds)
        for i, (start, end) in enumerate(zip(headingStarts, headingEnds)):
            if i in nestedHeadingIndices:
                continue
            level = fields[start].field.get('level', None)
            try:
                level = int(level)
            except (ValueError, TypeError):
                continue
            preCommand, postCommand = headingLevelRule.getNumericSpeechCommand(level)
            if isinstance(preCommand, speech.commands.BaseProsodyCommand):
                pass
            elif isinstance(preCommand, str):
                if i == 0 and unit in [textInfos.UNIT_CHARACTER, textInfos.UNIT_WORD]:
                    # Compare with cached heading level - we don't want to repeat heading level on every char or word move
                    if cache.get('headingLevel', None) == level:
                        continue
                elif reason == OutputReason.QUICKNAV:
                    # During quickNav speak Heading level at the end.
                    preCommand, postCommand = postCommand, preCommand
            else:
                raise RuntimeError
            if preCommand is not None:
                if firstHeadingCommand is None:
                    firstHeadingCommand = preCommand
                newCommands[start].append(preCommand)
            if postCommand is not None:
                newCommands[end].append(postCommand)
    if fontSizeRule is not None:
        samplePreCommand, samplePostCommand = fontSizeRule.getNumericSpeechCommand(10)
        # If configured to report heading levels and font size via same prosody  command, then skip headings to avoid interference
        skipHeadingsForFontSize = processHeadings and isinstance(samplePreCommand, speech.commands.BaseProsodyCommand) and type(samplePreCommand) == type(firstHeadingCommand)
        for begin, end in findAllFormatFieldBrackets(fields):
            if skipHeadingsForFontSize and any(headingStart < begin < headingEnd for headingStart, headingEnd in zip(headingStarts, headingEnds)):
                continue
            try:
                fontSizeStr = fields[begin].field['font-size']
                fontSizeStr =re.sub(" ?pt$", "", fontSizeStr)
                fontSize = float(fontSizeStr)
            except (KeyError, ValueError):
                try:
                    del newCache['fontSize']
                except KeyError:
                    pass
                continue
            prevFontSize = newCache.get('fontSize', None)
            newCache['fontSize'] = fontSize
            preCommand, postCommand = fontSizeRule.getNumericSpeechCommand(fontSize)
            if isinstance(preCommand, speech.commands.BaseProsodyCommand):
                pass
            elif isinstance(preCommand, str):
                if True:
                    # Compare with cached font size
                    if prevFontSize == fontSize:
                        continue
            else:
                raise RuntimeError
            if preCommand is not None:
                newCommands[begin].append(preCommand)
            if postCommand is not None:
                newCommands[end].append(postCommand)

    newCache.update(computeCacheableStateAtEnd(fields))
    info.obj.ppCache = newCache
    
    previousIndex = 0
    fakeTextInfo.setSkipSet(skipSet)
    nFields = len(fields)
    intervalsAndCommands = []
    nIntervals = 0
    emptyIntervals = set()
    for i in sorted(newCommands.keys()) + [nFields]:
        intervalsAndCommands.append((previousIndex, i))
        nIntervals += 1
        # If there are no str fields in this range, skip it, otherwise it'll believe we exited some controls and store that in the cache.
        isEmpty = not any(isinstance(field, str) for field in fields[previousIndex:i])
        if isEmpty:
            emptyIntervals.add(len(intervalsAndCommands) - 1)
        try:
            intervalsAndCommands.append(newCommands[i])
        except KeyError:
            pass
        previousIndex = i
    emptyIndex = 0
    allEmpty = nIntervals == len(emptyIntervals)
    filteredIntervalsAndCommands = []
    # Filtering out empty intervals. However, if all intervals are empty, we would like to keep the first one.
    for i, interval in enumerate(intervalsAndCommands):
        if isinstance(interval, list):
            # injected commands - always keep them
            filteredIntervalsAndCommands.append(interval)
        elif isinstance(interval, tuple):
            isEmpty = i in emptyIntervals
            if not isEmpty or (allEmpty and emptyIndex ==0):
                filteredIntervalsAndCommands.append(interval)
            emptyIndex += int(isEmpty)
        else:
            raise RuntimeError
    result = []
    # Even though we have already filtered out empty intervals (e.g. intervals containingg no string to speak),
    # Some of the intervals might still be blank, e.g., if an interval only contains a single whitespace character,
    # NVDA would speak it as blank".
    # We would like to avoid that, so we will suppress blanks on all intervals except for the last one if all previous are blank.
    lastIntervalIndex = [i for i, interval in enumerate(filteredIntervalsAndCommands) if isinstance(interval, tuple)][-1]
    isBlankSoFar = True

    for i, item in enumerate(filteredIntervalsAndCommands):
        if isinstance(item, list):
            # Injected commands
            result.append(item)
        elif isinstance(item, tuple):
            # Interval
            start, end = item
            fakeTextInfo.setStartAndEnd(start, end)
            effectiveSuppressBlanks=True if i < lastIntervalIndex or not isBlankSoFar else suppressBlanks
            if not effectiveSuppressBlanks:
                # We are not suppressing the blanks
                # 1. back up cache
                # 2. Get the sequence with blanks suppressed, so that we can compare it later and decide whether blank is to be spoken
                # 3. Restore the cache if applicable
                if isinstance(useCache, speech.speech.SpeakTextInfoState):
                    useCacheBackup = useCache.copy()
                elif useCache:
                    speakTextInfoStateBackup = speech.speech.SpeakTextInfoState(info.obj)
                suppressedSequence = list(original_getTextInfoSpeech(
                    fakeTextInfo,
                    useCache ,
                    formatConfig,
                    unit ,
                    reason ,
                    _prefixSpeechCommand,
                    onlyInitialFields,
                    suppressBlanks=True,
                ))
                if isinstance(useCache, speech.speech.SpeakTextInfoState):
                    useCache = useCacheBackup
                elif useCache:
                    speakTextInfoStateBackup.updateObj()

            sequence = list(original_getTextInfoSpeech(
                fakeTextInfo,
                useCache ,
                formatConfig,
                unit ,
                reason ,
                _prefixSpeechCommand,
                onlyInitialFields,
                suppressBlanks=effectiveSuppressBlanks,
            ))
            if not effectiveSuppressBlanks:
                blankRule = otherRules.get(OtherRule.BLANK, None)
                if blankRule is not None:
                    # only compare string commands
                    sequenceStrings = [s for ss in sequence for s in ss if isinstance(s, str)]
                    suppressedSequenceStrings = [s for ss in suppressedSequence for s in ss if isinstance(s, str)]
                    if len(sequenceStrings) == 1 and len(suppressedSequenceStrings) == 0:
                        # Blank detected!
                        blankString = sequenceStrings[0]
                        blankCommand = blankRule.getSpeechCommand()[0]
                        for subsequence in sequence:
                            for i, command in enumerate(subsequence):
                                if command == blankString:
                                    subsequence[i] = blankCommand
            isBlank = isBlankSequence(sequence)
            if not isBlank:
                isBlankSoFar = False
            result.extend(sequence)
            # Whatever is the original value of indentation reporting,
            # we should only report it for the first interval and turn off for all the rest.
            formatConfig["reportLineIndentation"] = ReportLineIndentation.OFF
    # At this point result is a list of lists of speech commands.
    # We group them together - this way if speech is interrupted, then NVDA will automatically cancel pending pitch and other prosody commands.
    result = [[item for subgroup in result for item in subgroup]]
    yield from result

# some random funny Unicode characters
PROPERTY_SPEECH_SIGNATURE = "🪛🪕🚛"
PROPERTY_SPEECH_SIGNATURE2 = "🪼‣⁋"
original_getPropertiesSpeech = None
def new_getPropertiesSpeech(
    reason: OutputReason = OutputReason.QUERY,
    **propertyValues,
):
    if not isPhoneticPunctuationEnabled():
        return original_getPropertiesSpeech(reason, **propertyValues)
    if len(propertyValues) == 1:
        role = propertyValues.get('role', None)
        if role in roleRules and roleRules[role].enabled:
            return [f"{PROPERTY_SPEECH_SIGNATURE}{role.name}{PROPERTY_SPEECH_SIGNATURE}"]
        states = propertyValues.get('states', None)
            
    result =  original_getPropertiesSpeech(reason, **propertyValues)
    if 'role' in propertyValues and len(propertyValues) == 1:
        # Only role text is requested. We need to mark it with signature, so that later we can tell whether we're jumping out of container.
        # We will strip off the signature downstream.
        if len(result) == 1:
            result = [f"{PROPERTY_SPEECH_SIGNATURE2}{result[0]}{PROPERTY_SPEECH_SIGNATURE2}"]
    return result

PROPERTY_SPEECH_PATTERN = re.compile(f"{PROPERTY_SPEECH_SIGNATURE}(\w+){PROPERTY_SPEECH_SIGNATURE}")
PROPERTY_SPEECH_PATTERN2 = re.compile(f"{PROPERTY_SPEECH_SIGNATURE2}(.+){PROPERTY_SPEECH_SIGNATURE2}")
original_getControlFieldSpeech = None
api.co = []
def new_getControlFieldSpeech(
    attrs,
    ancestorAttrs,
    fieldType,
    formatConfig=None,
    extraDetail = False,
    reason = None,
):
    result = original_getControlFieldSpeech(attrs, ancestorAttrs, fieldType, formatConfig, extraDetail, reason)
    if not isPhoneticPunctuationEnabled():
        return result
    result2 = []
    for i, utterance in enumerate(result):
        if isinstance(utterance, str):
            # The differentce between PROPERTY_SPEECH_PATTERN and PROPERTY_SPEECH_PATTERN2 is as follows:
            # PROPERTY_SPEECH_PATTERN is found when we aim to replace role utterance with an earcone because there is a rule configured for this role.
            # PROPERTY_SPEECH_PATTERN2 is found when we plan to keep the original role utterance (no rule configured for that role), but we still need to detect "out of container" mode.
            # When either of these two patterns are perfectly matched, this means we are entering said role.
            # When the match is not perfect, e.g. extra characters are present, that means that we are exiting the container, and that the string is something like "out of frame" where "out of" might be localized.
            if m := PROPERTY_SPEECH_PATTERN.match(utterance):
                # Replacing role speech with earcon
                role = getattr(controlTypes.Role, m.group(1))
                rule = roleRules[role]
                command = rule.getSpeechCommand()[0]
                result2.append(command)
                continue
            elif m := PROPERTY_SPEECH_PATTERN2.match(utterance):
                # Just strip off the signature - this is just a role utterance
                result2.append(m.group(1))
                continue
            elif m := PROPERTY_SPEECH_PATTERN.search(utterance):
                # We have the string, but there are also some other extra characters present.
                # We assume this says something like "Out of frame" - that is we are exiting a container.
                # Since "out of" is possibly translated to other languages, we can't just match it, so we detect presence of extra characters instead.
                oocRule = otherRules.get(OtherRule.OUT_OF_CONTAINER, None)
                if oocRule is not None:
                    command = oocRule.getSpeechCommand()[0]
                    result2.append(command)
                    continue
                else:
                    role = getattr(controlTypes.Role, m.group(1))
                    rule = roleRules[role]
                    command = rule.getSpeechCommand()[0]
                    result2.append(_("out of"))
                    result2.append(command)
                    continue
            elif m := PROPERTY_SPEECH_PATTERN2.search(utterance):
                # We have the string, but there are also some other extra characters present.
                # We assume this says something like "Out of frame" - that is we are exiting a container.
                # Since "out of" is possibly translated to other languages, we can't just match it, so we detect presence of extra characters instead.
                oocRule = otherRules.get(OtherRule.OUT_OF_CONTAINER, None)
                if oocRule is not None:
                    command = oocRule.getSpeechCommand()[0]
                    result2.append(command)
                    continue
                else:
                    restoredUtterance = PROPERTY_SPEECH_PATTERN2.sub(r'\1', utterance)
                    result2.append(restoredUtterance)
                    continue
        result2.append(utterance)
    return result2

original_processAndLabelStates = None
def new_processAndLabelStates(
    role,
    states,
    reason,
    positiveStates= None,
    negativeStates=None,
    positiveStateLabelDict={},
    negativeStateLabelDict={},
):
    # Braille provides custom dictionaries for positive and negative states - we don't mess with Braille.
    # However when the dictionaries are empty, we provide our own custom dictionaries.
    if len(positiveStateLabelDict) == 0 and len(negativeStateLabelDict) == 0:
        positiveStateLabelDict = stateDict
        negativeStateLabelDict = negativeStateDict
    return  original_processAndLabelStates(
        role,
        states,
        reason,
        positiveStates,
        negativeStates,
        positiveStateLabelDict,
        negativeStateLabelDict,
    )

original_getTextInfoSpeech_considerSpelling = None
def new_getTextInfoSpeech_considerSpelling(
    unit,
    onlyInitialFields,
    textWithFields,
    reason,
    speechSequence,
    language,
):
    """
    For some reason the original function is set up to drop all the previous commands unless a string is present.
    This inadvertently drops our earcons when navigating by character.
    Specifically "out of container" earcon.
    Overriding the whole function to patch that behavior.
    """
    #if onlyInitialFields or any(isinstance(x, str) for x in speechSequence):
    if True:
        yield speechSequence
    if not onlyInitialFields:
        spellingSequence = list(
            speech.speech.getSpellingSpeech(
                textWithFields[0],
                locale=language,
            ),
        )
        speech.types.logBadSequenceTypes(spellingSequence)
        yield spellingSequence
        if (
            reason == OutputReason.CARET
            and unit == textInfos.UNIT_CHARACTER
            and config.conf["speech"]["delayedCharacterDescriptions"]
        ):
            descriptionSequence = list(
                speech.speech.getSingleCharDescription(
                    textWithFields[0],
                    locale=language,
                ),
            )
            yield descriptionSequence

