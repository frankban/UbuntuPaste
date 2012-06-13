============
Ubuntu Paste
============

This Sublime Text 2 plugin can be used to paste code snippets on
http://pastebin.ubuntu.com/

Installation
============

Branch this project into Sublime Text Packages directory.
On Linux: ``~/.config/sublime-text-2/Packages/``
On MacOs: ``~/Library/Application Support/Sublime Text 2/Packages/``

E.g.::

    git clone https://github.com/frankban/UbuntuPaste.git ~/.config/sublime-text-2/Packages/UbuntuPaste

Usage
=====

If you want to customize options, go to
Preferences >> Package Settings >> UbuntuPaste >> Settings - Default.

``Control + Alt + Super (Cmd) + u`` will paste the content of current view
or, if present, the current selection(s).
Alternativly you can use the command ``ubuntupaste``.

The resulting URL is copied to the clipboard and diplayed on the status bar.
