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

from .utils import *

try:
    outputDevice=config.conf["speech"]["outputDevice"]
except KeyError:
    outputDevice=config.conf["audio"]["outputDevice"]
ppSynchronousPlayer = nvwave.WavePlayer(channels=2, samplesPerSec=int(tones.SAMPLE_RATE), bitsPerSample=16, outputDevice=outputDevice,wantDucking=True, purpose=nvwave.AudioPurpose.SOUNDS,)

class PpSynchronousCommand(speech.commands.BaseCallbackCommand):
    def getDuration(self):
        raise NotImplementedError()
    def terminate(self):
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

    def terminate(self):
        ppSynchronousPlayer.stop()

class PpWaveFileCommand(PpSynchronousCommand):
    def __init__(self, fileName, startAdjustment=0, endAdjustment=0, volume=100):
        self.fileName = fileName
        self.startAdjustment = startAdjustment
        self.endAdjustment = endAdjustment
        self.volume = volume
        self.f = wave.open(self.fileName,"r")
        f = self.f
        if self.f is None:
            raise RuntimeError("can not open file %s"%self.fileName)
        if f.getsampwidth() != 2:
            bits = f.getsampwidth() * 8
            raise RuntimeError(f"We only support 16-bit encoded wav files. '{fileName}' is encoded with {bits} bits per sample.")
        buf =  f.readframes(f.getnframes())
        bufSize = len(buf)
        n = bufSize//2
        unpacked = struct.unpack(f"<{n}h", buf)
        unpacked = list(unpacked)
        for i in range(n):
            unpacked[i] = int(unpacked[i] * volume/100)
        if self.startAdjustment > 0:
            pos = self.startAdjustment * f.getframerate() // 1000
            pos *= f.getnchannels()
            unpacked = unpacked[pos:]
            n = len(unpacked)
        packed = struct.pack(f"<{n}h", *unpacked)
        self.buf = packed
        try:
            outputDevice=config.conf["speech"]["outputDevice"]
        except KeyError:
            outputDevice=config.conf["audio"]["outputDevice"]
        self.fileWavePlayer = nvwave.WavePlayer(
            channels=f.getnchannels(),
            samplesPerSec=f.getframerate(),
            bitsPerSample=f.getsampwidth()*8,
            outputDevice=outputDevice,
            wantDucking=False,
            purpose=nvwave.AudioPurpose.SOUNDS,
        )
        

    def run(self):
        f = self.f
        f.rewind()
        if self.startAdjustment < 0:
            time.sleep(-self.startAdjustment / 1000.0)
        elif self.startAdjustment > 0:
            # this is now handled in __init__
            pass
        fileWavePlayer = self.fileWavePlayer
        fileWavePlayer.stop()
        fileWavePlayer.feed(self.buf)
        fileWavePlayer.idle()

    def getDuration(self):
        frames = self.f.getnframes()
        rate = self.f.getframerate()
        wavMillis = int(1000 * frames / rate)
        result = wavMillis - self.startAdjustment - self.endAdjustment
        return max(0, result)

    def __repr__(self):
        return "PpWaveFileCommand(%r)" % self.fileName

    def terminate(self):
        self.fileWavePlayer.stop()

currentChain = None
class PpChainCommand(PpSynchronousCommand):
    def __init__(self, subcommands):
        super().__init__()
        self.subcommands = subcommands
        self.terminated = False

    def run(self):
        global currentChain
        currentChain = self
        threadPool.add_task(self.threadFunc)

    def getDuration(self):
        return sum([subcommand.getDuration() for subcommand in self.subcommands])

    def threadFunc(self):
        global currentChain
        timestamp = time.time()
        for subcommand in self.subcommands:
            if self.terminated:
                return
            threadPool.add_task(subcommand.run)
            timestamp += subcommand.getDuration() / 1000
            sleepTime = timestamp - time.time()
            if sleepTime > 0:
                time.sleep(sleepTime)
        currentChain = None
        

    def __repr__(self):
        return f"PpChainCommand({self.subcommands})"

    def terminate(self):
        global currentChain
        self.terminated = True
        for subcommand in self.subcommands:
            subcommand.terminate()
        currentChain = None
