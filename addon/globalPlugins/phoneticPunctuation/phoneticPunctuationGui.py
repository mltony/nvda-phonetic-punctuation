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

from .phoneticPunctuation import *
from . import phoneticPunctuation as pp
from .utils import *
from . import common
class AudioRuleDialog(wx.Dialog):
    TYPE_LABELS = {
        audioRuleBuiltInWave: _("&Built in wave"),
        audioRuleWave: _("&Wave file"),
        audioRuleBeep: _("&Beep"),
        audioRuleProsody: _("&Prosody"),
    }
    PROSODY_LABELS = [
        "Pitch",
        "Volume",
        "Rate",
    ]
    TYPE_LABELS_ORDERING = audioRuleTypes

    def __init__(
        self,
        parent,
        title=_("Edit audio rule"),
        frenzyType=None,
        disallowedFrenzyValues=None,
    ):
        self.frenzyType = frenzyType
        if frenzyType        == FrenzyType.ROLE:
            self.possibleFrenzyValues = [controlTypes.role._roleLabels[role] for role in controlTypes.Role]
        elif frenzyType        == FrenzyType.STATE:
            self.possibleFrenzyValues = [controlTypes.state._stateLabels[state] for state in controlTypes.State]
        elif frenzyType        == FrenzyType.TEXT:
            self.possibleFrenzyValues = []
        elif frenzyType        == FrenzyType.FORMAT:
            self.possibleFrenzyValues = [TEXT_FORMAT_NAMES[f] for f in TextFormat]
        elif frenzyType        == FrenzyType.NUMERIC_FORMAT:
            self.possibleFrenzyValues = [NUMERIC_TEXT_FORMAT_NAMES[f] for f in NumericTextFormat]
        else:
            raise RuntimeError
        self.disallowedFrenzyValues = disallowedFrenzyValues
        
        self.lastTestTime = 0
        super(AudioRuleDialog,self).__init__(parent,title=title)
        mainSizer=wx.BoxSizer(wx.VERTICAL)
        sHelper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

      # Translators: label for pattern  edit field in add Audio Rule dialog.
        patternLabelText = _("&Pattern")
        self.patternTextCtrl=sHelper.addLabeledControl(patternLabelText, wx.TextCtrl)

      # Translators: label for frenzyValue
        labelText=FRENZY_NAMES_SINGULAR[self.frenzyType]
        self.frenzyValueCategory=guiHelper.LabeledControlHelper(
            self,
            labelText,
            wx.Choice,
            choices=self.possibleFrenzyValues,
        )
        self.frenzyValueCategory.control.Bind(wx.EVT_CHOICE,self.onFrenzyValueCategory)

      # Translators: label for rule_enabled  checkbox in add audio rule dialog.
        enabledText = _("Rule enabled")
        self.enabledCheckBox=sHelper.addItem(wx.CheckBox(self,label=enabledText))
        self.enabledCheckBox.SetValue(True)
      # Translators: label for enable passthrough checkbox
        labelText = _("Pass raw text through to synth. Typically you want to enable this only for punctuation marks and disable for all other rules.")
        self.passThroughCheckBox=sHelper.addItem(wx.CheckBox(self,label=labelText))
        self.passThroughCheckBox.SetValue(False)

      # Translators:  label for type selector radio buttons in add audio rule dialog
        typeText = _("&Type")
        typeChoices = [AudioRuleDialog.TYPE_LABELS[i] for i in AudioRuleDialog.TYPE_LABELS_ORDERING]
        self.typeRadioBox=sHelper.addItem(wx.RadioBox(self,label=typeText, choices=typeChoices))
        self.typeRadioBox.Bind(wx.EVT_RADIOBOX,self.onType)
        self.setType(audioRuleBuiltInWave)

        self.typeControls = {
            audioRuleBuiltInWave: [],
            audioRuleWave: [],
            audioRuleBeep: [],
            audioRuleProsody: [],
        }

      # Translators: built in wav category  combo box
        biwCategoryLabelText=_("&Category:")
        self.biwCategory=guiHelper.LabeledControlHelper(
            self,
            biwCategoryLabelText,
            wx.Choice,
            choices=self.getBiwCategories(),
        )
        self.biwCategory.control.Bind(wx.EVT_CHOICE,self.onBiwCategory)
        self.typeControls[audioRuleBuiltInWave].append(self.biwCategory.control)
      # Translators: built in wav file combo box
        biwListLabelText=_("&Wave:")
        #self.biwList = sHelper.addLabeledControl(biwListLabelText, wx.Choice, choices=self.getBuiltInWaveFiles())
        self.biwList=guiHelper.LabeledControlHelper(
            self,
            biwListLabelText,
            wx.Choice,
            choices=[],
        )

        self.biwList.control.Bind(wx.EVT_CHOICE,self.onBiw)
        self.typeControls[audioRuleBuiltInWave].append(self.biwList.control)
      # Translators: wav file edit box
        self.wavName  = sHelper.addLabeledControl(_("Wav file"), wx.TextCtrl)
        #self.wavName.Disable()
        self.typeControls[audioRuleWave].append(self.wavName)

      # Translators: This is the button to browse for wav file
        self._browseButton = sHelper.addItem (wx.Button (self, label = _("&Browse...")))
        self._browseButton.Bind(wx.EVT_BUTTON, self._onBrowseClick)
        self.typeControls[audioRuleWave].append(self._browseButton)
      # Volume slider
        label = _("Volume")
        self.volumeSlider = sHelper.addLabeledControl(label, wx.Slider, minValue=0,maxValue=100)
        self.volumeSlider.SetValue(100)
        self.typeControls[audioRuleWave].append(self.volumeSlider)
        self.typeControls[audioRuleBuiltInWave].append(self.volumeSlider)
        self.typeControls[audioRuleBeep].append(self.volumeSlider)

      # Translators: label for adjust start
        label = _("Start adjustment in millis - positive to cut off start, negative for extra pause in the beginning.")
        self.startAdjustmentTextCtrl=sHelper.addLabeledControl(label, wx.TextCtrl)
        self.typeControls[audioRuleWave].append(self.startAdjustmentTextCtrl)
        self.typeControls[audioRuleBuiltInWave].append(self.startAdjustmentTextCtrl)
      # Translators: label for adjust end
        label = _("End adjustment in millis - positive for early cut off, negative for extra pause in the end")
        self.endAdjustmentTextCtrl=sHelper.addLabeledControl(label, wx.TextCtrl)
        self.typeControls[audioRuleWave].append(self.endAdjustmentTextCtrl)
        self.typeControls[audioRuleBuiltInWave].append(self.endAdjustmentTextCtrl)
      # Translators: label for tone
        toneLabelText = _("&Tone")
        self.toneTextCtrl=sHelper.addLabeledControl(toneLabelText, wx.TextCtrl)
        #self.toneTextCtrl.Disable()
        self.typeControls[audioRuleBeep].append(self.toneTextCtrl)
      # Translators: label for duration
        durationLabelText = _("Duration in milliseconds:")
        self.durationTextCtrl=sHelper.addLabeledControl(durationLabelText, wx.TextCtrl)
        #self.durationTextCtrl.Disable()
        self.typeControls[audioRuleBeep].append(self.durationTextCtrl)
      # Translators: prosody name comboBox
        prosodyNameLabelText=_("&Prosody name:")
        self.prosodyNameCategory=guiHelper.LabeledControlHelper(
            self,
            prosodyNameLabelText,
            wx.Choice,
            choices=self.PROSODY_LABELS,
        )
        self.typeControls[audioRuleProsody].append(self.prosodyNameCategory.control)
      # Translators: label for prosody offset
        prosodyOffsetLabelText = _("Prosody offset:")
        self.prosodyOffsetTextCtrl=sHelper.addLabeledControl(prosodyOffsetLabelText, wx.TextCtrl)
        self.typeControls[audioRuleProsody].append(self.prosodyOffsetTextCtrl)
      # Translators: label for prosody multiplier
        prosodyMultiplierLabelText = _("Prosody multiplier:")
        self.prosodyMultiplierTextCtrl=sHelper.addLabeledControl(prosodyMultiplierLabelText, wx.TextCtrl)
        self.typeControls[audioRuleProsody].append(self.prosodyMultiplierTextCtrl)

      # Translators: label for comment edit box
        commentLabelText = _("&Comment")
        self.commentTextCtrl=sHelper.addLabeledControl(commentLabelText, wx.TextCtrl)
      # Translators: This is the button to test audio rule
        self.testButton = sHelper.addItem (wx.Button (self, label = _("&Test, press twice for repeated sound")))
        self.testButton.Bind(wx.EVT_BUTTON, self.onTestClick)

        sHelper.addDialogDismissButtons(self.CreateButtonSizer(wx.OK|wx.CANCEL))

        mainSizer.Add(sHelper.sizer,border=20,flag=wx.ALL)
        mainSizer.Fit(self)
        self.SetSizer(mainSizer)
        self.patternTextCtrl.SetFocus()
        self.Bind(wx.EVT_BUTTON,self.onOk,id=wx.ID_OK)
      # Touching up
        self.onType(None)
        if self.frenzyType == FrenzyType.TEXT:
            self.frenzyValueCategory.control.Disable()
        else:
            self.patternTextCtrl.Disable()
            self.passThroughCheckBox.Disable()
            self.frenzyValueCategory.control.SetFocus()


    def getType(self):
        typeRadioValue = self.typeRadioBox.GetSelection()
        if typeRadioValue == wx.NOT_FOUND:
            return audioRuleBuiltInWave
        return AudioRuleDialog.TYPE_LABELS_ORDERING[typeRadioValue]

    def setType(self, type):
        self.typeRadioBox.SetSelection(AudioRuleDialog.TYPE_LABELS_ORDERING.index(type))

    def getInt(self, s):
        if len(s) == 0:
            return None
        return int(s)

    def editRule(self, rule):
        self.commentTextCtrl.SetValue(rule.comment)
        self.patternTextCtrl.SetValue(rule.pattern)
        if self.frenzyType != rule.getFrenzyType():
            raise RuntimeError
        idx = None
        if self.frenzyType        == FrenzyType.ROLE:
            idx = list(controlTypes.Role).index(rule.getFrenzyValue())
        elif self.frenzyType        == FrenzyType.STATE:
            idx = list(controlTypes.State).index(rule.getFrenzyValue())
        if idx is not None:
            self.frenzyValueCategory.control.SetSelection(idx)

        self.setType(rule.ruleType)
        self.wavName.SetValue(rule.wavFile)
        self.setBiw(rule.builtInWavFile)
        self.volumeSlider.SetValue(rule.volume or 100)
        self.startAdjustmentTextCtrl.SetValue(str(rule.startAdjustment or 0))
        self.endAdjustmentTextCtrl.SetValue(str(rule.endAdjustment or 0))
        self.toneTextCtrl.SetValue(str(rule.tone or 500))
        self.durationTextCtrl.SetValue(str(rule.duration or 50))
        self.enabledCheckBox.SetValue(rule.enabled)
        try:
            prosodyCategoryIndex = self.PROSODY_LABELS.index(rule.prosodyName)
        except ValueError:
            prosodyCategoryIndex = 0
        self.prosodyNameCategory.control.SetSelection(prosodyCategoryIndex)
        self.prosodyOffsetTextCtrl.SetValue(str(rule.prosodyOffset or ""))
        self.prosodyMultiplierTextCtrl.SetValue(str(rule.prosodyMultiplier or ""))
        #self.caseSensitiveCheckBox.SetValue(rule.caseSensitive)
        self.passThroughCheckBox.SetValue(rule.passThrough)
        self.onType(None)

    def makeRule(self):
        if self.frenzyType == FrenzyType.TEXT:
            if not self.patternTextCtrl.GetValue():
                # Translators: This is an error message to let the user know that the pattern field is not valid.
                gui.messageBox(_("A pattern is required."), _("Dictionary Entry Error"), wx.OK|wx.ICON_WARNING, self)
                self.patternTextCtrl.SetFocus()
                return
            try:
                r = re.compile(self.patternTextCtrl.GetValue())
            except sre_constants.error:
                # Translators: Invalid regular expression
                gui.messageBox(_("Invalid regular expression."), _("Dictionary Entry Error"), wx.OK|wx.ICON_WARNING, self)
                self.patternTextCtrl.SetFocus()
                return
            if r.search(''):
                gui.messageBox(_("Regular expression pattern matches empty string. This is not allowed. Please change the pattern."), _("Dictionary Entry Error"), wx.OK|wx.ICON_WARNING, self)
                self.patternTextCtrl.SetFocus()
                return
            frenzyValue = None
        else:
            frenzyValueStr = self.possibleFrenzyValues[self.frenzyValueCategory.control.GetSelection()]
            if self.frenzyType == FrenzyType.ROLE:
                frenzyValue = [k for k, v in controlTypes.role._roleLabels.items() if v == frenzyValueStr][0]
            elif self.frenzyType == FrenzyType.STATE:
                frenzyValue = [k for k, v in controlTypes.state._stateLabels.items() if v == frenzyValueStr][0]
            elif self.frenzyType == FrenzyType.FORMAT:
                frenzyValue = ""
            else:
                raise RuntimeError
            if frenzyValue in self.disallowedFrenzyValues:
                gui.messageBox(_("This value is already used in another rule."), _("Dictionary Entry Error"), wx.OK|wx.ICON_WARNING, self)
                self.frenzyValueCategory.control.SetFocus()
                return


        if self.getType() == audioRuleWave:
            if not self.wavName.GetValue() or not os.path.exists(self.wavName.GetValue()):
                # Translators: wav file not found
                gui.messageBox(_("Wav file not found."), _("Dictionary Entry Error"), wx.OK|wx.ICON_WARNING, self)
                self.wavName.SetFocus()
                return
            try:
                wave.open(self.wavName.GetValue(), "r").close()
            except wave.Error:
                # Translators: Invalid wav file
                gui.messageBox(_("Invalid wav file."), _("Dictionary Entry Error"), wx.OK|wx.ICON_WARNING, self)
                self.wavName.SetFocus()
                return
        try:
            self.getInt(self.startAdjustmentTextCtrl.GetValue())
        except ValueError:
            # Translators: Invalid regular expression
            gui.messageBox(_("Start adjustment must be a number."), _("Dictionary Entry Error"), wx.OK|wx.ICON_WARNING, self)
            self.startAdjustmentTextCtrl.SetFocus()
            return
        try:
            self.getInt(self.endAdjustmentTextCtrl.GetValue())
        except ValueError:
            # Translators: Invalid regular expression
            gui.messageBox(_("End adjustment must be a number."), _("Dictionary Entry Error"), wx.OK|wx.ICON_WARNING, self)
            self.endAdjustmentTextCtrl.SetFocus()
            return
        if self.getType() == audioRuleBeep:
            good = False
            try:
                tone = self.getInt(self.toneTextCtrl.GetValue())
                if 0 <= tone <= 50000:
                    good = True
            except ValueError:
                pass
            if not good:
                gui.messageBox(_("tone must be an integer between 0 and 50000"), _("Dictionary Entry Error"), wx.OK|wx.ICON_WARNING, self)
                self.toneTextCtrl.SetFocus()
                return

            good = False
            try:
                duration = self.getInt(self.durationTextCtrl.GetValue())
                if 0 <= duration <= 60000:
                    good = True
            except ValueError:
                pass
            if not good:
                gui.messageBox(_("duration must be an integer between 0 and 60000"), _("Dictionary Entry Error"), wx.OK|wx.ICON_WARNING, self)
                self.durationTextCtrl.SetFocus()
                return
        prosodyOffset = None
        prosodyMultiplier = None
        if self.getType() == audioRuleProsody:
            good = False
            try:
                if len(self.prosodyOffsetTextCtrl.GetValue()) == 0:
                    prosodyOffset = None
                    good = True
                else:
                    prosodyOffset = self.getInt(self.prosodyOffsetTextCtrl.GetValue())
                    if -100 <= prosodyOffset <= 100:
                        good = True
            except ValueError:
                pass
            if not good:
                gui.messageBox(_("prosody offset must be an integer between -100 and 100"), _("Dictionary Entry Error"), wx.OK|wx.ICON_WARNING, self)
                self.prosodyOffsetTextCtrl.SetFocus()
                return
            good = False
            try:
                if len(self.prosodyMultiplierTextCtrl.GetValue()) == 0:
                    prosodyMultiplier = None
                    good = True
                else:
                    prosodyMultiplier = float(self.prosodyMultiplierTextCtrl.GetValue())
                    if .1 <= prosodyMultiplier <= 10:
                        good = True
            except ValueError:
                pass
            if not good:
                gui.messageBox(_("prosody multiplier must be a float between 0.1 and 10"), _("Dictionary Entry Error"), wx.OK|wx.ICON_WARNING, self)
                self.prosodyMultiplierTextCtrl.SetFocus()
                return
            if prosodyOffset is not None and prosodyMultiplier is not None:
                gui.messageBox(_("You must specify either prosody offset or multiplier but not both"), _("Dictionary Entry Error"), wx.OK|wx.ICON_WARNING, self)
                self.prosodyOffsetTextCtrl.SetFocus()
                return
            if prosodyOffset is  None and prosodyMultiplier is  None:
                gui.messageBox(_("You must specify either prosody offset or multiplier."), _("Dictionary Entry Error"), wx.OK|wx.ICON_WARNING, self)
                self.prosodyOffsetTextCtrl.SetFocus()
                return
            mylog(f"prosodyOffset={prosodyOffset}")
            mylog(f"prosodyMultiplier={prosodyMultiplier}")

        try:
            result = AudioRule(
                comment=self.commentTextCtrl.GetValue(),
                pattern=self.patternTextCtrl.GetValue(),
                ruleType=self.getType(),
                wavFile=self.wavName.GetValue(),
                builtInWavFile=self.getBiw(),
                startAdjustment=self.getInt(self.startAdjustmentTextCtrl.GetValue()) or 0,
                endAdjustment=self.getInt(self.endAdjustmentTextCtrl.GetValue()) or 0,
                tone=self.getInt(self.toneTextCtrl.GetValue()),
                duration=self.getInt(self.durationTextCtrl.GetValue()),
                enabled=bool(self.enabledCheckBox.GetValue()),
                prosodyName=self.PROSODY_LABELS[self.prosodyNameCategory.control.GetSelection()],
                prosodyOffset=prosodyOffset,
                prosodyMultiplier=prosodyMultiplier,
                volume=self.volumeSlider.Value or 100,
                passThrough=bool(self.passThroughCheckBox.GetValue()),
                frenzyType=self.frenzyType,
                frenzyValue=frenzyValue,
            )
            return result
        except Exception as e:
            log.error("Could not add Audio Rule", e)
            # Translators: This is an error message to let the user know that the Audio rule is not valid.
            gui.messageBox(
                _(f"Error creating audio rule: {e}"),
                _("Audio rule Error"),
                wx.OK|wx.ICON_WARNING, self
            )
            return


    def onOk(self,evt):
        rule = self.makeRule()
        if rule is not None:
            self.rule = rule
            evt.Skip()

    def _onBrowseClick(self, evt):
        p= 'c:'
        while True:
            # Translators: browse wav file message
            fd = wx.FileDialog(self, message=_("Select wav file:"),
                wildcard="*.wav",
                defaultDir=os.path.dirname(p), style=wx.FD_OPEN
            )
            if not fd.ShowModal() == wx.ID_OK: break
            p = fd.GetPath()
            self.wavName.SetValue(p)
            break

    def onTestClick(self, evt):
        if time.time() - self.lastTestTime < 1:
            # Button pressed twice within a second
            repeat = True
        else:
            repeat = False
        self.lastTestTime = time.time()
        common.rulesDialogOpen = False
        try:
            rule = self.makeRule()
            if rule is None:
                return
            preText = _("Hello")
            postText = _("world")
            preCommand, postCommand = rule.getSpeechCommand()
            if postCommand is not None:
                utterance = [preText, preCommand, postText, postCommand]
            elif not repeat:
                utterance = [preText, preCommand, postText]
            else:
                utterance = [preText] + [preCommand] * 3 + [postText]
            speech.cancelSpeech()
            speech.speak(utterance)
        finally:
            common.rulesDialogOpen = True

    def getBiwCategories(self):
        soundsPath = getSoundsPath()
        return [o for o in os.listdir(soundsPath)
            if os.path.isdir(os.path.join(soundsPath,o))
        ]

    def getBuiltInWaveFilesInCategory(self):
        soundsPath = getSoundsPath()
        category = self.getBiwCategory()
        ext = ".wav"
        return [o for o in os.listdir(os.path.join(soundsPath, category))
            if not os.path.isdir(os.path.join(soundsPath,o))
                and o.lower().endswith(ext)
        ]

    def getBuiltInWaveFiles(self):
        soundsPath = getSoundsPath()
        result = []
        for dirName, subdirList, fileList in os.walk(soundsPath, topdown=True):
            relDirName = dirName[len(soundsPath):]
            if len(relDirName) > 0 and relDirName[0] == "\\":
                relDirName = relDirName[1:]
            for fileName in fileList:
                if fileName.lower().endswith(".wav"):
                    result.append(os.path.join(relDirName, fileName))
        return result

    def getBiw(self):
        return os.path.join(
            self.getBiwCategory(),
            self.getBuiltInWaveFilesInCategory()[self.biwList.control.GetSelection()]
        )

    def setBiw(self, biw):
        category, biwFile = os.path.split(biw)
        categoryIndex = self.getBiwCategories().index(category)
        self.biwCategory.control.SetSelection(categoryIndex)
        self.onBiwCategory(None)
        biwIndex = self.getBuiltInWaveFilesInCategory().index(biwFile)
        self.biwList.control.SetSelection(biwIndex)


    def onBiw(self, evt):
        soundsPath = getSoundsPath()
        biw = self.getBiw()
        fullPath = os.path.join(soundsPath, biw)
        nvwave.playWaveFile(fullPath)

    def getBiwCategory(self):
        return   self.getBiwCategories()[self.biwCategory.control.GetSelection()]

    def onBiwCategory(self, evt):
        soundsPath = getSoundsPath()
        category = self.getBiwCategory()
        self.biwList.control.SetItems(self.getBuiltInWaveFilesInCategory())

    def onType(self, evt):
        [control.Disable() for (t,controls) in self.typeControls.items() for control in controls]
        ct = self.getType()
        [control.Enable() for control in self.typeControls[ct]]

    def onFrenzyValueCategory(self, evt):
        pass

