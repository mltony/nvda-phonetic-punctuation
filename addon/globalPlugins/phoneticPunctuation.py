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

debug = True
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
    confspec = {
        "prePause" : "integer( default=1, min=0, max=60000)",
        "rules" : "string( default='')",
        "applicationsBlacklist" : "string( default='audacity')",
    }
    config.conf.spec[pp] = confspec

        

class SleepCommand(speech.commands.BaseCallbackCommand):
    def __init__(self, seconds):
        self.seconds = seconds

    def run(self):
        import time
        time.sleep(self.seconds)

    def __repr__(self):
        return "SleepCommand({self.seconds})".format(**locals())
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
        #mylog(f"run {self}")
        from NVDAHelper import generateBeep
        hz,length,left,right = self.hz, self.length, self.left, self.right
        bufSize=generateBeep(None,hz,length,left,right)
        buf=create_string_buffer(bufSize)
        generateBeep(buf,hz,length,left,right)
        import time
        t0 = time.time()
        ppSynchronousPlayer.feed(buf.raw)
        ppSynchronousPlayer.idle()
        t1 = time.time()
        dt = int(1000 * (t1-t0))
        #mylog(f"feed successful {dt} ms")
        
    def getDuration(self):
        return self.length

    def __repr__(self):
        return "PpBeepCommand({hz}, {length}, left={left}, right={right})".format(
            hz=self.hz, length=self.length, left=self.left, right=self.right)

class PpWaveFileCommand(PpSynchronousCommand):
    def __init__(self, fileName):
        self.fileName = fileName
        self.f = wave.open(self.fileName,"r")
        if self.f is None: 
            raise RuntimeError("can not open file %s"%self.fileName)
        

    def run(self):
        f = self.f
        fileWavePlayer = nvwave.WavePlayer(channels=f.getnchannels(), samplesPerSec=f.getframerate(),bitsPerSample=f.getsampwidth()*8, outputDevice=config.conf["speech"]["outputDevice"],wantDucking=False)
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




def hook(*args, **kwargs):
    pass
    #tones.beep(500, 50)
    #mylog("Hook!")
    #mylog(args)
    #mylog(kwargs)

def interceptSpeech():
    def makeInterceptFunc(targetFunc):
        def wrapperFunc(*args, **kwargs):
            hook(*args, **kwargs)
            #args[0] = [speech.commands.BeepCommand(500, 300)] + args[0]
            #new_speech = [speech.commands.BeepCommand(500, 300)] + args[0][1:]
            seq = args[0]
            #mylog(str(seq))
            new_seq = []
            for s in seq:
                if isinstance(s, str):
                    ss = s.split("(")
                    new_seq.append(ss[0])
                    for sss in ss[1:]:
                        new_seq.append(speech.commands.BeepCommand(500, 500))
                        #new_seq.append(SleepCommand(1))
                        new_seq.append(speech.BreakCommand(500))
                        new_seq.append(sss)
                else:
                    new_seq.append(s)
            #new_speech = [SleepCommand(1)] + args[0][1:]
            new_args = [new_seq] + list(args)[1:]
            new_args = tuple(new_args)
            targetFunc(*new_args, **kwargs)
        return wrapperFunc
    speech.speak = makeInterceptFunc(speech.speak)

#interceptSpeech    ()

audioRuleWave = "wave"
audioRuleBeep = "beep"
audioRuleTypes = [
    audioRuleWave,
    audioRuleBeep,
]

class AudioRule:
    def __init__(
        self, 
        comment,
        pattern,
        ruleType,
        wavFile=None,
        tone=None,
        duration=None,
        enabled=True,
        caseSensitive=True,
    ):
        self.comment = comment
        self.pattern = pattern
        self.ruleType = ruleType
        self.wavFile = wavFile
        self.tone = tone
        self.duration = duration
        self.enabled = enabled
        self.caseSensitive = caseSensitive
        
    def getDisplayName(self):
        return self.comment or self.pattern
        
    def getReplacementDescription(self):
        if self.ruleType == audioRuleWave:
            return f"Wav: {self.wavFile}"
        elif ruleType == audioRuleBeep:
            return f"Beep: {self.tone}@{self.duration}"
        else:
            raise ValueError()
            
    def asJson():
        return {
            'comment': self.comment,
            'pattern': self.pattern,
            'ruleType': self.ruleType,
            'wavFile': self.wavFile,
            'tone': self.tone,
            'duration': self.duration,
            'enabled': self.enabled,
            'caseSensitive': self.caseSensitive,
        }
        
rules = []
def reloadRules():
    global rules
    mylog("reload")
    mylog(config.conf[pp]["rules"])
    rules = [
        AudioRule(**ruleDict)   
        for ruleDict in json.loads(config.conf[pp]["rules"])
    ]


initConfiguration()
#reloadRules()
addonHandler.initTranslation()


