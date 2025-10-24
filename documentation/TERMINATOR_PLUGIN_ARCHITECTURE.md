# Terminator Plugin Architecture - Comprehensive Guide

This document explains Terminator's plugin system, based on analysis of the official Terminator repository (gnome-terminator/terminator).

---

## 1. Plugin Loading Mechanism

### 1.1 Plugin Discovery and Load Paths

Plugins are discovered from two locations:

```
1. /path/to/terminatorlib/plugins/  (built-in plugins)
2. ~/.config/terminator/plugins/     (user plugins)
```

**Code: plugin.py (lines 61-66)**
```python
def prepare_attributes(self):
    """Prepare our attributes"""
    if not self.path:
        self.path = []
        (head, _tail) = os.path.split(borg.__file__)
        self.path.append(os.path.join(head, 'plugins'))
        self.path.append(os.path.join(get_config_dir(), 'plugins'))
        dbg('Plugin path: %s' % self.path)
```

### 1.2 Plugin Loading Process

The `PluginRegistry.load_plugins()` method:

1. Scans each directory in the plugin path
2. Imports each Python file (except `__init__.py`)
3. Looks for an `AVAILABLE` list in the module
4. Instantiates plugins that are in the config's `enabled_plugins`

**Code: plugin.py (lines 72-119)**
```python
def load_plugins(self, force=False):
    """Load all plugins present in the plugins/ directory in our module"""
    if self.done and (not force):
        dbg('Already loaded')
        return

    config = Config()

    for plugindir in self.path:
        sys.path.insert(0, plugindir)
        try:
            files = os.listdir(plugindir)
        except OSError:
            sys.path.remove(plugindir)
            continue
        
        for plugin in files:
            if plugin == '__init__.py':
                continue
            pluginpath = os.path.join(plugindir, plugin)
            
            if os.path.isfile(pluginpath) and plugin[-3:] == '.py':
                dbg('Importing plugin %s' % plugin)
                try:
                    module = __import__(plugin[:-3], None, None, [''])
                    
                    # CRITICAL: Plugin must define AVAILABLE list
                    for item in getattr(module, 'AVAILABLE'):
                        func = getattr(module, item)
                        
                        # Register available plugins
                        if item not in list(self.available_plugins.keys()):
                            self.available_plugins[item] = func
                        
                        # Check if enabled in config
                        if item not in config['enabled_plugins']:
                            dbg('plugin %s not enabled, skipping' % item)
                            continue
                        
                        # Instantiate enabled plugins
                        if item not in self.instances:
                            self.instances[item] = func()
                        elif force:
                            # Reload: unload old, create new
                            self.instances[item].unload()
                            self.instances.pop(item, None)
                            self.instances[item] = func()
                            
                except Exception as ex:
                    err('PluginRegistry::load_plugins: Importing plugin %s failed: %s' 
                        % (plugin, ex))

    self.done = True
```

### 1.3 AVAILABLE Array Requirement

Every plugin module MUST define an `AVAILABLE` list containing class names to expose:

**Example: testplugin.py**
```python
import terminatorlib.plugin as plugin

# REQUIRED: List all plugin classes in AVAILABLE
AVAILABLE = ['TestPlugin']

class TestPlugin(plugin.Plugin):
    capabilities = ['test']
    
    def do_test(self):
        return('TestPluginWin')
```

**Example: url_handlers.py**
```python
AVAILABLE = ['LaunchpadBugURLHandler', 'LaunchpadCodeURLHandler', 'APTURLHandler']

class LaunchpadBugURLHandler(plugin.URLHandler):
    # ...
```

---

## 2. Plugin Base Classes

### 2.1 Plugin Base Class

**Code: plugin.py (lines 33-43)**
```python
class Plugin(object):
    """Definition of our base plugin class"""
    capabilities = None

    def __init__(self):
        """Class initialiser."""
        pass

    def unload(self):
        """Prepare to be unloaded"""
        pass
```

**Requirements:**
- Must inherit from `plugin.Plugin`
- Must define `capabilities` list
- `__init__()` is called when plugin is instantiated
- `unload()` is called when plugin is being disabled (should clean up signals/resources)

### 2.2 Built-in Plugin Base Classes

Terminator provides several specialized base classes:

#### URLHandler

