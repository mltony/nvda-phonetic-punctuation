#!/usr/bin/python

import os,re,sys
import json

disablePatterns  =[
    f'\\{c}'
    for c in '(()[]{}'
]
escapePatterns = [
    rf'\{c}'
    for c in '.,!?'
]
unescapePatterns = [
    rf'{c}'
    for c in '.,!?'
]

j = json.loads(open(r"C:\Users\tony\AppData\Roaming\nvda\phoneticPunctuationRules.json", 'r', encoding='utf-8').read())
d = []
for rule in j:
    if (
        rule['frenzyType'] != 'TEXT'
        or rule["comment"] in [
            "ALL_CAPITAL",
            "...",
            '.',
            '!',
            '?',
            ',',
        ]
        or rule["pattern"] in disablePatterns + escapePatterns + unescapePatterns
    ):
        if rule["pattern"] in disablePatterns:
            rule['enabled'] = False
        d.append(rule)

f = open("defaultEarconsAndSpeechRules.json", 'w', encoding='utf-8')
print(json.dumps(d, indent=4, sort_keys=True), file=f)
f.close()
