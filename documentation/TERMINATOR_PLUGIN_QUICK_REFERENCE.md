# Terminator Plugin Quick Reference

## File Structure

```
~/.config/terminator/plugins/my_plugin.py
```

## Minimal Plugin Template

```python
import terminatorlib.plugin as plugin
from terminatorlib.util import dbg, err

# REQUIRED
AVAILABLE = ['MyPlugin']

class MyPlugin(plugin.Plugin):
    capabilities = ['custom']  # Define what this plugin does
    
    def __init__(self):
        """Called when plugin is instantiated"""
        plugin.Plugin.__init__(self)
        dbg('MyPlugin initialized')
    
    def unload(self):
        """Called when plugin is being disabled"""
        dbg('MyPlugin unloading')
```

## Common Plugin Types

### 1. Terminal Menu Plugin (Right-Click Context Menu)

```python
from gi.repository import Gtk
import terminatorlib.plugin as plugin

AVAILABLE = ['MyMenuPlugin']

class MyMenuPlugin(plugin.MenuItem):
    capabilities = ['terminal_menu']
    
    def callback(self, menuitems, menu, terminal):
        """
        Args:
            menuitems: List to append menu items to
            menu: The GTK Menu widget
            terminal: The Terminal widget being right-clicked
        """
        item = Gtk.MenuItem.new_with_label('My Action')
        item.connect('activate', self.on_activate, terminal)
        menuitems.append(item)
    
    def on_activate(self, widget, terminal):
        """Handle menu item click"""
        terminal.vte.feed_child(b'echo "Hello!"\n')
```

### 2. URL Handler Plugin

```python
import re
import terminatorlib.plugin as plugin

AVAILABLE = ['MyURLHandler']

class MyURLHandler(plugin.URLHandler):
    capabilities = ['url_handler']
    handler_name = 'my_handler'
    match = r'\b(myscheme):[^\s]+\b'
    nameopen = "Open with my handler"
    namecopy = "Copy my URL"
    
    def callback(self, url):
        """Transform the matched URL"""
        return 'https://example.com/' + url
```

### 3. Basic Plugin with Terminal Access

```python
import terminatorlib.plugin as plugin
from terminatorlib.terminator import Terminator

AVAILABLE = ['MyPlugin']

class MyPlugin(plugin.Plugin):
    capabilities = ['custom']
    
    def __init__(self):
        plugin.Plugin.__init__(self)
        
        # Access all terminals
        terminator = Terminator()
        for terminal in terminator.terminals:
            dbg(f'Found terminal: {terminal}')
        
        # Access all windows
        for window in terminator.windows:
            dbg(f'Found window: {window}')
```

## Key Objects and Methods

### Terminator Singleton

```python
from terminatorlib.terminator import Terminator

terminator = Terminator()

# Available attributes
terminator.windows              # List of window objects
terminator.terminals            # List of terminal objects
terminator.config              # Config object
terminator.get_windows()        # Get all windows
```

### Terminal Widget

```python
terminal.vte                    # The VTE terminal widget
terminal.terminator             # Reference back to Terminator
terminal.emit('signal-name')    # Emit signals
terminal.get_vte()              # Get VTE widget
terminal.get_toplevel()         # Get parent window
terminal.feed_child(b'command\n')  # Send input to terminal
```

### GTK Menu Items

```python
from gi.repository import Gtk

# Create simple menu item
item = Gtk.MenuItem.new_with_label('Label')

# Create menu item with mnemonic (Alt+key)
item = Gtk.MenuItem.new_with_mnemonic('_Label')  # Alt+L

# Create submenu
submenu = Gtk.Menu()
item.set_submenu(submenu)

# Connect to click event
item.connect('activate', handler_function, user_data)

# Append to list
menuitems.append(item)
```

## Configuration

### Reading Config

```python
from terminatorlib.config import Config

config = Config()
sections = config.plugin_get_config(self.__class__.__name__)

if sections and 'setting_name' in sections:
    value = sections['setting_name']
```

### Writing Config

```python
from terminatorlib.config import Config

config = Config()
config.plugin_set(self.__class__.__name__, 'key_name', value)
config.save()
```

## Signal Connection

### Connect to Widget Signal

```python
# In __init__()
widget.connect('signal-name', self.handler_method, optional_data)

# Handler signature
def handler_method(self, widget, optional_data):
    pass
```

### Prevent Duplicate Connections

```python
_processed_widgets = set()

def process_widget(widget):
    obj_id = id(widget)
    if obj_id in _processed_widgets:
        return  # Already processed
    _processed_widgets.add(obj_id)

    # Now safe to connect signals
    widget.connect('signal', self.handler)
```

## GTK Notebook Signals

### Common Notebook Signals

For plugins that work with tabs:

```python
from terminatorlib.factory import Factory

factory = Factory()

# Find notebook widgets
for window in terminator.windows:
    notebooks = find_notebooks_in_window(window)
    for notebook in notebooks:
        # Connect to tab-related signals
        notebook.connect('page-added', self.on_tab_added)
        notebook.connect('page-removed', self.on_tab_removed)
        notebook.connect('page-reordered', self.on_tab_reordered)
        notebook.connect('switch-page', self.on_tab_switched)
```

