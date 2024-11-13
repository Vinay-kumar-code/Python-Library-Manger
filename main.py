import tkinter as tk
from tkinter import messagebox
import sys
import pkg_resources
import pkgutil
import subprocess
import os
import importlib.util

def get_package_size(package_name):
    """Calculate the size of the package directory in bytes."""
    try:
        spec = importlib.util.find_spec(package_name)
        if not spec or not spec.submodule_search_locations:
            return "N/A"
        package_path = spec.submodule_search_locations[0]
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(package_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
        return f"{total_size / (1024 ** 2):.2f} MB"  # Convert bytes to MB
    except Exception:
        return "N/A"

def list_libraries():

    for widget in text_frame.winfo_children():
        widget.destroy()


    installed_packages = {pkg.key: pkg.version for pkg in pkg_resources.working_set}

    
    builtin_libs = {module.name for module in pkgutil.iter_modules() if module.module_finder is None}
    

    builtin_label = tk.Label(text_frame, text="Built-in Libraries:", font=("Arial", 12, "bold"))
    builtin_label.pack(anchor="w", padx=10)
    
    for lib in sorted(builtin_libs):
        label = tk.Label(text_frame, text=f"{lib}", anchor="w")
        label.pack(fill="x", padx=20)
    
    
    installed_label = tk.Label(text_frame, text="User-Installed Libraries:", font=("Arial", 12, "bold"))
    installed_label.pack(anchor="w", padx=10, pady=(10, 0))
    
    for lib, version in sorted(installed_packages.items()):
        frame = tk.Frame(text_frame)
        frame.pack(fill="x", padx=20)
        
    
        size = get_package_size(lib)
        
        label = tk.Label(frame, text=f"{lib}=={version} ({size})", anchor="w")
        label.pack(side="left")
        
        remove_button = tk.Button(frame, text="Remove", command=lambda lib=lib: remove_library(lib))
        remove_button.pack(side="right")

def remove_library(library_name):

    if messagebox.askyesno("Confirm Remove", f"Are you sure you want to remove '{library_name}'?"):
        try:
            
            subprocess.check_call([sys.executable, "-m", "pip", "uninstall", library_name, "-y"])
            messagebox.showinfo("Success", f"'{library_name}' has been removed.")
            list_libraries()  
        except subprocess.CalledProcessError:
            messagebox.showerror("Error", f"Failed to remove '{library_name}'.")


window = tk.Tk()
window.title("Python Libraries: Built-in and User-Installed")


text_frame = tk.Frame(window)
text_frame.pack(fill="both", expand=True)

canvas = tk.Canvas(text_frame)
scrollbar = tk.Scrollbar(text_frame, orient="vertical", command=canvas.yview)
scrollable_frame = tk.Frame(canvas)

scrollable_frame.bind(
    "<Configure>",
    lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
)

canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)

canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")
text_frame = scrollable_frame

refresh_button = tk.Button(window, text="Refresh List", command=list_libraries)
refresh_button.pack(pady=10)

list_libraries()

# Start the GUI loop
window.mainloop()
