# Kodi SponsorBlock

This is an **unofficial** port of the [SponsorBlock](https://sponsor.ajay.app/) browser extension.
It works as an extension to the [YouTube Plugin](https://github.com/jdf76/plugin.video.youtube).

Once installed, the addon will automatically skip sponsor segments in all YouTube videos you watch.

For a detailed explanation of how SponsorSkip works please visit the [offical website](https://sponsor.ajay.app/).


## Installation

### IMPORTANT NOTE

This addon depends on the YouTube plugin, specifically [version 6.7.0](https://github.com/jdf76/plugin.video.youtube/releases/tag/6.7.0-dev) which is currently in alpha.
This means that it isn't yet part of the official repository.

If you still wish to use this addon, follow [this guide](https://github.com/jdf76/plugin.video.youtube/wiki/Installation) to install the development version of the YouTube plugin.

<br/>

The addon is available in [siku2's repository](https://siku2.io/kodi-repository).

1. Install [siku2's repository](https://siku2.io/kodi-repository/install)
2. Go to "Add-ons" > "Install from repository" > "siku2's Repository"
3. Install "SponsorBlock" under "Services"

Congratulations, you now have SponsorBlock installed.


## Configuration

Different settings are shown based on your [Settings Level](https://kodi.wiki/view/Settings#Settings_Level).
For instance, you can only change your user id if your settings level is "Advanced" or above.


## Issues and Suggestions

Feel free to [open a new issue](https://github.com/siku2/script.service.sponsorblock/issues/new) if you've encountered an issue or if you have a suggestion.
Bonus points if you [provide the debug logs](https://kodi.wiki/view/Log_file/Easy).

### Known Issues

#### Seeking to just before the start of a sponsor segment doesn't skip it

This is hard to fix because Kodi doesn't accurately report the current time after seeking.
For a short period after seeking Kodi still reports the previous time.

#### Ad skip dialog is ugly

Yeah, it definitely needs some work...