**Code: plugin.py (lines 163-189)**
```python
class URLHandler(Plugin):
    """Base class for URL handlers"""
    capabilities = ['url_handler']
    handler_name = None
    match = None
    nameopen = None
    namecopy = None

    def __init__(self):
        """Class initialiser"""
        Plugin.__init__(self)
        terminator = Terminator()
        for terminal in terminator.terminals:
            terminal.match_add(self.handler_name, self.match)

    def callback(self, url):
        """Callback to transform the enclosed URL"""
        raise NotImplementedError

    def unload(self):
        """Handle being removed"""
        if not self.handler_name:
            err('unload called without self.handler_name being set')
            return
        terminator = Terminator()
        for terminal in terminator.terminals:
            terminal.match_remove(self.handler_name)
```

**Usage: url_handlers.py**
```python
class LaunchpadBugURLHandler(plugin.URLHandler):
    """Handle LP: #12345 style URLs"""
    capabilities = ['url_handler']
    handler_name = 'launchpad_bug'
    match = r'\b(lp|LP):?\s?#?[0-9]+(,\s*#?[0-9]+)*\b'
    nameopen = "Open Launchpad bug"
    namecopy = "Copy bug URL"

    def callback(self, url):
        """Transform the URL"""
        for item in re.findall(r'[0-9]+', url):
            url = 'https://bugs.launchpad.net/bugs/%s' % item
            return(url)
```

#### MenuItem

**Code: plugin.py (lines 193-199)**
```python
class MenuItem(Plugin):
    """Base class for menu items"""
    capabilities = ['terminal_menu']

    def callback(self, menuitems, menu, terminal):
        """Callback to transform the enclosed URL"""
        raise NotImplementedError
```

**Usage: insert_term_name.py**
```python
class InsertTermName(plugin.MenuItem):
    capabilities = ['terminal_menu']

    def __init__(self):
        plugin.MenuItem.__init__(self)

    def callback(self, menuitems, menu, terminal):
        item = Gtk.MenuItem.new_with_label('Insert terminal name')
        item.connect('activate', lambda x: terminal.emit('insert-term-name'))
        menuitems.append(item)
```

---

## 3. Plugin Capabilities System

Plugins declare their capabilities, and Terminator selects plugins by capability.

### 3.1 Capability Strings

Common capabilities:
- `'url_handler'` - Handles regex patterns in terminal output
- `'terminal_menu'` - Adds items to terminal right-click context menu
- `'test'` - Custom capability (for testing)

### 3.2 Capability Query

Plugins with specific capabilities are retrieved via:

**Code: plugin.py (lines 121-129)**
```python
def get_plugins_by_capability(self, capability):
    """Return a list of plugins with a particular capability"""
    result = []
    dbg('searching %d plugins for %s' % (len(self.instances), capability))
    for plugin in self.instances:
        if capability in self.instances[plugin].capabilities:
            result.append(self.instances[plugin])
    return result
```

**Usage: terminal_popup_menu.py**
```python
plugins = registry.get_plugins_by_capability('terminal_menu')
for menuplugin in plugins:
    menuplugin.callback(menuitems, menu, terminal)
```

---

## 4. Plugin Lifecycle

### 4.1 Initialization Sequence

1. **Plugin Load Phase** - When plugins are first discovered:
   - `PluginRegistry.load_plugins()` scans directories
   - Finds `AVAILABLE` list in each module
   - Reads config to check if plugin is enabled

2. **Plugin Instantiation** - If enabled in config:
   - Plugin class is instantiated: `self.instances[item] = func()`
   - `__init__()` method is called
   - Plugin can connect to Terminator singleton

3. **Usage** - Plugins are used by name or by capability:
   - Terminal menu: queries `'terminal_menu'` capability
   - URL handlers: queries `'url_handler'` capability

### 4.2 Accessing Terminator State

Plugins can access the global Terminator singleton:

**Code: plugin.py (lines 174-176)**
```python
def __init__(self):
    """Class initialiser"""
    Plugin.__init__(self)
    terminator = Terminator()
    for terminal in terminator.terminals:
        terminal.match_add(self.handler_name, self.match)
```

The Terminator singleton (from terminator.py) provides:
- `terminator.windows` - List of all window objects
- `terminator.terminals` - List of all terminal widgets
- `terminator.config` - Configuration object

### 4.3 Unload/Cleanup

When plugins are disabled or reloaded:

