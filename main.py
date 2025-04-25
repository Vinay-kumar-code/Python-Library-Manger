import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sys
import subprocess
import os
import importlib.util
import importlib.metadata # Added for potentially faster version lookup
import json
import threading
from queue import Queue # For thread communication

# --- Helper Functions ---

def run_pip_command(command, show_output=False):
    """Runs a pip command using subprocess and returns the output or status."""
    try:
        # Ensure pip commands target the correct Python environment
        python_executable = sys.executable
        full_command = [python_executable, "-m", "pip"] + command

        if show_output:
            result = subprocess.run(full_command, capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            return result.stdout.strip()
        else:
            subprocess.check_call(full_command, creationflags=subprocess.CREATE_NO_WINDOW)
            return True
    except subprocess.CalledProcessError as e:
        error_message = f"Error running command: {' '.join(command)}\n{e}"
        if e.stderr:
            error_message += f"\nStderr: {e.stderr.strip()}"
        if e.stdout:
            error_message += f"\nStdout: {e.stdout.strip()}"
        messagebox.showerror("Pip Error", error_message)
        return None
    except FileNotFoundError:
        messagebox.showerror("Pip Error", f"Command not found: {python_executable} -m pip. Is pip installed and in PATH?")
        return None
    except Exception as e:
        messagebox.showerror("Error", f"An unexpected error occurred: {e}")
        return None

def get_package_details(package_name):
    """Gets version, size, and dependencies for a package."""
    version = "N/A"
    size = "N/A"
    dependencies = []

    # Get version and dependencies using pip show
    try:
        output = run_pip_command(["show", package_name], show_output=True)
        if output:
            details = {}
            for line in output.splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    details[key.strip()] = value.strip()

            version = details.get("Version", "N/A")
            dependencies = details.get("Requires", "").split(", ") if details.get("Requires") else []

            # Get size (more reliable via pip show if location is available)
            location = details.get("Location")
            if location:
                package_path = os.path.join(location, package_name.replace('-', '_')) # Handle hyphens vs underscores
                # Try common variations if the direct path doesn't exist
                if not os.path.exists(package_path):
                     package_path = os.path.join(location, package_name)
                if not os.path.exists(package_path) and os.path.exists(location):
                     # Fallback: check top-level modules/packages in the location
                     potential_dirs = [d for d in os.listdir(location) if os.path.isdir(os.path.join(location, d))]
                     for d in potential_dirs:
                         if d.lower() == package_name.lower().replace('-', '_'):
                             package_path = os.path.join(location, d)
                             break

                if os.path.exists(package_path) and os.path.isdir(package_path):
                    total_size = 0
                    try:
                        for dirpath, dirnames, filenames in os.walk(package_path):
                            for f in filenames:
                                fp = os.path.join(dirpath, f)
                                if not os.path.islink(fp): # Avoid double counting links
                                    total_size += os.path.getsize(fp)
                        size = f"{total_size / (1024 ** 2):.2f} MB"
                    except OSError:
                        size = "Error reading size"
                else:
                     size = "N/A (Dir not found)" # Indicate path issue

    except Exception:
        # Fallback for version if pip show fails (less reliable)
        try:
            version = importlib.metadata.version(package_name)
        except importlib.metadata.PackageNotFoundError:
            # If pip show failed, try importlib.metadata as a fallback for version
            if version == "N/A":
                try:
                    version = importlib.metadata.version(package_name)
                except importlib.metadata.PackageNotFoundError:
                    version = "N/A" # Still not found
                except Exception:
                    version = "Error getting version" # Different error
        except Exception as e:
             # Catch potential errors in pip show execution itself
             version = "Error"
             size = "Error"
             dependencies = ["Error fetching details"]
             print(f"Error in get_package_details for {package_name}: {e}") # Log error

    return version, size, dependencies


def get_installed_packages():
    """Gets a list of installed packages using pip list."""
    output = run_pip_command(["list", "--format=json"], show_output=True)
    if output:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            messagebox.showerror("Error", "Failed to parse pip list output.")
            return []
    return []

def get_outdated_packages():
    """Gets a list of outdated packages using pip list."""
    output = run_pip_command(["list", "--outdated", "--format=json"], show_output=True)
    if output:
        try:
            # Pip might return empty string or non-json on no outdated packages
            if not output.strip():
                return []
            return json.loads(output)
        except json.JSONDecodeError:
            # Handle cases where pip might output warnings before JSON
            try:
                # Find the start of the JSON array
                json_start_index = output.find('[')
                if json_start_index != -1:
                    json_output = output[json_start_index:]
                    return json.loads(json_output)
                else:
                     messagebox.showwarning("Pip Warning", f"Could not parse outdated packages list. Output:\n{output}")
                     return []
            except json.JSONDecodeError:
                 messagebox.showerror("Error", f"Failed to parse pip list --outdated output even after searching for JSON.\nOutput:\n{output}")
                 return []
    # Return empty list if command failed or returned None
    return []


# --- GUI Application Class ---

class LibraryManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Python Library Manager")
        self.root.geometry("800x600")

        # --- Frames ---
        self.top_frame = ttk.Frame(root, padding="10")
        self.top_frame.pack(fill="x")

        self.tree_frame = ttk.Frame(root, padding="10")
        self.tree_frame.pack(fill="both", expand=True)

        self.bottom_frame = ttk.Frame(root, padding="10")
        self.bottom_frame.pack(fill="x")

        # --- Top Frame Widgets (Install) ---
        ttk.Label(self.top_frame, text="Install Package:").pack(side="left", padx=(0, 5))
        self.install_entry = ttk.Entry(self.top_frame, width=30)
        self.install_entry.pack(side="left", padx=5)
        self.install_button = ttk.Button(self.top_frame, text="Install", command=self.install_package)
        self.install_button.pack(side="left", padx=5)

        # --- Treeview (Package List) ---
        # --- Treeview (Package List) ---
        self.tree = ttk.Treeview(
            self.tree_frame,
            columns=("Package Name", "Version", "Size", "Dependencies"), # Add "Package Name" here
            show="headings" # Only show headings, no separate tree column needed now
        )
        # Define headings
        self.tree.heading("Package Name", text="Package Name") # Heading for the new column
        self.tree.heading("Version", text="Version")
        self.tree.heading("Size", text="Size")
        self.tree.heading("Dependencies", text="Dependencies")

        # Define column properties
        self.tree.column("Package Name", width=250, anchor="w", stretch=tk.YES) # Properties for the new column
        self.tree.column("Version", width=100, anchor="center", stretch=tk.NO)
        self.tree.column("Size", width=100, anchor="center", stretch=tk.NO)
        self.tree.column("Dependencies", width=300, anchor="w", stretch=tk.YES)

        # Scrollbars
        vsb = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self.tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)

        # Bind selection event to load details
        self.tree.bind("<<TreeviewSelect>>", self.on_package_select)

        # --- Bottom Frame Widgets (Actions) ---
        self.refresh_button = ttk.Button(self.bottom_frame, text="Refresh List", command=self.refresh_package_list_threaded)
        self.refresh_button.pack(side="left", padx=5)

        self.update_selected_button = ttk.Button(self.bottom_frame, text="Update Selected", command=self.update_selected_package)
        self.update_selected_button.pack(side="left", padx=5)

        self.check_updates_button = ttk.Button(self.bottom_frame, text="Check All Updates", command=self.check_all_updates_threaded)
        self.check_updates_button.pack(side="left", padx=5)

        self.uninstall_button = ttk.Button(self.bottom_frame, text="Uninstall Selected", command=self.uninstall_package)
        self.uninstall_button.pack(side="right", padx=5)

        # --- Status Bar ---
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w", padding="2 5")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.set_status("Ready.")

        # --- Threading Queue ---
        self.queue = Queue()
        self.root.after(100, self.process_queue) # Check queue periodically

        # --- Initial Population ---
        self.refresh_package_list_threaded()

    def set_status(self, message):
        self.status_var.set(message)
        self.root.update_idletasks() # Ensure status updates immediately

    def clear_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

    def refresh_package_list_threaded(self):
        """Starts a thread to get the list of installed packages."""
        self.set_status("Loading installed packages...")
        self._disable_buttons() # Disable buttons during refresh
        thread = threading.Thread(target=self._get_packages_worker)
        thread.start()

    def _get_packages_worker(self):
        """Worker thread to get package list."""
        packages = get_installed_packages()
        # Send packages back to main thread via queue
        self.queue.put(("populate_initial_list", packages))

    def populate_initial_list(self, packages):
        """Populates the tree with basic info (name, version) in the main thread."""
        self.clear_tree()
        if packages is None:
            self.set_status("Failed to load packages.")
            self._enable_buttons()
            return

        total = len(packages)
        for i, pkg in enumerate(packages):
            name = pkg.get('name', 'Unknown')
            version = pkg.get('version', 'N/A')
            # Insert name into the values tuple now
            self.tree.insert("", "end", iid=name, values=(name, version, "...", "...")) # Use name as item ID (iid)

        self.set_status(f"Loaded {total} packages. Select a package to view details.")
        self._enable_buttons() # Re-enable buttons after list is populated

    def on_package_select(self, event=None):
        """Handles package selection: triggers detail fetching in a thread."""
        selected_items = self.tree.selection()
        if not selected_items:
            return

        item_id = selected_items[0] # Get the first selected item's ID (which we set to the package name)
        # Retrieve values for the selected item
        current_values = self.tree.item(item_id, "values")
        if not current_values: # Should not happen if selection is valid, but check anyway
             return
        package_name = current_values[0] # Name is now the first value

        # Check if details are already loaded (or being loaded) by looking at Size/Dependencies columns
        # Indices shift because name is now values[0]: Version=1, Size=2, Deps=3
        if current_values[2] != "..." or current_values[3] != "...": # Check if size/deps are placeholders
             # Details already loaded or loading, do nothing
             # print(f"Details already loaded/loading for {package_name}")
             return

        self.set_status(f"Fetching details for {package_name}...")
        # Set placeholders to indicate loading, keeping name and version
        self.tree.item(item_id, values=(package_name, current_values[1], "Loading...", "Loading..."))

        # Start thread to fetch details
        thread = threading.Thread(target=self._get_details_worker, args=(item_id, package_name))
        thread.start()

    def _get_details_worker(self, item_id, package_name):
        """Worker thread to fetch package details."""
        version, size, dependencies = get_package_details(package_name)
        # Send details back to main thread via queue
        self.queue.put(("update_package_details", item_id, version, size, dependencies))

    def update_package_details(self, item_id, version, size, dependencies):
        """Updates the treeview item with fetched details in the main thread."""
        try:
            if self.tree.exists(item_id): # Check if item still exists
                 # Get the package name again from the item_id (which is the name)
                 # or retrieve current values to preserve the name column
                 current_vals = self.tree.item(item_id, "values")
                 package_name_in_tree = current_vals[0] # Get name from first column
                 self.tree.item(item_id, values=(package_name_in_tree, version, size, ", ".join(dependencies) if dependencies else "-"))
                 self.set_status(f"Details loaded for {package_name_in_tree}.")
            else:
                 print(f"Item {item_id} no longer exists in tree.") # Item might have been deleted by a refresh
        except tk.TclError as e:
             print(f"Error updating tree item {item_id}: {e}") # Catch potential Tcl errors if item is gone

    def _disable_buttons(self):
        """Disables action buttons."""
        self.refresh_button.config(state=tk.DISABLED)
        self.install_button.config(state=tk.DISABLED)
    def _enable_buttons(self):
        """Enables action buttons."""
        self.refresh_button.config(state=tk.NORMAL)
        self.install_button.config(state=tk.NORMAL)
        self.update_selected_button.config(state=tk.NORMAL)
        self.check_updates_button.config(state=tk.NORMAL)
        self.uninstall_button.config(state=tk.NORMAL)

    # --- Action Methods (Install, Uninstall, Update) ---

    def install_package(self):
        package_name = self.install_entry.get().strip()
        if not package_name:
            messagebox.showwarning("Input Needed", "Please enter a package name to install.")
            return

        self.set_status(f"Installing {package_name}...")
        self._disable_buttons()
        thread = threading.Thread(target=self._pip_command_worker, args=(["install", package_name], f"install_{package_name}"))
        thread.start()

    def uninstall_package(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Selection Needed", "Please select a package to uninstall.")
            return

        item_id = selected_items[0]
        package_name = self.tree.item(item_id, "values")[0] # Get name from values

        if messagebox.askyesno("Confirm Uninstall", f"Are you sure you want to uninstall '{package_name}'?"):
            self.set_status(f"Uninstalling {package_name}...")
            self._disable_buttons()
            thread = threading.Thread(target=self._pip_command_worker, args=(["uninstall", package_name, "-y"], f"uninstall_{package_name}"))
            thread.start()

    def update_selected_package(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Selection Needed", "Please select a package to update.")
            return

        item_id = selected_items[0]
        package_name = self.tree.item(item_id, "values")[0] # Get name from values

        self.set_status(f"Updating {package_name}...")
        self._disable_buttons()
        thread = threading.Thread(target=self._pip_command_worker, args=(["install", "--upgrade", package_name], f"update_{package_name}"))
        thread.start()

    def check_all_updates_threaded(self):
        self.set_status("Checking for all outdated packages...")
        self._disable_buttons()
        thread = threading.Thread(target=self._check_all_updates_worker)
        thread.start()

    def _check_all_updates_worker(self):
        """Worker thread to check for outdated packages."""
        outdated = get_outdated_packages()
        self.queue.put(("process_outdated_results", outdated))

    def process_outdated_results(self, outdated):
        """Handles the list of outdated packages in the main thread."""
        self._enable_buttons() # Re-enable buttons first

        if outdated is None: # Error occurred during check
            self.set_status("Failed to check for updates.")
            return

        if not outdated:
            self.set_status("All packages are up-to-date.")
            messagebox.showinfo("Updates", "All packages are up-to-date.")
            return

        outdated_info = "\n".join([f"- {pkg['name']} ({pkg['version']} -> {pkg['latest_version']})" for pkg in outdated])

        # Highlight outdated rows
        self._highlight_outdated(outdated)

        # Ask user if they want to update all
        if messagebox.askyesno("Updates Available", f"Found {len(outdated)} outdated packages:\n{outdated_info}\n\nDo you want to update all of them?"):
            self.update_multiple_packages_threaded(outdated)
        else:
            self.set_status(f"{len(outdated)} updates available. Outdated packages highlighted.")

    

        # Apply tag to outdated items (Ensure this loop is at the correct indentation)
        for item_id in self.tree.get_children():
            values = self.tree.item(item_id, "values")
            if not values: continue # Skip if item somehow has no values
            package_name = values[0] # Get name from values
            if package_name in outdated_names: # Ensure this block is indented correctly
                current_tags = list(self.tree.item(item_id, "tags"))
                if "outdated_row" not in current_tags: # Ensure this block is indented correctly
                    current_tags.append("outdated_row")
                    self.tree.item(item_id, tags=tuple(current_tags))

    def update_multiple_packages_threaded(self, packages_to_update):
        """Starts a thread to update multiple packages."""
        package_names = [pkg['name'] for pkg in packages_to_update]
        if not package_names:
            return
        self.set_status(f"Updating {len(package_names)} packages...")
        self._disable_buttons()
        thread = threading.Thread(target=self._pip_command_worker, args=(["install", "--upgrade"] + package_names, "update_multiple"))
        thread.start()

    def _pip_command_worker(self, command, action_id):
        """Generic worker thread for running pip commands."""
        success = run_pip_command(command)
        # Send result back to main thread via queue
        self.queue.put(("pip_command_complete", action_id, success, command))

    def process_pip_command_result(self, action_id, success, command):
        """Handles the result of a pip command in the main thread."""
        self._enable_buttons() # Always re-enable buttons

        action_parts = action_id.split('_', 1)
        action_type = action_parts[0]
        package_name = action_parts[1] if len(action_parts) > 1 else None

        if success:
            message = "Operation successful."
            if action_type == "install":
                message = f"'{package_name}' installed successfully."
            elif action_type == "uninstall":
                message = f"'{package_name}' uninstalled successfully."
            elif action_type == "update":
                 message = f"'{package_name}' updated successfully."
            elif action_type == "update_multiple":
                 message = f"{len(command) - 2} packages updated successfully." # command = ['install', '--upgrade', pkg1, pkg2,...]

            messagebox.showinfo("Success", message)
            self.refresh_package_list_threaded() # Refresh list on success
        else:
            # Error message should have been shown by run_pip_command
            self.set_status(f"Failed to {action_type} {package_name or 'packages'}. See error popup.")

    # --- Queue Processor ---
    def process_queue(self):
        """Processes messages from the worker threads."""
        try:
            while True: # Process all messages currently in the queue
                message = self.queue.get_nowait()
                msg_type = message[0]
                args = message[1:]

                if msg_type == "populate_initial_list":
                    self.populate_initial_list(*args)
                elif msg_type == "update_package_details":
                    self.update_package_details(*args)
                elif msg_type == "process_outdated_results":
                    self.process_outdated_results(*args)
                elif msg_type == "pip_command_complete":
                    self.process_pip_command_result(*args)
                # Add other message types as needed

        except Exception as e: # Use generic Exception to catch queue.Empty and others
            if "queue.Empty" not in str(type(e)): # Ignore queue empty error
                 print(f"Error processing queue: {e}")

        # Reschedule after processing
        self.root.after(100, self.process_queue)


# --- Main Execution ---
if __name__ == "__main__":
    root = tk.Tk()
    app = LibraryManagerApp(root)
    root.mainloop()
