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
import copy
import ctypes
from ctypes import create_string_buffer, byref
import globalPluginHandler
import gui
from gui import guiHelper, nvdaControls
import itertools
import json
from logHandler import log
import NVDAHelper
from NVDAObjects.window import winword
import nvwave
import operator
import os
import re
import sayAllHandler
from scriptHandler import script, willSayAllResume
import speech
import speech.commands
import struct
import textInfos
import threading
import tones
import ui
import wave
import wx

debug = False
if debug:
    f = open("C:\\Users\\tony\\Dropbox\\1.txt", "w")
def mylog(s):
    if debug:
        print(str(s), file=f)
        f.flush()

def myAssert(condition):
    if not condition:
        raise RuntimeError("Assertion failed")

pp = "phoneticpunctuation"
def initConfiguration():
    defaultRules = """
        [
            {
                "builtInWavFile": "3d\\item.wav",
                "caseSensitive": false,
                "comment": "",
                "duration": null,
                "enabled": true,
                "pattern": "!",
                "ruleType": "builtInWave",
                "tone": null,
                "wavFile": ""
            },
            {
                "builtInWavFile": "classic\\ask-short-question.wav",
                "caseSensitive": false,
                "comment": "",
                "duration": 50,
                "enabled": true,
                "pattern": "@",
                "ruleType": "builtInWave",
                "tone": 500,
                "wavFile": ""
            },
            {
                "builtInWavFile": "3d\\left.wav",
                "caseSensitive": false,
                "comment": "(",
                "duration": null,
                "enabled": true,
                "pattern": "\\(",
                "ruleType": "builtInWave",
                "tone": null,
                "wavFile": ""
            },
            {
                "builtInWavFile": "3d\\right.wav",
                "caseSensitive": false,
                "comment": ")",
                "duration": null,
                "enabled": true,
                "pattern": "\\)",
                "ruleType": "builtInWave",
                "tone": null,
                "wavFile": ""
            },
            {
                "builtInWavFile": "3d\\network-up.wav",
                "caseSensitive": false,
                "comment": "[",
                "duration": 50,
                "enabled": true,
                "pattern": "\\[",
                "ruleType": "builtInWave",
                "tone": 500,
                "wavFile": ""
            },
            {
                "builtInWavFile": "3d\\network-down.wav",
                "caseSensitive": false,
                "comment": "]",
                "duration": 50,
                "enabled": true,
                "pattern": "\\]",
                "ruleType": "builtInWave",
                "tone": 500,
                "wavFile": ""
            },
            {
                "builtInWavFile": "3d\\ellipses.wav",
                "caseSensitive": false,
                "comment": "...",
                "duration": null,
                "enabled": true,
                "pattern": "\\.{3,}",
                "ruleType": "builtInWave",
                "tone": null,
                "wavFile": ""
            },
            {
                "builtInWavFile": "chimes\\close-object.wav",
                "caseSensitive": false,
                "comment": ".",
                "duration": 50,
                "enabled": true,
                "pattern": "\\.",
                "ruleType": "builtInWave",
                "tone": 500,
                "wavFile": ""
            },
            {
                "builtInWavFile": "chimes\\delete-object.wav",
                "caseSensitive": false,
                "comment": "",
                "duration": null,
                "enabled": true,
                "pattern": ",",
                "ruleType": "builtInWave",
                "tone": null,
                "wavFile": ""
            },
            {
                "builtInWavFile": "chimes\\yank-object.wav",
                "caseSensitive": false,
                "comment": "?",
                "duration": null,
                "enabled": true,
                "pattern": "\\?",
                "ruleType": "builtInWave",
                "tone": null,
                "wavFile": ""
            },
            {
                "builtInWavFile": "3d\\window-resize.wav",
                "caseSensitive": true,
                "comment": "blank",
                "duration": 50,
                "enabled": true,
                "pattern": "^blank$",
                "ruleType": "builtInWave",
                "tone": 500,
                "wavFile": ""
            }
        ]
    """
    confspec = {
        "prePause" : "integer( default=1, min=0, max=60000)",
        "rules" : "string( default=defaultRules)",
        "applicationsBlacklist" : "string( default='audacity')",
    }
    config.conf.spec[pp] = confspec




