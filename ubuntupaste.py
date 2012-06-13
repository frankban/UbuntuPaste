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

    def __init__(self, command_name, view):
        self.command_name = command_name.title()
        self.view = view
        self.count = itertools.count()

    def _get_content(self, contents):
        return '{0}: {1}'.format(self.command_name, ' '.join(contents))

    def message(self, *contents):
        """Display a message in the status bar."""
        sublime.status_message(self._get_content(contents))

    def status(self, *contents):
        """Add a status to the view, using contents as value."""
        self.view.set_status(self.command_name, self._get_content(contents))

    def progress(self, url):
        """Show pasting progress."""
        dots = '.' * (self.count.next() % 4)
        self.status('Pasting to', url, '[', dots.ljust(3), ']')

    def error(self, *contents):
        """Display an error in the status bar."""
        self.message('ERROR:', *contents)

    def success(self, result, copy_to_clipboard, open_in_browser):
        """Paste succeded."""
        contents = ['URL:', result, '|']
        if copy_to_clipboard:
            contents.append('Copied to your clipboard!')
        if open_in_browser:
            contents.append('Opened in your browser!')
        self.message(*contents)

    def done(self):
        """Erase the status messages."""
        self.view.erase_status(self.command_name)


class Settings(object):
    """Store and validate plugin settings."""

    def __init__(self, global_settings, local_settings):
        self._global_settings = global_settings
        self._local_settings = local_settings
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
            self.error = 'Invalid URL.'
            return False
        copy_to_clipboard = settings.get('copy_to_clipboard', True)
        open_in_browser = settings.get('open_in_browser', False)
        if not (copy_to_clipboard or open_in_browser):
            self.error = 'You need to either copy or open the URL.'
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

    def __init__(self, url, **kwargs):
        self.url = url
        self.data = kwargs
        self.error = None
        self.result = None
        threading.Thread.__init__(self)

    def run(self):
        try:
            request = urllib2.Request(
                self.url, urllib.urlencode(self.data),
                headers={'User-Agent': 'SublimeText2'})
            response = urllib2.urlopen(request, timeout=5)
        except urllib2.HTTPError as err:
            self.error = 'HTTP error {0}.'.format(err.code)
        except urllib2.URLError as err:
            self.error = 'URL error {0}.'.format(err.reason)
        else:
            self.result = response.url


class UbuntupasteCommand(sublime_plugin.TextCommand):
    """Paste code snippets on http://pastebin.ubuntu.com/."""

    def __init__(self, *args, **kwargs):
        self.ui = None
        self._is_enabled = True
        super(UbuntupasteCommand, self).__init__(*args, **kwargs)

    def is_enabled(self):
        return self._is_enabled

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
        self._is_enabled = False
        self.ui = UserInterface(self.name(), self.view)
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
            url, content=self.get_content(sep), poster=poster, syntax=syntax)
        self.ui.progress(url)
        paster.start()
        self.wait(paster, copy_to_clipboard, open_in_browser)

    def wait(self, paster, *args):
        if not paster.is_alive():
            return self.done(paster, *args)
        self.ui.progress(paster.url)
        sublime.set_timeout(lambda: self.wait(paster, *args), 200)

    def done(self, paster, copy_to_clipboard, open_in_browser):
        result = paster.result
        if result:
            if copy_to_clipboard:
                sublime.set_clipboard(result)
            if open_in_browser:
                webbrowser.open(result)
            self.ui.success(result, copy_to_clipboard, open_in_browser)
        else:
            self.ui.error(paster.error)
        self.ui.done()
        self._is_enabled = True
