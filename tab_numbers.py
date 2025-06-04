#!/usr/bin/env python3
# Terminator Plugin: Tab Numbers (Improved)
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
            
            # Keep original timer frequency for reliability
            GObject.timeout_add(10, self.periodic_check)
            
            dbg('TabNumbers plugin initialized successfully')
        except Exception as e:
            err('TabNumbers: Error in delayed_init: %s' % e)
        
        return False  # Don't repeat this idle callback
    
    def periodic_check(self):
        """Periodically check for new windows and update tab numbers"""
        try:
            for window in self.terminator.windows:
                self.process_window(window)
        except Exception as e:
            err('TabNumbers: Error in periodic_check: %s' % e)
        
        return True  # Keep the timer running
    
    def process_window(self, window):
        """Process a window to find and connect to notebooks"""
        try:
            notebooks = self.find_notebooks_in_widget(window)
            
            for notebook in notebooks:
                self.setup_notebook(notebook)
        except Exception as e:
            err('TabNumbers: Error processing window: %s' % e)
    
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
            
            # Connect to tab label edit-done events for existing tabs
            self.connect_tab_label_signals(notebook)
            
            # Update existing tabs immediately
            self.update_tab_numbers(notebook)
        except Exception as e:
            err('TabNumbers: Error setting up notebook: %s' % e)
    
    def on_tab_event(self, notebook, *args):
        """Handle tab events (add, remove, reorder)"""
        # Connect to tab label signals for any new tabs
        self.connect_tab_label_signals(notebook)
        # Update immediately, then schedule another update to be sure
        self.update_tab_numbers(notebook)
        GObject.idle_add(self.update_tab_numbers, notebook)
    
    def on_tab_switch(self, notebook, page, page_num, *args):
        """Handle tab switch events for immediate response"""
        # Update immediately when switching tabs
        GObject.idle_add(self.update_tab_numbers, notebook)
    
    def connect_tab_label_signals(self, notebook):
        """Connect to tab label edit-done signals for all tabs in a notebook"""
        try:
            num_pages = notebook.get_n_pages()
            
            for i in range(num_pages):
                page = notebook.get_nth_page(i)
                if page:
                    tab_label = notebook.get_tab_label(page)
                    if tab_label and hasattr(tab_label, 'label'):
                        # Connect to the EditableLabel's edit-done signal
                        if not hasattr(tab_label.label, '_tabnumbers_edit_connected'):
                            tab_label.label.connect('edit-done', self.on_tab_label_edited, notebook)
                            tab_label.label._tabnumbers_edit_connected = True
                            dbg('TabNumbers: Connected to tab label edit-done signal')
        except Exception as e:
            err('TabNumbers: Error connecting tab label signals: %s' % e)
    
    def on_tab_label_edited(self, editable_label, notebook):
        """Handle tab label edit-done events"""
        # Update tab numbers when any tab label is edited
        GObject.idle_add(self.update_tab_numbers, notebook)
    
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
    
    def update_tab_numbers(self, notebook):
        """Update tab numbers for all tabs in a notebook"""
        try:
            # Validate notebook still exists
            if not notebook or not hasattr(notebook, 'get_n_pages'):
                return False
                
            num_pages = notebook.get_n_pages()
            
            for i in range(num_pages):
                page = notebook.get_nth_page(i)
                if page:
                    tab_label = notebook.get_tab_label(page)
                    if tab_label and hasattr(tab_label, 'get_label'):
                        current_text = tab_label.get_label()
                        
                        # Handle empty or None text gracefully
                        if not current_text:
                            current_text = ""
                        
                        # Remove existing number prefix if present
                        clean_text = self.remove_number_prefix(current_text)
                        
                        # Add new number prefix
                        new_text = "%d: %s" % (i + 1, clean_text)
                        
                        # Only update if the text has changed to avoid unnecessary updates
                        if current_text != new_text:
                            try:
                                # Check if this tab was originally custom
                                was_custom = hasattr(tab_label, 'label') and tab_label.label.is_custom()
                                
                                if was_custom:
                                    # For custom tabs, force the update
                                    tab_label.set_custom_label(new_text, force=True)
                                else:
                                    # For automatic tabs, use regular set_text to preserve auto-update behavior
                                    tab_label.label.set_text(new_text, force=True)
                                
                                dbg('TabNumbers: Updated tab %d to "%s"' % (i + 1, new_text))
                            except Exception as e:
                                err('TabNumbers: Error updating individual tab: %s' % e)
        except Exception as e:
            err('TabNumbers: Error updating tab numbers: %s' % e)
        
        return False  # Don't repeat this idle callback
    
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
            dbg('TabNumbers plugin unloaded')
        except Exception as e:
            err('TabNumbers: Error during unload: %s' % e)