**Code: plugin.py (lines 152-156)**
```python
def disable(self, plugin):
    """Disable a plugin"""
    dbg("Disabling %s" % plugin)
    self.instances[plugin].unload()
    del(self.instances[plugin])
```

Plugins should override `unload()` to:
- Disconnect signal handlers
- Clean up resources
- Remove any added features

**Example: logger.py**
```python
def stop_logger(self, _widget, terminal):
    vte_terminal = terminal.get_vte()
    # ... save remaining buffer ...
    fd = self.loggers[vte_terminal]["fd"]
    fd.close()
    vte_terminal.disconnect(self.loggers[vte_terminal]["handler_id"])
    del(self.loggers[vte_terminal])
```

---

## 5. Terminal Menu Plugin API

### 5.1 MenuItem Callback Signature

When Terminator builds the terminal context menu, it calls:

**Code: terminal_popup_menu.py**
```python
plugins = registry.get_plugins_by_capability('terminal_menu')
for menuplugin in plugins:
    menuplugin.callback(menuitems, menu, terminal)
```

The callback receives:
- `menuitems` - List to append GTK menu items to
- `menu` - The GTK Menu widget
- `terminal` - The Terminal widget object

### 5.2 Terminal Object Reference

The Terminal object provides:

```python
terminal.vte                    # The VTE widget
terminal.terminator             # Reference to Terminator singleton
terminal.emit('signal-name')    # Emit terminal signals
terminal.get_vte()              # Get VTE widget
terminal.get_toplevel()         # Get parent window
```

### 5.3 Example: Custom Commands Plugin

**Code: custom_commands.py (excerpt)**
```python
class CustomCommandsMenu(plugin.MenuItem):
    capabilities = ['terminal_menu']
    
    def callback(self, menuitems, menu, terminal):
        """Add custom menu items"""
        item = Gtk.MenuItem.new_with_mnemonic(_('_Custom Commands'))
        menuitems.append(item)
        
        submenu = Gtk.Menu()
        item.set_submenu(submenu)
        
        # Add command items
        for command in self.cmd_list.values():
            menuitem = Gtk.MenuItem(command['name'])
            terminals = terminal.terminator.get_target_terms(terminal)
            menuitem.connect("activate", self._execute,
                           {'terminals': terminals,
                            'command': command['command']})
            submenu.append(menuitem)
    
    def _execute(self, widget, data):
        command = data['command']
        if command[-1] != '\n':
            command = command + '\n'
        for terminal in data['terminals']:
            terminal.vte.feed_child(command.encode())
```

---

## 6. Factory Pattern for Type Checking

Terminator provides a `Factory` class for runtime type checking:

**Code: factory.py (lines 48-72)**
```python
class Factory(Borg):
    """Definition of a class that makes other classes"""
    types = {'Terminal': 'terminal',
             'VPaned': 'paned',
             'HPaned': 'paned',
             'Paned': 'paned',
             'Notebook': 'notebook',
             'Container': 'container',
             'Window': 'window'}

    def isinstance(self, product, classtype):
        """Check if a given product is a particular type of object"""
        if classtype in self.types_keys:
            try:
                type_key = 'terminatorlib.%s' % self.types[classtype]
                if type_key not in self.instance_types_keys:
                    self.instance_types[type_key] = __import__(type_key, None, None, [''])
                    self.instance_types_keys.append(type_key)
                module = self.instance_types[type_key]
            except ImportError:
                type_key = self.types[classtype]
                # ... fallback ...
            return isinstance(product, getattr(module, classtype))
        else:
            err('Factory::isinstance: unknown class type: %s' % classtype)
            return False
```

**Usage in plugins:**
```python
from terminatorlib.factory import Factory

factory = Factory()

# Check object types
if factory.isinstance(obj, 'Terminal'):
    # It's a Terminal widget
    pass
elif factory.isinstance(obj, 'Notebook'):
    # It's a Notebook widget
    pass
```

---

## 7. EditableLabel - Tab Title Integration

### 7.1 EditableLabel Signal

The `EditableLabel` class (used for tab titles) emits a signal when editing is done:

**Code: editablelabel.py (lines 37-39)**
```python
__gsignals__ = {
    'edit-done': (GObject.SignalFlags.RUN_LAST, None, ()),
}
```

### 7.2 set_text() Method

The `set_text()` method is the common interception point for tab title updates:

