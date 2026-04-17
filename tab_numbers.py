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
import terminatorlib.plugin as plugin
from terminatorlib.terminator import Terminator
from gi.repository import GObject
from terminatorlib.util import dbg, err

AVAILABLE = ['TabNumbers']

# Keep these paired — the regex must strip whatever NUMBER_FORMAT produces.
NUMBER_FORMAT = "%d: %s"
NUMBER_PREFIX_RE = re.compile(r'^\d+:\s*')
assert NUMBER_PREFIX_RE.match(NUMBER_FORMAT % (1, '')), \
    "NUMBER_FORMAT and NUMBER_PREFIX_RE have drifted"

_NOTEBOOK_SIGNALS = ('page-added', 'page-removed', 'page-reordered')


def _strip_prefix(text):
    if not text:
        return ""
    return NUMBER_PREFIX_RE.sub('', text)


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
            original = self._original_register_window

            def wrapped_register_window(window):
                original(window)
                try:
                    self.process_window(window)
                except Exception as e:
                    err('TabNumbers: Error processing new window: %s' % e)

            self.terminator.register_window = wrapped_register_window

            for window in self.terminator.windows:
                self.process_window(window)
            dbg('TabNumbers plugin initialized')
        except Exception as e:
            err('TabNumbers: Error in delayed_init: %s' % e)
        return False  # don't repeat this idle callback

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
        if hasattr(notebook, '_tabnumbers_handler_ids'):
            return
        notebook._tabnumbers_handler_ids = [
            notebook.connect(sig, self.on_tab_event)
            for sig in _NOTEBOOK_SIGNALS
        ]
        dbg('TabNumbers: Connected to notebook signals')
        self.wrap_tab_labels(notebook)
        self.renumber_all_tabs(notebook)

    def wrap_tab_labels(self, notebook):
        for page, editable_label in _iter_tab_labels(notebook):
            self.wrap_editablelabel_set_text(editable_label, page, notebook)

    def wrap_editablelabel_set_text(self, editable_label, page, notebook):
        if hasattr(editable_label, '_tabnumbers_original_set_text'):
            return

        original_set_text = editable_label.set_text
        editable_label._tabnumbers_original_set_text = original_set_text

        # Closure captures `page` so page_num() is an O(1) C-level lookup
        # instead of a per-update Python scan of every tab.
        def numbered_set_text(text, force=False):
            raw_text = text if text else ""
            try:
                page_index = notebook.page_num(page)
                if page_index < 0:
                    return original_set_text(raw_text, force=force)
                numbered = NUMBER_FORMAT % (page_index + 1, _strip_prefix(raw_text))
                # Skip the GTK property set + Pango relayout when unchanged.
                if numbered == editable_label.get_text():
                    return None
                return original_set_text(numbered, force=force)
            except Exception as e:
                err('TabNumbers: Error in wrapped set_text: %s' % e)
                return original_set_text(raw_text, force=force)

        editable_label.set_text = numbered_set_text

        handler_id = editable_label.connect('edit-done', self.on_tab_label_edited)
        editable_label._tabnumbers_edit_handler = handler_id
        dbg('TabNumbers: Wrapped set_text for EditableLabel')

    def on_tab_event(self, notebook, *args):
        try:
            self.wrap_tab_labels(notebook)
            self.renumber_all_tabs(notebook)
            self.check_for_new_windows()
        except Exception as e:
            err('TabNumbers: Error in on_tab_event: %s' % e)

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
            err('TabNumbers: Error in on_tab_label_edited: %s' % e)

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
            err('TabNumbers: Error during unload: %s' % e)

    def _unwrap_window(self, window):
        if not (hasattr(window, 'is_child_notebook') and window.is_child_notebook()):
            return
        notebook = window.get_child()
        handler_ids = getattr(notebook, '_tabnumbers_handler_ids', None)
        if handler_ids:
            for hid in handler_ids:
                try:
                    notebook.disconnect(hid)
                except Exception:
                    pass
            del notebook._tabnumbers_handler_ids
        for _page, editable_label in _iter_tab_labels(notebook):
            original = getattr(editable_label, '_tabnumbers_original_set_text', None)
            if original is None:
                continue
            handler_id = getattr(editable_label, '_tabnumbers_edit_handler', None)
            if handler_id is not None:
                try:
                    editable_label.disconnect(handler_id)
                except Exception:
                    pass
                del editable_label._tabnumbers_edit_handler
            editable_label.set_text = original
            del editable_label._tabnumbers_original_set_text
