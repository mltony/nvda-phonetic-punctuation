# -*- coding: UTF-8 -*-
#A part of the Phonetic Punctuation addon for NVDA
#Copyright (C) 2019-2023 Tony Malykh
#This file is covered by the GNU General Public License.
#See the file COPYING.txt for more details.


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
    FRENZY_ROLE = 'role'
    FRENZY_STATE = 'state'
    FRENZY_FORMAT = 'format'