### Signal Handlers

```python
def on_tab_added(self, notebook, child, page_num):
    """Called when a new tab is added"""
    # child is the page widget (Terminal or container)
    # page_num is the index where it was inserted
    pass

def on_tab_removed(self, notebook, child, page_num):
    """Called when a tab is removed"""
    # Clean up resources for this tab
    pass

def on_tab_reordered(self, notebook, child, page_num):
    """Called when tabs are reordered (drag & drop)"""
    # Update any tab-index-dependent features
    pass

def on_tab_switched(self, notebook, page, page_num):
    """Called when user switches to a different tab"""
    # page is the GTK page widget
    # page_num is the new active tab index
    pass
```

## TabLabel Widget

### TabLabel Structure

Understanding the tab label widget hierarchy:

```python
# TabLabel is a composite widget containing an EditableLabel
tab_label = notebook.get_tab_label(page)  # Returns TabLabel (GTK HBox)
editable_label = tab_label.label           # Returns EditableLabel widget

# Access the actual text
text = editable_label.get_text()
editable_label.set_text("New Title")
```

### TabLabel Methods

```python
from terminatorlib.factory import Factory

factory = Factory()

# Get tab label for a page
for i in range(notebook.get_n_pages()):
    page = notebook.get_nth_page(i)
    tab_label = notebook.get_tab_label(page)

    # TabLabel methods
    tab_label.set_label("Title")           # Set label text
    text = tab_label.get_label()           # Get label text
    tab_label.set_custom_label("Custom")   # Set custom label
    custom = tab_label.get_custom_label()  # Get custom label (or None)

    # EditableLabel methods (via tab_label.label)
    editable = tab_label.label
    editable.set_text("Text", force=True)  # Force update even if custom
    editable.edit()                        # Start editing mode
    is_custom = editable.is_custom()       # Check if user customized
```

## Debugging

### Logging Output

```python
from terminatorlib.util import dbg, err

dbg('Debug message')
err('Error message')
```

### Run Terminator with Debug

```bash
terminator -d
```

Look for your plugin's messages in the output.

## Testing Plugin Locally

```bash
# Install to user plugins directory
mkdir -p ~/.config/terminator/plugins
cp my_plugin.py ~/.config/terminator/plugins/

# Restart Terminator
# Enable plugin in Preferences > Plugins

# Or run with debug
terminator -d
```

## Common Patterns

### Wrapping a Method

```python
# Save original method
original_method = SomeClass.some_method

# Create wrapper
def wrapped_method(self, *args, **kwargs):
    # Pre-processing
    print("Before")
    # Call original
    result = original_method(self, *args, **kwargs)
    # Post-processing
    print("After")
    return result

# Replace with wrapper
SomeClass.some_method = wrapped_method
```

### Cached Regex Pattern

```python
import re

_my_pattern = re.compile(r'pattern_here')

def use_pattern(text):
    return _my_pattern.sub('replacement', text)
```

### Factory Type Checking

```python
from terminatorlib.factory import Factory

factory = Factory()

if factory.isinstance(obj, 'Terminal'):
    # It's a Terminal
    pass
elif factory.isinstance(obj, 'Notebook'):
    # It's a Notebook
    pass
```

## Useful Files

- **terminatorlib/plugin.py** - Plugin base classes
- **terminatorlib/terminator.py** - Terminator singleton
- **terminatorlib/factory.py** - Type checking
- **terminatorlib/terminal.py** - Terminal widget
- **terminatorlib/editablelabel.py** - Tab label widget
- **~/.config/terminator/config** - Terminator config file

## Common Mistakes

1. **Missing AVAILABLE list** - Plugin won't load
   ```python
   AVAILABLE = ['MyPlugin']  # REQUIRED
   ```

2. **Forgetting to call parent __init__** - May cause issues
   ```python
   def __init__(self):
       plugin.MenuItem.__init__(self)  # Don't forget this
   ```

3. **Not handling unload()** - Resource leaks
   ```python
   def unload(self):
       # Disconnect signals
       widget.disconnect(handler_id)
   ```

4. **Duplicate signal connections** - Causes multiple handlers to fire
   ```python
   # Track processed objects
   if id(obj) not in _processed:
       _processed.add(id(obj))
       obj.connect('signal', handler)
   ```

5. **Assuming plugins initialize early** - Other plugins may not be ready
   ```python
   # Use GObject.idle_add() for delayed initialization
   from gi.repository import GObject
   GObject.idle_add(self.delayed_init)
   ```

## Testing Your Plugin

Create a test script:

```python
#!/usr/bin/env python3
import sys
sys.path.insert(0, '/path/to/terminatorlib')

from my_plugin import MyPlugin

plugin = MyPlugin()
print(f"Plugin loaded: {plugin}")
print(f"Capabilities: {plugin.capabilities}")
```

