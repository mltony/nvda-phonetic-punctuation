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
from controlTypes import OutputReason
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

def monkeyUnpatch():
    speech.speech.getObjectPropertiesSpeech = original_getObjectPropertiesSpeech
    speech.speech.getTextInfoSpeech = original_getTextInfoSpeech

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

class FakeTextInfo:
    def __init__(self, info, formatConfig):
        self.info = info
        self.formatConfig = formatConfig
        self.fields = info.getTextWithFields(formatConfig)
    
    def setSkipSet(self, skipSet):
        self.skipSet = skipSet
        
    def setStartAndEnd(self, start, end):
        self.start, self.end = start, end

    def getTextWithFields(self, formatConfig= None):
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

def isBlankSequence(sequence):
    for grouping  in sequence:
        for s in grouping:
            if isinstance(s, str)  and not speech.speech.isBlank(s):
                return False
    return True


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
        # Computing if - identical to logic in the original function
        extraDetail = unit in (textInfos.UNIT_CHARACTER, textInfos.UNIT_WORD)
        if not formatConfig:
            formatConfig = config.conf["documentFormatting"]
        formatConfig = formatConfig.copy()
        if extraDetail:
            formatConfig["extraDetail"] = True
        # For performance reasons, when navigating by paragraph or table cell, spelling errors will not be announced.
        if unit in (textInfos.UNIT_PARAGRAPH, textInfos.UNIT_CELL) and reason == OutputReason.CARET:
            formatConfig["reportSpellingErrors"] = False
    processHeadings = True
    headingRule = pp.AudioRule(
        comment='asdf',
        pattern="",
        ruleType=audioRuleProsody,
        wavFile=None,
        builtInWavFile=None,
        startAdjustment=0,
        endAdjustment=0,
        tone=None,
        duration=None,
        enabled=True,
        caseSensitive=True,
        prosodyName="Pitch",
        prosodyOffset=None,
        prosodyMultiplier=None,
        volume=100,
        passThrough=False,
        frenzyType=FrenzyType.NUMERIC_FORMAT.name,
        frenzyValue=NumericTextFormat.HEADING_LEVEL,
        minNumericValue=1,
        maxNumericValue=6,
        prosodyMinOffset=-30,
        prosodyMaxOffset=30,
        replacementPattern=None,
    )
    fakeTextInfo  = FakeTextInfo(info, formatConfig)
    fields = fakeTextInfo.fields
    
    #skip set contains indices where heading controls start and end.
    # We will filter them out before returning from this function as we don't want built-in NVDA logic to double-process headings.
    # They also serve as boundaries for other font attribute processing as typically text formatting changes when we enter/exit a heading.
    skipSet = set()
    newCommands = collections.defaultdict(lambda: [])
    if processHeadings:
        headingStarts = list(findAllHeadings(fields))
        headingEnds = [findControlEnd(fields, headingSstart) for headingSstart in headingStarts]
        nHeadings = len(headingStarts)
        for i in range(nHeadings - 1):
            if headingStarts[i + 1] < headingEnds[i]:
                log.error("Nested headings detected. Earcons add-on doesn't support that yet.")
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
        skipSet.update(headingStarts)
        skipSet.update(headingEnds)
        for start, end in zip(headingStarts, headingEnds):
            level = fields[start].field.get('level', 1)
            try:
                level = int(level)
            except ValueError:
                continue
            preCommand, postCommand = headingRule.getNumericSpeechCommand(level)
            if preCommand is not None:
                newCommands[start].append(preCommand)
            if postCommand is not None:
                newCommands[end].append(postCommand)
    # TODO: process font attributes here
    previousIndex = 0
    fakeTextInfo.setSkipSet(skipSet)
    #tones.beep(500, 50)
    s = []
    api.s.append(s)
    b = []
    api.b.append(b)
    nFields = len(fields)
    intervalsAndCommands = []
    nIntervals = 0
    emptyIntervals = set()
    for i in sorted(newCommands.keys()) + [nFields]:
        intervalsAndCommands.append((previousIndex, i))
        nIntervals += 1
        # If there are no str fields in this range, skip it, otherwise it'll believe we exited some controls and store that in the cache.
        isEmpty = not any(isinstance(field, str) and not speech.speech.isBlank(field) for field in fields[previousIndex:i])
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
            filteredIntervalsAndCommands.append(interval)
        elif isinstance(interval, tuple):
            isEmpty = i in emptyIntervals
            if not isEmpty or (allEmpty and emptyIndex ==0):
                filteredIntervalsAndCommands.append(interval)
            emptyIndex += int(isEmpty)
        else:
            raise RuntimeError
    result = []
    for item in filteredIntervalsAndCommands:
        if isinstance(item, list):
            # Injected commands
            result.append(item)
        elif isinstance(item, tuple):
            # Interval
            i, j = item
            fakeTextInfo.setStartAndEnd(i, j)
            sequence = list(original_getTextInfoSpeech(
                fakeTextInfo,
                useCache ,
                formatConfig,
                unit ,
                reason ,
                _prefixSpeechCommand,
                onlyInitialFields,
                suppressBlanks=suppressBlanks,
            ))
            #yield from sequence
            result.extend(sequence)
    # At this point result is a list of lists of speech commands.
    # We group them together - this way if speech is interrupted, then NVDA will automatically cancel pending pitch and other prosody commands.
    result = [[item for subgroup in result for item in subgroup]]
    yield from result
