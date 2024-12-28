# Earcons and Speech Rules
Earcons and Speech Rules is an NVDA add-on that allows NVDA to play earcons as well as other speech effects, such as prosody changes.
Formerly this add-on was known as Phonetic punctuation.
This add-on also includes almost all functionality of Unspoken add-on, which appears to be abandoned as of 2024.

## Demo
You can listen to a sample speech output with phonetic punctuation here (10 seconds audio):
https://soundcloud.com/user-977282820/nvda-phonetic-punctuation-demo

## Download

Please install the latest version from NVDA add-on store.

## Usage
1. Make sure Earcons and Speech Rules add-on is enabled. Press NVDA+Alt+P to enable.
2. Rules can be configured via a dialog box in NVDA preferences menu.
3. By default you will have a set  of predefined audio rules. However, only a few of them are enabled by default. You can enable other rules, as well as add new rules in the configuration dialog.
4. The rules are saved in a file called `earconsAndSpeechRules.json` in NVDA user configuration directory.
5. Not all synthesizers support all settings. In fact there are many synthesizer that don't support many settings. Please see "Supported voice synthesizers" section for more information.

## Types of rules

Rules can be configured in NVDA Settings, in the  Earcons and speech rules pane.

### Text rules

Text rules trigger on a configurable regular expression in NVDA speech. Once a rule is triggered, you can either replace matched text with an earcon or adjust prosody (such as voice pitch) for that match.

Additionally you can specify a text rule to trigger for only:

* specific applications (please refer to "Blacklist Setting" section to learn how to figure out application names),
* Windows with specific titles,
* Specific URLs (requires BrowserNav add-on to be installed and running).

Text rules are executed in the order they appear in the configuration dialog. If your rule doesn't seem to work, try moving it to the topmost position. E.g., if you are trying to match an IP address containing periods, check whether periods have been replaced by a preceding rule, which would make matching IP address impossible.

Text rules are not triggered when moving by character - please see the next section.

### Character rules

Character rules allow you to substitute a character description in spelling mode (such as "space" or "Tab") with an earcon. These rules don't affect NVDA speech when reading text unless spelling characters.

### Roles

Roles such as Editable or Button are internal NVDA property of objects describing their type. You can configure an earcon to be played for each role instead of speaking role name.

This feature was previously a part of Unspoken add-on, which appears to be abandoned as of 2024.

### States and negative states

States like "checked" and negative states like "Unchecked" can also be replaced with earcons.

You can also suppress announcing certain states that are not that important. In order to do so, check "Suppress this state in non-verbose mode" checkbox. Then you can triggerconsise state reporting by pressing NVDA+Alt+[ (left bracket; the key immediately to the right from letter P on English keyboard).

To further illustrate concise state reporting, open http://google.com and compare how the main editable is reported in verbose and concise modes.

### Text formatting

Certain formatting attributes can be expressed either as prosody or an earcon. Currently we support:

* Bold and italic
* Underline and strikethrough
* Highlighted
* Heading

### Numeric text formatting

We support two options here:

* Font size can be reported via voice pitch.
* Heading level can be reported via either voice pitch or a shorter message, such as "H1" instead of "Heading level 1".

### Other audio rules

This includes some unrelated phrases spoken by NVDA that can also be replaced with earcons:

* Blank;
* Out of container, such as out of frame;
* No indent when indentation level announcement is set to speech.

## Supported voice synthesizers
Earcons and speech rules makes use of advanced NVDA speech commands and they are not always well supported by all TTS synthesizers.

Synthesizers known to work well with Earcons and Speech Rules:
* Microsoft Speech API
* eSpeak
* Windows OneCore Voices
* Eloquence threshold

Synthesizers known to have issues with Earcons and Speech Rules:
* IBMTTS (as of December 2024): see [this issue](https://github.com/davidacm/NVDA-IBMTTS-Driver/issues/22). I fixed this problem in [this PR](https://github.com/davidacm/NVDA-IBMTTS-Driver/pull/96), however the author for some reason is not accepting it, so if you want to use earcons and Speech Rules with IBM TTS, please ask the author to merge this PR.
* RHVoice: Break command is not supported as of January 2020.

## Blacklist Setting
You can disable Earcons and Speech Rules in certain applications.  This is a comma-separated blacklist of applications where Earcons and Speech Rules will be disabled. 
If you are not sure what should be the name of your application, switch to that application, Press NVDA+Control+Z to open up NVDA console and type: "focus.appModule.appName" without quotes to obtain the name of current application.
Example list: slack,discord


## Known issues and limitations

* Sometimes "out of container" earcons are played out of order, e.g. after headingand not before.
* Roles, states and text formatting rules don't work in sayAll mode.

## Copyright notice

* Earcons in 3d, chimes, classic and pan-chimes categories were designed by T.V. Raman and are a part of emacspeak. For more information, see: https://github.com/tvraman/emacspeak/ .
* Earcons in the punctuation category were designed by Kara Goldfinch.
* Earcons in the roles category were designed by the authors of Unspoken add-on.