**Code: editablelabel.py (lines 60-64)**
```python
def set_text(self, text, force=False):
    """set the text of the label"""
    self._autotext = text
    if not self._custom or force:
        self._label.set_text(text)
```

**This is called by:**
- Direct terminal output changes: `tab_label.label.set_text()`
- Custom TabLabel updates: `TabLabel.set_label()` → `EditableLabel.set_text()`

### 7.3 Example: Tab Numbers Plugin Pattern

The tab_numbers plugin wraps `EditableLabel.set_text()` to:
1. Intercept ALL tab title updates
2. Add number prefix before setting text
3. Re-apply numbers after user edits (via edit-done signal)

---

## 8. TabLabel Widget - Tab Title Container

### 8.1 TabLabel Architecture

The `TabLabel` class (defined in `notebook.py` lines 576-686) is a composite widget that represents a tab's visual label in a Notebook. Understanding this structure is critical for plugins that manipulate tab titles.

**Code: notebook.py (lines 576-607)**
```python
class TabLabel(Gtk.HBox):
    """Class implementing a label widget for Notebook tabs"""
    notebook = None
    terminator = None
    config = None
    label = None      # This is the EditableLabel widget
    icon = None
    button = None     # Close button

    def __init__(self, title, notebook):
        """Class initialiser"""
        GObject.GObject.__init__(self)

        self.notebook = notebook
        self.terminator = Terminator()
        self.config = Config()

        # IMPORTANT: TabLabel contains an EditableLabel
        self.label = EditableLabel(title)
        self.update_angle()

        self.pack_start(self.label, True, True, 0)
        self.update_button()
        self.show_all()
```

**Key Architecture Points**:
- TabLabel is a GTK HBox container
- It **contains** an `EditableLabel` widget (stored in `self.label`)
- It also contains a close button (if enabled in config)
- TabLabel is what you get from `notebook.get_tab_label(page)`

### 8.2 TabLabel Methods

**Code: notebook.py (lines 608-625)**
```python
def set_label(self, text):
    """Update the text of our label"""
    self.label.set_text(text)

def get_label(self):
    return self.label.get_text()

def set_custom_label(self, text, force=False):
    """Set a permanent label as if the user had edited it"""
    self.label.set_text(text, force=force)
    self.label.set_custom()

def get_custom_label(self):
    """Return a custom label if we have one, otherwise None"""
    if self.label.is_custom():
        return(self.label.get_text())
    else:
        return(None)
```

**Important**: `TabLabel.set_label()` calls `EditableLabel.set_text()` - this is the call chain that plugins intercept.

### 8.3 Two-Level Access Pattern

When working with tab titles in plugins, you must understand the two-level access:

```python
# Get the TabLabel for a page
tab_label = notebook.get_tab_label(page)  # Returns TabLabel widget

# Access the EditableLabel inside
editable_label = tab_label.label           # Returns EditableLabel widget

# Access methods
text = editable_label.get_text()          # Get current text
editable_label.set_text("New Text")       # Set new text
```

**Usage in tab_numbers plugin:**
```python
def wrap_tab_labels(self, notebook):
    for i in range(num_pages):
        page = notebook.get_nth_page(i)
        tab_label = notebook.get_tab_label(page)     # Get TabLabel

        if tab_label and hasattr(tab_label, 'label'):
            editable_label = tab_label.label          # Get EditableLabel
            # Now wrap editable_label.set_text()
```

### 8.4 Tab Title Update Flow

Understanding how tab titles update is crucial for tab-related plugins:

**Normal Update Flow**:
```
Terminal title changes → Notebook.update_tab_label_text()
                      ↓
           TabLabel.set_label(text)
                      ↓
           EditableLabel.set_text(text)  ← Plugin wrapper intercepts here
                      ↓
           GTK Label widget updates
```

**Code: notebook.py (lines 433-441)**
```python
def update_tab_label_text(self, widget, text):
    """Update the text of a tab label"""
    notebook = self.find_tab_root(widget)
    label = self.get_tab_label(notebook)
    if not label:
        err('Notebook::update_tab_label_text: %s not found' % widget)
        return

    label.set_label(text)  # Calls TabLabel.set_label()
```

### 8.5 Why This Matters for Plugins

The TabLabel/EditableLabel distinction is important because:

