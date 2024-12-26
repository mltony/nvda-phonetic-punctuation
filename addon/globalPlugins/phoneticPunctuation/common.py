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
audioRuleNumericProsody = "numericProsody"
audioRuleTextSubstitution = "textSubstitution"
audioRuleNoop = "noop"

audioRuleTypes = [
    audioRuleBuiltInWave,
    audioRuleWave,
    audioRuleBeep,
    audioRuleProsody,
    audioRuleNumericProsody,
    audioRuleTextSubstitution,
    audioRuleNoop,
]

class FrenzyType(Enum):
    TEXT = 'text'
    CHARACTER = 'character'
    ROLE = 'role'
    STATE = 'state'
    NEGATIVE_STATE = 'negative_state'
    FORMAT = 'format'
    NUMERIC_FORMAT = 'numeric_format'
    OTHER_RULE = 'other_rule'


FRENZY_NAMES = {
    FrenzyType.TEXT: "Text regular expressions",
    FrenzyType.CHARACTER: "Characters",
    FrenzyType.ROLE: "Roles",
    FrenzyType.STATE: "States",
    FrenzyType.NEGATIVE_STATE: "Negative states",
    FrenzyType.FORMAT: "Text formatting",
    FrenzyType.NUMERIC_FORMAT: "Numeric text formatting",
    FrenzyType.OTHER_RULE: "Other audio rules",
}

FRENZY_NAMES_SINGULAR = {
    FrenzyType.TEXT: "Text regular expression pattern",
    FrenzyType.CHARACTER: "Character",
    FrenzyType.ROLE: "Role",
    FrenzyType.STATE: "State",
    FrenzyType.NEGATIVE_STATE: "Negative state",
    FrenzyType.FORMAT: "Format",
    FrenzyType.NUMERIC_FORMAT: "Numeric format",
    FrenzyType.OTHER_RULE: "Other audio rule",
}

rulesDialogOpen = False

class TextFormat(Enum):
    BOLD = 'bold'
    ITALIC = 'italic'
    SUPERSCRIPT = 'superscript'
    SUBSCRIPT = 'subscript'
    HEADING = 'heading'
TEXT_FORMAT_NAMES = {
    TextFormat.BOLD: _('Bold'),
    TextFormat.ITALIC: _('Italic'),
    TextFormat.SUPERSCRIPT: _('Superscript'),
    TextFormat.SUBSCRIPT: _('Subscript'),
    TextFormat.HEADING: _('Heading'),
}

class NumericTextFormat(Enum):
    FONT_SIZE = 'font_size'
    HEADING_LEVEL = 'heading_level'

NUMERIC_TEXT_FORMAT_NAMES = {
    NumericTextFormat.FONT_SIZE: _('Font size'),
    NumericTextFormat.HEADING_LEVEL: _('Heading level'),
}

class OtherRule(Enum):
    OUT_OF_CONTAINER = 'out_of_container'
    BLANK = "blank"

OTHER_RULE_NAMES = {
    OtherRule.OUT_OF_CONTAINER: _('Out of container'),
    OtherRule.BLANK: _('Blank announcement'),
}

ALLOWED_TYPES_BY_FRENZY_TYPE = {
    FrenzyType.TEXT: [
        audioRuleBuiltInWave,
        audioRuleWave,
        audioRuleBeep,
        audioRuleProsody,
        #audioRuleTextSubstitution,
    ],
    FrenzyType.CHARACTER: [
        audioRuleBuiltInWave,
        audioRuleWave,
        audioRuleBeep,
        audioRuleTextSubstitution,
    ],
    FrenzyType.ROLE: [
        audioRuleBuiltInWave,
        audioRuleWave,
        audioRuleBeep,
        #audioRuleProsody,
        audioRuleTextSubstitution,
    ],
    FrenzyType.STATE: [
        audioRuleBuiltInWave,
        audioRuleWave,
        audioRuleBeep,
        audioRuleProsody,
        audioRuleTextSubstitution,
        audioRuleNoop,
    ],
    FrenzyType.NEGATIVE_STATE: [
        audioRuleBuiltInWave,
        audioRuleWave,
        audioRuleBeep,
        audioRuleProsody,
        audioRuleTextSubstitution,
        audioRuleNoop,
    ],
    FrenzyType.FORMAT: [
        audioRuleBuiltInWave,
        audioRuleWave,
        audioRuleBeep,
        audioRuleProsody,
        audioRuleTextSubstitution,
    ],
    FrenzyType.NUMERIC_FORMAT: [
        audioRuleNumericProsody,
        audioRuleTextSubstitution,
    ],
    FrenzyType.OTHER_RULE: [
        audioRuleBuiltInWave,
        audioRuleWave,
        audioRuleBeep,
        #audioRuleProsody,
        audioRuleTextSubstitution,
    ],

}
