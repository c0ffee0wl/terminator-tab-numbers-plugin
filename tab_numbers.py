#!/usr/bin/env python3
# Terminator Plugin: Tab Numbers
# Copyright (C) 2025
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# Displays the current tab number in the title of each tab

import re
import traceback
import terminatorlib.plugin as plugin
from terminatorlib.terminator import Terminator
from gi.repository import GObject
from terminatorlib.util import dbg, err

AVAILABLE = ['TabNumbers']

# Keep these paired — the regex must strip whatever NUMBER_FORMAT produces.
NUMBER_FORMAT = "%d: %s"
NUMBER_PREFIX_RE = re.compile(r'^\d+:\s*')
if not NUMBER_PREFIX_RE.match(NUMBER_FORMAT % (1, '')):
    raise RuntimeError("NUMBER_FORMAT and NUMBER_PREFIX_RE have drifted")

_NOTEBOOK_SIGNALS = ('page-added', 'page-removed', 'page-reordered')

_NOTEBOOK_HANDLERS_ATTR = '_tabnumbers_handler_ids'
_ORIG_SET_TEXT_ATTR = '_tabnumbers_original_set_text'
_EDIT_HANDLER_ATTR = '_tabnumbers_edit_handler'


def _strip_prefix(text):
    return NUMBER_PREFIX_RE.sub('', text)


def _log_err(context, exc):
    err('TabNumbers: Error in %s: %s\n%s' %
        (context, exc, traceback.format_exc()))


def _iter_tab_labels(notebook):
    """Yield (page, editable_label) for each numberable tab in the notebook."""
    for i in range(notebook.get_n_pages()):
        page = notebook.get_nth_page(i)
        if not page:
            continue
        tab_label = notebook.get_tab_label(page)
        if tab_label and hasattr(tab_label, 'label'):
            yield page, tab_label.label


