# nvda-phonetic-punctuation
Phonetic punctuation is an NVDA add-on that allows to convert punctuation signs into audio icons. In general, it can also convert any regular expressions into audio icons.

## Demo
You can listen to a sample speech output with phonetic punctuation here (10 seconds audio):
https://soundcloud.com/user-977282820/nvda-phonetic-punctuation-demo

## Download
TBD
[Latest PhoneticPunctuation release](https://github.com/mltony/nvda-phonetic-punctuation/releases/latest/download/phoneticPunctuation.nvda-addon)

## Usage
1. Make sure that your symbol level is set to appropriate value. If you're not sure, then press NVDA+P several times until you select "Symbol level all".
2. Make sure phonetic punctuation is enabled. Press NVDA+Alt+P to enable.
3. Phonetic punctuation rules can be configured via a dialog box in NVDA preferences menu.
4. Phonetic punctuation comes with a set of predefined audio rules. However, only a few of them are enabled by default. You can enable other rules, as well as add new rules in the configuration dialog.
5. Audio rules are saved in a file called `phoneticPunctuationRules.json` in NVDA user configuration directory.

## Supported voice synthesizers
Phonetic punctuation depends on new NVDA speech framework, and as of today (October 2019), not all voice synthesizers have proper support for the new commands. This means that phonetic punctuation might not work correctly with some voice synthesizers.

Synthesizers known to work well with Phonetic Punctuation:
* Microsoft Speech API
* eSpeak
* Windows OneCore Voices

Synthesizers known to have problems with PhoneticPunctuation:
* IBMTTS: see [this issue](https://github.com/davidacm/NVDA-IBMTTS-Driver/issues/22).
* RHVoice: Break command is not supported.

## Copyright notice
Built-in audio icons were designed by T.V. Raman and are a part of emacspeak. For more information, see: https://github.com/tvraman/emacspeak/ .