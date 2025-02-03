# -*- coding: UTF-8 -*-
#A part of the Earcons and Speech Rules addon for NVDA
#Copyright (C) 2019-2023 Tony Malykh
#This file is covered by the GNU General Public License.
#See the file COPYING.txt for more details.

import addonHandler
from enum import Enum
addonHandler.initTranslation()

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
    FrenzyType.TEXT: _("Text regular expressions"),
    FrenzyType.CHARACTER: _("Characters"),
    FrenzyType.ROLE: _("Roles"),
    FrenzyType.STATE: _("States"),
    FrenzyType.NEGATIVE_STATE: _("Negative states"),
    FrenzyType.FORMAT: _("Text formatting"),
    FrenzyType.NUMERIC_FORMAT: _("Numeric text formatting"),
    FrenzyType.OTHER_RULE: _("Other audio rules"),
}

FRENZY_NAMES_SINGULAR = {
    FrenzyType.TEXT: _("Text regular expression pattern"),
    FrenzyType.CHARACTER: _("Character"),
    FrenzyType.ROLE: _("Role"),
    FrenzyType.STATE: _("State"),
    FrenzyType.NEGATIVE_STATE: _("Negative state"),
    FrenzyType.FORMAT: _("Format"),
    FrenzyType.NUMERIC_FORMAT: _("Numeric format"),
    FrenzyType.OTHER_RULE: _("Other audio rule"),
}

rulesDialogOpen = False

class TextFormat(Enum):
    BOLD = 'bold'
    ITALIC = 'italic'
    UNDERLINE = 'underline'
    STRIKETHROUGH = 'strikethrough'
    HIGHLIGHTED = 'highlighted'
    HEADING = 'heading'
    HEADING1 = 'heading1'
    HEADING2 = 'heading2'
    HEADING3 = 'heading3'
    HEADING4 = 'heading4'
    HEADING5 = 'heading5'
    HEADING6 = 'heading6'

TEXT_FORMAT_NAMES = {
    TextFormat.BOLD: _('Bold'),
    TextFormat.ITALIC: _('Italic'),
    TextFormat.UNDERLINE: _('Underline'),
    TextFormat.STRIKETHROUGH: _('Strikethrough'),
    TextFormat.HEADING: _('Heading'),
    TextFormat.HIGHLIGHTED: _('Highlighted'),
    TextFormat.HEADING1: _('Heading level 1'),
    TextFormat.HEADING2: _('Heading level 2'),
    TextFormat.HEADING3: _('Heading level 3'),
    TextFormat.HEADING4: _('Heading level 4'),
    TextFormat.HEADING5: _('Heading level 5'),
    TextFormat.HEADING6: _('Heading level 6'),
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
    NO_INDENT = "no_indent"

OTHER_RULE_NAMES = {
    OtherRule.OUT_OF_CONTAINER: _('Out of container'),
    OtherRule.BLANK: _('Blank announcement'),
    OtherRule.NO_INDENT: _('No indent announcement'),
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

PROSODY_LABELS = [
    "Pitch",
    "Volume",
    "Rate",
]
