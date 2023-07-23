# nvda-phonetic-punctuation
Phonetic punctuation is an NVDA add-on that allows to convert punctuation signs into audio icons. In general, it can also convert any regular expressions into audio icons.
As of version 1.3 it can also change prosody settings, such as pitch or rate, subject to proper support from the synthesizer.

## Demo
You can listen to a sample speech output with phonetic punctuation here (10 seconds audio):
https://soundcloud.com/user-977282820/nvda-phonetic-punctuation-demo

## Download
[Latest PhoneticPunctuation release](https://github.com/mltony/nvda-phonetic-punctuation/releases/latest/download/phoneticPunctuation.nvda-addon)

## Usage
1. Make sure that your symbol level is set to appropriate value. If you're not sure, then press NVDA+P several times until you select "Symbol level all".
2. Make sure phonetic punctuation is enabled. Press NVDA+Alt+P to enable.
3. Phonetic punctuation rules can be configured via a dialog box in NVDA preferences menu.
4. Phonetic punctuation comes with a set of predefined audio rules. However, only a few of them are enabled by default. You can enable other rules, as well as add new rules in the configuration dialog.
5. Audio rules are saved in a file called `phoneticPunctuationRules.json` in NVDA user configuration directory.
6. Rules are executed in the order they appear in the configuration dialog. If your rule doesn't seem to work, try moving it to the topmost position. E.g., if you are trying to match an IP address containing periods, check whether periods have been replaced by a preceding rule, which would make matching IP address impossible.
7. Not all synthesizers support all settings. In fact there are many synthesizer that don't support many settings.

## Supported voice synthesizers
Phonetic punctuation depends on new NVDA speech framework, and as of today (October 2019), not all voice synthesizers have proper support for the new commands. This means that phonetic punctuation might not work correctly with some voice synthesizers.

Synthesizers known to work well with Phonetic Punctuation:
* Microsoft Speech API
* eSpeak
* Windows OneCore Voices

Synthesizers known to have problems with PhoneticPunctuation:
* IBMTTS (as of January 2020): see [this issue](https://github.com/davidacm/NVDA-IBMTTS-Driver/issues/22). Use eloquence_threshold synthesizer instead.
* RHVoice: Break command is not supported as of January 2020.

## Blacklist Setting
You can disable phonetic-punctuation in certain applications.  This is a comma-separated blacklist of applications where phonetic-punctuation will be disabled. 
If you are not sure what should be the name of your application, switch to that application, Press NVDA+Control+Z to open up NVDA console and type: "focus.appModule.appName" without quotes to obtain the name of current application.
Example list: slack,discord

## Copyright notice

Built-in audio icons in 3d, chimes, classic and pan-chimes categories were designed by T.V. Raman and are a part of emacspeak. For more information, see: https://github.com/tvraman/emacspeak/ .

Built-in audio icons in punctuation category were designed by Kara Goldfinch.

