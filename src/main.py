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
from pathlib import Path
from screeninfo import get_monitors
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.progress import Progress

class TwitchLauncher:
    def __init__(self):
        self.console = Console()
        self.settings_file = Path("settings.json")
        self.processes = []
        self.windows = []
        self.running = True
        self.network_thread = None
        self.cpu_monitor_thread = None
        self.num_windows = 0
        self.streamer = ""
        self.url = ""
        self.chrome_path = self._find_chrome_path()
        self.quality = "auto"  # Default quality setting
        self.memory_limit_per_process = None  # Memory limit in MB
        
        # Set up signal handlers for clean exit
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

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
                    return json.load(f)
            except json.JSONDecodeError:
                self.console.print("[bold red]Error reading settings file. Using defaults.[/bold red]")
        return {"num_windows": 4, "streamer": "", "quality": "auto", "memory_limit_per_process": None}

    def save_settings(self):
        """Save current settings to file"""
        try:
            with open(self.settings_file, "w") as f:
                json.dump({
                    "num_windows": self.num_windows, 
                    "streamer": self.streamer,
                    "quality": self.quality,
                    "memory_limit_per_process": self.memory_limit_per_process
                }, f, indent=2)
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
        """Validate that Chrome profiles exist"""
        valid_profiles = []
        
        if platform.system() == "Windows":
            chrome_profile_dir = os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\User Data")
        elif platform.system() == "Darwin":  # macOS
            chrome_profile_dir = os.path.expanduser("~/Library/Application Support/Google/Chrome")
        else:  # Linux
            chrome_profile_dir = os.path.expanduser("~/.config/google-chrome")
        
        if not os.path.exists(chrome_profile_dir):
            self.console.print(f"[bold yellow]Warning: Chrome profile directory not found at {chrome_profile_dir}[/bold yellow]")
            return profiles  # Return all profiles and hope for the best
            
        for profile in profiles:
            profile_path = os.path.join(chrome_profile_dir, profile)
            if os.path.exists(profile_path):
                valid_profiles.append(profile)
            else:
                self.console.print(f"[bold yellow]Warning: Chrome profile '{profile}' not found.[/bold yellow]")
        
        if not valid_profiles:
            self.console.print("[bold red]No valid Chrome profiles found. Creating new profiles.[/bold red]")
            return profiles  # Return all profiles and let Chrome create them
            
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

    def monitor_cpu_memory(self):
        """Monitor CPU and memory usage of Chrome processes in a separate thread"""
        update_interval = 5  # seconds
        
        while self.running:
            time.sleep(update_interval)
            try:
                # Get Chrome processes
                chrome_processes = []
                for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                    if 'chrome' in proc.info['name'].lower():
                        chrome_processes.append(proc)
                
                # Limit memory usage if specified
                if self.memory_limit_per_process:
                    for proc in chrome_processes:
                        try:
                            memory_mb = proc.info['memory_info'].rss / (1024 * 1024)
                            if memory_mb > self.memory_limit_per_process:
                                # If exceeding memory limit, restart the process
                                self.console.print(f"[bold yellow]Process {proc.info['pid']} using {memory_mb:.1f}MB. Restarting...[/bold yellow]")
                                proc.kill()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                
                # Calculate total memory and CPU
                total_memory = sum([p.info['memory_info'].rss for p in chrome_processes if hasattr(p.info['memory_info'], 'rss')])
                total_memory_mb = total_memory / (1024 * 1024)
                
                # Calculate CPU percent for all Chrome processes
                cpu_percent = 0
                for proc in chrome_processes:
                    try:
                        cpu_percent += proc.cpu_percent(interval=0.1)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                self.console.print(f"[magenta]\\[💻] Chrome processes: {len(chrome_processes)} | CPU: {cpu_percent:.1f}% | RAM: {total_memory_mb:.1f} MB[/magenta]", end="\r")
                
            except Exception as e:
                self.console.print(f"[bold red]CPU/Memory monitoring error: {e}[/bold red]", end="\r")

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
        
        # Create profile list and validate
        chrome_profiles = [f"Profile {i}" for i in range(1, self.num_windows + 1)]
        chrome_profiles = self.validate_chrome_profiles(chrome_profiles)
        
        # Additional Chrome parameters for performance
        chrome_params = [
            "--disable-extensions",
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
            
            for profile in chrome_profiles:
                try:
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
        
        return True

    def arrange_windows(self):
        """Find and arrange Chrome windows in a grid"""
        try:
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

    def optimize_processes(self):
        """Optimize running Chrome processes"""
        try:
            # Get Chrome processes
            chrome_processes = []
            for proc in psutil.process_iter(['pid', 'name']):
                if 'chrome' in proc.info['name'].lower():
                    chrome_processes.append(proc)
            
            with Progress() as progress:
                task = progress.add_task("[cyan]Optimizing Chrome processes...", total=len(chrome_processes))
                
                for proc in chrome_processes:
                    try:
                        # Lower the priority of the process slightly
                        if platform.system() == "Windows":
                            p = psutil.Process(proc.info['pid'])
                            p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                        else:  # Unix-based systems
                            p = psutil.Process(proc.info['pid'])
                            p.nice(10)  # Slightly lower priority
                        
                        progress.update(task, advance=1)
                    except (psutil.NoSuchProcess, psutil.AccessDenied, Exception) as e:
                        self.console.print(f"[bold red]Error optimizing process {proc.info['pid']}: {e}[/bold red]")
                        progress.update(task, advance=1)
            
            self.console.print("[bold green]✅ Chrome processes optimized![/bold green]")
            return True
        except Exception as e:
            self.console.print(f"[bold red]Error during process optimization: {e}[/bold red]")
            return False

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

    def cleanup(self):
        """Clean up resources on exit"""
        self.running = False
        if self.network_thread and self.network_thread.is_alive():
            self.network_thread.join(timeout=1)
        if self.cpu_monitor_thread and self.cpu_monitor_thread.is_alive():
            self.cpu_monitor_thread.join(timeout=1)
        self.close_windows()

    def show_menu(self):
        """Display and handle the terminal menu"""
        while self.running:
            self.console.print("\n[bold blue]🖥️ TERMINAL MENU[/bold blue]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Option", style="cyan", justify="center")
            table.add_column("Action")
            table.add_row("1", "Close all Twitch windows")
            table.add_row("2", "Close a specific number of windows")
            table.add_row("3", "Show current network/CPU/memory usage")
            table.add_row("4", "Reload all windows")
            table.add_row("5", "Rearrange windows")
            table.add_row("6", "Change streamer")
            table.add_row("7", "Change stream quality")
            table.add_row("8", "Optimize resource usage")
            table.add_row("9", "Export current settings")
            table.add_row("10", "Import settings")
            table.add_row("11", "Exit script")
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
                self.console.print("[bold green]📡 Network, CPU and memory usage is displayed live in the terminal.[/bold green]")
            
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
                self.console.print("[bold yellow]Optimizing resource usage...[/bold yellow]")
                self.optimize_processes()
                
            elif choice == "9":
                self.export_settings()
                
            elif choice == "10":
                if self.import_settings():
                    if Confirm.ask("[bold yellow]Reload windows with imported settings?[/bold yellow]"):
                        self.close_windows()
                        self.launch_chrome_windows()
                        self.arrange_windows()
            
            elif choice == "11":
                self.console.print("[bold red]🔴 Exiting script...[/bold red]")
                self.running = False
            
            else:
                self.console.print("[bold red]❌ Invalid choice! Please select a valid option.[/bold red]")

    def run(self):
        """Main method to run the application"""
        self.console.print(Panel.fit("[bold cyan]Twitch Multi-Profile Launcher v3.0[/bold cyan]", 
                                    subtitle="Enhanced with Quality Selection, Import/Export, and Optimization"))
        
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
            
            # Start CPU/memory monitoring in a separate thread
            self.cpu_monitor_thread = threading.Thread(target=self.monitor_cpu_memory, daemon=True)
            self.cpu_monitor_thread.start()
            
            # Show menu
            self.show_menu()
            
        except Exception as e:
            self.console.print(f"[bold red]An error occurred: {e}[/bold red]")
        finally:
            self.cleanup()

if __name__ == "__main__":
    launcher = TwitchLauncher()
    launcher.run() 