1. **Single Interception Point**: By wrapping `EditableLabel.set_text()`, plugins catch ALL title updates regardless of source
2. **Automatic vs Manual Updates**: Both automatic terminal updates and manual user edits flow through this method
3. **Access Pattern**: You must access `tab_label.label` to get to the EditableLabel you need to wrap

**Example: tab_numbers plugin pattern**
```python
# Get to the EditableLabel (two-level access)
tab_label = notebook.get_tab_label(page)    # TabLabel widget
editable_label = tab_label.label             # EditableLabel widget

# Save original method
original_set_text = editable_label.set_text

# Create wrapper
def numbered_set_text(text, force=False):
    # Add number prefix
    clean_text = self.remove_number_prefix(text)
    numbered_text = "%d: %s" % (page_index + 1, clean_text)
    # Call original
    return original_set_text(numbered_text, force=force)

# Replace method
editable_label.set_text = numbered_set_text
```

---

## 9. GTK Notebook Signals

### 9.1 Built-in Notebook Signals

The GTK Notebook widget emits several signals that are useful for tab-related plugins:

**Code: GTK Notebook signals (from GTK documentation)**
```python
# These are standard GTK Notebook signals
'page-added'      # (notebook, child, page_num)
'page-removed'    # (notebook, child, page_num)
'page-reordered'  # (notebook, child, page_num)
'switch-page'     # (notebook, page, page_num)
```

### 9.2 Signal Usage in Plugins

**Example: tab_numbers plugin (tab_numbers.py lines 94-98)**
```python
def setup_notebook(self, notebook):
    """Set up a notebook for tab numbering"""
    # Connect to notebook signals for immediate response
    notebook.connect('page-added', self.on_tab_event)
    notebook.connect('page-removed', self.on_tab_event)
    notebook.connect('page-reordered', self.on_tab_event)
    notebook.connect('switch-page', self.on_tab_switch)
```

### 9.3 Signal Descriptions

| Signal | Parameters | When Emitted | Use Case |
|--------|-----------|--------------|----------|
| `page-added` | `(notebook, child, page_num)` | After a new tab is added | Initialize new tab features |
| `page-removed` | `(notebook, child, page_num)` | After a tab is removed | Clean up resources, renumber remaining tabs |
| `page-reordered` | `(notebook, child, page_num)` | After tabs are reordered | Update tab-dependent features (like numbers) |
| `switch-page` | `(notebook, page, page_num)` | When user switches to a different tab | Track active tab, update state |

### 9.4 Handling Structural Changes

When tabs are added, removed, or reordered, the GTK Notebook doesn't automatically update existing tab labels. Plugins must manually trigger updates:

**Example: tab_numbers plugin (tab_numbers.py lines 193-200)**
```python
def on_tab_event(self, notebook, *args):
    """Handle tab events (add, remove, reorder)"""
    # Wrap any new tab labels
    self.wrap_tab_labels(notebook)
    # Force renumbering of all existing tabs
    self.renumber_all_tabs(notebook)
    # Check for new windows
    self.check_for_new_windows()
```

**Why renumber all tabs?**
- When tab 2 is removed, tab 3 becomes the new tab 2
- GTK doesn't call `set_text()` on remaining tabs automatically
- Plugin must explicitly call `set_text()` on each tab to trigger wrapper

### 9.5 Tab Creation Signal Flow

When a new tab is created:

**Code: notebook.py (lines 314-344)**
```python
def newtab(self, debugtab=False, widget=None, cwd=None, metadata=None, profile=None):
    """Add a new tab, optionally supplying a child widget"""
    # ... create terminal widget ...

    # Create TabLabel
    label = TabLabel(self.window.get_title(), self)
    if metadata and 'label' in metadata:
        label.set_custom_label(metadata['label'])
    label.connect('close-clicked', self.closetab)

    # Insert page (this emits 'page-added' signal)
    self.insert_page(widget, None, tabpos)

    # Attach the TabLabel to the page
    self.set_tab_label(widget, label)
    # ... rest of setup ...
```

**Signal emission order**:
1. `insert_page()` is called
2. GTK emits `page-added` signal
3. Plugin's handler is called
4. Plugin can wrap the new TabLabel's EditableLabel

---

## 10. Signal Management

### 10.1 GObject Signals

Terminator widgets use GObject signals for event handling:

