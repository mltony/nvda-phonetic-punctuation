# -*- coding: UTF-8 -*-
#A part of the Phonetic Punctuation addon for NVDA
#Copyright (C) 2019-2023 Tony Malykh
#This file is covered by the GNU General Public License.
#See the file COPYING.txt for more details.

from enum import Enum

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

class FrenzyType(Enum):
    TEXT = 'text'
    ROLE = 'role'
    STATE = 'state'
    FORMAT = 'format'


FRENZY_NAMES = {
    FrenzyType.TEXT: "Text regular expressions",
    FrenzyType.ROLE: "Roles",
    FrenzyType.STATE: "States",
    FrenzyType.FORMAT: "Text formatting",
}

FRENZY_NAMES_SINGULAR = {
    FrenzyType.TEXT: "Text regular expression pattern",
    FrenzyType.ROLE: "Role",
    FrenzyType.STATE: "State",
    FrenzyType.FORMAT: "Format",
}

rulesDialogOpen = False
