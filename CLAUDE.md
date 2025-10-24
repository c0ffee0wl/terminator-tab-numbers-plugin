# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a plugin for Terminator (Linux terminal emulator) that adds tab numbering to tab titles. The plugin displays "1: ", "2: ", etc. before tab titles and updates in real-time when tabs are added, removed, or reordered.

**Key Innovation**: Uses a method wrapping pattern to intercept `EditableLabel.set_text()` - the single point where ALL tab title updates flow through. This catches automatic updates (terminal prompt changes), manual updates (user edits), and programmatic updates with minimal code complexity.

## Architecture

### Core Components

**Single-file plugin**: `tab_numbers.py` contains the entire plugin implementation following Terminator's plugin API.

**Key Architecture Patterns**:

1. **Method Wrapping** - Wraps `EditableLabel.set_text()` to intercept ALL tab title updates at one common point
2. **Delayed Initialization** - Uses `GObject.idle_add()` to defer setup until Terminator is fully initialized
3. **Event-Driven Updates** - Connects to GTK notebook signals (`page-added`, `page-removed`, `page-reordered`) for structural changes
4. **Object ID Tracking** - Prevents duplicate signal connections and method wrapping without memory leaks

### How It Works

```
Terminal title change → EditableLabel.set_text() → Wrapped method intercepts
                                                 ↓
                                    Strip old number, add correct number
                                                 ↓
                                    Original set_text() called with numbered text
```

The wrapper automatically handles:
- Automatic terminal prompt updates
- User manual edits (via `edit-done` signal)
- Programmatic title changes
- Tab reordering and deletion

## Tab Lifecycle and Architecture

### TabLabel Widget Structure

Understanding the tab label widget hierarchy is crucial for this plugin:

**Widget Hierarchy**:
```
Notebook
  └── Page (Terminal widget)
       └── TabLabel (GTK HBox) ← notebook.get_tab_label(page)
             ├── EditableLabel ← tab_label.label (the actual text label)
             └── Close Button (if enabled)
```

**Key Architectural Points**:
- `TabLabel` is a composite widget defined in `notebook.py` (lines 576-686)
- `TabLabel` **contains** an `EditableLabel` widget stored in `tab_label.label`
- Plugin wraps `EditableLabel.set_text()` - the innermost level
- **Two-level access required**: `tab_label.label.set_text()`

### Tab Creation Flow

When a new tab is created in Terminator:

1. **Notebook.newtab()** is called (`notebook.py` line 261)
2. **TabLabel created** with initial title (`notebook.py` line 314):
   ```python
   label = TabLabel(self.window.get_title(), self)
   ```
3. **TabLabel initializes EditableLabel** (`notebook.py` line 600):
   ```python
   self.label = EditableLabel(title)  # Inside TabLabel.__init__
   ```
4. **Page inserted into notebook** (`notebook.py` line 324):
   ```python
   self.insert_page(widget, None, tabpos)
   # This emits GTK 'page-added' signal
   ```
5. **TabLabel attached to page** (`notebook.py` line 338):
   ```python
   self.set_tab_label(widget, label)
   ```
6. **Plugin's signal handler called** (tab_numbers.py line 95):
   ```python
   # Connected earlier: notebook.connect('page-added', self.on_tab_event)
   # Handler wraps the new tab's EditableLabel
   ```

### Tab Title Update Flow

Understanding how tab titles update is key to the plugin's design:

**Normal Update Flow**:
```
Terminal title changes (e.g., user runs command that changes PS1)
         ↓
Notebook.update_tab_label_text() called (notebook.py line 433)
         ↓
TabLabel.set_label(text) called (notebook.py line 441)
         ↓
EditableLabel.set_text(text) called (notebook.py line 610)
         ↓
Plugin's wrapper intercepts here ← SINGLE INTERCEPTION POINT
         ↓
Plugin adds number prefix
         ↓
Original set_text() called with numbered text
         ↓
GTK Label widget displays numbered title
```

**Why This Matters**:
- **Single interception point**: ALL title updates flow through `EditableLabel.set_text()`
- **Automatic updates**: Terminal prompt changes trigger this flow automatically
- **Manual updates**: User edits (double-click tab) also flow through this same path
- **Wrapper catches everything**: No need for multiple hooks or signal handlers

### Signal Flow for Structural Changes

When tabs are added, removed, or reordered:

**Signal Emission** (GTK Notebook signals):
```
User action (drag tab, close tab, new tab)
         ↓
GTK Notebook emits signal:
  - 'page-added' (new tab)
  - 'page-removed' (closed tab)
  - 'page-reordered' (tab dragged)
         ↓
Plugin's on_tab_event() handler called (tab_numbers.py line 193)
         ↓
wrap_tab_labels() - Wraps any new tabs (tab_numbers.py line 196)
         ↓
renumber_all_tabs() - Forces update of all tabs (tab_numbers.py line 198)
```