**Code: terminal.py (lines 38-79) - Terminal signals**
```python
__gsignals__ = {
    'pre-close-term': (GObject.SignalFlags.RUN_LAST, None, ()),
    'close-term': (GObject.SignalFlags.RUN_LAST, None, ()),
    'title-change': (GObject.SignalFlags.RUN_LAST, None,
        (GObject.TYPE_STRING,)),
    'insert-term-name': (GObject.SignalFlags.RUN_LAST, None, ()),
    # ... many more ...
}
```

### 10.2 Connecting to Signals

Plugins connect to signals in `__init__()`:

```python
def __init__(self):
    plugin.MenuItem.__init__(self)
    terminator = Terminator()
    for window in terminator.get_windows():
        window.connect('key-press-event', self.on_keypress)
```

### 10.3 Tracking Connected Signals

To prevent duplicate connections, use object tracking:

**Pattern from tab_numbers plugin:**
```python
_processed_notebooks = set()
_wrapped_editablelabels = set()

def process_notebook(notebook):
    obj_id = id(notebook)
    if obj_id in _processed_notebooks:
        return  # Already processed
    _processed_notebooks.add(obj_id)
    
    # Connect signals only once
    notebook.connect('page-added', self.on_page_added)
    notebook.connect('page-removed', self.on_page_removed)
```

---

## 11. Plugin Loading Triggers

Plugins are loaded at key points:

### 11.1 Terminal Creation

**Code: terminal.py**
```python
def load_plugins(self, force = False):
    registry = plugin.PluginRegistry()
    registry.load_plugins(force)
```

Called when:
- Terminal widget is first initialized
- With `force=True` in some reload scenarios

### 11.2 Terminal Menu Display

**Code: terminal_popup_menu.py**
```python
registry = plugin.PluginRegistry()
registry.load_plugins()
plugins = registry.get_plugins_by_capability('terminal_menu')
for menuplugin in plugins:
    menuplugin.callback(menuitems, menu, terminal)
```

### 11.3 URL Handler Registration

**Code: terminal_popup_menu.py**
```python
plugins = registry.get_plugins_by_capability('url_handler')
for urlplugin in plugins:
    if urlplugin.handler_name == pluginname:
        # Use this handler
```

---

## 12. Complete Plugin Example: Logger Plugin

**Code: plugins/logger.py**
```python
import os
import sys
from gi.repository import Gtk, Vte
import terminatorlib.plugin as plugin
from terminatorlib.translation import _

# REQUIRED: Define AVAILABLE list
AVAILABLE = ['Logger']

class Logger(plugin.MenuItem):
    """Add logging capability to terminals"""
    capabilities = ['terminal_menu']
    loggers = None
    dialog_action = Gtk.FileChooserAction.SAVE
    dialog_buttons = (_("_Cancel"), Gtk.ResponseType.CANCEL,
                      _("_Save"), Gtk.ResponseType.OK)
    vte_version = Vte.get_minor_version()

    def __init__(self):
        """Initialize plugin"""
        plugin.MenuItem.__init__(self)
        if not self.loggers:
            self.loggers = {}

    def callback(self, menuitems, menu, terminal):
        """Called to add menu items"""
        vte_terminal = terminal.get_vte()
        if vte_terminal not in self.loggers:
            item = Gtk.MenuItem.new_with_mnemonic(_('Start _Logger'))
            item.connect("activate", self.start_logger, terminal)
        else:
            item = Gtk.MenuItem.new_with_mnemonic(_('Stop _Logger'))
            item.connect("activate", self.stop_logger, terminal)
            item.set_tooltip_text("Saving at '" + 
                                self.loggers[vte_terminal]["filepath"] + "'")
        menuitems.append(item)
        
    def start_logger(self, _widget, terminal):
        """Start logging terminal output"""
        savedialog = Gtk.FileChooserDialog(
            title=_("Save Log File As"),
            action=self.dialog_action,
            buttons=self.dialog_buttons)
        savedialog.set_transient_for(_widget.get_toplevel())
        savedialog.set_do_overwrite_confirmation(True)
        savedialog.show_all()
        
        response = savedialog.run()
        if response == Gtk.ResponseType.OK:
            try:
                logfile = os.path.join(savedialog.get_current_folder(),
                                      savedialog.get_filename())
                fd = open(logfile, 'w+')
                vte_terminal = terminal.get_vte()
                (col, row) = vte_terminal.get_cursor_position()

                self.loggers[vte_terminal] = {
                    "filepath": logfile,
                    "handler_id": 0,
                    "fd": fd,
                    "col": col,
                    "row": row
                }
                # Connect signal to save on content changes
                handler_id = vte_terminal.connect('contents-changed', self.save)
                self.loggers[vte_terminal]["handler_id"] = handler_id
            except Exception as e:
                error = Gtk.MessageDialog(None, Gtk.DialogFlags.MODAL,
                                        Gtk.MessageType.ERROR,
                                        Gtk.ButtonsType.OK, str(e))
                error.set_transient_for(savedialog)
                error.run()
                error.destroy()
        savedialog.destroy()

    def stop_logger(self, _widget, terminal):
        """Stop logging"""
        vte_terminal = terminal.get_vte()
        fd = self.loggers[vte_terminal]["fd"]
        fd.close()
        vte_terminal.disconnect(self.loggers[vte_terminal]["handler_id"])
        del self.loggers[vte_terminal]

    def save(self, terminal):
        """Save buffer contents (called on contents-changed signal)"""
        # ... save implementation ...
        pass

    def unload(self):
        """Plugin being unloaded - cleanup"""
        # Close all open log files
        for vte_terminal in list(self.loggers.keys()):
            self.stop_logger(None, vte_terminal)
```

