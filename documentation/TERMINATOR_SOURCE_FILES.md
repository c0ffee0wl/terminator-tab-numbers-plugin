# Terminator Source Files Reference

This document maps where key plugin system components are located in the official Terminator repository.

## Repository Information

- **Official Repository**: https://github.com/gnome-terminator/terminator
- **Clone Command**: `git clone https://github.com/gnome-terminator/terminator.git`
- **Key Directory**: `terminatorlib/`

## Plugin System Core Files

### terminatorlib/plugin.py
**Lines: 335 (total)**

Core plugin infrastructure:

- **Plugin class** (lines 33-43)
  - Base class for all plugins
  - Defines `capabilities` and `unload()` method

- **PluginRegistry class** (lines 45-157)
  - Singleton for managing plugins
  - `load_plugins()` - Discovers and loads plugins
  - `get_plugins_by_capability()` - Retrieves plugins by capability
  - `enable()`, `disable()` - Enable/disable plugins at runtime

- **URLHandler class** (lines 163-189)
  - Base class for URL pattern handlers
  - Auto-registers with all terminals in `__init__`
  - Implements `callback()` for URL transformation
  - Unregisters from terminals in `unload()`

- **MenuItem class** (lines 193-199)
  - Base class for terminal menu items
  - Implements `callback(menuitems, menu, terminal)` for building menus

- **KeyBindUtil class** (lines 216-335)
  - Utility for handling keybindings in plugins
  - Maps key combinations to actions
  - Integrates with Terminator's keybinding system

**File Path**: `/tmp/terminator/terminatorlib/plugin.py`

### terminatorlib/terminator.py
**Lines: ~500+**

Core Terminator application class (Borg singleton pattern):

- **Terminator class** (lines 42-100+)
  - Singleton providing global access to application state
  - `windows` - List of all window objects
  - `terminals` - List of all terminal objects
  - `config` - Configuration object
  - `get_windows()` - Get all windows
  - `register_terminal()` - Register new terminal
  - `deregister_terminal()` - Unregister terminal

**File Path**: `/tmp/terminator/terminatorlib/terminator.py`

### terminatorlib/terminal.py
**Lines: ~1200+**

Terminal widget and plugin integration:

- **Terminal class** (lines 35-100+)
  - GTK VTE widget wrapper
  - `__gsignals__` - Defines available signals (lines 38-79)
    - Terminal signals: 'title-change', 'close-term', 'insert-term-name', etc.
  - `load_plugins(force=False)` - Loads plugins
  - `vte` - The VTE terminal widget
  - `feed_child(command)` - Send input to terminal
  - `match_add()`, `match_remove()` - Add/remove regex patterns for URL handlers

**File Path**: `/tmp/terminator/terminatorlib/terminal.py`

### terminatorlib/terminal_popup_menu.py
**Lines: ~200+**

Right-click context menu handling:

- Calls `get_plugins_by_capability('terminal_menu')`
- Iterates through plugins and calls their `callback(menuitems, menu, terminal)`
- URL handler integration for custom regex matches

**File Path**: `/tmp/terminator/terminatorlib/terminal_popup_menu.py`

### terminatorlib/editablelabel.py
**Lines: ~150**

Editable tab label widget:

- **EditableLabel class**
  - `set_text(text, force=False)` (lines 60-64) - Common update point for tab titles
  - `__gsignals__` (lines 37-39) - Defines 'edit-done' signal
  - `editing()` - Check if currently in edit mode
  - `_entry_to_label()` - Called when editing finishes, emits 'edit-done'

**File Path**: `/tmp/terminator/terminatorlib/editablelabel.py`

### terminatorlib/factory.py
**Lines: ~120**

Factory pattern for type checking:

- **Factory class**
  - `isinstance(product, classtype)` (lines 48-72) - Runtime type checking
  - Supports: 'Terminal', 'Window', 'Notebook', 'VPaned', 'HPaned', 'Container', 'Paned'
  - Lazy-loads module types for efficiency

**File Path**: `/tmp/terminator/terminatorlib/factory.py`