class RulesDialog(SettingsPanel):
    # Translators: Title for the settings dialog
    title = _("Phonetic Punctuation  rules")

    def makeSettings(self, settingsSizer):
        rulesDialogOpen = True
        pp.reloadRules()
        self.allRules = [rule for frenzyType, rules in pp.rulesByFrenzy.items() for rule in rules]
        self.frenzyRules = []

        sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
      # Translators: frenzy type combo box
        labelText=_("&Category:")
        self.frenzyCategory=guiHelper.LabeledControlHelper(
            self,
            labelText,
            wx.Choice,
            choices=[FRENZY_NAMES[ft] for ft in FrenzyType]
        )
        self.frenzyCategory.control.Bind(wx.EVT_CHOICE,self.onFrenzyType)
        self.frenzyCategory.control.SetSelection(0)
        self.frenzyType = None

      # Rules table
        self.prepareRulesForFrenzy(FrenzyType.TEXT)
        rulesText = _("&Rules")
        self.rulesList = sHelper.addLabeledControl(
            rulesText,
            nvdaControls.AutoWidthColumnListCtrl,
            autoSizeColumn=2,
            itemTextCallable=self.getItemTextForList,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_VIRTUAL
        )

        # Translators: The label for a column in symbols list used to identify a symbol.
        self.rulesList.InsertColumn(0, _("Pattern"), width=self.scaleSize(150))
        self.rulesList.InsertColumn(1, _("Status"))
        self.rulesList.InsertColumn(2, _("Type"))
        self.rulesList.InsertColumn(3, _("Effect"))
        self.rulesList.Bind(wx.EVT_LIST_ITEM_FOCUSED, self.onListItemFocused)
        self.rulesList.ItemCount = len(self.frenzyRules)
      # Buttons
        bHelper = sHelper.addItem(guiHelper.ButtonHelper(orientation=wx.HORIZONTAL))
        self.toggleButton = bHelper.addButton(self, label=_("Toggle"))
        self.toggleButton.Bind(wx.EVT_BUTTON, self.onToggleClick)
        self.moveUpButton = bHelper.addButton(self, label=_("Move &up"))
        self.moveUpButton.Bind(wx.EVT_BUTTON, lambda evt: self.OnMoveClick(evt, -1))
        self.moveDownButton = bHelper.addButton(self, label=_("Move &down"))
        self.moveDownButton.Bind(wx.EVT_BUTTON, lambda evt: self.OnMoveClick(evt, 1))
        self.addAudioButton = bHelper.addButton(self, label=_("Add &audio rule"))
        self.addAudioButton.Bind(wx.EVT_BUTTON, self.OnAddClick)
        self.editButton = bHelper.addButton(self, label=_("&Edit"))
        self.editButton.Bind(wx.EVT_BUTTON, self.OnEditClick)
        self.removeButton = bHelper.addButton(self, label=_("Re&move rule"))
        self.removeButton.Bind(wx.EVT_BUTTON, self.OnRemoveClick)

        self.applicationsBlacklistEdit = sHelper.addLabeledControl(_("Disable PhoneticPuntuation in applications (comma-separated list)"), wx.TextCtrl)
        self.applicationsBlacklistEdit.Value = getConfig("applicationsBlacklist")

    def postInit(self):
        self.frenzyCategory.SetFocus()
        self.frenzyCategory.control.SetSelection(1)

    def getItemTextForList(self, item, column):
        try:
            rule = self.frenzyRules[item]
        except IndexError:
            return "?"
        if column == 0:
            return rule.getDisplayName()
        elif column == 1:
            return _("Enabled") if rule.enabled else _("Disabled")
        elif column == 2:
            return rule.ruleType
        elif column == 3:
            return rule.getReplacementDescription()
        else:
            raise ValueError("Unknown column: %d" % column)

    def updateAllRules(self, oldFrenzyType):
        if self.frenzyType is not None:
            self.allRules = sorted(
                [
                    rule
                    for rule in self.allRules
                    if rule.getFrenzyType() != oldFrenzyType
                ] + self.frenzyRules,
                key=lambda r:r.getFrenzyType().value,
            )
            self.frenzyRules = None
        
    def prepareRulesForFrenzy(self, frenzyType):
        self.frenzyType = frenzyType
        self.frenzyRules = [
            rule
            for rule in self.allRules
            if rule.getFrenzyType() == self.frenzyType
        ]

    def onFrenzyType(self, evt):
        oldFrenzyType = self.frenzyType
        if oldFrenzyType is not None:
            self.updateAllRules(oldFrenzyType)
        i = self.frenzyCategory.control.GetSelection()
        self.prepareRulesForFrenzy(list(FrenzyType)[i])
        self.rulesList.ItemCount = len(self.frenzyRules)

    def onListItemFocused(self, evt):
        if self.rulesList.GetSelectedItemCount()!=1:
            return
        index=self.rulesList.GetFirstSelected()
        rule = self.allRules[index]
        if rule.enabled:
            self.toggleButton.SetLabel(_("Disable (&toggle)"))
        else:
            self.toggleButton.SetLabel(_("Enable (&toggle)"))

    def onToggleClick(self,evt):
        if self.rulesList.GetSelectedItemCount()!=1:
            return
        index=self.rulesList.GetFirstSelected()
        self.frenzyRules[index].enabled = not self.frenzyRules[index].enabled
        if self.frenzyRrules[index].enabled:
            msg = _("Rule enabled")
        else:
            msg = _("Rule disabled")
        core.callLater(100, lambda: ui.message(msg))
        self.onListItemFocused(None)

    def OnAddClick(self,evt):
        disallowedFrenzyValues = [rule.getFrenzyValue() for rule in self.frenzyRules]
        entryDialog=AudioRuleDialog(self,title=_("Add audio rule"), frenzyType=self.frenzyType, disallowedFrenzyValues=disallowedFrenzyValues)
        if entryDialog.ShowModal()==wx.ID_OK:
            self.frenzyRules.append(entryDialog.rule)
            self.rulesList.ItemCount = len(self.frenzyRules)
            index = self.rulesList.ItemCount - 1
            self.rulesList.Select(index)
            self.rulesList.Focus(index)
            # We don't get a new focus event with the new index.
            self.rulesList.sendListItemFocusedEvent(index)
            self.rulesList.SetFocus()
            entryDialog.Destroy()

    def OnEditClick(self,evt):
        if self.rulesList.GetSelectedItemCount()!=1:
            return
        editIndex=self.rulesList.GetFirstSelected()
        if editIndex<0:
            return
        disallowedFrenzyValues = [rule.getFrenzyValue() for rule in self.frenzyRules]
        allowedFrenzyValue = self.frenzyRules[editIndex].getFrenzyValue()
        del disallowedFrenzyValues[disallowedFrenzyValues.index(allowedFrenzyValue)]
        entryDialog=AudioRuleDialog(self, frenzyType=self.frenzyType, disallowedFrenzyValues=disallowedFrenzyValues)
        entryDialog.editRule(self.frenzyRules[editIndex])
        if entryDialog.ShowModal()==wx.ID_OK:
            self.frenzyRules[editIndex] = entryDialog.rule
            self.rulesList.SetFocus()
        entryDialog.Destroy()

    def OnMoveClick(self,evt, increment):
        if self.rulesList.GetSelectedItemCount()!=1:
            return
        index=self.rulesList.GetFirstSelected()
        if index<0:
            return
        newIndex = index + increment
        if 0 <= newIndex < len(self.frenzyRules):
            # Swap
            tmp = self.frenzyRules[index]
            self.frenzyRules[index] = self.frenzyRules[newIndex]
            self.frenzyRules[newIndex] = tmp
            self.rulesList.Select(newIndex)
            self.rulesList.Focus(newIndex)
        else:
            return

    def OnToggleEnable(self,evt, increment):
        pass

    def OnRemoveClick(self,evt):
        index=self.rulesList.GetFirstSelected()
        while index>=0:
            self.rulesList.DeleteItem(index)
            del self.frenzyRules[index]
            index=self.rulesList.GetNextSelected(index)
        self.rulesList.SetFocus()

    def onSave(self):
        common.rulesDialogOpen = False
        self.updateAllRules(self.frenzyType)
        rulesDicts = [rule.asDict() for rule in self.allRules]
        rulesJson = json.dumps(rulesDicts, indent=4, sort_keys=True)
        rulesFile = open(rulesFileName, "w")
        try:
            rulesFile.write(rulesJson)
        finally:
            rulesFile.close()
        reloadRules()

        setConfig("applicationsBlacklist",self.applicationsBlacklistEdit.Value)

    def onDiscard(self):
        common.rulesDialogOpen = False