**Why renumber ALL tabs?**
- When tab 2 is closed, tab 3 becomes the new tab 2
- GTK doesn't automatically call `set_text()` on remaining tabs
- Plugin must explicitly call `set_text()` to trigger wrapper
- Wrapper recalculates index and applies correct number

## Development Commands

### Testing the Plugin

```bash
# Install to Terminator plugins directory
mkdir -p ~/.config/terminator/plugins
cp tab_numbers.py ~/.config/terminator/plugins/

# Run with debug output to see plugin messages
terminator -d

# Look for "TabNumbers:" messages in the output
terminator -d 2>&1 | grep TabNumbers
```

### Manual Test Scenarios

```bash
# Test tab creation: Ctrl+Shift+T repeatedly
# Test tab reordering: Drag tabs to new positions
# Test tab deletion: Close tabs, verify renumbering
# Test manual rename: Double-click tab, edit title, press Enter
# Test automatic updates: Run commands that change terminal title
```

### Debugging

```bash
# Enable debug logging
terminator -d

# Expected output patterns:
# TabNumbers: Wrapped set_text for EditableLabel
# TabNumbers: Connected to notebook signals
# TabNumbers: Renumbering N tabs
```

## Important Implementation Details

### Method Wrapping Pattern

The plugin wraps the `EditableLabel.set_text()` method on each tab. Note the **two-level access** to get to the EditableLabel:

```python
# Get TabLabel from notebook (this is the composite widget)
tab_label = notebook.get_tab_label(page)

# Get EditableLabel from TabLabel (this is the actual text label)
editable_label = tab_label.label  # TWO-LEVEL ACCESS

# Save original method for later use
original_set_text = editable_label.set_text
editable_label._tabnumbers_original_set_text = original_set_text

# Create wrapper with closure (captures notebook, tab_label)
def numbered_set_text(text, force=False):
    # Find tab index, strip old number, add new number
    clean_text = self.remove_number_prefix(text)
    numbered_text = "%d: %s" % (page_index + 1, clean_text)
    return original_set_text(numbered_text, force=force)

# Replace method on the EditableLabel
editable_label.set_text = numbered_set_text
```

**Why this works**:
- All tab title updates eventually call `EditableLabel.set_text()`, making it the perfect single interception point
- `tab_label.label` gives us the EditableLabel inside the TabLabel composite widget
- The wrapper intercepts ALL calls: automatic terminal updates, manual edits, and programmatic changes

### Signal Management

- **Tracked notebooks** (`_processed_notebooks`): Prevents duplicate signal connections
- **Wrapped EditableLabels** (`_wrapped_editablelabels`): Prevents double-wrapping
- **Object IDs**: Used for tracking to avoid weak reference overhead

### Forced Renumbering

When tabs are removed or reordered, GTK doesn't automatically call `set_text()` on remaining tabs. The plugin manually triggers updates via `renumber_all_tabs()` which calls `set_text()` for each tab. The wrapper intercepts these calls and adds correct numbers.

## Key Architectural Decisions

**Why wrapper instead of signals only?**
- Signal-only approach misses automatic terminal title updates
- Wrapper catches ALL text updates at single chokepoint
- Cleaner architecture with one interception point

**Why renumber ALL tabs on structural changes?**
- Simpler and more reliable than selective updates
- Guarantees correctness
- Performance difference negligible (~1-2ms for 20 tabs)

**Why delayed initialization?**
- Plugin `__init__()` runs before GTK main loop
- Windows/terminals don't exist yet
- `GObject.idle_add()` schedules after initialization completes

## Detailed Documentation

For comprehensive information about Terminator's plugin system, architecture, and implementation details, see the `documentation/` directory:

- **[TERMINATOR_PLUGIN_ARCHITECTURE.md](documentation/TERMINATOR_PLUGIN_ARCHITECTURE.md)** - Complete guide to Terminator's plugin system, base classes, signals, lifecycle, and advanced patterns
- **[PLUGIN_QUICK_REFERENCE.md](documentation/PLUGIN_QUICK_REFERENCE.md)** - Quick reference with code templates, common patterns, and plugin types
- **[TERMINATOR_SOURCE_FILES.md](documentation/TERMINATOR_SOURCE_FILES.md)** - Mapping of key Terminator source files and where to find specific functionality

These documents contain:
- Plugin loading mechanism and discovery
- Base classes (Plugin, URLHandler, MenuItem)
- Complete signal reference
- Widget hierarchy and navigation
- Tab lifecycle flows
- Testing and debugging techniques
- Example plugins from Terminator source

## Compatibility

- Requires Terminator 1.90+
- Python 3.6+
- Depends on GObject introspection (gi.repository)
- Uses terminatorlib plugin API

## Performance

**Optimization techniques**:
- Cached regex pattern for removing number prefixes
- Cached Factory instance for type checking
- Object ID tracking (faster than weak references)
- Single interception point minimizes overhead

**Measured costs**:
- Initialization: ~5ms for typical setup
- Per-tab structural event: ~1-2ms (for 5-20 tabs)
- Per-text update: ~0.1ms (happens frequently)
