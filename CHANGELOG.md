# Twitch Multi-Account Tool Changelog

## Version 3.1.0 (2023-08-25)

### Major New Features
- **Profile Management System**
  - Create, edit and delete profile configurations
  - Save different window setups with unique names and descriptions
  - Profiles store number of windows, Chrome profiles, streamer, and quality settings
  - Easily switch between different configurations

- **Multiple Monitor Support**
  - Create custom layouts for different monitors
  - Specify which monitor to use for each layout
  - Configure grid dimensions and window counts per monitor
  - Save and load different layouts
  - Perfect for multi-monitor setups

- **Crash Recovery System**
  - Automatic detection of crashed Chrome windows
  - Automatically reopens crashed windows with the same profile
  - Maintains window position and arrangement
  - Preserves stream URL and quality settings
  - Provides real-time status updates on recovery

### Improvements
- Better handling of Chrome profiles
- Improved error reporting for missing profiles
- Enhanced window arrangement algorithm
- More robust error handling overall

### Bug Fixes
- Fixed issue with window positioning on certain monitors
- Resolved window handle errors when closing Chrome instances
- Fixed profile directory detection on different operating systems

## Version 3.0.0 (2023-07-10)

### Major Features
- Multi-window Twitch viewer with Chrome profile support
- Watch time tracking for all windows
- Network usage monitoring
- Stream quality selection
- Settings import/export functionality

### Initial Release Features
- Support for up to 20 Chrome windows
- Automatic window arrangement
- Customizable streamer/channel selection
- Memory usage limitation options 