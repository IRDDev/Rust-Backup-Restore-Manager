# Rust Project Backup & Restore Manager

A desktop utility for backing up and restoring Rust project files, built with Python and Tkinter.

## Overview

Rust Project Backup & Restore Manager was created to simplify repetitive project backup tasks during development and debugging.

The application provides source-only and full-project backup modes, ZIP and TXT output formats, project file previews, and progress information during backup and restore operations.

## Features

- **Source Code Only:** Selects supported source files and project configuration files for backup.
- **Full Project Backup:** Archives project files while excluding `.git` and `target` directories.
- **ZIP Backup:** Supports configurable compression levels from 0 to 9.
- **TXT Backup:** Combines `Cargo.toml` and Rust source files under `src/` into a text-based backup.
- **ZIP Restore:** Extracts a ZIP backup into a selected destination folder.
- **TXT Restore:** Reconstructs files from the supported file markers in a TXT backup.
- **File Preview:** Displays the files selected for backup before the operation starts.
- **Progress Tracking:** Displays file count, data size, transfer speed, progress percentage, and estimated time remaining.
- **Automatic Backup Naming:** Generates a default backup name using the project name and timestamp.
- **Backup Information:** Includes project details and a file structure listing in the backup.
- **Background Processing:** Runs backup and restore operations in worker threads to keep the interface responsive.

## Backup Formats

### ZIP

Creates a ZIP archive containing the selected files and a `PROJECT_INFORMATION.txt` entry.

ZIP compression levels range from 0 to 9. Certain file types that are already compressed are stored without additional compression.

### TXT

Creates a text-based backup containing:

- `.toml` files located at the project root.
- `.rs` files located inside `src/`.

The TXT format is intended for the supported Rust source and configuration files, not for reconstructing every file in a complete project.

## Requirements

- Windows
- Python 3.x
- The required Python packages

## Installation

Install the required third-party packages:

```bash
python -m pip install
```

The application uses Python's standard library along with Tkinter, `psutil` is not required, and the third-party dependencies for this project should be installed as listed below:

```bash
python -m pip install
```

## Run the Application

Run the application from its project directory:

```bash
python main.py
```

Replace `main.py` with the actual filename used for the application source code.

## Project Background

This project was developed to reduce the repetitive work of manually backing up project files during software development and debugging.

It provides a dedicated interface for selecting files, creating backups, restoring projects, and monitoring operation progress.

## Project Status

A practical desktop utility for Rust project backup and restore workflows.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