ppSynchronousPlayer = nvwave.WavePlayer(channels=2, samplesPerSec=int(tones.SAMPLE_RATE), bitsPerSample=16, outputDevice=config.conf["speech"]["outputDevice"],wantDucking=True)

class PpSynchronousCommand(speech.commands.BaseCallbackCommand):
    def getDuration(self):
        raise NotImplementedError()

class PpBeepCommand(PpSynchronousCommand):
    def __init__(self, hz, length, left=50, right=50):
        super().__init__()
        self.hz = hz
        self.length = length
        self.left = left
        self.right = right

    def run(self):
        from NVDAHelper import generateBeep
        hz,length,left,right = self.hz, self.length, self.left, self.right
        bufSize=generateBeep(None,hz,length,left,right)
        buf=create_string_buffer(bufSize)
        generateBeep(buf,hz,length,left,right)
        ppSynchronousPlayer.feed(buf.raw)
        ppSynchronousPlayer.idle()

    def getDuration(self):
        return self.length

    def __repr__(self):
        return "PpBeepCommand({hz}, {length}, left={left}, right={right})".format(
            hz=self.hz, length=self.length, left=self.left, right=self.right)

class PpWaveFileCommand(PpSynchronousCommand):
    def __init__(self, fileName):
        self.fileName = fileName
        self.f = wave.open(self.fileName,"r")
        f = self.f
        if self.f is None:
            raise RuntimeError("can not open file %s"%self.fileName)
        self.fileWavePlayer = nvwave.WavePlayer(channels=f.getnchannels(), samplesPerSec=f.getframerate(),bitsPerSample=f.getsampwidth()*8, outputDevice=config.conf["speech"]["outputDevice"],wantDucking=False)

    def run(self):
        f = self.f
        f.rewind()
        fileWavePlayer = self.fileWavePlayer
        fileWavePlayer.feed(f.readframes(f.getnframes()))
        fileWavePlayer.idle()

    def getDuration(self):
        frames = self.f.getnframes()
        rate = self.f.getframerate()
        return int(1000 * frames / rate)

    def __repr__(self):
        return "PpWaveFileCommand(%r)" % self.fileName

class PpChainCommand(PpSynchronousCommand):
    def __init__(self, subcommands):
        super().__init__()
        self.subcommands = subcommands

    def run(self):
        thread1 = threading.Thread(target = self.threadFunc)
        thread1.start()

    def getDuration(self):
        return sum([subcommand.getDuration() for subcommand in self.subcommands])

    def threadFunc(self):
        for subcommand in self.subcommands:
            subcommand.run()

    def __repr__(self):
        return f"PpChainCommand({self.subcommands})"

def getSoundsPath():
    globalPluginPath = os.path.abspath(os.path.dirname(__file__))
    addonPath = os.path.split(globalPluginPath)[0]
    soundsPath = os.path.join(addonPath, "sounds")
    return soundsPath


audioRuleBuiltInWave = "builtInWave"
audioRuleWave = "wave"
audioRuleBeep = "beep"
audioRuleTypes = [
    audioRuleBuiltInWave,
    audioRuleWave,
    audioRuleBeep,
]

class AudioRule:
    jsonFields = "comment pattern ruleType wavFile builtInWavFile tone duration enabled caseSensitive ".split()
    def __init__(
        self,
        comment,
        pattern,
        ruleType,
        wavFile=None,
        builtInWavFile=None,
        tone=None,
        duration=None,
        enabled=True,
        caseSensitive=True,
    ):
        self.comment = comment
        self.pattern = pattern
        self.ruleType = ruleType
        self.wavFile = wavFile
        self.builtInWavFile = builtInWavFile
        self.tone = tone
        self.duration = duration
        self.enabled = enabled
        self.caseSensitive = caseSensitive
        self.regexp = re.compile(self.pattern)
        self.speechCommand = self.getSpeechCommand()

    def getDisplayName(self):
        return self.comment or self.pattern

    def getReplacementDescription(self):
        if self.ruleType == audioRuleWave:
            return f"Wav: {self.wavFile}"
        elif self.ruleType == audioRuleBuiltInWave:
            return self.builtInWavFile
        elif ruleType == audioRuleBeep:
            return f"Beep: {self.tone}@{self.duration}"
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
            return PpWaveFileCommand(wavFile)
        elif self.ruleType == audioRuleBeep:
            return PpBeepCommand(self.tone, self.duration)
        else:
            raise ValueError()

    def processString(self, s):
        if not self.enabled:
            yield s
            return
        for command in self.processStringInternal(s):
            if isinstance(command, str):
                if len(command) > 0:
                    yield command
            else:
                yield command

    def processStringInternal(self, s):
        index = 0
        for match in self.regexp.finditer(s):
            yield s[index:match.start(0)]
            yield self.speechCommand
            index = match.end(0)
        yield s[index:]


