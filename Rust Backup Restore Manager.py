# ============================================================
# Copyright © 2026 IRD Development. All rights reserved.
# ============================================================

import os
import re
import json
import queue
import threading
import zipfile
import shutil
import time
import tkinter as tk

from tkinter import filedialog, messagebox, ttk
from datetime import datetime

# Windows Registry Module
try:
    import winreg
except ImportError:
    winreg = None


# ============================================================
# CONFIGURATION & REGISTRY KEYS
# ============================================================

APP_TITLE = "Rust Project Backup & Restore Manager"
COPYRIGHT_TEXT = "Copyright © 2026 IRD Development. All rights reserved."
REG_SUBKEY = r"Software\IRD Rust Project Manager"
MAX_HISTORY_ITEMS = 15

# Junk folders and files that MUST be excluded
EXCLUDED_DIRECTORIES = {
    ".git",
    "target",
    ".vscode",
    ".idea",
    ".vs",
    "__pycache__",
    ".DS_Store",
    "Thumbs.db",
}

STORE_EXTENSIONS = {
    ".zip",
    ".7z",
    ".rar",
    ".gz",
    ".bz2",
    ".xz",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".bmp",
    ".ico",
    ".mp3",
    ".mp4",
    ".m4a",
    ".avi",
    ".mkv",
    ".mov",
    ".pdf",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
}

ZIP_COMPRESSION = zipfile.ZIP_DEFLATED
PROGRESS_UPDATE_INTERVAL = 0.15


class RustBackupApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("980x830")
        self.root.minsize(900, 750)

        # ----------------------------------------------------
        # VARIABLES - BACKUP
        # ----------------------------------------------------

        self.project_path = tk.StringVar()
        self.backup_path = tk.StringVar()
        self.backup_name = tk.StringVar()

        self.backup_mode = tk.StringVar(value="source")
        self.backup_format = tk.StringVar(value="zip")
        self.zip_compress_level = tk.IntVar(value=4)

        self.same_as_project = tk.BooleanVar(value=False)

        # ----------------------------------------------------
        # VARIABLES - RESTORE
        # ----------------------------------------------------

        self.restore_file_path = tk.StringVar()
        self.restore_dest_path = tk.StringVar()

        # ----------------------------------------------------
        # HISTORY LISTS (BACKUP & RESTORE)
        # ----------------------------------------------------

        self.project_history = []
        self.backup_history = []
        self.restore_file_history = []
        self.restore_dest_history = []

        # ----------------------------------------------------
        # VARIABLES - PROGRESS & STATUS
        # ----------------------------------------------------

        self.status_text = tk.StringVar(value="Ready.")
        self.file_count_text = tk.StringVar(value="Files: 0 / 0")
        self.size_text = tk.StringVar(value="Size: 0 B / 0 B")
        self.speed_text = tk.StringVar(value="Speed: --")
        self.eta_text = tk.StringVar(value="ETA: --")

        self.progress_value = tk.DoubleVar(value=0)

        # ----------------------------------------------------
        # INTERNAL STATE
        # ----------------------------------------------------

        self.files_to_backup = []
        self.total_size = 0

        self.worker_queue = queue.Queue()
        self.worker_thread = None
        self.is_working = False
        self.start_time = None

        # Load configuration & histories from Windows Registry
        self.load_settings_from_registry()

        # ----------------------------------------------------
        # UI BUILD & EVENT HANDLERS
        # ----------------------------------------------------

        self.build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self.process_worker_queue)

    # ========================================================
    # REGISTRY MANAGEMENT
    # ========================================================

    def load_settings_from_registry(self):
        if not winreg:
            return

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_SUBKEY, 0, winreg.KEY_READ) as key:
                def get_val(name, default=""):
                    try:
                        val, _ = winreg.QueryValueEx(key, name)
                        return val
                    except OSError:
                        return default

                self.project_path.set(get_val("ProjectPath", ""))
                self.backup_path.set(get_val("BackupPath", ""))
                self.restore_file_path.set(get_val("RestoreFilePath", ""))
                self.restore_dest_path.set(get_val("RestoreDestPath", ""))
                self.backup_mode.set(get_val("BackupMode", "source"))
                self.backup_format.set(get_val("BackupFormat", "zip"))
                self.zip_compress_level.set(int(get_val("ZipCompressLevel", 4)))
                self.same_as_project.set(bool(get_val("SameAsProject", 0)))

                try:
                    self.project_history = json.loads(get_val("ProjectHistory", "[]"))
                except Exception:
                    self.project_history = []

                try:
                    self.backup_history = json.loads(get_val("BackupHistory", "[]"))
                except Exception:
                    self.backup_history = []

                try:
                    self.restore_file_history = json.loads(get_val("RestoreFileHistory", "[]"))
                except Exception:
                    self.restore_file_history = []

                try:
                    self.restore_dest_history = json.loads(get_val("RestoreDestHistory", "[]"))
                except Exception:
                    self.restore_dest_history = []

        except OSError:
            pass

    def save_settings_to_registry(self):
        if not winreg:
            return

        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_SUBKEY) as key:
                winreg.SetValueEx(key, "ProjectPath", 0, winreg.REG_SZ, self.project_path.get())
                winreg.SetValueEx(key, "BackupPath", 0, winreg.REG_SZ, self.backup_path.get())
                winreg.SetValueEx(key, "RestoreFilePath", 0, winreg.REG_SZ, self.restore_file_path.get())
                winreg.SetValueEx(key, "RestoreDestPath", 0, winreg.REG_SZ, self.restore_dest_path.get())
                winreg.SetValueEx(key, "BackupMode", 0, winreg.REG_SZ, self.backup_mode.get())
                winreg.SetValueEx(key, "BackupFormat", 0, winreg.REG_SZ, self.backup_format.get())
                winreg.SetValueEx(key, "ZipCompressLevel", 0, winreg.REG_DWORD, int(self.zip_compress_level.get()))
                winreg.SetValueEx(key, "SameAsProject", 0, winreg.REG_DWORD, int(self.same_as_project.get()))
                winreg.SetValueEx(key, "ProjectHistory", 0, winreg.REG_SZ, json.dumps(self.project_history))
                winreg.SetValueEx(key, "BackupHistory", 0, winreg.REG_SZ, json.dumps(self.backup_history))
                winreg.SetValueEx(key, "RestoreFileHistory", 0, winreg.REG_SZ, json.dumps(self.restore_file_history))
                winreg.SetValueEx(key, "RestoreDestHistory", 0, winreg.REG_SZ, json.dumps(self.restore_dest_history))
        except OSError as e:
            print(f"Failed to save settings to registry: {e}")

    def add_project_history(self, path):
        path = os.path.abspath(path.strip())
        if not path:
            return
        if path in self.project_history:
            self.project_history.remove(path)
        self.project_history.insert(0, path)
        self.project_history = self.project_history[:MAX_HISTORY_ITEMS]
        if hasattr(self, 'project_combo'):
            self.project_combo['values'] = self.project_history

    def add_backup_history(self, path):
        path = os.path.abspath(path.strip())
        if not path:
            return
        if path in self.backup_history:
            self.backup_history.remove(path)
        self.backup_history.insert(0, path)
        self.backup_history = self.backup_history[:MAX_HISTORY_ITEMS]
        if hasattr(self, 'backup_combo'):
            self.backup_combo['values'] = self.backup_history

    def add_restore_file_history(self, path):
        path = os.path.abspath(path.strip())
        if not path:
            return
        if path in self.restore_file_history:
            self.restore_file_history.remove(path)
        self.restore_file_history.insert(0, path)
        self.restore_file_history = self.restore_file_history[:MAX_HISTORY_ITEMS]
        if hasattr(self, 'restore_file_combo'):
            self.restore_file_combo['values'] = self.restore_file_history

    def add_restore_dest_history(self, path):
        path = os.path.abspath(path.strip())
        if not path:
            return
        if path in self.restore_dest_history:
            self.restore_dest_history.remove(path)
        self.restore_dest_history.insert(0, path)
        self.restore_dest_history = self.restore_dest_history[:MAX_HISTORY_ITEMS]
        if hasattr(self, 'restore_dest_combo'):
            self.restore_dest_combo['values'] = self.restore_dest_history

    def on_close(self):
        self.save_settings_to_registry()
        self.root.destroy()

    # ========================================================
    # UI BUILD
    # ========================================================

    def build_ui(self):
        main = ttk.Frame(self.root, padding=15)
        main.pack(fill="both", expand=True)

        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill="both", expand=True, pady=(0, 10))

        # TAB 1: BACKUP
        self.backup_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.backup_tab, text="  Backup Project  ")
        self.build_backup_tab(self.backup_tab)

        # TAB 2: RESTORE
        self.restore_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.restore_tab, text="  Restore Project  ")
        self.build_restore_tab(self.restore_tab)

        # GLOBAL PROGRESS & STATUS FRAME
        progress_frame = ttk.LabelFrame(main, text="Operation Progress", padding=10)
        progress_frame.pack(fill="x")

        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_value, maximum=100)
        self.progress_bar.pack(fill="x", pady=(0, 8))

        info_frame = ttk.Frame(progress_frame)
        info_frame.pack(fill="x")

        ttk.Label(info_frame, textvariable=self.file_count_text).pack(side="left")
        ttk.Label(info_frame, textvariable=self.size_text).pack(side="left", padx=20)
        ttk.Label(info_frame, textvariable=self.speed_text).pack(side="left", padx=20)
        ttk.Label(info_frame, textvariable=self.eta_text).pack(side="left")

        ttk.Label(progress_frame, textvariable=self.status_text).pack(anchor="w", pady=(8, 0))

        footer_label = ttk.Label(main, text=COPYRIGHT_TEXT, font=("Segoe UI", 10), foreground="#666666")
        footer_label.pack(side="bottom", pady=(8, 0))

    # ========================================================
    # TAB 1 UI: BACKUP
    # ========================================================

    def build_backup_tab(self, parent):
        # 1. Project Folder
        project_frame = ttk.LabelFrame(parent, text="Project Folder", padding=10)
        project_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(project_frame, text="Project:").grid(row=0, column=0, sticky="w")

        self.project_combo = ttk.Combobox(
            project_frame,
            textvariable=self.project_path,
            values=self.project_history
        )
        self.project_combo.grid(row=0, column=1, sticky="ew", padx=8)
        self.project_combo.bind("<Button-1>", lambda e: self.show_dropdown(self.project_combo))
        self.project_combo.bind("<<ComboboxSelected>>", self.on_project_selected)

        self.project_browse_button = ttk.Button(project_frame, text="Browse", command=self.browse_project)
        self.project_browse_button.grid(row=0, column=2)
        project_frame.columnconfigure(1, weight=1)

        # 2. Backup Location
        backup_frame = ttk.LabelFrame(parent, text="Backup Location", padding=10)
        backup_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(backup_frame, text="Folder:").grid(row=0, column=0, sticky="w")

        self.backup_combo = ttk.Combobox(
            backup_frame,
            textvariable=self.backup_path,
            values=self.backup_history
        )
        self.backup_combo.grid(row=0, column=1, sticky="ew", padx=8)
        self.backup_combo.bind("<Button-1>", lambda e: self.show_dropdown(self.backup_combo))

        self.backup_browse_button = ttk.Button(backup_frame, text="Browse", command=self.browse_backup_folder)
        self.backup_browse_button.grid(row=0, column=2)

        self.same_checkbox = ttk.Checkbutton(
            backup_frame,
            text="Same as Project Folder",
            variable=self.same_as_project,
            command=self.toggle_same_as_project
        )
        self.same_checkbox.grid(row=1, column=1, sticky="w", pady=(8, 0))
        backup_frame.columnconfigure(1, weight=1)

        # 3. Backup Name
        name_frame = ttk.LabelFrame(parent, text="Backup Name", padding=10)
        name_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(name_frame, text="Name:").grid(row=0, column=0, sticky="w")

        self.name_entry = ttk.Entry(name_frame, textvariable=self.backup_name)
        self.name_entry.grid(row=0, column=1, sticky="ew", padx=8)

        self.name_browse_button = ttk.Button(name_frame, text="Browse", command=self.browse_existing_backup_name)
        self.name_browse_button.grid(row=0, column=2, padx=(0, 8))

        ttk.Label(name_frame, text="Extension is added automatically").grid(row=0, column=3, sticky="w")
        name_frame.columnconfigure(1, weight=1)

        # 4. Backup Options
        options_frame = ttk.LabelFrame(parent, text="Backup Options", padding=10)
        options_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(options_frame, text="Backup Mode:").grid(row=0, column=0, sticky="w")

        self.radio_mode_src = ttk.Radiobutton(
            options_frame, text="Source Code Only", variable=self.backup_mode, value="source", command=self.mode_changed
        )
        self.radio_mode_src.grid(row=0, column=1, sticky="w", padx=10)

        self.radio_mode_full = ttk.Radiobutton(
            options_frame, text="Full Project", variable=self.backup_mode, value="full", command=self.mode_changed
        )
        self.radio_mode_full.grid(row=0, column=2, sticky="w", padx=10)

        # Format & Level ZIP
        ttk.Label(options_frame, text="Format:").grid(row=1, column=0, sticky="w", pady=(10, 0))

        zip_wrapper = ttk.Frame(options_frame)
        zip_wrapper.grid(row=1, column=1, sticky="w", padx=10, pady=(10, 0))

        self.zip_radio = ttk.Radiobutton(
            zip_wrapper, text="ZIP", variable=self.backup_format, value="zip", command=self.mode_changed
        )
        self.zip_radio.pack(side="left")

        self.level_combo = ttk.Combobox(
            zip_wrapper, textvariable=self.zip_compress_level, values=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], width=3, state="readonly"
        )
        self.level_combo.pack(side="left", padx=(6, 0))

        self.txt_radio = ttk.Radiobutton(
            options_frame, text="TXT (src/*.rs & Cargo.toml)", variable=self.backup_format, value="txt", command=self.mode_changed
        )
        self.txt_radio.grid(row=1, column=2, sticky="w", padx=10, pady=(10, 0))

        # Action Buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill="x", pady=(0, 10))

        self.scan_button = ttk.Button(button_frame, text="Scan Project", command=self.scan_project)
        self.scan_button.pack(side="left")

        self.backup_button = ttk.Button(button_frame, text="Create Backup", command=self.create_backup)
        self.backup_button.pack(side="left", padx=8)

        ttk.Label(
            button_frame,
            text="Tip: Use Ctrl+A, Ctrl+Click, or Shift+Click to choose specific files to backup.",
            font=("Segoe UI", 8, "italic"),
            foreground="#555555"
        ).pack(side="right")

        # 5. Preview List
        preview_frame = ttk.LabelFrame(parent, text="Project Files Preview (Selectable)", padding=8)
        preview_frame.pack(fill="both", expand=True)

        list_frame = ttk.Frame(preview_frame)
        list_frame.pack(fill="both", expand=True)

        self.preview_listbox = tk.Listbox(
            list_frame,
            font=("Consolas", 9),
            selectmode="extended",
            exportselection=False
        )
        self.preview_listbox.pack(side="left", fill="both", expand=True)

        preview_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.preview_listbox.yview)
        preview_scrollbar.pack(side="right", fill="y")
        self.preview_listbox.config(yscrollcommand=preview_scrollbar.set)

        self.preview_listbox.bind("<Control-a>", self.select_all_preview)
        self.preview_listbox.bind("<Control-A>", self.select_all_preview)
        self.preview_listbox.bind("<<ListboxSelect>>", self.on_preview_selection_changed)

    # ========================================================
    # TAB 2 UI: RESTORE
    # ========================================================

    def build_restore_tab(self, parent):
        # 1. Backup File Selection (Combobox with History)
        source_frame = ttk.LabelFrame(parent, text="Select Backup File (.zip or .txt)", padding=10)
        source_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(source_frame, text="Backup File:").grid(row=0, column=0, sticky="w")

        self.restore_file_combo = ttk.Combobox(
            source_frame,
            textvariable=self.restore_file_path,
            values=self.restore_file_history
        )
        self.restore_file_combo.grid(row=0, column=1, sticky="ew", padx=8)
        self.restore_file_combo.bind("<Button-1>", lambda e: self.show_dropdown(self.restore_file_combo))

        self.restore_file_browse_button = ttk.Button(source_frame, text="Browse", command=self.browse_restore_file)
        self.restore_file_browse_button.grid(row=0, column=2)
        source_frame.columnconfigure(1, weight=1)

        # 2. Destination Folder Selection (Combobox with History)
        dest_frame = ttk.LabelFrame(parent, text="Destination Folder (Where to Restore)", padding=10)
        dest_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(dest_frame, text="Restore To:").grid(row=0, column=0, sticky="w")

        self.restore_dest_combo = ttk.Combobox(
            dest_frame,
            textvariable=self.restore_dest_path,
            values=self.restore_dest_history
        )
        self.restore_dest_combo.grid(row=0, column=1, sticky="ew", padx=8)
        self.restore_dest_combo.bind("<Button-1>", lambda e: self.show_dropdown(self.restore_dest_combo))

        self.restore_dest_browse_button = ttk.Button(dest_frame, text="Browse", command=self.browse_restore_dest)
        self.restore_dest_browse_button.grid(row=0, column=2)
        dest_frame.columnconfigure(1, weight=1)

        # Action Button
        action_frame = ttk.Frame(parent)
        action_frame.pack(fill="x", pady=10)

        self.restore_button = ttk.Button(action_frame, text="Start Restore Project", command=self.create_restore)
        self.restore_button.pack(side="left")

        # Info Box
        info_help_frame = ttk.LabelFrame(parent, text="Restore Information", padding=12)
        info_help_frame.pack(fill="both", expand=True)

        help_text = (
            "Project Restoration Guidelines:\n\n"
            "1. ZIP Backup Archive (.zip):\n"
            "   - All project files and directory hierarchy will be fully extracted to your selected target folder.\n\n"
            "2. TXT Backup File (.txt):\n"
            "   - Reconstructs Cargo.toml in root and all .rs source files located inside src/.\n\n"
            "Ensure the destination path is valid and accessible before initiating restore."
        )
        lbl = ttk.Label(info_help_frame, text=help_text, justify="left", font=("Segoe UI", 9))
        lbl.pack(anchor="nw", fill="both", expand=True)

    # ========================================================
    # BROWSING & SELECTION HELPERS
    # ========================================================

    def show_dropdown(self, combobox_widget):
        self.root.after(10, lambda: combobox_widget.event_generate("<Down>"))

    def select_all_preview(self, event=None):
        self.preview_listbox.select_set(0, tk.END)
        self.on_preview_selection_changed()
        return "break"

    def on_preview_selection_changed(self, event=None):
        selected_indices = self.preview_listbox.curselection()
        if not selected_indices:
            self.file_count_text.set(f"Selected: 0 / {len(self.files_to_backup):,} files")
            self.size_text.set("Size: 0 B")
            return

        selected_size = sum(self.files_to_backup[i]["size"] for i in selected_indices if i < len(self.files_to_backup))
        self.file_count_text.set(f"Selected: {len(selected_indices):,} / {len(self.files_to_backup):,} files")
        self.size_text.set(f"Size: {self.format_bytes(selected_size)}")

    def on_project_selected(self, event=None):
        folder = self.project_path.get().strip()
        if folder:
            project_name = os.path.basename(os.path.normpath(folder))
            self.set_default_backup_name(project_name)
            if self.same_as_project.get():
                self.backup_path.set(folder)

    def browse_project(self):
        if self.is_working:
            return

        folder = filedialog.askdirectory(title="Select Rust Project Folder")
        if not folder:
            return

        abs_path = os.path.abspath(folder)
        self.project_path.set(abs_path)
        self.add_project_history(abs_path)

        project_name = os.path.basename(os.path.normpath(abs_path))
        self.set_default_backup_name(project_name)

        if self.same_as_project.get():
            self.backup_path.set(abs_path)

        self.status_text.set("Project selected. Click Scan Project.")

    def browse_backup_folder(self):
        if self.is_working:
            return

        folder = filedialog.askdirectory(title="Select Backup Folder")
        if not folder:
            return

        abs_path = os.path.abspath(folder)
        self.same_as_project.set(False)
        self.backup_path.set(abs_path)
        self.add_backup_history(abs_path)

    def browse_existing_backup_name(self):
        if self.is_working:
            return

        initial_dir = self.backup_path.get().strip()
        if not initial_dir or not os.path.isdir(initial_dir):
            initial_dir = self.project_path.get().strip()
        if not initial_dir or not os.path.isdir(initial_dir):
            initial_dir = os.getcwd()

        file_selected = filedialog.askopenfilename(
            title="Select Existing Backup Name",
            initialdir=initial_dir,
            filetypes=[("Backup Files", "*.zip;*.txt"), ("ZIP Archives", "*.zip"), ("TXT Files", "*.txt"), ("All Files", "*.*")]
        )
        if file_selected:
            filename = os.path.basename(file_selected)
            name_without_ext = os.path.splitext(filename)[0]
            self.backup_name.set(name_without_ext)
            self.apply_backup_name_suffix()

    def browse_restore_file(self):
        if self.is_working:
            return

        file_selected = filedialog.askopenfilename(
            title="Select Backup File",
            filetypes=[("Backup Files", "*.zip;*.txt"), ("ZIP Archives", "*.zip"), ("TXT Files", "*.txt"), ("All Files", "*.*")]
        )
        if file_selected:
            abs_path = os.path.abspath(file_selected)
            self.restore_file_path.set(abs_path)
            self.add_restore_file_history(abs_path)

    def browse_restore_dest(self):
        if self.is_working:
            return

        folder = filedialog.askdirectory(title="Select Destination Folder to Restore")
        if folder:
            abs_path = os.path.abspath(folder)
            self.restore_dest_path.set(abs_path)
            self.add_restore_dest_history(abs_path)

    def toggle_same_as_project(self):
        if self.same_as_project.get():
            project = self.project_path.get().strip()
            if project:
                self.backup_path.set(os.path.abspath(project))
        else:
            self.backup_path.set("")

    def set_default_backup_name(self, project_name):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        base_name = f"{project_name}_{timestamp}"
        self.backup_name.set(base_name)
        self.apply_backup_name_suffix()

    def apply_backup_name_suffix(self):
        current_name = self.backup_name.get().strip()
        if not current_name:
            return

        clean_name = re.sub(r'(_sc|_full)$', '', current_name, flags=re.IGNORECASE)

        if self.backup_format.get() == "zip":
            if self.backup_mode.get() == "source":
                clean_name += "_sc"
            elif self.backup_mode.get() == "full":
                clean_name += "_full"

        self.backup_name.set(clean_name)

    def mode_changed(self):
        self.apply_backup_name_suffix()
        if not self.project_path.get():
            return
        self.status_text.set("Backup options changed. Click Scan Project to refresh preview.")

    # ========================================================
    # SCAN PROJECT
    # ========================================================

    def scan_project(self):
        if self.is_working:
            return

        project = self.project_path.get().strip()
        if not project:
            messagebox.showwarning("Project Required", "Please select a project folder first.")
            return

        if not os.path.isdir(project):
            messagebox.showerror("Invalid Project", "The selected project folder does not exist.")
            return

        self.add_project_history(project)

        try:
            self.files_to_backup = self.get_files_to_backup()
            self.total_size = sum(item["size"] for item in self.files_to_backup)
            self.update_preview()

            self.status_text.set(f"Scan complete: {len(self.files_to_backup):,} files found.")
            self.on_preview_selection_changed()

        except Exception as e:
            messagebox.showerror("Scan Error", str(e))

    # ========================================================
    # GET FILES
    # ========================================================

    def get_files_to_backup(self):
        project = os.path.abspath(self.project_path.get())
        backup_folder = os.path.abspath(self.backup_path.get()) if self.backup_path.get().strip() else None
        files = []

        mode = self.backup_mode.get()
        backup_format = self.backup_format.get()

        for root, dirs, filenames in os.walk(project):
            dirs[:] = [d for d in dirs if d.lower() not in {x.lower() for x in EXCLUDED_DIRECTORIES}]
            current_root = os.path.abspath(root)

            if backup_folder:
                if backup_folder != project and self.is_subpath(backup_folder, current_root):
                    dirs[:] = [d for d in dirs if os.path.abspath(os.path.join(current_root, d)) != backup_folder]

            for filename in filenames:
                full_path = os.path.join(root, filename)
                relative_path = os.path.relpath(full_path, project)
                rel_normalized = relative_path.replace("\\", "/")

                if backup_format == "txt":
                    is_src_rs = (rel_normalized.startswith("src/")) and rel_normalized.lower().endswith(".rs")
                    is_root_toml = (os.sep not in relative_path and "/" not in relative_path) and rel_normalized.lower().endswith(".toml")
                    if not (is_src_rs or is_root_toml):
                        continue

                if self.is_current_backup_file(filename):
                    continue

                if mode == "source" and backup_format != "txt":
                    if not self.is_source_file(filename):
                        continue

                try:
                    size = os.path.getsize(full_path)
                except OSError:
                    continue

                files.append({
                    "absolute": full_path,
                    "relative": relative_path,
                    "size": size
                })

        files.sort(key=lambda x: x["relative"].lower())
        return files

    def is_source_file(self, filename):
        lower = filename.lower()
        if lower.endswith((".rs", ".toml", ".lock", ".md", ".json", ".yaml", ".yml", ".proto", ".sql")):
            return True
        if lower in {"cargo.toml", "cargo.lock", "build.rs", ".gitignore", ".env.example"}:
            return True
        return False

    def is_current_backup_file(self, filename):
        backup_name = self.sanitize_filename(self.backup_name.get().strip())
        if not backup_name:
            return False
        zip_name = backup_name + ".zip"
        txt_name = backup_name + ".txt"
        return filename.lower() in {zip_name.lower(), txt_name.lower()}

    @staticmethod
    def is_subpath(parent, child):
        try:
            return os.path.commonpath([parent, child]) == parent
        except ValueError:
            return False

    def update_preview(self):
        self.preview_listbox.delete(0, tk.END)
        project_name = os.path.basename(os.path.normpath(self.project_path.get()))
        for item in self.files_to_backup:
            display_path = os.path.join(project_name, item["relative"])
            self.preview_listbox.insert(tk.END, display_path)

        self.preview_listbox.select_set(0, tk.END)

    # ========================================================
    # CREATE BACKUP
    # ========================================================

    def create_backup(self):
        if self.is_working:
            return

        project = self.project_path.get().strip()
        if not project:
            messagebox.showwarning("Project Required", "Please select a project folder first.")
            return

        if not os.path.isdir(project):
            messagebox.showerror("Invalid Project", "The selected project folder does not exist.")
            return

        selected_indices = self.preview_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("No Files Selected", "Please select at least one file from the preview list to backup (use Ctrl+A to select all).")
            return

        worker_files = [self.files_to_backup[i] for i in selected_indices if i < len(self.files_to_backup)]
        worker_total_size = sum(item["size"] for item in worker_files)

        backup_folder = self.backup_path.get().strip()
        if not backup_folder:
            if self.same_as_project.get():
                backup_folder = project
            else:
                messagebox.showwarning("Backup Folder Required", "Please select a backup folder.")
                return

        backup_folder = os.path.abspath(backup_folder)
        try:
            os.makedirs(backup_folder, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Backup Folder Error", str(e))
            return

        self.add_project_history(project)
        self.add_backup_history(backup_folder)
        self.save_settings_to_registry()

        backup_name = self.backup_name.get().strip()
        if not backup_name:
            project_name = os.path.basename(os.path.normpath(project))
            self.set_default_backup_name(project_name)
            backup_name = self.backup_name.get().strip()

        backup_name = self.sanitize_filename(backup_name)
        if not backup_name:
            messagebox.showerror("Invalid Backup Name", "Please enter a valid backup name.")
            return

        backup_format = self.backup_format.get()
        extension = ".zip" if backup_format == "zip" else ".txt"
        output_path = os.path.join(backup_folder, backup_name + extension)

        if os.path.exists(output_path):
            answer = messagebox.askyesno(
                "File Exists",
                f"The backup file already exists:\n\n{output_path}\n\nDo you want to replace it?"
            )
            if not answer:
                return

        worker_mode = self.backup_mode.get()
        worker_format = self.backup_format.get()
        worker_output = output_path
        worker_project = os.path.abspath(project)
        worker_backup_name = backup_name
        worker_compress_level = self.zip_compress_level.get()

        self.set_ui_busy(True)
        self.progress_value.set(0)
        self.file_count_text.set(f"Files: 0 / {len(worker_files):,}")
        self.size_text.set(f"Size: 0 B / {self.format_bytes(worker_total_size)}")
        self.speed_text.set("Speed: --")
        self.eta_text.set("ETA: --")
        self.status_text.set("Starting backup...")

        self.start_time = time.perf_counter()

        self.worker_thread = threading.Thread(
            target=self.backup_worker,
            args=(
                worker_files,
                worker_mode,
                worker_format,
                worker_output,
                worker_project,
                worker_backup_name,
                worker_compress_level,
                worker_total_size,
            ),
            daemon=True
        )
        self.worker_thread.start()

    # ========================================================
    # BACKUP WORKERS
    # ========================================================

    def backup_worker(self, files, mode, backup_format, output_path, project_path, backup_name, compress_level, total_size):
        try:
            if backup_format == "zip":
                self.create_zip_backup_worker(files, mode, output_path, project_path, backup_name, compress_level, total_size)
            else:
                self.create_txt_backup_worker(files, mode, output_path, project_path, backup_name, total_size)
        except Exception as e:
            self.worker_queue.put({"type": "error", "message": str(e)})

    def create_zip_backup_worker(self, files, mode, output_path, project_path, backup_name, compress_level, total_size):
        project_name = os.path.basename(os.path.normpath(project_path))
        total_files = len(files)
        processed_files = 0
        processed_bytes = 0
        last_update = 0
        temp_path = output_path + ".tmp"

        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

        try:
            with zipfile.ZipFile(
                temp_path,
                mode="w",
                compression=ZIP_COMPRESSION if compress_level > 0 else zipfile.ZIP_STORED,
                compresslevel=compress_level if compress_level > 0 else None
            ) as zf:
                project_info = self.build_project_information(
                    project_path=project_path,
                    project_name=project_name,
                    backup_name=backup_name,
                    mode=mode,
                    files=files
                )
                zf.writestr(f"{project_name}/PROJECT_INFORMATION.txt", project_info)

                for index, item in enumerate(files, start=1):
                    absolute_path = item["absolute"]
                    relative_path = item["relative"]
                    archive_path = os.path.join(project_name, relative_path).replace("\\", "/")

                    extension = os.path.splitext(absolute_path)[1].lower()
                    compression = zipfile.ZIP_STORED if (extension in STORE_EXTENSIONS or compress_level == 0) else ZIP_COMPRESSION

                    with open(absolute_path, "rb") as source:
                        zip_info = zipfile.ZipInfo(archive_path)
                        try:
                            stat = os.stat(absolute_path)
                            zip_info.date_time = datetime.fromtimestamp(stat.st_mtime).timetuple()[:6]
                            zip_info.external_attr = (stat.st_mode & 0xFFFF) << 16
                        except OSError:
                            pass

                        zip_info.compress_type = compression

                        with zf.open(zip_info, mode="w") as destination:
                            while True:
                                chunk = source.read(1024 * 1024)
                                if not chunk:
                                    break
                                destination.write(chunk)
                                processed_bytes += len(chunk)
                                now = time.perf_counter()
                                if now - last_update >= PROGRESS_UPDATE_INTERVAL:
                                    self.send_progress(processed_files, total_files, processed_bytes, total_size, now)
                                    last_update = now

                    processed_files += 1
                    now = time.perf_counter()
                    self.send_progress(processed_files, total_files, processed_bytes, total_size, now)

            if os.path.exists(output_path):
                os.remove(output_path)

            os.replace(temp_path, output_path)
            elapsed = time.perf_counter() - self.start_time

            self.worker_queue.put({
                "type": "done",
                "action": "Backup",
                "path": output_path,
                "files": total_files,
                "bytes": processed_bytes,
                "elapsed": elapsed
            })

        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise

    def create_txt_backup_worker(self, files, mode, output_path, project_path, backup_name, total_size):
        project_name = os.path.basename(os.path.normpath(project_path))
        total_files = len(files)
        processed_files = 0
        processed_bytes = 0
        last_update = 0
        temp_path = output_path + ".tmp"

        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

        try:
            with open(temp_path, "w", encoding="utf-8", errors="replace", newline="") as output:
                project_info = self.build_project_information(
                    project_path=project_path,
                    project_name=project_name,
                    backup_name=backup_name,
                    mode=mode,
                    files=files
                )
                output.write(project_info + "\n\n" + "=" * 70 + "\nPROJECT FILE CONTENTS\n" + "=" * 70 + "\n\n")

                for item in files:
                    absolute_path = item["absolute"]
                    relative_path = item["relative"]
                    display_path = os.path.join(project_name, relative_path).replace("\\", "/")

                    output.write(f"<<<--- BEGIN_FILE: {display_path} --->>>\n")

                    with open(absolute_path, "r", encoding="utf-8", errors="replace") as source:
                        while True:
                            chunk = source.read(1024 * 1024)
                            if not chunk:
                                break
                            output.write(chunk)
                            processed_bytes += len(chunk.encode("utf-8", errors="replace"))
                            now = time.perf_counter()
                            if now - last_update >= PROGRESS_UPDATE_INTERVAL:
                                self.send_progress(processed_files, total_files, processed_bytes, total_size, now)
                                last_update = now

                    output.write("\n<<<--- END_FILE --->>>\n\n")
                    processed_files += 1
                    now = time.perf_counter()
                    self.send_progress(processed_files, total_files, processed_bytes, total_size, now)

            if os.path.exists(output_path):
                os.remove(output_path)

            os.replace(temp_path, output_path)
            elapsed = time.perf_counter() - self.start_time

            self.worker_queue.put({
                "type": "done",
                "action": "Backup",
                "path": output_path,
                "files": total_files,
                "bytes": processed_bytes,
                "elapsed": elapsed
            })

        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise

    # ========================================================
    # CREATE RESTORE
    # ========================================================

    def create_restore(self):
        if self.is_working:
            return

        source_file = self.restore_file_path.get().strip()
        dest_folder = self.restore_dest_path.get().strip()

        if not source_file:
            messagebox.showwarning("File Required", "Please select a backup file (.zip or .txt) first.")
            return

        if not os.path.isfile(source_file):
            messagebox.showerror("File Error", "The selected backup file does not exist.")
            return

        if not dest_folder:
            messagebox.showwarning("Destination Required", "Please select a destination folder.")
            return

        try:
            os.makedirs(dest_folder, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Folder Error", f"Cannot create destination folder:\n{e}")
            return

        # Record histories for restore file & destination folder
        self.add_restore_file_history(source_file)
        self.add_restore_dest_history(dest_folder)
        self.save_settings_to_registry()

        self.set_ui_busy(True)
        self.progress_value.set(0)
        self.file_count_text.set("Files: 0 / 0")
        self.size_text.set("Size: 0 B / 0 B")
        self.speed_text.set("Speed: --")
        self.eta_text.set("ETA: --")
        self.status_text.set("Starting restore...")

        self.start_time = time.perf_counter()

        self.worker_thread = threading.Thread(
            target=self.restore_worker,
            args=(source_file, dest_folder),
            daemon=True
        )
        self.worker_thread.start()

    # ========================================================
    # RESTORE WORKERS
    # ========================================================

    def restore_worker(self, source_file, dest_folder):
        try:
            if source_file.lower().endswith(".zip"):
                self.restore_zip_worker(source_file, dest_folder)
            else:
                self.restore_txt_worker(source_file, dest_folder)
        except Exception as e:
            self.worker_queue.put({"type": "error", "message": str(e)})

    def restore_zip_worker(self, source_file, dest_folder):
        with zipfile.ZipFile(source_file, "r") as zf:
            infolist = zf.infolist()
            total_files = len(infolist)
            total_size = sum(item.file_size for item in infolist)
            processed_files = 0
            processed_bytes = 0
            last_update = 0

            for item in infolist:
                zf.extract(item, dest_folder)
                processed_files += 1
                processed_bytes += item.file_size
                now = time.perf_counter()
                if now - last_update >= PROGRESS_UPDATE_INTERVAL:
                    self.send_progress(processed_files, total_files, processed_bytes, total_size, now)
                    last_update = now

        elapsed = time.perf_counter() - self.start_time
        self.worker_queue.put({
            "type": "done",
            "action": "Restore",
            "path": dest_folder,
            "files": total_files,
            "bytes": processed_bytes,
            "elapsed": elapsed
        })

    def restore_txt_worker(self, source_file, dest_folder):
        total_size = os.path.getsize(source_file)
        processed_bytes = 0
        file_count = 0
        last_update = 0

        with open(source_file, "r", encoding="utf-8", errors="replace") as sf:
            file_handle = None

            for line in sf:
                processed_bytes += len(line.encode("utf-8", errors="replace"))

                if line.startswith("<<<--- BEGIN_FILE: ") and line.strip().endswith("--->>>"):
                    if file_handle:
                        file_handle.close()
                        file_handle = None

                    raw_path = line.strip()[19:-6].strip()
                    parts = raw_path.split("/")
                    rel_path = "/".join(parts[1:]) if len(parts) > 1 else parts[0]
                    target_full = os.path.join(dest_folder, rel_path)

                    os.makedirs(os.path.dirname(target_full), exist_ok=True)
                    file_handle = open(target_full, "w", encoding="utf-8", newline="")
                    file_count += 1
                    continue

                if line.strip() == "<<<--- END_FILE --->>>":
                    if file_handle:
                        file_handle.close()
                        file_handle = None
                    continue

                if file_handle:
                    file_handle.write(line)

                now = time.perf_counter()
                if now - last_update >= PROGRESS_UPDATE_INTERVAL:
                    self.send_progress(file_count, file_count, processed_bytes, total_size, now)
                    last_update = now

            if file_handle:
                file_handle.close()

        elapsed = time.perf_counter() - self.start_time
        self.worker_queue.put({
            "type": "done",
            "action": "Restore",
            "path": dest_folder,
            "files": file_count,
            "bytes": processed_bytes,
            "elapsed": elapsed
        })

    # ========================================================
    # PROGRESS & QUEUE
    # ========================================================

    def send_progress(self, processed_files, total_files, processed_bytes, total_bytes, now):
        if total_bytes > 0:
            percent = (processed_bytes / total_bytes * 100)
        elif total_files > 0:
            percent = (processed_files / total_files * 100)
        else:
            percent = 100

        elapsed = max(now - self.start_time, 0.001)
        speed = processed_bytes / elapsed

        if speed > 0 and total_bytes > processed_bytes:
            eta_seconds = (total_bytes - processed_bytes) / speed
        else:
            eta_seconds = 0

        self.worker_queue.put({
            "type": "progress",
            "percent": min(percent, 100),
            "files": processed_files,
            "total_files": total_files,
            "bytes": processed_bytes,
            "total_bytes": total_bytes,
            "speed": speed,
            "eta": eta_seconds
        })

    def process_worker_queue(self):
        try:
            while True:
                message = self.worker_queue.get_nowait()
                message_type = message.get("type")

                if message_type == "progress":
                    self.progress_value.set(message["percent"])
                    self.file_count_text.set(f"Files: {message['files']:,} / {message['total_files']:,}")
                    self.size_text.set(f"Size: {self.format_bytes(message['bytes'])} / {self.format_bytes(message['total_bytes'])}")
                    self.speed_text.set("Speed: " + self.format_speed(message["speed"]))
                    self.eta_text.set("ETA: " + self.format_eta(message["eta"]))
                    self.status_text.set("Processing operation...")

                elif message_type == "done":
                    self.progress_value.set(0)
                    self.file_count_text.set("Files: 0 / 0")
                    self.size_text.set("Size: 0 B / 0 B")
                    self.speed_text.set("Speed: --")
                    self.eta_text.set("ETA: --")
                    self.status_text.set("Ready.")

                    self.set_ui_busy(False)

                    action_title = f"{message['action']} Complete"
                    short_msg = (
                        f"{message['action']} completed successfully!\n\n"
                        f"Location : {message['path']}\n"
                        f"Files    : {message['files']:,} items\n"
                        f"Size     : {self.format_bytes(message['bytes'])}\n"
                        f"Duration : {self.format_duration(message['elapsed'])}"
                    )
                    messagebox.showinfo(action_title, short_msg)

                elif message_type == "error":
                    self.progress_value.set(0)
                    self.speed_text.set("Speed: --")
                    self.eta_text.set("ETA: --")
                    self.status_text.set("Ready.")
                    self.set_ui_busy(False)
                    messagebox.showerror("Operation Error", message["message"])

        except queue.Empty:
            pass

        self.root.after(100, self.process_worker_queue)

    # ========================================================
    # UI STATE TOGGLE
    # ========================================================

    def set_ui_busy(self, busy):
        self.is_working = busy
        state = "disabled" if busy else "normal"
        readonly_state = "disabled" if busy else "readonly"

        # Backup Tab Controls
        self.project_browse_button.config(state=state)
        self.backup_browse_button.config(state=state)
        self.name_browse_button.config(state=state)
        self.same_checkbox.config(state=state)
        self.scan_button.config(state=state)
        self.backup_button.config(state=state)
        self.name_entry.config(state=state)
        self.project_combo.config(state=state)
        self.backup_combo.config(state=state)
        self.zip_radio.config(state=state)
        self.txt_radio.config(state=state)
        self.radio_mode_src.config(state=state)
        self.radio_mode_full.config(state=state)
        self.level_combo.config(state=readonly_state)
        self.preview_listbox.config(state=state)

        # Restore Tab Controls
        self.restore_file_combo.config(state=state)
        self.restore_file_browse_button.config(state=state)
        self.restore_dest_combo.config(state=state)
        self.restore_dest_browse_button.config(state=state)
        self.restore_button.config(state=state)

    # ========================================================
    # PROJECT INFORMATION HELPER
    # ========================================================

    def build_project_information(self, project_path, project_name, backup_name, mode, files):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total_size = sum(item["size"] for item in files)
        lines = []

        lines.append("=" * 70)
        lines.append("RUST PROJECT BACKUP INFORMATION")
        lines.append(f"{COPYRIGHT_TEXT}")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"Project Name : {project_name}")
        lines.append(f"Project Path : {project_path}")
        lines.append(f"Backup Name  : {backup_name}")
        lines.append(f"Backup Date  : {now}")
        lines.append(f"Backup Mode  : {'Source Code Only' if mode == 'source' else 'Full Project'}")
        lines.append(f"File Count   : {len(files):,}")
        lines.append(f"Total Size   : {self.format_bytes(total_size)}")
        lines.append("")
        lines.append("=" * 70)
        lines.append("PROJECT STRUCTURE")
        lines.append("=" * 70)
        lines.append("")

        for item in files:
            lines.append(f"{project_name}/{item['relative']}")

        lines.append("")
        lines.append("=" * 70)
        lines.append("END OF PROJECT INFORMATION")
        lines.append("=" * 70)

        return "\n".join(lines)

    # ========================================================
    # UTILITY HELPERS
    # ========================================================

    @staticmethod
    def sanitize_filename(name):
        invalid_chars = '<>:"/\\|?*'
        result = name
        for char in invalid_chars:
            result = result.replace(char, "_")
        return result.strip().rstrip(" .")

    @staticmethod
    def format_bytes(value):
        value = float(value)
        units = ["B", "KB", "MB", "GB", "TB"]
        for unit in units:
            if value < 1024:
                return f"{value:.0f} {unit}" if unit == "B" else f"{value:.2f} {unit}"
            value /= 1024
        return f"{value:.2f} PB"

    @staticmethod
    def format_speed(bytes_per_second):
        if bytes_per_second <= 0:
            return "--"
        return RustBackupApp.format_bytes(bytes_per_second) + "/s"

    @staticmethod
    def format_eta(seconds):
        if seconds <= 0:
            return "00:00"
        seconds = int(max(0, seconds))
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    @staticmethod
    def format_duration(seconds):
        seconds = int(max(0, seconds))
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        if minutes > 0:
            return f"{minutes}m {secs}s"
        return f"{secs}s"


# ============================================================
# MAIN APPLICATION
# ============================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = RustBackupApp(root)
    root.mainloop()