### terminatorlib/config.py
**Lines: ~500+**

Configuration management:

- **Config class** (Borg singleton)
  - `plugin_get_config(plugin_name)` - Get plugin-specific config
  - `plugin_set(plugin_name, key, value)` - Set plugin config
  - `save()` - Persist configuration

**File Path**: `/tmp/terminator/terminatorlib/config.py`

### terminatorlib/util.py
**Lines: ~200+**

Utility functions:

- `dbg(text)` - Debug logging (shown with `terminator -d`)
- `err(text)` - Error logging
- `get_config_dir()` - Get user config directory (~/.config/terminator)

**File Path**: `/tmp/terminator/terminatorlib/util.py`

### terminatorlib/borg.py
**Lines: ~50+**

Borg pattern singleton implementation:

- Used by PluginRegistry, Terminator, Config, Factory
- Ensures single shared state across all instances

**File Path**: `/tmp/terminator/terminatorlib/borg.py`

## Example Plugins

All located in `terminatorlib/plugins/`:

### testplugin.py
Minimal plugin example:
- Demonstrates `AVAILABLE` list
- Basic `Plugin` subclass
- Custom capability

**File Path**: `/tmp/terminator/terminatorlib/plugins/testplugin.py`
**Lines**: ~11

### insert_term_name.py
Terminal menu plugin:
- Inherits `MenuItem`
- Implements `callback(menuitems, menu, terminal)`
- Adds single menu item

**File Path**: `/tmp/terminator/terminatorlib/plugins/insert_term_name.py`
**Lines**: ~18

### url_handlers.py
URL handler plugins:
- Three examples of `URLHandler` subclass
- Shows `handler_name`, `match` regex, `nameopen`, `namecopy`
- Implements `callback(url)` for URL transformation

**File Path**: `/tmp/terminator/terminatorlib/plugins/url_handlers.py`
**Lines**: ~59

### logger.py
Complete MenuItem plugin:
- Signal connection (`contents-changed`)
- Resource management (file handles)
- Menu item state management
- Proper `unload()` cleanup

**File Path**: `/tmp/terminator/terminatorlib/plugins/logger.py`
**Lines**: ~114

### custom_commands.py
Advanced MenuItem plugin:
- Configuration management
- Keybinding integration
- Complex menu building
- Settings dialog
- Signal management for window tracking

**File Path**: `/tmp/terminator/terminatorlib/plugins/custom_commands.py`
**Lines**: ~656

### save_last_session_layout.py
Session management plugin:
- Demonstrates plugin that runs at specific Terminator lifecycle point
- Configuration persistence

**File Path**: `/tmp/terminator/terminatorlib/plugins/save_last_session_layout.py`

## Key Code Patterns in Source

### 1. Plugin Loading (plugin.py, lines 82-119)
```python
for plugindir in self.path:
    # ... scan directory ...
    for plugin in files:
        # ... import module ...
        for item in getattr(module, 'AVAILABLE'):
            # ... register and instantiate ...
```

### 2. Capability Query (plugin.py, lines 121-129)
```python
def get_plugins_by_capability(self, capability):
    for plugin in self.instances:
        if capability in self.instances[plugin].capabilities:
            result.append(self.instances[plugin])
```

### 3. Terminal Menu Building (terminal_popup_menu.py)
```python
plugins = registry.get_plugins_by_capability('terminal_menu')
for menuplugin in plugins:
    menuplugin.callback(menuitems, menu, terminal)
```

### 4. URLHandler Initialization (plugin.py, lines 174-176)
```python
def __init__(self):
    Plugin.__init__(self)
    terminator = Terminator()
    for terminal in terminator.terminals:
        terminal.match_add(self.handler_name, self.match)
```

### 5. Terminator Access (terminator.py, lines 71-100)
```python
class Terminator(Borg):
    windows = None
    terminals = None
    config = None
    
    def __init__(self):
        Borg.__init__(self, self.__class__.__name__)
        self.prepare_attributes()
```

## GObject and GTK References

