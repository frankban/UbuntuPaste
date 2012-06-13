import itertools
import os
import pwd
import threading
import urllib
import urllib2
import webbrowser

import sublime
import sublime_plugin


class UserInterface(object):
    """User interface for this plugin."""

    def __init__(self, command_name):
        self.command_name = command_name.title()
        self.count = itertools.count()

    def message(self, *contents):
        """Display a message in the status bar."""
        content = ' '.join(contents)
        sublime.status_message('{0}: {1}'.format(self.command_name, content))

    def error(self, *contents):
        """Display an error in the status bar."""
        self.message('ERROR:', *contents)

    def progress(self, url):
        """Show pasting progress."""
        self.message('Pasting to {0}{1}'.format(url, '.' * self.count.next()))

    def done(self, result, copy_to_clipboard, open_in_browser):
        """Paste succeded."""
        contents = ['URL:', result, '|']
        if copy_to_clipboard:
            contents.append('Copied to your clipboard!')
        if open_in_browser:
            contents.append('Opened in your browser!')
        self.message(*contents)


class Settings(object):
    """Store and validate plugin settings."""

    def __init__(self, global_settings, local_settings):
        self._global_settings = global_settings
        self._local_settings = local_settings
        self._errors = {
            'url': 'Invalid URL.',
            'copy_or_open': 'You need to either copy or open the URL.',
            }
        self.error = None
        self.options = ()

    def _get_poster(self):
        """Get the current system user name."""
        return os.getenv('USER', pwd.getpwuid(os.geteuid()).pw_name)

    def _get_syntax(self, syntax_map, default):
        """Return the syntax to be used by the paster."""
        syntax_file = self._global_settings.get('syntax')
        if syntax_file is None:
            return default
        syntax = os.path.splitext(os.path.basename(syntax_file))[0]
        return syntax_map.get(syntax.lower(), default)

    def are_valid(self):
        """Validate and set up options."""
        settings = self._local_settings
        url = settings.get('url')
        if url is None:
            self.error = self._errors['url']
            return False
        copy_to_clipboard = settings.get('copy_to_clipboard', True)
        open_in_browser = settings.get('open_in_browser', False)
        if not (copy_to_clipboard or open_in_browser):
            self.error = self._errors['copy_or_open']
            return False
        poster = settings.get('poster')
        if not poster:
            poster = self._get_poster()
        sep = settings.get('sep', '\n\n # ---\n\n')
        syntax_default = settings.get('syntax_default', 'text')
        syntax_guess = settings.get('syntax_guess', True)
        if syntax_guess:
            syntax_map = settings.get('syntax_map', {})
            syntax = self._get_syntax(syntax_map, syntax_default)
        else:
            syntax = syntax_default
        self.options = (
            url, copy_to_clipboard, open_in_browser, poster, sep, syntax
            )
        return True


class Paster(threading.Thread):
    """Paste code snippets to ubuntu pastebin."""

    def __init__(self, ui, url, **kwargs):
        self.ui = ui
        self.url = url
        self.data = kwargs
        self.error = None
        self.result = None
        threading.Thread.__init__(self)

    def run(self):
        self.ui.progress(self.url)
        try:
            request = urllib2.Request(
                self.url, urllib.urlencode(self.data),
                headers={'User-Agent': self.ui.command_name})
            response = urllib2.urlopen(request, timeout=5)
        except urllib2.HTTPError as err:
            self.error = 'HTTP error {0}.'.format(err.code)
        except urllib2.URLError as err:
            self.error = 'URL error {0}.'.format(err.reason)
        else:
            self.result = response.url

    def when_done(self, callback, *args):
        if not self.is_alive():
            return callback(self, *args)
        self.ui.progress(self.url)
        sublime.set_timeout(lambda: self.when_done(callback, *args), 200)


class UbuntupasteCommand(sublime_plugin.TextCommand):
    """Paste code snippets on http://pastebin.ubuntu.com/."""

    def get_content(self, sep):
        """Return the contents of current selections.

        If no region is selected, return all the text in the current view.
        """
        view = self.view
        regions = [i for i in view.sel() if not i.empty()]
        if not regions:
            regions = [sublime.Region(0, view.size())]
        return sep.join(view.substr(region) for region in regions)

    def run(self, edit):
        self.ui = UserInterface(self.name())
        settings = Settings(
            self.view.settings(),
            sublime.load_settings('UbuntuPaste.sublime-settings'))
        if settings.are_valid():
           self.handle(*settings.options)
        else:
            self.ui.error(settings.error)

    def handle(
        self, url, copy_to_clipboard, open_in_browser, poster, sep, syntax):
        paster = Paster(
            self.ui, url,
            content=self.get_content(sep), poster=poster, syntax=syntax)
        paster.start()
        paster.when_done(self.done, copy_to_clipboard, open_in_browser)

    def done(self, paster, copy_to_clipboard, open_in_browser):
        result = paster.result
        if result:
            if copy_to_clipboard:
                sublime.set_clipboard(result)
            if open_in_browser:
                webbrowser.open(result)
            self.ui.done(result, copy_to_clipboard, open_in_browser)
        else:
            self.ui.error(paster.error)
