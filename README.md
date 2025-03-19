# Twitch Multi-Account Tool

A powerful tool that allows you to manage and watch multiple Twitch streams simultaneously in separate Chrome windows with customizable layouts and quality settings.

## Features

- **Multiple Streams:** Open and manage multiple Twitch streams in separate Chrome windows
- **Custom Layout:** Automatically arrange windows in an optimal grid layout
- **Quality Control:** Set quality preferences for streams (auto, source, 720p, 480p, 360p, 160p)
- **Resource Monitoring:** Real-time tracking of network, CPU, and memory usage
- **Performance Optimization:** Limit memory usage and optimize Chrome processes
- **Flexible Configuration:** Import/export settings and customize window count

## Requirements

- Python 3.6+
- Google Chrome browser
- Windows, macOS, or Linux operating system

## Installation

### Using Pre-compiled Executable (Windows)

1. Download the latest release from the [Releases](https://github.com/yourusername/TwitchMultiAccount-GitHub/releases) page
2. Extract the ZIP file to a location of your choice
3. Run `TwitchMultiAccount.exe`

### Running from Source

1. Clone this repository:
```
git clone https://github.com/yourusername/TwitchMultiAccount-GitHub.git
cd TwitchMultiAccount-GitHub
```

2. Install the required dependencies:
```
pip install -r requirements.txt
```

3. Run the application:
```
python src/main.py
```

## Usage

1. Launch the application
2. Enter the number of Twitch windows you want to open
3. Enter a streamer name or leave blank for the Twitch homepage
4. Select stream quality
5. Optionally set a memory limit per Chrome process
6. Use the terminal menu to control windows, change settings, or monitor resources

## Configuration

You can customize the following settings:
- Number of windows
- Streamer name
- Stream quality
- Memory limit per Chrome process

These settings can be exported to a JSON file for backup or sharing, and imported later.

## Troubleshooting

- **Chrome Not Found:** Ensure Google Chrome is installed in the default location
- **Window Arrangement Issues:** If windows don't arrange properly, try manually repositioning them and select "Rearrange windows" from the menu
- **Performance Problems:** If experiencing slowdowns, try:
  - Reducing the number of windows
  - Lowering stream quality
  - Setting a memory limit
  - Using the "Optimize resource usage" option

## Privacy

This application does not collect or transmit any personal data. It operates entirely on your local machine, opening Chrome windows with Twitch URLs.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. 