# Terminator Tab Numbers Plugin

A Terminator plugin that displays tab numbers in front of tab titles, making it easy to navigate between tabs using keyboard shortcuts or visual identification.

![Plugin Demo](https://img.shields.io/badge/status-stable-green) ![Python](https://img.shields.io/badge/python-3.6+-blue) ![License](https://img.shields.io/badge/license-GPL--3.0-blue)

## Features

- 🔢 **Automatic tab numbering**: Displays "1: ", "2: ", etc. before tab titles
- 🎯 **Works with all title types**: Both automatic (system-generated) and custom (user-set) titles
- ⚡ **Real-time updates**: Numbers update immediately when tabs are added, removed, or reordered


## Stylized screenshots

### Before
```
Terminal 1    user@host: ~/projects    My Custom Tab
```

### After
```
1: Terminal 1    2: user@host: ~/projects    3: My Custom Tab
```

## Installation

### Method 1: Manual Installation

1. **Locate your Terminator plugins directory**:
   ```bash
   mkdir -p ~/.config/terminator/plugins
   cd ~/.config/terminator/plugins
   ```

2. **Download the plugin**:
   ```bash
   wget https://raw.githubusercontent.com/c0ffee0wl/terminator-tab-numbers-plugin/main/tab_numbers.py
   ```
   
   Or copy the content of `tab_numbers.py` to `~/.config/terminator/plugins/tab_numbers.py`

3. **Enable the plugin**:
   - Right-click in Terminator → Preferences → Plugins
   - Check "TabNumbers" in the plugin list
   - Click "Close"

### Method 2: Git Clone

```bash
git clone https://github.com/c0ffee0wl/terminator-tab-numbers-plugin.git
cd terminator-tab-numbers-plugin
cp tab_numbers.py ~/.config/terminator/plugins/tab_numbers.py
```

## Usage

Once installed and enabled, the plugin works automatically:

- **New tabs**: Numbers appear immediately when creating new tabs
- **Tab reordering**: Numbers update when you drag tabs to reorder them
- **Custom titles**: Double-click a tab to edit its title - the number prefix is preserved
- **Multiple windows**: Each Terminator window has independent tab numbering

### Keyboard Navigation (Default Terminator shortcuts)

With numbered tabs, you can easily use Terminator's built-in shortcuts:
- `Ctrl+PageUp` / `Ctrl+PageDown` - Navigate between tabs
- `Ctrl+Shift+T` - New tab
- `Ctrl+Shift+W` - Close tab

## Configuration

The plugin works out of the box with no configuration required. However, you can modify the source code for customization:

### Change Number Format
```python
# In update_tab_numbers method, change this line:
new_text = "%d: %s" % (i + 1, clean_text)

# Examples:
new_text = "[%d] %s" % (i + 1, clean_text)    # [1] Title
new_text = "%d. %s" % (i + 1, clean_text)     # 1. Title  
new_text = "(%d) %s" % (i + 1, clean_text)    # (1) Title
```

## Troubleshooting

### Plugin Not Appearing
1. Check file location: `~/.config/terminator/plugins/tab_numbers.py`
2. Verify file permissions: `chmod 644 ~/.config/terminator/plugins/tab_numbers.py`
3. Restart Terminator completely
4. Check Terminator version compatibility (tested with 1.90+)

### Numbers Not Updating
1. Check debug output: Run `terminator -d` to see plugin messages
2. Verify plugin is enabled in Preferences → Plugins
3. Try the minimal optimized version if issues persist

### Performance Issues
1. Use `tab_numbers_minimal_optimized.py` for better performance
2. Adjust timer frequency (see Configuration section)
3. Monitor with `htop` or similar tools


### Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Test thoroughly with different scenarios
5. Submit a pull request


## Known Issues

- Very rapid tab operations (>10 tabs/second) may cause brief display delays
- Memory usage grows slightly over very long sessions (weeks)
- Not compatible with Terminator versions < 1.90


## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Terminator development team for the excellent terminal emulator
- Community feedback and bug reports

---

**Star this repository if you find it useful!** ⭐