rulesDialogOpen = False
rules = []
def reloadRules():
    global rules
    mylog("Loading rules:")
    mylog(config.conf[pp]["rules"])
    rules = [
        AudioRule(**ruleDict)
        for ruleDict in json.loads(config.conf[pp]["rules"])
    ]


initConfiguration()
reloadRules()
addonHandler.initTranslation()


class AudioRuleDialog(wx.Dialog):
    TYPE_LABELS = {
        audioRuleBuiltInWave: _("&Built in wave"),
        audioRuleWave: _("&Wave file"),
        audioRuleBeep: _("&Beep"),
    }
    TYPE_LABELS_ORDERING = audioRuleTypes

    def __init__(self, parent, title=_("Edit audio rule")):
        #self.biws = self.getBuiltInWaveFiles()
        super(AudioRuleDialog,self).__init__(parent,title=title)
        mainSizer=wx.BoxSizer(wx.VERTICAL)
        sHelper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

      # Translators: label for pattern  edit field in add Audio Rule dialog.
        patternLabelText = _("&Pattern")
        self.patternTextCtrl=sHelper.addLabeledControl(patternLabelText, wx.TextCtrl)

      # Translators: label for case sensitivity  checkbox in add audio rule dialog.
        caseSensitiveText = _("Case &sensitive")
        self.caseSensitiveCheckBox=sHelper.addItem(wx.CheckBox(self,label=caseSensitiveText))

      # Translators: label for rule_enabled  checkbox in add audio rule dialog.
        enabledText = _("Rule enabled")
        self.enabledCheckBox=sHelper.addItem(wx.CheckBox(self,label=enabledText))
        self.enabledCheckBox.SetValue(True)
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
        sHelper.sizer.Add(self.biwCategory.control)
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
        sHelper.sizer.Add(self.biwList.control)
        #self.biwList.control.Disable()
        self.typeControls[audioRuleBuiltInWave].append(self.biwList.control)
      # Translators: wav file edit box
        self.wavName  = sHelper.addLabeledControl(_("Wav file"), wx.TextCtrl)
        #self.wavName.Disable()
        self.typeControls[audioRuleWave].append(self.wavName)

      # Translators: This is the button to browse for wav file
        self._browseButton = sHelper.addItem (wx.Button (self, label = _("&Browse...")))
        self._browseButton.Bind(wx.EVT_BUTTON, self._onBrowseClick)
        #self._browseButton.Disable()
        self.typeControls[audioRuleWave].append(self._browseButton)

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

      # Translators: label for comment edit box
        commentLabelText = _("&Comment")
        self.commentTextCtrl=sHelper.addLabeledControl(commentLabelText, wx.TextCtrl)

        sHelper.addDialogDismissButtons(self.CreateButtonSizer(wx.OK|wx.CANCEL))

        mainSizer.Add(sHelper.sizer,border=20,flag=wx.ALL)
        mainSizer.Fit(self)
        self.SetSizer(mainSizer)
        self.patternTextCtrl.SetFocus()
        self.Bind(wx.EVT_BUTTON,self.onOk,id=wx.ID_OK)
        self.onType(None)

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
        self.setType(rule.ruleType)
        self.wavName.SetValue(rule.wavFile)
        self.setBiw(rule.builtInWavFile)
        self.toneTextCtrl.SetValue(str(rule.tone or 500))
        self.durationTextCtrl.SetValue(str(rule.duration or 50))
        self.enabledCheckBox.SetValue(rule.enabled)
        self.caseSensitiveCheckBox.SetValue(rule.caseSensitive)

    def onOk(self,evt):
        if not self.patternTextCtrl.GetValue():
            # Translators: This is an error message to let the user know that the pattern field is not valid.
            gui.messageBox(_("A pattern is required."), _("Dictionary Entry Error"), wx.OK|wx.ICON_WARNING, self)
            self.patternTextCtrl.SetFocus()
            return
        # TODO: more validation
        try:
            self.rule=AudioRule(
                comment=self.commentTextCtrl.GetValue(),
                pattern=self.patternTextCtrl.GetValue(),
                ruleType=self.getType(),
                wavFile=self.wavName.GetValue(),
                builtInWavFile=self.getBiw(),
                tone=self.getInt(self.toneTextCtrl.GetValue()),
                duration=self.getInt(self.durationTextCtrl.GetValue()),
                enabled=bool(self.enabledCheckBox.GetValue()),
                caseSensitive=bool(self.caseSensitiveCheckBox.GetValue()),
            )
        except Exception as e:
            log.debugWarning("Could not add Audio Rule", e)
            # Translators: This is an error message to let the user know that the Audio rule is not valid.
            gui.messageBox(
                _(f"Error creating audio rule: {e}"),
                _("Audio rule Error"),
                wx.OK|wx.ICON_WARNING, self
            )
            return
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
        tones.beep(500, 50)
        soundsPath = getSoundsPath()
        category = self.getBiwCategory()
        self.biwList.control.SetItems(self.getBuiltInWaveFilesInCategory())

    def onType(self, evt):
        [control.Disable() for (t,controls) in self.typeControls.items() for control in controls]
        ct = self.getType()
        [control.Enable() for control in self.typeControls[ct]]