class TabNumbers(plugin.Plugin):
    """Plugin to display tab numbers in tab titles"""
    capabilities = ['tab_numbers']

    def __init__(self):
        plugin.Plugin.__init__(self)
        self.terminator = None
        self._original_register_window = None
        # Terminator's singleton and windows aren't ready during plugin init;
        # idle_add defers setup until after the GTK main loop is running.
        GObject.idle_add(self.delayed_init)

    def delayed_init(self):
        try:
            self.terminator = Terminator()

            # Terminator exposes no window-added signal, so wrap register_window
            # to catch new windows without polling.
            self._original_register_window = self.terminator.register_window

            def wrapped_register_window(window):
                self._original_register_window(window)
                try:
                    self.process_window(window)
                except Exception as e:
                    _log_err('processing new window', e)

            self.terminator.register_window = wrapped_register_window

            for window in self.terminator.windows:
                self.process_window(window)
            dbg('TabNumbers plugin initialized')
        except Exception as e:
            _log_err('delayed_init', e)
        return False

    def process_window(self, window):
        # A Terminator Window's direct child is either a Terminal or a Notebook.
        if hasattr(window, 'is_child_notebook') and window.is_child_notebook():
            self.setup_notebook(window.get_child())

    def check_for_new_windows(self):
        # Fallback for the transition where a naked single-Terminal window
        # gains a Notebook on its first-tab creation — register_window is not
        # re-invoked for that transition. Only wired to the low-frequency
        # on_tab_event handler, not to every tab switch.
        if self.terminator is None:
            return
        for window in self.terminator.windows:
            self.process_window(window)

    def setup_notebook(self, notebook):
        # Skip wrap/renumber on re-entry: the on_tab_event path handles new
        # tabs on already-wired notebooks directly. This keeps
        # check_for_new_windows a cheap O(W) walk that only does work for
        # newly-appeared notebooks.
        if hasattr(notebook, _NOTEBOOK_HANDLERS_ATTR):
            return
        setattr(notebook, _NOTEBOOK_HANDLERS_ATTR, [
            notebook.connect(sig, self.on_tab_event)
            for sig in _NOTEBOOK_SIGNALS
        ])
        dbg('TabNumbers: Connected to notebook signals')
        self.wrap_tab_labels(notebook)
        self.renumber_all_tabs(notebook)

    def wrap_tab_labels(self, notebook):
        for page, editable_label in _iter_tab_labels(notebook):
            self.wrap_editablelabel_set_text(editable_label, page, notebook)

    def wrap_editablelabel_set_text(self, editable_label, page, notebook):
        if hasattr(editable_label, _ORIG_SET_TEXT_ATTR):
            return

        original_set_text = editable_label.set_text
        setattr(editable_label, _ORIG_SET_TEXT_ATTR, original_set_text)

        # Closure captures `page` so page_num() is an O(1) C-level lookup
        # instead of a per-update Python scan of every tab. One-element
        # list so the fallback can rebind without `nonlocal`.
        current_page = [page]

        def numbered_set_text(text, force=False):
            raw_text = text if text else ""
            try:
                page_index = notebook.page_num(current_page[0])
                if page_index < 0:
                    # split_axis() swaps the page widget but reuses this
                    # EditableLabel via set_tab_label(). Re-resolve by
                    # label identity and heal the holder so subsequent
                    # calls take the fast path again.
                    for p, lbl in _iter_tab_labels(notebook):
                        if lbl is editable_label:
                            current_page[0] = p
                            page_index = notebook.page_num(p)
                            break
                    if page_index < 0:
                        return original_set_text(raw_text, force=force)
                numbered = NUMBER_FORMAT % (page_index + 1, _strip_prefix(raw_text))
                # Skip the GTK property set + Pango relayout when unchanged.
                if numbered == editable_label.get_text():
                    return None
                return original_set_text(numbered, force=force)
            except Exception as e:
                _log_err('wrapped set_text', e)
                return original_set_text(raw_text, force=force)

        editable_label.set_text = numbered_set_text

        handler_id = editable_label.connect('edit-done', self.on_tab_label_edited)
        setattr(editable_label, _EDIT_HANDLER_ATTR, handler_id)
        dbg('TabNumbers: Wrapped set_text for EditableLabel')

    def on_tab_event(self, notebook, *args):
        try:
            self.wrap_tab_labels(notebook)
            self.renumber_all_tabs(notebook)
            self.check_for_new_windows()
        except Exception as e:
            _log_err('on_tab_event', e)

    def renumber_all_tabs(self, notebook):
        dbg('TabNumbers: Renumbering %d tabs' % notebook.get_n_pages())
        for _page, editable_label in _iter_tab_labels(notebook):
            # The wrapper strips and re-applies the correct prefix; force=True
            # overrides EditableLabel's _custom flag so user-edited tabs also
            # get renumbered when their position changes.
            editable_label.set_text(editable_label.get_text(), force=True)

    def on_tab_label_edited(self, editable_label):
        try:
            # User edits reach the inner Gtk.Label directly via
            # EditableLabel._on_entry_activated, bypassing the wrapper. Re-run
            # set_text so the wrapper re-applies the number prefix.
            editable_label.set_text(editable_label.get_text(), force=True)
        except Exception as e:
            _log_err('on_tab_label_edited', e)

    def unload(self):
        try:
            if self.terminator is not None:
                if self._original_register_window is not None:
                    self.terminator.register_window = self._original_register_window
                    self._original_register_window = None
                for window in self.terminator.windows:
                    self._unwrap_window(window)
            dbg('TabNumbers plugin unloaded')
        except Exception as e:
            _log_err('unload', e)

    def _unwrap_window(self, window):
        if not (hasattr(window, 'is_child_notebook') and window.is_child_notebook()):
            return
        notebook = window.get_child()
        handler_ids = getattr(notebook, _NOTEBOOK_HANDLERS_ATTR, None)
        if handler_ids:
            for hid in handler_ids:
                try:
                    notebook.disconnect(hid)
                except Exception:
                    pass
            delattr(notebook, _NOTEBOOK_HANDLERS_ATTR)
        for _page, editable_label in _iter_tab_labels(notebook):
            original = getattr(editable_label, _ORIG_SET_TEXT_ATTR, None)
            if original is None:
                continue
            handler_id = getattr(editable_label, _EDIT_HANDLER_ATTR, None)
            if handler_id is not None:
                try:
                    editable_label.disconnect(handler_id)
                except Exception:
                    pass
                delattr(editable_label, _EDIT_HANDLER_ATTR)
            editable_label.set_text = original
            delattr(editable_label, _ORIG_SET_TEXT_ATTR)
