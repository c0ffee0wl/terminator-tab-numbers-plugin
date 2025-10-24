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

import terminatorlib.plugin as plugin
from terminatorlib.terminator import Terminator
from terminatorlib.factory import Factory
from gi.repository import GObject
from terminatorlib.util import dbg, err
import re

# Every plugin you want Terminator to load *must* be listed in 'AVAILABLE'
AVAILABLE = ['TabNumbers']

class TabNumbers(plugin.Plugin):
    """Plugin to display tab numbers in tab titles"""
    capabilities = ['tab_numbers']
    
    def __init__(self):
        """Initialize the plugin"""
        plugin.Plugin.__init__(self)
        dbg('TabNumbers plugin initializing...')
        
        # Cache regex pattern and factory for performance
        self._number_prefix_pattern = re.compile(r'^\d+:\s*')
        self._factory = Factory()
        
        # Track processed notebooks to avoid duplicate signal connections
        self._processed_notebooks = set()

        # Track wrapped EditableLabels to avoid double-wrapping
        self._wrapped_editablelabels = set()

        # Use idle_add to ensure Terminator is fully initialized
        GObject.idle_add(self.delayed_init)
    
    def delayed_init(self):
        """Initialize the plugin after Terminator is ready"""
        try:
            self.terminator = Terminator()
            dbg('TabNumbers: Terminator instance obtained')
            
            # Process existing windows
            for window in self.terminator.windows:
                self.process_window(window)

            dbg('TabNumbers plugin initialized successfully')
        except Exception as e:
            err('TabNumbers: Error in delayed_init: %s' % e)
        
        return False  # Don't repeat this idle callback

    def process_window(self, window):
        """Process a window to find and connect to notebooks"""
        try:
            notebooks = self.find_notebooks_in_widget(window)

            for notebook in notebooks:
                self.setup_notebook(notebook)
        except Exception as e:
            err('TabNumbers: Error processing window: %s' % e)

    def check_for_new_windows(self):
        """Check for new windows and process them (lightweight operation)"""
        try:
            for window in self.terminator.windows:
                self.process_window(window)
        except Exception as e:
            err('TabNumbers: Error checking for new windows: %s' % e)

    def setup_notebook(self, notebook):
        """Set up a notebook for tab numbering"""
        try:
            # Use object id for tracking to avoid memory leaks
            notebook_id = id(notebook)
            
            # Check if we've already processed this notebook
            if notebook_id not in self._processed_notebooks:
                # Connect to notebook signals for immediate response
                notebook.connect('page-added', self.on_tab_event)
                notebook.connect('page-removed', self.on_tab_event)
                notebook.connect('page-reordered', self.on_tab_event)
                notebook.connect('switch-page', self.on_tab_switch)
                
                # Mark as processed
                self._processed_notebooks.add(notebook_id)
                dbg('TabNumbers: Connected to notebook signals')
            
            # Wrap tab labels for existing tabs to intercept all label updates
            self.wrap_tab_labels(notebook)
        except Exception as e:
            err('TabNumbers: Error setting up notebook: %s' % e)
    
    def wrap_tab_labels(self, notebook):
        """Wrap EditableLabel.set_text() methods to automatically add tab numbers"""
        try:
            num_pages = notebook.get_n_pages()

            for i in range(num_pages):
                page = notebook.get_nth_page(i)
                if page:
                    tab_label = notebook.get_tab_label(page)
                    if tab_label and hasattr(tab_label, 'label'):
                        self.wrap_editablelabel_set_text(tab_label, notebook)
        except Exception as e:
            err('TabNumbers: Error wrapping tab labels: %s' % e)

    def wrap_editablelabel_set_text(self, tab_label, notebook):
        """Wrap a single EditableLabel.set_text() method to add numbering"""
        try:
            editable_label = tab_label.label

            # Use object id for tracking to avoid memory leaks
            editablelabel_id = id(editable_label)

            # Check if already wrapped
            if editablelabel_id in self._wrapped_editablelabels:
                return

            # Save original method on the EditableLabel itself for edit-done handler to use
            original_set_text = editable_label.set_text
            editable_label._tabnumbers_original_set_text = original_set_text

            # Create wrapper function
            def numbered_set_text(text, force=False):
                """Wrapper that automatically adds tab number prefix"""
                try:
                    # Validate input
                    if not text:
                        text = ""

                    # Find current page index for this tab_label
                    num_pages = notebook.get_n_pages()
                    page_index = -1

                    for i in range(num_pages):
                        page = notebook.get_nth_page(i)
                        if page and notebook.get_tab_label(page) == tab_label:
                            page_index = i
                            break

                    # If we found the page, add numbering
                    if page_index >= 0:
                        # Strip existing number prefix
                        clean_text = self.remove_number_prefix(text)
                        # Add correct number prefix
                        text = "%d: %s" % (page_index + 1, clean_text)
                        dbg('TabNumbers: Wrapped set_text called for tab %d: "%s"' % (page_index + 1, text))

                    # Call original method
                    return original_set_text(text, force=force)
                except Exception as e:
                    err('TabNumbers: Error in wrapped set_text: %s' % e)
                    # Fallback to original method on error
                    return original_set_text(text, force=force)

            # Replace method with wrapper
            editable_label.set_text = numbered_set_text

            # Mark as wrapped
            self._wrapped_editablelabels.add(editablelabel_id)
            dbg('TabNumbers: Wrapped set_text for EditableLabel')

            # Also connect to edit-done signal if not already connected
            if not hasattr(editable_label, '_tabnumbers_edit_connected'):
                editable_label.connect('edit-done', self.on_tab_label_edited, notebook, tab_label)
                editable_label._tabnumbers_edit_connected = True
                dbg('TabNumbers: Connected to tab label edit-done signal')

            # Trigger initial numbering for this tab
            current_text = editable_label.get_text()
            if current_text:
                # Use the wrapper to add numbers
                numbered_set_text(current_text, force=True)
        except Exception as e:
            err('TabNumbers: Error wrapping EditableLabel.set_text: %s' % e)

    def on_tab_event(self, notebook, *args):
        """Handle tab events (add, remove, reorder)"""
        # Wrap any new tab labels
        self.wrap_tab_labels(notebook)
        # Force renumbering of all existing tabs
        self.renumber_all_tabs(notebook)
        # Check for new windows (lightweight, handles new Terminator windows)
        self.check_for_new_windows()
    
    def renumber_all_tabs(self, notebook):
        """Force renumbering of all tabs in the notebook"""
        try:
            num_pages = notebook.get_n_pages()
            dbg('TabNumbers: Renumbering %d tabs' % num_pages)

            for i in range(num_pages):
                page = notebook.get_nth_page(i)
                if not page:
                    continue

                tab_label = notebook.get_tab_label(page)
                if not tab_label or not hasattr(tab_label, 'label'):
                    continue

                editable_label = tab_label.label

                # Get current text and strip existing number
                current_text = editable_label.get_text()
                clean_text = self.remove_number_prefix(current_text)

                # Use the original unwrapped set_text to update with correct number
                # This triggers the wrapper which will add the correct number
                if hasattr(editable_label, '_tabnumbers_original_set_text'):
                    # Force the update by calling the wrapper through the current set_text
                    editable_label.set_text(clean_text, force=True)
                    dbg('TabNumbers: Renumbered tab %d to: "%d: %s"' % (i, i + 1, clean_text))
        except Exception as e:
            err('TabNumbers: Error renumbering tabs: %s' % e)

    def on_tab_switch(self, notebook, page, page_num, *args):
        """Handle tab switch events"""
        # Check for new windows (lightweight, handles new Terminator windows)
        self.check_for_new_windows()

    def on_tab_label_edited(self, editable_label, notebook, tab_label):
        """Handle tab label edit-done events"""
        try:
            # Get the edited text from the EditableLabel
            current_text = editable_label.get_text()

            # Find which tab this label belongs to
            num_pages = notebook.get_n_pages()
            page_index = -1

            for i in range(num_pages):
                page = notebook.get_nth_page(i)
                if page and notebook.get_tab_label(page) == tab_label:
                    page_index = i
                    break

            # If we found the tab, update with correct number
            if page_index >= 0:
                # Remove existing number prefix
                clean_text = self.remove_number_prefix(current_text)
                # Add correct number prefix
                numbered_text = "%d: %s" % (page_index + 1, clean_text)

                # Use the original unwrapped set_text to avoid double-processing
                if hasattr(editable_label, '_tabnumbers_original_set_text'):
                    editable_label._tabnumbers_original_set_text(numbered_text, force=True)
                else:
                    # Fallback if original not stored (shouldn't happen)
                    editable_label.set_text(numbered_text, force=True)

                dbg('TabNumbers: Re-added number after edit for tab %d: "%s"' % (page_index + 1, numbered_text))

            # Check for new windows (lightweight, handles new Terminator windows)
            self.check_for_new_windows()
        except Exception as e:
            err('TabNumbers: Error in on_tab_label_edited: %s' % e)
    
    def find_notebooks_in_widget(self, widget):
        """Recursively find all notebook widgets"""
        notebooks = []
        
        try:
            # Use cached factory instance
            if self._factory.isinstance(widget, 'Notebook'):
                notebooks.append(widget)
            
            # Check children
            if hasattr(widget, 'get_children'):
                for child in widget.get_children():
                    notebooks.extend(self.find_notebooks_in_widget(child))
            elif hasattr(widget, 'get_child'):
                child = widget.get_child()
                if child:  # Check if child exists before recursing
                    notebooks.extend(self.find_notebooks_in_widget(child))
        except Exception as e:
            err('TabNumbers: Error finding notebooks: %s' % e)
            
        return notebooks
    
    def remove_number_prefix(self, text):
        """Remove existing number prefix from tab title"""
        if not text:
            return ""
        # Use cached regex pattern for performance
        return self._number_prefix_pattern.sub('', text)
    
    def cleanup_destroyed_notebooks(self):
        """Clean up references to destroyed notebooks"""
        # This could be called periodically if memory usage becomes an issue
        # For now, we rely on Python's garbage collection
        pass
    
    def unload(self):
        """Clean up when plugin is unloaded"""
        try:
            # Clear tracking sets
            self._processed_notebooks.clear()
            self._wrapped_editablelabels.clear()
            dbg('TabNumbers plugin unloaded')
        except Exception as e:
            err('TabNumbers: Error during unload: %s' % e)