class RulesDialog(gui.SettingsDialog):
    # Translators: Title for the settings dialog
    title = _("Phonetic Punctuation  rules")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def makeSettings(self, settingsSizer):
        global rulesDialogOpen
        rulesDialogOpen = True
        reloadRules()
        self.rules = rules[:]

        sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
      # Rules table
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
        self.rulesList.ItemCount = len(self.rules)
      # Buttons
        bHelper = sHelper.addItem(guiHelper.ButtonHelper(orientation=wx.HORIZONTAL))
        self.moveUpButton = bHelper.addButton(self, label=_("Move &up"))
        self.moveDownButton = bHelper.addButton(self, label=_("Move &down"))
        self.addAudioButton = bHelper.addButton(self, label=_("Add &audio rule"))
        self.addAudioButton.Bind(wx.EVT_BUTTON, self.OnAddClick)
        self.editButton = bHelper.addButton(self, label=_("Edi&t"))
        self.editButton.Bind(wx.EVT_BUTTON, self.OnEditClick)
        self.removeButton = bHelper.addButton(self, label=_("Re&move rule"))
        self.removeButton.Bind(wx.EVT_BUTTON, self.OnRemoveClick)


    def postInit(self):
        self.rulesList.SetFocus()

    def getItemTextForList(self, item, column):
        rule = self.rules[item]
        if column == 0:
            return rule.getDisplayName()
        elif column == 1:
            return "Enabled" if rule.enabled else "Disabled"
        elif column == 2:
            return rule.ruleType
        elif column == 3:
            return rule.getReplacementDescription()
        else:
            raise ValueError("Unknown column: %d" % column)

    def onListItemFocused(self, evt):
        pass
        #evt.Skip()

    def OnAddClick(self,evt):
        entryDialog=AudioRuleDialog(self,title=_("Add audio rule"))
        if entryDialog.ShowModal()==wx.ID_OK:
            self.rules.append(entryDialog.rule)
            self.rulesList.ItemCount = len(self.rules)
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
        entryDialog=AudioRuleDialog(self)
        entryDialog.editRule(rules[editIndex])
        if entryDialog.ShowModal()==wx.ID_OK:
            self.rules[editIndex] = entryDialog.rule
            self.rulesList.SetFocus()
        entryDialog.Destroy()



    def OnRemoveClick(self,evt):
        index=self.rulesList.GetFirstSelected()
        while index>=0:
            self.rulesList.DeleteItem(index)
            del self.rules[index]
            index=self.rulesList.GetNextSelected(index)
        self.rulesList.SetFocus()

    def onOk(self, evt):
        global rulesDialogOpen
        rulesDialogOpen = False
        rulesDicts = [rule.asDict() for rule in self.rules]
        rulesJson = json.dumps(rulesDicts, indent=4, sort_keys=True)
        config.conf[pp]["rules"] = rulesJson
        reloadRules()
        super().onOk(evt)

    def onCancel(self,evt):
        global rulesDialogOpen
        rulesDialogOpen = False
        super().onCancel(evt)