### GObject Signals (used throughout)
- `GObject.SignalFlags.RUN_LAST` - Signal execution mode
- `GObject.TYPE_STRING`, `GObject.TYPE_INT`, etc. - Signal parameter types
- `widget.emit('signal-name')` - Emit custom signal
- `widget.connect('signal', handler, data)` - Connect to signal

### GTK Menu Items (terminal_popup_menu.py, custom_commands.py)
```python
from gi.repository import Gtk

Gtk.MenuItem.new_with_label('text')
Gtk.MenuItem.new_with_mnemonic('_text')
Gtk.SeparatorMenuItem()
Gtk.Menu()
item.set_submenu(submenu)
item.connect('activate', handler)
```

## Notebook Widget (for tab handling)

### terminatorlib/notebook.py
**Lines: ~686**

Located in `terminatorlib/notebook.py`:
- GTK Notebook widget wrapper
- Contains multiple tabs (pages)
- Each page contains a Terminal widget

**Notebook class** (lines 19-575)
- Manages tabbed interface
- Creates and manages TabLabel widgets
- Methods:
  - `newtab()` (line 261) - Creates new tab with TabLabel
  - `update_tab_label_text()` (line 433) - Updates tab title text
  - `closetab()` (line 357) - Closes a tab
  - `split_axis()` (line 162) - Splits terminal in a tab

**GTK Notebook Signals** (standard GTK signals):
- `page-added` - Emitted when a new tab is added
- `page-removed` - Emitted when a tab is removed
- `page-reordered` - Emitted when tabs are reordered by dragging
- `switch-page` - Emitted when user switches between tabs

**TabLabel class** (lines 576-686)
- Composite widget for tab labels
- Contains an EditableLabel widget
- Structure:
  ```
  TabLabel (GTK HBox)
    ├── EditableLabel (self.label) - The actual text label
    └── Close Button (if enabled)
  ```
- Methods:
  - `set_label(text)` (line 608) - Calls `self.label.set_text(text)`
  - `get_label()` (line 612) - Returns label text
  - `set_custom_label(text, force=False)` (line 615) - Sets custom label
  - `get_custom_label()` (line 620) - Gets custom label if set
  - `edit()` (line 627) - Starts label editing mode
  - `update_button()` (line 630) - Updates close button state
  - `update_angle()` (line 662) - Updates label angle based on tab position

**Important for Plugins**:
- `notebook.get_tab_label(page)` returns a TabLabel widget (not EditableLabel)
- TabLabel contains EditableLabel at `tab_label.label`
- Two-level access required: `notebook.get_tab_label(page).label.set_text()`
- TabLabel.set_label() → EditableLabel.set_text() call chain

**File Path**: `/tmp/terminator/terminatorlib/notebook.py`

## Related Imports

Common imports in plugins:
```python
import terminatorlib.plugin as plugin
from terminatorlib.terminator import Terminator
from terminatorlib.factory import Factory
from terminatorlib.config import Config
from terminatorlib.util import dbg, err
from gi.repository import Gtk, GObject
```

## Plugin Directory Locations

Built-in plugins:
```
/path/to/terminatorlib/plugins/
```

User plugins:
```
~/.config/terminator/plugins/
```

Configuration:
```
~/.config/terminator/config
```

## Entry Points to Plugin System

1. **Terminal Creation** (`terminal.py`)
   - Calls `load_plugins()`

2. **Terminal Menu Display** (`terminal_popup_menu.py`)
   - Queries plugins by capability
   - Builds menu from plugin callbacks

3. **URL Pattern Matching** (`terminal.py`)
   - URLHandler plugins register patterns
   - Called when user right-clicks matched text

4. **Preferences Dialog** (`prefseditor.py`)
   - Lists available plugins
   - Manages enable/disable state

## Testing and Debugging

Run with debug output:
```bash
terminator -d
```

Plugin loading messages appear in output, e.g.:
```
TabNumbers: Wrapping EditableLabel for set_text
TabNumbers: Connecting page-added signal to notebook
```

