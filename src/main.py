import subprocess
import time
import pygetwindow as gw
import psutil
import threading
import os
import json
import sys
import signal
import platform
import datetime
import uuid
from pathlib import Path
from screeninfo import get_monitors
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.progress import Progress
from rich.columns import Columns
from rich.markdown import Markdown

class TwitchLauncher:
    def __init__(self):
        self.console = Console()
        self.settings_file = Path("settings.json")
        self.profiles_dir = Path("profiles")
        self.processes = []
        self.windows = []
        self.running = True
        self.network_thread = None
        self.num_windows = 0
        self.streamer = ""
        self.url = ""
        self.chrome_path = self._find_chrome_path()
        self.quality = "auto"  # Default quality setting
        self.memory_limit_per_process = None  # Memory limit in MB
        
        # Watch time tracking
        self.watch_start_times = {}  # Dictionary to track start time for each window
        self.watch_time_thread = None  # Thread for tracking watch time
        self.total_session_time = 0  # Total time for the whole session
        self.session_start_time = None
        
        # Profile management
        self.profiles = {}  # Dictionary to store profiles
        self.current_profile = None  # Currently active profile
        
        # Window state tracking (for crash recovery)
        self.window_states = {}  # Track state of each window
        self.crash_recovery_thread = None  # Thread for monitoring crashes
        
        # Multiple monitor layout support
        self.monitor_layouts = {}  # Custom layouts for multiple monitors
        self.active_layout = None  # Currently active layout
        
        # Set up signal handlers for clean exit
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Initialize directories
        if not self.profiles_dir.exists():
            self.profiles_dir.mkdir(exist_ok=True)
        
        # Load profiles
        self.load_all_profiles()

    def _signal_handler(self, sig, frame):
        """Handle termination signals for clean exit"""
        self.console.print("[bold red]Received termination signal. Cleaning up...[/bold red]")
        self.running = False
        self.cleanup()
        sys.exit(0)

    def _find_chrome_path(self):
        """Find Chrome executable path based on operating system"""
        if platform.system() == "Windows":
            paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe")
            ]
            for path in paths:
                if os.path.exists(path):
                    return path
        elif platform.system() == "Darwin":  # macOS
            return "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        elif platform.system() == "Linux":
            for path in ["/usr/bin/google-chrome", "/usr/bin/chrome", "/usr/bin/chromium"]:
                if os.path.exists(path):
                    return path
        
        self.console.print("[bold red]Chrome not found! Please install Chrome or specify the path manually.[/bold red]")
        return None

    def load_settings(self):
        """Load last used settings from file"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r") as f:
                    settings = json.load(f)
                    
                    # Load current profile if specified
                    if "current_profile_id" in settings and settings["current_profile_id"] in self.profiles:
                        self.current_profile = settings["current_profile_id"]
                    
                    # Load active layout if specified
                    if "active_layout" in settings:
                        self.active_layout = settings["active_layout"]
                        
                    return settings
            except json.JSONDecodeError:
                self.console.print("[bold red]Error reading settings file. Using defaults.[/bold red]")
        return {
            "num_windows": 4, 
            "streamer": "", 
            "quality": "auto", 
            "memory_limit_per_process": None
        }

    def save_settings(self):
        """Save current settings to file"""
        try:
            settings = {
                "num_windows": self.num_windows,
                "streamer": self.streamer,
                "quality": self.quality,
                "memory_limit_per_process": self.memory_limit_per_process
            }
            
            # Save current profile if one is active
            if self.current_profile:
                settings["current_profile_id"] = self.current_profile
                
            # Save active layout if one is active
            if self.active_layout:
                settings["active_layout"] = self.active_layout
                
            with open(self.settings_file, "w") as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            self.console.print(f"[bold red]Error saving settings: {e}[/bold red]")

    def export_settings(self, filepath=None):
        """Export settings to a user-specified file"""
        if not filepath:
            filepath = Prompt.ask(
                "[bold yellow]Enter path to export settings[/bold yellow]",
                default="twitch_launcher_settings.json"
            )
        
        try:
            settings = {
                "num_windows": self.num_windows,
                "streamer": self.streamer,
                "quality": self.quality,
                "memory_limit_per_process": self.memory_limit_per_process
            }
            
            with open(filepath, "w") as f:
                json.dump(settings, f, indent=2)
                
            self.console.print(f"[bold green]✅ Settings exported successfully to {filepath}[/bold green]")
        except Exception as e:
            self.console.print(f"[bold red]Error exporting settings: {e}[/bold red]")
    
    def import_settings(self, filepath=None):
        """Import settings from a user-specified file"""
        if not filepath:
            filepath = Prompt.ask(
                "[bold yellow]Enter path to import settings from[/bold yellow]",
                default="twitch_launcher_settings.json"
            )
        
        try:
            if not os.path.exists(filepath):
                self.console.print(f"[bold red]Settings file not found: {filepath}[/bold red]")
                return False
                
            with open(filepath, "r") as f:
                settings = json.load(f)
            
            # Update settings with validation
            if "num_windows" in settings and isinstance(settings["num_windows"], int) and settings["num_windows"] > 0:
                self.num_windows = settings["num_windows"]
            
            if "streamer" in settings:
                self.streamer = settings["streamer"]
                self.url = f"https://www.twitch.tv/{self.streamer}" if self.streamer else "https://www.twitch.tv"
            
            if "quality" in settings and settings["quality"] in ["auto", "source", "720p", "480p", "360p", "160p"]:
                self.quality = settings["quality"]
                
            if "memory_limit_per_process" in settings:
                self.memory_limit_per_process = settings["memory_limit_per_process"]
            
            # Save to the default settings file
            self.save_settings()
            self.console.print(f"[bold green]✅ Settings imported successfully from {filepath}[/bold green]")
            return True
        except json.JSONDecodeError:
            self.console.print(f"[bold red]Invalid JSON format in settings file: {filepath}[/bold red]")
            return False
        except Exception as e:
            self.console.print(f"[bold red]Error importing settings: {e}[/bold red]")
            return False

    def get_screen_resolution(self):
        """Get all available monitors"""
        try:
            monitors = get_monitors()
            if not monitors:
                self.console.print("[bold yellow]Warning: No monitors detected. Using default resolution.[/bold yellow]")
                return [{"width": 1920, "height": 1080, "x": 0, "y": 0}]
            
            return [{"width": m.width, "height": m.height, "x": m.x, "y": m.y} for m in monitors]
        except Exception as e:
            self.console.print(f"[bold red]Error detecting monitors: {e}. Using default resolution.[/bold red]")
            return [{"width": 1920, "height": 1080, "x": 0, "y": 0}]

    def validate_chrome_profiles(self, profiles):
        """Get only valid existing Chrome profiles"""
        valid_profiles = []
        missing_profiles = []
        
        if platform.system() == "Windows":
            chrome_profile_dir = os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\User Data")
        elif platform.system() == "Darwin":  # macOS
            chrome_profile_dir = os.path.expanduser("~/Library/Application Support/Google/Chrome")
        else:  # Linux
            chrome_profile_dir = os.path.expanduser("~/.config/google-chrome")
        
        if not os.path.exists(chrome_profile_dir):
            self.console.print(f"[bold red]Chrome profile directory not found at {chrome_profile_dir}[/bold red]")
            self.console.print("[bold yellow]Please make sure Chrome is installed and has been run at least once.[/bold yellow]")
            return []
            
        # List existing profiles to provide info
        existing_profiles = []
        try:
            for item in os.listdir(chrome_profile_dir):
                item_path = os.path.join(chrome_profile_dir, item)
                if os.path.isdir(item_path) and (item.startswith("Profile ") or item == "Default" or item.startswith("Twich ")):
                    existing_profiles.append(item)
        except Exception as e:
            self.console.print(f"[bold red]Error listing Chrome profiles: {e}[/bold red]")
            
        # Check if each profile exists and only use existing ones
        for profile in profiles:
            profile_path = os.path.join(chrome_profile_dir, profile)
            if os.path.exists(profile_path):
                valid_profiles.append(profile)
            else:
                missing_profiles.append(profile)
        
        # Show missing profiles if any
        if missing_profiles:
            self.console.print("\n[bold yellow]---------------------------- MISSING PROFILES ----------------------------[/bold yellow]")
            self.console.print("[bold yellow]The following Chrome profiles are missing:[/bold yellow]")
            for profile in missing_profiles:
                self.console.print(f"  • [yellow]{profile}[/yellow]")
            
            self.console.print("\n[bold cyan]Existing profiles:[/bold cyan]")
            if existing_profiles:
                for profile in sorted(existing_profiles):
                    self.console.print(f"  • [green]{profile}[/green]")
            else:
                self.console.print("  [yellow]No custom profiles found[/yellow]")
            
            self.console.print("\n[bold cyan]Chrome profile directory:[/bold cyan]")
            self.console.print(f"  [magenta]{chrome_profile_dir}[/magenta]")
            
            self.console.print("\n[bold cyan]How to create profiles:[/bold cyan]")
            self.console.print("  1. Open Chrome and click on your profile icon in the top-right corner")
            self.console.print("  2. Click 'Add' to create a new profile")
            self.console.print("  3. Set the profile name and click 'Done'")
            
            self.console.print("\n[bold yellow]Only existing profiles will be used.[/bold yellow]")
            self.console.print("[bold yellow]--------------------------------------------------------------------[/bold yellow]\n")
        
        if not valid_profiles:
            self.console.print("[bold red]No existing Chrome profiles found! Please create Chrome profiles first.[/bold red]")
            
        return valid_profiles

    def calculate_grid(self, num_windows, monitors):
        """Calculate optimal window layout across available monitors"""
        # For simplicity, we'll use the first monitor for all windows
        monitor = monitors[0]
        screen_width, screen_height = monitor["width"], monitor["height"]
        
        # Calculate grid dimensions
        cols = max(1, round(num_windows ** 0.5))
        rows = max(1, (num_windows + cols - 1) // cols)
        win_width = screen_width // cols
        win_height = screen_height // rows
        
        return cols, rows, win_width, win_height, monitor["x"], monitor["y"]

    def monitor_network(self):
        """Monitor network usage in a separate thread"""
        old_recv = psutil.net_io_counters().bytes_recv
        old_sent = psutil.net_io_counters().bytes_sent
        update_interval = 2  # seconds
        
        while self.running:
            time.sleep(update_interval)
            try:
                new_recv = psutil.net_io_counters().bytes_recv
                new_sent = psutil.net_io_counters().bytes_sent
                
                download_speed = (new_recv - old_recv) / 1024 / update_interval
                upload_speed = (new_sent - old_sent) / 1024 / update_interval
                
                old_recv, old_sent = new_recv, new_sent
                
                self.console.print(f"[cyan]\\[📶] Download: {download_speed:.2f} KB/s | [🚀] Upload: {upload_speed:.2f} KB/s[/cyan]", end="\r")
            except Exception as e:
                self.console.print(f"[bold red]Network monitoring error: {e}[/bold red]", end="\r")

    def get_user_input(self):
        """Get and validate user input"""
        last_settings = self.load_settings()
        
        # Get number of windows
        while True:
            try:
                self.num_windows = int(Prompt.ask(
                    "[bold yellow]How many windows do you want to open?[/bold yellow]", 
                    default=str(last_settings["num_windows"])
                ))
                
                if self.num_windows <= 0:
                    self.console.print("[bold red]Number of windows must be positive.[/bold red]")
                    continue
                    
                if self.num_windows > 20:
                    if not Confirm.ask("[bold red]Opening more than 20 windows may cause performance issues. Continue?[/bold red]"):
                        continue
                break
            except ValueError:
                self.console.print("[bold red]Please enter a valid number.[/bold red]")
        
        # Get streamer name
        self.streamer = Prompt.ask(
            "[bold yellow]Enter a streamer name or leave blank for the Twitch homepage[/bold yellow]",
            default=last_settings["streamer"]
        ).strip()
        
        # Get stream quality
        quality_options = ["auto", "source", "720p", "480p", "360p", "160p"]
        self.console.print("[bold yellow]Available quality options:[/bold yellow]")
        for i, quality in enumerate(quality_options, 1):
            self.console.print(f"  {i}. {quality}")
            
        while True:
            quality_choice = Prompt.ask(
                "[bold yellow]Select stream quality[/bold yellow]",
                default=last_settings.get("quality", "auto")
            )
            
            # Handle both number input and direct quality name
            if quality_choice.isdigit() and 1 <= int(quality_choice) <= len(quality_options):
                self.quality = quality_options[int(quality_choice) - 1]
                break
            elif quality_choice in quality_options:
                self.quality = quality_choice
                break
            else:
                self.console.print("[bold red]Invalid quality selection. Please try again.[/bold red]")
        
        # Get memory limit per process (optional)
        memory_limit_str = Prompt.ask(
            "[bold yellow]Set memory limit per Chrome process (MB, leave blank for no limit)[/bold yellow]",
            default="" if last_settings.get("memory_limit_per_process") is None else str(last_settings.get("memory_limit_per_process"))
        )
        
        if memory_limit_str.strip():
            try:
                self.memory_limit_per_process = int(memory_limit_str)
                if self.memory_limit_per_process <= 0:
                    self.console.print("[bold red]Invalid memory limit. No limit will be applied.[/bold red]")
                    self.memory_limit_per_process = None
            except ValueError:
                self.console.print("[bold red]Invalid memory limit. No limit will be applied.[/bold red]")
                self.memory_limit_per_process = None
        else:
            self.memory_limit_per_process = None
        
        self.url = f"https://www.twitch.tv/{self.streamer}" if self.streamer else "https://www.twitch.tv"
        
        # Save settings
        self.save_settings()

    def get_quality_url_parameter(self):
        """Generate URL parameter for stream quality"""
        if self.quality == "auto" or not self.streamer:  # Don't use quality param for the homepage
            return self.url
            
        # Map quality to Twitch URL parameter
        quality_map = {
            "source": "chunked",
            "720p": "720p60",
            "480p": "480p30",
            "360p": "360p30",
            "160p": "160p30"
        }
        
        quality_param = quality_map.get(self.quality, "chunked")  # Default to source if invalid
        
        # Use different URL formats depending on whether we're on a specific channel or the homepage
        if self.streamer:
            return f"{self.url}?quality={quality_param}"
        return self.url

    def launch_chrome_windows(self):
        """Launch Chrome windows with different profiles"""
        if not self.chrome_path:
            self.console.print("[bold red]Chrome executable not found. Exiting.[/bold red]")
            return False
        
        # Add quality selection to URL    
        quality_url = self.get_quality_url_parameter()
        
        self.console.print(Panel.fit(
            f"[bold green]Launching {self.num_windows} Chrome windows on: {quality_url}[/bold green]\n" +
            f"[bold blue]Quality: {self.quality}[/bold blue]", 
            title="Twitch Multi-Profile Launcher"
        ))
        
        # Use standard Chrome profiles (Profile 1, Profile 2, etc.)
        chrome_profiles = []
        for i in range(1, self.num_windows + 1):
            chrome_profiles.append(f"Profile {i}")
        
        # Validate profiles exist
        chrome_profiles = self.validate_chrome_profiles(chrome_profiles)
        
        # Chrome parameters
        chrome_params = [
            "--disable-plugins",
            "--disable-software-rasterizer",
            "--disable-gpu-compositing"
        ]
        
        # Add memory limit if specified
        if self.memory_limit_per_process:
            chrome_params.append(f"--js-flags=--max-old-space-size={self.memory_limit_per_process}")
        
        # Launch Chrome with different profiles
        with Progress() as progress:
            task = progress.add_task("[cyan]Launching Chrome windows...", total=len(chrome_profiles))
            
            for i, profile in enumerate(chrome_profiles):
                try:
                    # Launch Chrome with the profile
                    if platform.system() == "Windows":
                        cmd = f'start "" "{self.chrome_path}" --new-window "{quality_url}" --profile-directory="{profile}" {" ".join(chrome_params)}'
                        process = subprocess.Popen(cmd, shell=True)
                    else:  # macOS or Linux
                        cmd = [self.chrome_path, "--new-window", quality_url, f"--profile-directory={profile}"] + chrome_params
                        process = subprocess.Popen(cmd)
                        
                    self.processes.append(process)
                    time.sleep(1)  # Wait between launches to avoid overwhelming the system
                    progress.update(task, advance=1)
                except Exception as e:
                    self.console.print(f"[bold red]Error launching Chrome: {e}[/bold red]")
        
        # Wait for windows to load
        self.console.print("[bold yellow]Waiting for Chrome windows to load...[/bold yellow]")
        time.sleep(5)
        
        # Start tracking watch time
        self.start_watch_time_tracking()
        
        return True

    def arrange_windows(self):
        """Find and arrange Chrome windows in a grid"""
        try:
            # If there's an active layout, use it
            if self.active_layout and self.active_layout in self.monitor_layouts:
                return self.arrange_windows_with_layout(self.monitor_layouts[self.active_layout])
                
            # Otherwise, use default arrangement
            # Find Chrome windows
            all_windows = gw.getWindowsWithTitle('')
            self.windows = [w for w in all_windows if ('Twitch' in w.title or 'Chrome' in w.title)]
            self.windows = self.windows[:self.num_windows]  # Limit to requested number
            
            if not self.windows:
                self.console.print("[bold red]No Chrome windows found![/bold red]")
                return False
                
            # Get monitor information
            monitors = self.get_screen_resolution()
            cols, rows, win_width, win_height, offset_x, offset_y = self.calculate_grid(self.num_windows, monitors)
            
            # Arrange windows
            x, y = offset_x, offset_y
            for win in self.windows:
                try:
                    win.moveTo(x, y)
                    win.resizeTo(win_width, win_height)
                    x += win_width
                    if x + win_width > offset_x + monitors[0]["width"]:
                        x = offset_x
                        y += win_height
                except Exception as e:
                    self.console.print(f"[bold red]Error positioning window: {e}[/bold red]")
                    
            self.console.print("[bold green]✅ Windows arranged successfully![/bold green]")
            return True
        except Exception as e:
            self.console.print(f"[bold red]Error arranging windows: {e}[/bold red]")
            return False

    def close_windows(self, count=None):
        """Close a specific number of windows or all windows"""
        if count is None:
            # Close all windows
            for process in self.processes:
                try:
                    process.terminate()
                except:
                    pass
            self.processes = []
            
            # Try to close by window handle as well
            for win in self.windows:
                try:
                    win.close()
                except:
                    pass
            self.windows = []
            
            self.console.print("[bold green]✅ All windows closed![/bold green]")
        else:
            # Close specific number of windows
            count = min(count, len(self.processes))
            for _ in range(count):
                try:
                    process = self.processes.pop()
                    process.terminate()
                except:
                    pass
                    
            # Try to close by window handle as well
            for _ in range(min(count, len(self.windows))):
                try:
                    win = self.windows.pop()
                    win.close()
                except:
                    pass
                    
            self.console.print(f"[bold green]✅ Closed {count} windows![/bold green]")

    def change_quality(self):
        """Change the quality of all streams"""
        quality_options = ["auto", "source", "720p", "480p", "360p", "160p"]
        
        self.console.print("[bold yellow]Available quality options:[/bold yellow]")
        for i, quality in enumerate(quality_options, 1):
            self.console.print(f"  {i}. {quality}")
            
        quality_choice = Prompt.ask(
            "[bold yellow]Select new stream quality[/bold yellow]",
            default=self.quality
        )
        
        # Handle both number input and direct quality name
        new_quality = None
        if quality_choice.isdigit() and 1 <= int(quality_choice) <= len(quality_options):
            new_quality = quality_options[int(quality_choice) - 1]
        elif quality_choice in quality_options:
            new_quality = quality_choice
            
        if new_quality and new_quality != self.quality:
            self.quality = new_quality
            self.save_settings()
            
            if Confirm.ask("[bold yellow]Reload windows with new quality setting?[/bold yellow]"):
                self.close_windows()
                self.launch_chrome_windows()
                self.arrange_windows()
                return True
        elif not new_quality:
            self.console.print("[bold red]Invalid quality selection.[/bold red]")
        
        return False

    def start_watch_time_tracking(self):
        """Start tracking watch time for all windows"""
        self.session_start_time = time.time()
        
        # Initialize watch start times for each window
        for i in range(self.num_windows):
            self.watch_start_times[i] = time.time()
            
        # Start watch time tracking thread
        self.watch_time_thread = threading.Thread(target=self.update_watch_time, daemon=True)
        self.watch_time_thread.start()
        
    def update_watch_time(self):
        """Update and display watch time periodically"""
        update_interval = 60  # Update every minute
        
        while self.running:
            time.sleep(update_interval)
            
            current_time = time.time()
            self.total_session_time = current_time - self.session_start_time
            
            # Log watch time to console occasionally
            hours = int(self.total_session_time // 3600)
            minutes = int((self.total_session_time % 3600) // 60)
            
            if hours > 0:
                self.console.print(f"[green]Session watch time: {hours}h {minutes}m[/green]", end="\r")
            else:
                self.console.print(f"[green]Session watch time: {minutes}m[/green]", end="\r")

    def show_watch_time_stats(self):
        """Display detailed watch time statistics"""
        if self.session_start_time is None:
            self.console.print("[bold yellow]No watch time data available.[/bold yellow]")
            return
            
        current_time = time.time()
        self.total_session_time = current_time - self.session_start_time
        
        # Calculate session time
        hours = int(self.total_session_time // 3600)
        minutes = int((self.total_session_time % 3600) // 60)
        seconds = int(self.total_session_time % 60)
        
        # Create a table to display the statistics
        table = Table(title="Twitch Watch Time Statistics")
        table.add_column("Window", style="cyan")
        table.add_column("Watch Time", style="magenta", justify="right")
        
        # Add session total
        formatted_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        # Calculate start datetime
        start_datetime = datetime.datetime.fromtimestamp(self.session_start_time).strftime("%Y-%m-%d %H:%M:%S")
        
        # Add rows for each window
        for i in range(self.num_windows):
            if i in self.watch_start_times:
                window_watch_time = current_time - self.watch_start_times[i]
                w_hours = int(window_watch_time // 3600)
                w_minutes = int((window_watch_time % 3600) // 60)
                w_seconds = int(window_watch_time % 60)
                
                window_time = f"{w_hours:02d}:{w_minutes:02d}:{w_seconds:02d}"
                
                table.add_row(f"Window {i+1}", window_time)
        
        # Add the session total as the last row
        table.add_row("Total Session", formatted_time, style="bold")
        table.add_row("Started", start_datetime)
        
        self.console.print(table)

    def show_profiles(self):
        """Display available profiles"""
        if not self.profiles:
            self.console.print("[bold yellow]No profiles found. Create one using option 'Create new profile'.[/bold yellow]")
            return
            
        self.console.print("\n[bold blue]Available Profiles[/bold blue]")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="cyan", justify="center")
        table.add_column("Name", style="green")
        table.add_column("Windows", justify="center")
        table.add_column("Streamer", style="blue")
        table.add_column("Description")
        
        for i, (profile_id, profile) in enumerate(self.profiles.items(), 1):
            name = profile["name"]
            if self.current_profile == profile_id:
                name = f"[bold green]{name} (Active)[/bold green]"
                
            table.add_row(
                str(i),
                name,
                str(profile["num_windows"]),
                profile.get("streamer", ""),
                profile.get("description", "")
            )
            
        self.console.print(table)

    def select_profile(self):
        """Select and activate a profile"""
        self.show_profiles()
        
        if not self.profiles:
            return False
            
        choice = Prompt.ask("[bold yellow]Select a profile number or enter 'q' to cancel[/bold yellow]")
        
        if choice.lower() == 'q':
            return False
            
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(self.profiles):
                self.console.print("[bold red]Invalid profile number.[/bold red]")
                return False
                
            profile_id = list(self.profiles.keys())[index]
            return self.activate_profile(profile_id)
        except ValueError:
            self.console.print("[bold red]Please enter a valid number.[/bold red]")
            return False

    def activate_profile(self, profile_id):
        """Activate a profile and launch windows according to its settings"""
        if profile_id not in self.profiles:
            self.console.print("[bold red]Profile not found.[/bold red]")
            return False
            
        profile = self.profiles[profile_id]
        
        self.console.print(f"[bold green]Activating profile: {profile['name']}[/bold green]")
        
        # Update settings from profile
        self.num_windows = profile["num_windows"]
        self.streamer = profile.get("streamer", "")
        self.quality = profile.get("quality", "auto")
        self.url = f"https://www.twitch.tv/{self.streamer}" if self.streamer else "https://www.twitch.tv"
        
        # Set current profile
        self.current_profile = profile_id
        self.save_settings()
        
        # Close any existing windows
        self.close_windows()
        
        # Launch new windows based on profile
        chrome_profiles = profile.get("chrome_profiles", [])
        if not chrome_profiles:
            # Use default naming if not specified
            chrome_profiles = [f"Profile {i}" for i in range(1, self.num_windows + 1)]
            
        # Launch Chrome windows
        self._launch_chrome_with_profiles(chrome_profiles)
        
        # Arrange windows
        self.arrange_windows()
        
        return True

    def _launch_chrome_with_profiles(self, chrome_profiles):
        """Launch Chrome with specified profiles (helper method for profile activation)"""
        if not self.chrome_path:
            self.console.print("[bold red]Chrome executable not found. Exiting.[/bold red]")
            return False
        
        # Add quality selection to URL    
        quality_url = self.get_quality_url_parameter()
        
        self.console.print(Panel.fit(
            f"[bold green]Launching {len(chrome_profiles)} Chrome windows on: {quality_url}[/bold green]\n" +
            f"[bold blue]Quality: {self.quality}[/bold blue]", 
            title="Twitch Multi-Profile Launcher"
        ))
        
        # Validate profiles exist
        valid_profiles = self.validate_chrome_profiles(chrome_profiles)
        
        # Chrome parameters
        chrome_params = [
            "--disable-plugins",
            "--disable-software-rasterizer",
            "--disable-gpu-compositing"
        ]
        
        # Add memory limit if specified
        if self.memory_limit_per_process:
            chrome_params.append(f"--js-flags=--max-old-space-size={self.memory_limit_per_process}")
        
        # Launch Chrome with different profiles
        with Progress() as progress:
            task = progress.add_task("[cyan]Launching Chrome windows...", total=len(valid_profiles))
            
            for i, profile in enumerate(valid_profiles):
                try:
                    # Launch Chrome with the profile
                    if platform.system() == "Windows":
                        cmd = f'start "" "{self.chrome_path}" --new-window "{quality_url}" --profile-directory="{profile}" {" ".join(chrome_params)}'
                        process = subprocess.Popen(cmd, shell=True)
                    else:  # macOS or Linux
                        cmd = [self.chrome_path, "--new-window", quality_url, f"--profile-directory={profile}"] + chrome_params
                        process = subprocess.Popen(cmd)
                        
                    self.processes.append(process)
                    
                    # Initialize window state for crash recovery
                    self.window_states[i] = {
                        "profile": profile,
                        "url": quality_url,
                        "active": True,
                        "last_check": time.time()
                    }
                    
                    time.sleep(1)  # Wait between launches to avoid overwhelming the system
                    progress.update(task, advance=1)
                except Exception as e:
                    self.console.print(f"[bold red]Error launching Chrome: {e}[/bold red]")
        
        # Wait for windows to load
        self.console.print("[bold yellow]Waiting for Chrome windows to load...[/bold yellow]")
        time.sleep(5)
        
        # Start tracking watch time
        self.start_watch_time_tracking()
        
        # Start crash recovery monitoring
        self.start_crash_recovery()
        
        return True

    def load_all_profiles(self):
        """Load all saved profiles from the profiles directory"""
        self.profiles = {}
        
        try:
            if not self.profiles_dir.exists():
                return
                
            for profile_file in self.profiles_dir.glob("*.json"):
                try:
                    with open(profile_file, "r") as f:
                        profile_data = json.load(f)
                        
                        # Validate required fields
                        if "id" in profile_data and "name" in profile_data:
                            self.profiles[profile_data["id"]] = profile_data
                except json.JSONDecodeError:
                    self.console.print(f"[bold red]Error reading profile file {profile_file}. Skipping.[/bold red]")
                except Exception as e:
                    self.console.print(f"[bold red]Error loading profile {profile_file}: {e}[/bold red]")
        except Exception as e:
            self.console.print(f"[bold red]Error loading profiles: {e}[/bold red]")
            
        self.console.print(f"[green]Loaded {len(self.profiles)} profiles.[/green]")

    def create_new_profile(self):
        """Create a new profile configuration"""
        self.console.print("\n[bold blue]Create New Profile[/bold blue]")
        
        profile_name = Prompt.ask("[bold yellow]Enter profile name[/bold yellow]")
        if not profile_name.strip():
            self.console.print("[bold red]Profile name cannot be empty.[/bold red]")
            return False
            
        profile_description = Prompt.ask("[bold yellow]Enter profile description (optional)[/bold yellow]", default="")
        
        # Get chrome profiles
        chrome_profiles = []
        num_windows = int(Prompt.ask("[bold yellow]How many windows for this profile?[/bold yellow]", default="4"))
        
        if num_windows <= 0:
            self.console.print("[bold red]Number of windows must be positive.[/bold red]")
            return False
            
        self.console.print("[bold yellow]Enter Chrome profile for each window (leave blank for default naming)[/bold yellow]")
        use_default_naming = Confirm.ask("[bold yellow]Use default profile naming (Profile 1, Profile 2, etc.)?[/bold yellow]", default=True)
        
        if use_default_naming:
            for i in range(1, num_windows + 1):
                chrome_profiles.append(f"Profile {i}")
        else:
            for i in range(1, num_windows + 1):
                profile = Prompt.ask(f"[bold yellow]Window {i} Chrome profile[/bold yellow]", default=f"Profile {i}")
                chrome_profiles.append(profile)
        
        # Get streamer name
        streamer = Prompt.ask("[bold yellow]Enter a streamer name or leave blank for the Twitch homepage[/bold yellow]", default="").strip()
        
        # Get stream quality
        quality_options = ["auto", "source", "720p", "480p", "360p", "160p"]
        self.console.print("[bold yellow]Available quality options:[/bold yellow]")
        for i, quality in enumerate(quality_options, 1):
            self.console.print(f"  {i}. {quality}")
            
        quality_choice = Prompt.ask("[bold yellow]Select stream quality[/bold yellow]", default="auto")
        
        # Handle both number input and direct quality name
        if quality_choice.isdigit() and 1 <= int(quality_choice) <= len(quality_options):
            quality = quality_options[int(quality_choice) - 1]
        elif quality_choice in quality_options:
            quality = quality_choice
        else:
            quality = "auto"
        
        # Create unique ID for the profile
        profile_id = str(uuid.uuid4())
        
        # Create profile object
        new_profile = {
            "id": profile_id,
            "name": profile_name,
            "description": profile_description,
            "num_windows": num_windows,
            "chrome_profiles": chrome_profiles,
            "streamer": streamer,
            "quality": quality,
            "created_at": datetime.datetime.now().isoformat()
        }
        
        # Save profile
        try:
            profile_file = self.profiles_dir / f"{profile_id}.json"
            with open(profile_file, "w") as f:
                json.dump(new_profile, f, indent=2)
                
            self.profiles[profile_id] = new_profile
            self.console.print(f"[bold green]✅ Profile '{profile_name}' created successfully![/bold green]")
            
            # Offer to activate the new profile
            if Confirm.ask("[bold yellow]Activate this profile now?[/bold yellow]", default=True):
                self.activate_profile(profile_id)
                
            return True
        except Exception as e:
            self.console.print(f"[bold red]Error saving profile: {e}[/bold red]")
            return False

    def edit_profile(self, profile_id):
        """Edit an existing profile"""
        if profile_id not in self.profiles:
            self.console.print("[bold red]Profile not found.[/bold red]")
            return False
            
        profile = self.profiles[profile_id]
        self.console.print(f"\n[bold blue]Editing Profile: {profile['name']}[/bold blue]")
        
        # Edit basic info
        profile_name = Prompt.ask("[bold yellow]Enter profile name[/bold yellow]", default=profile["name"])
        if not profile_name.strip():
            self.console.print("[bold red]Profile name cannot be empty.[/bold red]")
            return False
            
        profile_description = Prompt.ask("[bold yellow]Enter profile description[/bold yellow]", default=profile.get("description", ""))
        
        # Edit number of windows
        num_windows = int(Prompt.ask("[bold yellow]How many windows for this profile?[/bold yellow]", default=str(profile["num_windows"])))
        
        if num_windows <= 0:
            self.console.print("[bold red]Number of windows must be positive.[/bold red]")
            return False
            
        # Edit Chrome profiles
        chrome_profiles = profile.get("chrome_profiles", [])
        edit_chrome_profiles = Confirm.ask("[bold yellow]Edit Chrome profiles for each window?[/bold yellow]", default=False)
        
        if edit_chrome_profiles:
            chrome_profiles = []
            use_default_naming = Confirm.ask("[bold yellow]Use default profile naming (Profile 1, Profile 2, etc.)?[/bold yellow]", default=True)
            
            if use_default_naming:
                for i in range(1, num_windows + 1):
                    chrome_profiles.append(f"Profile {i}")
            else:
                for i in range(1, num_windows + 1):
                    default_profile = f"Profile {i}"
                    if i <= len(profile.get("chrome_profiles", [])):
                        default_profile = profile["chrome_profiles"][i-1]
                        
                    profile_name = Prompt.ask(f"[bold yellow]Window {i} Chrome profile[/bold yellow]", default=default_profile)
                    chrome_profiles.append(profile_name)
        elif len(chrome_profiles) < num_windows:
            # Add more profiles if needed
            for i in range(len(chrome_profiles) + 1, num_windows + 1):
                chrome_profiles.append(f"Profile {i}")
        
        # Edit streamer
        streamer = Prompt.ask("[bold yellow]Enter a streamer name or leave blank for the Twitch homepage[/bold yellow]", default=profile.get("streamer", "")).strip()
        
        # Edit quality
        quality_options = ["auto", "source", "720p", "480p", "360p", "160p"]
        self.console.print("[bold yellow]Available quality options:[/bold yellow]")
        for i, quality in enumerate(quality_options, 1):
            self.console.print(f"  {i}. {quality}")
            
        quality_choice = Prompt.ask("[bold yellow]Select stream quality[/bold yellow]", default=profile.get("quality", "auto"))
        
        # Handle both number input and direct quality name
        if quality_choice.isdigit() and 1 <= int(quality_choice) <= len(quality_options):
            quality = quality_options[int(quality_choice) - 1]
        elif quality_choice in quality_options:
            quality = quality_choice
        else:
            quality = "auto"
        
        # Update profile object
        profile["name"] = profile_name
        profile["description"] = profile_description
        profile["num_windows"] = num_windows
        profile["chrome_profiles"] = chrome_profiles
        profile["streamer"] = streamer
        profile["quality"] = quality
        profile["updated_at"] = datetime.datetime.now().isoformat()
        
        # Save profile
        try:
            profile_file = self.profiles_dir / f"{profile_id}.json"
            with open(profile_file, "w") as f:
                json.dump(profile, f, indent=2)
                
            self.profiles[profile_id] = profile
            self.console.print(f"[bold green]✅ Profile '{profile_name}' updated successfully![/bold green]")
            
            # If this is the current profile, ask to reload
            if self.current_profile == profile_id:
                if Confirm.ask("[bold yellow]This is the current profile. Reload windows with updated settings?[/bold yellow]", default=True):
                    self.activate_profile(profile_id)
                    
            return True
        except Exception as e:
            self.console.print(f"[bold red]Error saving profile: {e}[/bold red]")
            return False

    def delete_profile(self, profile_id):
        """Delete a profile"""
        if profile_id not in self.profiles:
            self.console.print("[bold red]Profile not found.[/bold red]")
            return False
            
        profile = self.profiles[profile_id]
        
        if not Confirm.ask(f"[bold red]Are you sure you want to delete profile '{profile['name']}'? This cannot be undone.[/bold red]", default=False):
            return False
            
        try:
            # Delete profile file
            profile_file = self.profiles_dir / f"{profile_id}.json"
            if profile_file.exists():
                profile_file.unlink()
                
            # Remove from profiles dictionary
            del self.profiles[profile_id]
            
            # Clear current profile if it was deleted
            if self.current_profile == profile_id:
                self.current_profile = None
                self.save_settings()
                
            self.console.print(f"[bold green]✅ Profile '{profile['name']}' deleted successfully![/bold green]")
            return True
        except Exception as e:
            self.console.print(f"[bold red]Error deleting profile: {e}[/bold red]")
            return False

    def manage_profiles(self):
        """Show profile management menu"""
        while True:
            self.console.print("\n[bold blue]Profile Management[/bold blue]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Option", style="cyan", justify="center")
            table.add_column("Action")
            table.add_row("1", "View all profiles")
            table.add_row("2", "Create new profile")
            table.add_row("3", "Edit profile")
            table.add_row("4", "Delete profile")
            table.add_row("5", "Activate profile")
            table.add_row("6", "Back to main menu")
            self.console.print(table)
            
            choice = Prompt.ask("[bold yellow]Select an option[/bold yellow]")
            
            if choice == "1":
                self.show_profiles()
            
            elif choice == "2":
                self.create_new_profile()
            
            elif choice == "3":
                self.show_profiles()
                if self.profiles:
                    profile_num = Prompt.ask("[bold yellow]Enter profile number to edit or 'q' to cancel[/bold yellow]")
                    if profile_num.lower() != 'q':
                        try:
                            index = int(profile_num) - 1
                            if 0 <= index < len(self.profiles):
                                profile_id = list(self.profiles.keys())[index]
                                self.edit_profile(profile_id)
                            else:
                                self.console.print("[bold red]Invalid profile number.[/bold red]")
                        except ValueError:
                            self.console.print("[bold red]Please enter a valid number.[/bold red]")
            
            elif choice == "4":
                self.show_profiles()
                if self.profiles:
                    profile_num = Prompt.ask("[bold yellow]Enter profile number to delete or 'q' to cancel[/bold yellow]")
                    if profile_num.lower() != 'q':
                        try:
                            index = int(profile_num) - 1
                            if 0 <= index < len(self.profiles):
                                profile_id = list(self.profiles.keys())[index]
                                self.delete_profile(profile_id)
                            else:
                                self.console.print("[bold red]Invalid profile number.[/bold red]")
                        except ValueError:
                            self.console.print("[bold red]Please enter a valid number.[/bold red]")
            
            elif choice == "5":
                self.select_profile()
            
            elif choice == "6":
                return
            
            else:
                self.console.print("[bold red]❌ Invalid choice! Please select a valid option.[/bold red]")

    def show_menu(self):
        """Display and handle the terminal menu"""
        while self.running:
            self.console.print("\n[bold blue]🖥️ TERMINAL MENU[/bold blue]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Option", style="cyan", justify="center")
            table.add_column("Action")
            table.add_row("1", "Close all Twitch windows")
            table.add_row("2", "Close a specific number of windows")
            table.add_row("3", "Show current network usage")
            table.add_row("4", "Reload all windows")
            table.add_row("5", "Rearrange windows")
            table.add_row("6", "Change streamer")
            table.add_row("7", "Change stream quality")
            table.add_row("8", "Show watch time statistics")
            table.add_row("9", "Export current settings")
            table.add_row("10", "Import settings")
            table.add_row("11", "Profile management")
            table.add_row("12", "Multiple monitor layout settings")
            table.add_row("13", "Exit script")
            self.console.print(table)

            choice = Prompt.ask("[bold yellow]Select an option[/bold yellow]")
            
            if choice == "1":
                self.console.print("[bold red]❌ Closing all Twitch windows...[/bold red]")
                self.close_windows()
            
            elif choice == "2":
                try:
                    close_count = int(Prompt.ask("[bold yellow]How many windows do you want to close?[/bold yellow]"))
                    if close_count <= 0:
                        self.console.print("[bold red]Number must be positive.[/bold red]")
                    else:
                        self.close_windows(close_count)
                except ValueError:
                    self.console.print("[bold red]Please enter a valid number.[/bold red]")

            elif choice == "3":
                self.console.print("[bold green]📡 Network usage is displayed live in the terminal.[/bold green]")
            
            elif choice == "4":
                self.console.print("[bold yellow]Reloading all windows...[/bold yellow]")
                self.close_windows()
                self.launch_chrome_windows()
                self.arrange_windows()
                
            elif choice == "5":
                self.console.print("[bold yellow]Rearranging windows...[/bold yellow]")
                self.arrange_windows()
                
            elif choice == "6":
                new_streamer = Prompt.ask("[bold yellow]Enter a new streamer name or leave blank for the Twitch homepage[/bold yellow]").strip()
                self.streamer = new_streamer
                self.url = f"https://www.twitch.tv/{self.streamer}" if self.streamer else "https://www.twitch.tv"
                self.save_settings()
                
                if Confirm.ask("[bold yellow]Reload windows with new streamer?[/bold yellow]"):
                    self.close_windows()
                    self.launch_chrome_windows()
                    self.arrange_windows()
            
            elif choice == "7":
                self.change_quality()
                
            elif choice == "8":
                self.show_watch_time_stats()
                
            elif choice == "9":
                self.export_settings()
                
            elif choice == "10":
                if self.import_settings():
                    if Confirm.ask("[bold yellow]Reload windows with imported settings?[/bold yellow]"):
                        self.close_windows()
                        self.launch_chrome_windows()
                        self.arrange_windows()
            
            elif choice == "11":
                self.manage_profiles()
                
            elif choice == "12":
                self.manage_monitor_layouts()
            
            elif choice == "13":
                self.console.print("[bold red]🔴 Exiting script...[/bold red]")
                self.running = False
            
            else:
                self.console.print("[bold red]❌ Invalid choice! Please select a valid option.[/bold red]")

    def start_crash_recovery(self):
        """Start monitoring for crashed windows and recover them"""
        if self.crash_recovery_thread and self.crash_recovery_thread.is_alive():
            return
            
        self.crash_recovery_thread = threading.Thread(target=self._monitor_crashes, daemon=True)
        self.crash_recovery_thread.start()
        
    def _monitor_crashes(self):
        """Monitor for crashed windows and recover them"""
        check_interval = 5  # Check every 5 seconds
        
        while self.running:
            try:
                current_time = time.time()
                
                # Check each window's state
                for window_index, state in list(self.window_states.items()):
                    if not state["active"]:
                        continue
                        
                    # Check if window exists
                    window_exists = False
                    for win in self.windows:
                        if win.title and state["profile"] in win.title:
                            window_exists = True
                            break
                            
                    # If window doesn't exist and hasn't been checked recently
                    if not window_exists and (current_time - state["last_check"]) > check_interval:
                        self.console.print(f"[bold yellow]Window {window_index + 1} (Profile: {state['profile']}) appears to have crashed. Attempting recovery...[/bold yellow]")
                        
                        try:
                            # Launch new Chrome window with the same profile
                            if platform.system() == "Windows":
                                cmd = f'start "" "{self.chrome_path}" --new-window "{state["url"]}" --profile-directory="{state["profile"]}" --disable-plugins --disable-software-rasterizer --disable-gpu-compositing'
                                process = subprocess.Popen(cmd, shell=True)
                            else:  # macOS or Linux
                                cmd = [self.chrome_path, "--new-window", state["url"], f"--profile-directory={state['profile']}", "--disable-plugins", "--disable-software-rasterizer", "--disable-gpu-compositing"]
                                process = subprocess.Popen(cmd)
                                
                            # Update process list
                            if window_index < len(self.processes):
                                self.processes[window_index] = process
                            else:
                                self.processes.append(process)
                                
                            # Update window state
                            state["last_check"] = current_time
                            self.console.print(f"[bold green]✅ Window {window_index + 1} recovered successfully![/bold green]")
                            
                            # Wait for window to load
                            time.sleep(5)
                            
                            # Rearrange windows to maintain layout
                            self.arrange_windows()
                            
                        except Exception as e:
                            self.console.print(f"[bold red]Error recovering window {window_index + 1}: {e}[/bold red]")
                            state["active"] = False  # Mark as inactive if recovery failed
                            
                time.sleep(check_interval)
                
            except Exception as e:
                self.console.print(f"[bold red]Error in crash recovery monitoring: {e}[/bold red]")
                time.sleep(check_interval)
                
    def cleanup(self):
        """Clean up resources on exit"""
        self.running = False
        if self.network_thread and self.network_thread.is_alive():
            self.network_thread.join(timeout=1)
        if self.watch_time_thread and self.watch_time_thread.is_alive():
            self.watch_time_thread.join(timeout=1)
        if self.crash_recovery_thread and self.crash_recovery_thread.is_alive():
            self.crash_recovery_thread.join(timeout=1)
        self.close_windows()

    def run(self):
        """Main method to run the application"""
        self.console.print(Panel.fit("[bold cyan]Twitch Multi-Profile Launcher v3.0[/bold cyan]", 
                                    subtitle="Multi-window Twitch Viewer with Watch Time Tracking"))
        
        try:
            # Get user input
            self.get_user_input()
            
            # Launch Chrome windows
            if not self.launch_chrome_windows():
                return
            
            # Arrange windows
            self.arrange_windows()
            
            # Start network monitoring in a separate thread
            self.network_thread = threading.Thread(target=self.monitor_network, daemon=True)
            self.network_thread.start()
            
            # Show menu
            self.show_menu()
            
        except Exception as e:
            self.console.print(f"[bold red]An error occurred: {e}[/bold red]")
        finally:
            self.cleanup()

    def manage_monitor_layouts(self):
        """Show multiple monitor layout management menu"""
        while True:
            self.console.print("\n[bold blue]Multiple Monitor Layout Management[/bold blue]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Option", style="cyan", justify="center")
            table.add_column("Action")
            table.add_row("1", "View available monitors")
            table.add_row("2", "Create new layout")
            table.add_row("3", "Edit layout")
            table.add_row("4", "Delete layout")
            table.add_row("5", "Activate layout")
            table.add_row("6", "Back to main menu")
            self.console.print(table)
            
            choice = Prompt.ask("[bold yellow]Select an option[/bold yellow]")
            
            if choice == "1":
                self.show_monitors()
            
            elif choice == "2":
                self.create_new_layout()
            
            elif choice == "3":
                self.show_layouts()
                if self.monitor_layouts:
                    layout_num = Prompt.ask("[bold yellow]Enter layout number to edit or 'q' to cancel[/bold yellow]")
                    if layout_num.lower() != 'q':
                        try:
                            index = int(layout_num) - 1
                            if 0 <= index < len(self.monitor_layouts):
                                layout_id = list(self.monitor_layouts.keys())[index]
                                self.edit_layout(layout_id)
                            else:
                                self.console.print("[bold red]Invalid layout number.[/bold red]")
                        except ValueError:
                            self.console.print("[bold red]Please enter a valid number.[/bold red]")
            
            elif choice == "4":
                self.show_layouts()
                if self.monitor_layouts:
                    layout_num = Prompt.ask("[bold yellow]Enter layout number to delete or 'q' to cancel[/bold yellow]")
                    if layout_num.lower() != 'q':
                        try:
                            index = int(layout_num) - 1
                            if 0 <= index < len(self.monitor_layouts):
                                layout_id = list(self.monitor_layouts.keys())[index]
                                self.delete_layout(layout_id)
                            else:
                                self.console.print("[bold red]Invalid layout number.[/bold red]")
                        except ValueError:
                            self.console.print("[bold red]Please enter a valid number.[/bold red]")
            
            elif choice == "5":
                self.select_layout()
            
            elif choice == "6":
                return
            
            else:
                self.console.print("[bold red]❌ Invalid choice! Please select a valid option.[/bold red]")
                
    def show_monitors(self):
        """Display information about available monitors"""
        monitors = self.get_screen_resolution()
        
        if not monitors:
            self.console.print("[bold red]No monitors detected![/bold red]")
            return
            
        self.console.print("\n[bold blue]Available Monitors[/bold blue]")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="cyan", justify="center")
        table.add_column("Resolution", style="green")
        table.add_column("Position", style="blue")
        table.add_column("Primary", style="yellow")
        
        for i, monitor in enumerate(monitors, 1):
            is_primary = monitor.get("is_primary", False)
            primary_mark = "✓" if is_primary else ""
            
            table.add_row(
                str(i),
                f"{monitor['width']}x{monitor['height']}",
                f"({monitor['x']}, {monitor['y']})",
                primary_mark
            )
            
        self.console.print(table)
        
    def create_new_layout(self):
        """Create a new monitor layout configuration"""
        self.console.print("\n[bold blue]Create New Monitor Layout[/bold blue]")
        
        layout_name = Prompt.ask("[bold yellow]Enter layout name[/bold yellow]")
        if not layout_name.strip():
            self.console.print("[bold red]Layout name cannot be empty.[/bold red]")
            return False
            
        layout_description = Prompt.ask("[bold yellow]Enter layout description (optional)[/bold yellow]", default="")
        
        # Get available monitors
        monitors = self.get_screen_resolution()
        if not monitors:
            self.console.print("[bold red]No monitors detected![/bold red]")
            return False
            
        # Show monitors and get selection
        self.show_monitors()
        monitor_choice = Prompt.ask("[bold yellow]Select monitor number for this layout[/bold yellow]")
        
        try:
            monitor_index = int(monitor_choice) - 1
            if monitor_index < 0 or monitor_index >= len(monitors):
                self.console.print("[bold red]Invalid monitor number.[/bold red]")
                return False
                
            selected_monitor = monitors[monitor_index]
            
            # Get grid dimensions
            num_windows = int(Prompt.ask("[bold yellow]How many windows for this monitor?[/bold yellow]", default="4"))
            if num_windows <= 0:
                self.console.print("[bold red]Number of windows must be positive.[/bold red]")
                return False
                
            # Calculate grid dimensions
            cols = max(1, round(num_windows ** 0.5))
            rows = max(1, (num_windows + cols - 1) // cols)
            
            # Create layout object
            layout_id = str(uuid.uuid4())
            new_layout = {
                "id": layout_id,
                "name": layout_name,
                "description": layout_description,
                "monitor": selected_monitor,
                "num_windows": num_windows,
                "grid": {
                    "cols": cols,
                    "rows": rows
                },
                "created_at": datetime.datetime.now().isoformat()
            }
            
            # Save layout
            try:
                layout_file = self.profiles_dir / f"layout_{layout_id}.json"
                with open(layout_file, "w") as f:
                    json.dump(new_layout, f, indent=2)
                    
                self.monitor_layouts[layout_id] = new_layout
                self.console.print(f"[bold green]✅ Layout '{layout_name}' created successfully![/bold green]")
                
                # Offer to activate the new layout
                if Confirm.ask("[bold yellow]Activate this layout now?[/bold yellow]", default=True):
                    self.activate_layout(layout_id)
                    
                return True
            except Exception as e:
                self.console.print(f"[bold red]Error saving layout: {e}[/bold red]")
                return False
                
        except ValueError:
            self.console.print("[bold red]Please enter a valid number.[/bold red]")
            return False
            
    def edit_layout(self, layout_id):
        """Edit an existing monitor layout"""
        if layout_id not in self.monitor_layouts:
            self.console.print("[bold red]Layout not found.[/bold red]")
            return False
            
        layout = self.monitor_layouts[layout_id]
        self.console.print(f"\n[bold blue]Editing Layout: {layout['name']}[/bold blue]")
        
        # Edit basic info
        layout_name = Prompt.ask("[bold yellow]Enter layout name[/bold yellow]", default=layout["name"])
        if not layout_name.strip():
            self.console.print("[bold red]Layout name cannot be empty.[/bold red]")
            return False
            
        layout_description = Prompt.ask("[bold yellow]Enter layout description[/bold yellow]", default=layout.get("description", ""))
        
        # Get available monitors
        monitors = self.get_screen_resolution()
        if not monitors:
            self.console.print("[bold red]No monitors detected![/bold red]")
            return False
            
        # Show monitors and get selection
        self.show_monitors()
        monitor_choice = Prompt.ask("[bold yellow]Select monitor number for this layout[/bold yellow]", default=str(monitors.index(layout["monitor"]) + 1))
        
        try:
            monitor_index = int(monitor_choice) - 1
            if monitor_index < 0 or monitor_index >= len(monitors):
                self.console.print("[bold red]Invalid monitor number.[/bold red]")
                return False
                
            selected_monitor = monitors[monitor_index]
            
            # Edit number of windows
            num_windows = int(Prompt.ask("[bold yellow]How many windows for this monitor?[/bold yellow]", default=str(layout["num_windows"])))
            if num_windows <= 0:
                self.console.print("[bold red]Number of windows must be positive.[/bold red]")
                return False
                
            # Calculate grid dimensions
            cols = max(1, round(num_windows ** 0.5))
            rows = max(1, (num_windows + cols - 1) // cols)
            
            # Update layout object
            layout["name"] = layout_name
            layout["description"] = layout_description
            layout["monitor"] = selected_monitor
            layout["num_windows"] = num_windows
            layout["grid"] = {
                "cols": cols,
                "rows": rows
            }
            layout["updated_at"] = datetime.datetime.now().isoformat()
            
            # Save layout
            try:
                layout_file = self.profiles_dir / f"layout_{layout_id}.json"
                with open(layout_file, "w") as f:
                    json.dump(layout, f, indent=2)
                    
                self.monitor_layouts[layout_id] = layout
                self.console.print(f"[bold green]✅ Layout '{layout_name}' updated successfully![/bold green]")
                
                # If this is the active layout, ask to apply changes
                if self.active_layout == layout_id:
                    if Confirm.ask("[bold yellow]This is the active layout. Apply changes now?[/bold yellow]", default=True):
                        self.activate_layout(layout_id)
                        
                return True
            except Exception as e:
                self.console.print(f"[bold red]Error saving layout: {e}[/bold red]")
                return False
                
        except ValueError:
            self.console.print("[bold red]Please enter a valid number.[/bold red]")
            return False
            
    def delete_layout(self, layout_id):
        """Delete a monitor layout"""
        if layout_id not in self.monitor_layouts:
            self.console.print("[bold red]Layout not found.[/bold red]")
            return False
            
        layout = self.monitor_layouts[layout_id]
        
        if not Confirm.ask(f"[bold red]Are you sure you want to delete layout '{layout['name']}'? This cannot be undone.[/bold red]", default=False):
            return False
            
        try:
            # Delete layout file
            layout_file = self.profiles_dir / f"layout_{layout_id}.json"
            if layout_file.exists():
                layout_file.unlink()
                
            # Remove from layouts dictionary
            del self.monitor_layouts[layout_id]
            
            # Clear active layout if it was deleted
            if self.active_layout == layout_id:
                self.active_layout = None
                self.save_settings()
                
            self.console.print(f"[bold green]✅ Layout '{layout['name']}' deleted successfully![/bold green]")
            return True
        except Exception as e:
            self.console.print(f"[bold red]Error deleting layout: {e}[/bold red]")
            return False
            
    def show_layouts(self):
        """Display available monitor layouts"""
        if not self.monitor_layouts:
            self.console.print("[bold yellow]No layouts found. Create one using option 'Create new layout'.[/bold yellow]")
            return
            
        self.console.print("\n[bold blue]Available Monitor Layouts[/bold blue]")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="cyan", justify="center")
        table.add_column("Name", style="green")
        table.add_column("Monitor", style="blue")
        table.add_column("Windows", justify="center")
        table.add_column("Description")
        
        for i, (layout_id, layout) in enumerate(self.monitor_layouts.items(), 1):
            name = layout["name"]
            if self.active_layout == layout_id:
                name = f"[bold green]{name} (Active)[/bold green]"
                
            monitor = layout["monitor"]
            monitor_info = f"{monitor['width']}x{monitor['height']} ({monitor['x']}, {monitor['y']})"
            
            table.add_row(
                str(i),
                name,
                monitor_info,
                str(layout["num_windows"]),
                layout.get("description", "")
            )
            
        self.console.print(table)
        
    def select_layout(self):
        """Select and activate a monitor layout"""
        self.show_layouts()
        
        if not self.monitor_layouts:
            return False
            
        choice = Prompt.ask("[bold yellow]Select a layout number or enter 'q' to cancel[/bold yellow]")
        
        if choice.lower() == 'q':
            return False
            
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(self.monitor_layouts):
                self.console.print("[bold red]Invalid layout number.[/bold red]")
                return False
                
            layout_id = list(self.monitor_layouts.keys())[index]
            return self.activate_layout(layout_id)
        except ValueError:
            self.console.print("[bold red]Please enter a valid number.[/bold red]")
            return False
            
    def activate_layout(self, layout_id):
        """Activate a monitor layout and rearrange windows"""
        if layout_id not in self.monitor_layouts:
            self.console.print("[bold red]Layout not found.[/bold red]")
            return False
            
        layout = self.monitor_layouts[layout_id]
        
        self.console.print(f"[bold green]Activating layout: {layout['name']}[/bold green]")
        
        # Set active layout
        self.active_layout = layout_id
        self.save_settings()
        
        # Rearrange windows according to layout
        return self.arrange_windows_with_layout(layout)
        
    def arrange_windows_with_layout(self, layout):
        """Arrange windows according to the specified layout"""
        try:
            # Find Chrome windows
            all_windows = gw.getWindowsWithTitle('')
            self.windows = [w for w in all_windows if ('Twitch' in w.title or 'Chrome' in w.title)]
            self.windows = self.windows[:layout["num_windows"]]  # Limit to layout's number of windows
            
            if not self.windows:
                self.console.print("[bold red]No Chrome windows found![/bold red]")
                return False
                
            # Get monitor information from layout
            monitor = layout["monitor"]
            cols = layout["grid"]["cols"]
            rows = layout["grid"]["rows"]
            
            # Calculate window dimensions
            win_width = monitor["width"] // cols
            win_height = monitor["height"] // rows
            
            # Arrange windows
            x, y = monitor["x"], monitor["y"]
            for i, win in enumerate(self.windows):
                try:
                    # Calculate position in grid
                    col = i % cols
                    row = i // cols
                    
                    # Position window
                    win_x = x + (col * win_width)
                    win_y = y + (row * win_height)
                    
                    win.moveTo(win_x, win_y)
                    win.resizeTo(win_width, win_height)
                    
                except Exception as e:
                    self.console.print(f"[bold red]Error positioning window: {e}[/bold red]")
                    
            self.console.print("[bold green]✅ Windows arranged successfully![/bold green]")
            return True
        except Exception as e:
            self.console.print(f"[bold red]Error arranging windows: {e}[/bold red]")
            return False

if __name__ == "__main__":
    launcher = TwitchLauncher()
    launcher.run() 