---

## 13. Debugging Plugins

### 13.1 Terminator Debug Mode

Run Terminator with debug output:
```bash
terminator -d
```

This shows all `dbg()` calls, including plugin loading:
```
TabNumbers: Wrapping EditableLabel for set_text
TabNumbers: Connecting page-added signal to notebook
```

### 13.2 Plugin Logging

Use Terminator's logging utilities:

**Code: util.py**
```python
from terminatorlib.util import dbg, err

dbg('Debug message')      # Debug output
err('Error message')      # Error output
```

---

## 14. Plugin Configuration

### 14.1 Reading Configuration

Plugins can read from Terminator's config:

```python
from terminatorlib.config import Config

config = Config()
sections = config.plugin_get_config(self.__class__.__name__)
```

### 14.2 Saving Configuration

```python
config = Config()
config.plugin_set(self.__class__.__name__, 'key_name', value)
config.save()
```

---

## 15. Key Architecture Patterns

### Pattern 1: Common Interception Point

Instead of hooking many different methods, hook ONE method that all operations go through:
- Tab numbering intercepts `EditableLabel.set_text()`
- All tab updates flow through this method

### Pattern 2: Object ID Tracking

Avoid duplicate processing with object ID sets:
```python
_processed_notebooks = set()

def process(notebook):
    obj_id = id(notebook)
    if obj_id in _processed_notebooks:
        return
    _processed_notebooks.add(obj_id)
```

### Pattern 3: Cached Patterns

Pre-compile regex patterns for efficiency:
```python
_number_prefix_pattern = re.compile(r'^\d+:\s*')

def remove_prefix(text):
    return _number_prefix_pattern.sub('', text)
```

### Pattern 4: Method Wrapping

Wrap methods to intercept calls while preserving original:
```python
original_set_text = EditableLabel.set_text

def wrapped_set_text(self, text):
    # Pre-processing
    text = modify_text(text)
    # Call original
    return original_set_text(self, text)

EditableLabel.set_text = wrapped_set_text
```

---

## Summary Table

| Aspect | Details |
|--------|---------|
| **Plugin Directory** | `~/.config/terminator/plugins/` or `terminatorlib/plugins/` |
| **Required Element** | `AVAILABLE` list with class names |
| **Base Class** | `terminatorlib.plugin.Plugin` (or subclass) |
| **Capabilities** | Strings defining plugin type ('url_handler', 'terminal_menu', etc.) |
| **Initialization** | `__init__()` called when plugin instantiated |
| **Cleanup** | `unload()` called when plugin disabled |
| **Terminator Access** | `terminator = Terminator()` singleton |
| **Menu Plugins** | Inherit `MenuItem`, implement `callback(menuitems, menu, terminal)` |
| **URL Plugins** | Inherit `URLHandler`, define `handler_name` and `match` regex |
| **Signals** | Connect via `widget.connect(signal, handler_method)` |
| **Tracking** | Use object IDs to prevent duplicate processing |
| **Debugging** | Use `dbg()`, `err()` from `terminatorlib.util` |