class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    scriptCategory = _("Phonetic Punctuation")

    def __init__(self, *args, **kwargs):
        super(GlobalPlugin, self).__init__(*args, **kwargs)
        self.createMenu()
        self.injectSpeechInterceptor()
        self.enabled = True

    def createMenu(self):
        def _popupMenu(evt):
            gui.mainFrame._popupSettingsDialog(RulesDialog)
        self.prefsMenuItem = gui.mainFrame.sysTrayIcon.preferencesMenu.Append(wx.ID_ANY, _("Phonetic Punctuation and Audio Rules..."))
        gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, _popupMenu, self.prefsMenuItem)


    def terminate(self):
        self.restoreSpeechInterceptor()

    def injectSpeechInterceptor(self):
        self.originalSpeechSpeak = speech.speak
        speech.speak = lambda speechSequence, symbolLevel=None, *args, **kwargs: self.preSpeak(speechSequence, symbolLevel, *args, **kwargs)
        self.originalManagerSpeak = speech.manager.SpeechManager.speak
        speech.manager.SpeechManager.speak = lambda selfself, speechSequence, *args, **kwargs: self.postSpeak(selfself, speechSequence, *args, **kwargs)

    def  restoreSpeechInterceptor(self):
        speech.speak = self.originalSpeechSpeak
        speech.manager.SpeechManager.speak = self.originalManagerSpeak

    def preSpeak(self, speechSequence, symbolLevel=None, *args, **kwargs):
        if self.enabled and not rulesDialogOpen:
            if symbolLevel is None:
                symbolLevel=config.conf["speech"]["symbolLevel"]
            newSequence = []
            if False:
                for element in speechSequence:
                    if type(element) == str:
                        newSequence.extend(self.test(element, symbolLevel))
                    else:
                        newSequence.append(element)
            newSequence = speechSequence
            for rule in rules:
                newSequence = self.processRule(newSequence, rule, symbolLevel)
            newSequence = self.postProcessSynchronousCommands(newSequence, symbolLevel)
        else:
            newSequence = speechSequence
        return self.originalSpeechSpeak(newSequence, symbolLevel, *args, **kwargs)

    def postSpeak(self, selfself, speechSequence, *args, **kwargs):
        return self.originalManagerSpeak(selfself, speechSequence, *args, **kwargs)

    @script(description='Toggle phonetic punctuation.', gestures=['kb:NVDA+Alt+p'])
    def script_togglePp(self, gesture):
        self.enabled = not self.enabled
        if self.enabled:
            msg = _("Phonetic punctuation on")
        else:
            msg = _("Phonetic punctuation off")
        ui.message(msg)


    def getWavLengthMillis(self, fileName):
        return int(1000 * os.path.getsize(fileName) / tones.SAMPLE_RATE / 4)


    def test(self, s, symbolLevel):
        wav = "H:\\drp\\work\\emacspeak\\sounds\\classic\\alarm.wav"
        wavLength = self.getWavLengthMillis(wav)
        language=speech.getCurrentLanguage()
        tone = 500

        while "!" in s:
            index = s.index("!")
            prefix = s[:index]
            prefix = prefix.lstrip()
            pPrefix = speech.processText(language,prefix,symbolLevel)
            if speech.isBlank(pPrefix):
                pass
            else:
                yield  prefix
            #yield speech.commands.WaveFileCommand(wav)
            #yield speech.commands.BeepCommand(tone, 100)
            #yield PpBeepCommand(tone, 100)
            yield PpWaveFileCommand(wav)
            tone += 50
            #yield speech.commands.BreakCommand(100)
            s = s[index + 1:]
        if len(s) > 0:
            yield s

    def processRule(self, speechSequence, rule, symbolLevel):
        newSequence = []
        for command in speechSequence:
            if isinstance(command, str):
                newSequence.extend(rule.processString(command))
            else:
                newSequence.append(command)
        return newSequence

    def postProcessSynchronousCommands(self, speechSequence, symbolLevel):
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
        newSequence = self.eloquenceFix(newSequence, language, symbolLevel)
        return newSequence

    def eloquenceFix(self, speechSequence, language, symbolLevel):
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