class AudioRuleDialog(wx.Dialog):
    TYPE_LABELS = {
        audioRuleWave: _("&Wave file"),
        audioRuleBeep: _("&Beep"),
    }
    TYPE_LABELS_ORDERING = audioRuleTypes

    def __init__(self, parent, title=_("Edit audio rule")):
        super(AudioRuleDialog,self).__init__(parent,title=title)
        mainSizer=wx.BoxSizer(wx.VERTICAL)
        sHelper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

      # Translators: label for pattern  edit field in add Audio Rule dialog.
        patternLabelText = _("&Pattern")
        self.patternTextCtrl=sHelper.addLabeledControl(patternLabelText, wx.TextCtrl)
        
      # Translators: label for case sensitivity  checkbox in add audio rule dialog.
        caseSensitiveText = _("Case &sensitive")
        self.caseSensitiveCheckBox=sHelper.addItem(wx.CheckBox(self,label=caseSensitiveText))
        
      # Translators:  label for type selector radio buttons in add audio rule dialog
        typeText = _("&Type")
        typeChoices = [AudioRuleDialog.TYPE_LABELS[i] for i in AudioRuleDialog.TYPE_LABELS_ORDERING]
        self.typeRadioBox=sHelper.addItem(wx.RadioBox(self,label=typeText, choices=typeChoices))
        
      # Translators: wav file edit box
        self.wavName  = sHelper.addLabeledControl(_("Wav file"), wx.TextCtrl)
        
      # Translators: This is the button to browse for wav file
        self._browseButton = sHelper.addItem (wx.Button (self, label = _("&Browse...")))
        self._browseButton.Bind(wx.EVT_BUTTON, self._onBrowseClick)
        

      # Translators: label for tone
        toneLabelText = _("&Tone")
        self.ToneTextCtrl=sHelper.addLabeledControl(toneLabelText, wx.TextCtrl)

      # Translators: label for comment edit box
        commentLabelText = _("&Comment")
        self.commentTextCtrl=sHelper.addLabeledControl(commentLabelText, wx.TextCtrl)

        sHelper.addDialogDismissButtons(self.CreateButtonSizer(wx.OK|wx.CANCEL))

        mainSizer.Add(sHelper.sizer,border=20,flag=wx.ALL)
        mainSizer.Fit(self)
        self.SetSizer(mainSizer)
        self.setType(audioRuleWave)
        self.patternTextCtrl.SetFocus()
        self.Bind(wx.EVT_BUTTON,self.onOk,id=wx.ID_OK)

    def getType(self):
        typeRadioValue = self.typeRadioBox.GetSelection()
        if typeRadioValue == wx.NOT_FOUND:
            return audioRuleWave
        return AudioRuleDialog.TYPE_LABELS_ORDERING[typeRadioValue]
        
    def getInt(self, s):
        if len(s) == 0:
            return None
        return int(s)

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
                tone=self.getInt(self.ToneTextCtrl.GetValue()),
                duration=None,
                enabled=True,
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

    def setType(self, type):
        self.typeRadioBox.SetSelection(AudioRuleDialog.TYPE_LABELS_ORDERING.index(type))

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




class RulesDialog(gui.SettingsDialog):
    # Translators: Title for the settings dialog
    title = _("Phonetic Punctuation  rules")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def makeSettings(self, settingsSizer):
        reloadRules()
        self.rules = copy.deepcopy(rules)
        l = len(rules)
        ll = len(self.rules)
        mylog(f"hahaha {l} {ll}")
        
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
        self.removeButton = bHelper.addButton(self, label=_("Re&move rule"))
        self.removeButton.Disable()
        self.removeButton.Bind(wx.EVT_BUTTON, self.OnRemoveClick)
        
        
    def postInit(self):
        self.rulesList.SetFocus()
        
    def getItemTextForList(self, item, column):
        rule = self.rules[item]
        if column == 0:
            return rule.getDisplayName()
        elif column == 1:
            return str(rule.enabled)
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
            #entryDialog.Destroy()

    def OnRemoveClick(self,evt):
        index=self.rulesList.GetFirstSelected()
        while index>=0:
            self.rulesList.DeleteItem(index)
            del self.rules[index]
            index=self.rulesList.GetNextSelected(index)
        self.rulesList.SetFocus()

    def onOk(self, evt):
        rulesDicts = [rule.__dict__ for rule in self.rules]
        rulesJson = json.dumps(rulesDicts, indent=4, sort_keys=True)
        mylog("json")
        mylog(rulesJson)
        config.conf[pp]["rules"] = rulesJson
        reloadRules()
        super().onOk(evt)

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
        if self.enabled:
            if symbolLevel is None:
                symbolLevel=config.conf["speech"]["symbolLevel"]
            newSequence = []
            for element in speechSequence:
                if type(element) == str:
                    newSequence.extend(self.test(element, symbolLevel))
                else:
                    newSequence.append(element)
            newSequence = self.postProcessSynchronousCommands(newSequence, symbolLevel)
        else:
            newSequence = speechSequence
        return self.originalSpeechSpeak(newSequence, symbolLevel, *args, **kwargs)

    def postSpeak(self, selfself, speechSequence, *args, **kwargs):
        #mylog("postSpeak:")
        #mylog(str(speechSequence))
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
            #mylog(f"qwerty lang={language}")
            #mylog(f"qwerty {prefix} {symbolLevel}")
            pPrefix = speech.processText(language,prefix,symbolLevel)
            #mylog(f"pPrefix={pPrefix}")
            if speech.isBlank(pPrefix):
                pass
                #mylog("Empty prefix")
                #mylog(prefix)
                #mylog(pPrefix)
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

    def postProcessSynchronousCommands(self, speechSequence, symbolLevel):
        #mylog("asdf")
        #mylog(str(speechSequence))
        language=speech.getCurrentLanguage()
        speechSequence = [element for element in speechSequence
            if not isinstance(element, str)
            or not speech.isBlank(speech.processText(language,element,symbolLevel))
        ]
        
        #mylog(str(speechSequence))
        newSequence = []
        for (isSynchronous, values) in itertools.groupby(speechSequence, key=lambda x: isinstance(x, PpSynchronousCommand)):
            if isSynchronous:
                chain = PpChainCommand(list(values))
                duration = chain.getDuration()
                newSequence.append(chain)
                newSequence.append(speech.commands.BreakCommand(duration))
            else:
                newSequence.extend(values)
            l = len(newSequence)
            #mylog(f"hahaha {isSynchronous} {l}")
        
        #mylog(str(newSequence))
        return newSequence