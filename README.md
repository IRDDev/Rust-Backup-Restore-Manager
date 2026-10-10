# Rust Project Backup & Restore Manager

A desktop utility built with Python and Tkinter to simplify backing up and restoring Rust project files.

## Overview

Rust Project Backup & Restore Manager was created to reduce the repetitive work of manually copying source files or using command-line scripts when backing up Rust projects during development and debugging.

The application provides a graphical interface for creating backups and restoring projects.

## Features

- **Source Code Only** — Back up selected source code and project configuration files.
- **Full Project Backup** — Back up the project into a ZIP archive.
- **ZIP and TXT Formats** — Choose the backup format according to your needs.
- **Backup Preview** — Review the files selected for backup before starting.
- **Progress Tracking** — Monitor progress, processed data, speed, and estimated completion time.
- **Restore Functionality** — Restore projects from supported ZIP and TXT backups.
- **Backup Information** — ZIP backups include a `PROJECT_INFORMATION.txt` file with project and backup details.
- **Configurable ZIP Compression** — Select the compression level.
- **Flexible Backup Destination** — Choose where backups are stored.

## Backup Formats

### ZIP

Creates a ZIP archive containing the selected project files. Full Project mode also includes the project files selected for backup, while Source Code Only mode filters files according to the application's rules.

### TXT

Combines supported Rust source files and root-level TOML configuration files into a text-based backup using file delimiters, allowing the application to reconstruct the files during restoration.

## Requirements

- Python 3
- Tkinter, included with many standard Python installations

No third-party Python packages are required.

## How to Run

Open a terminal in the folder containing the source file and run:

```bash
python "Rust Backup Restore Manager.py"
```

If the `python` command is unavailable, try:

```bash
py "Rust Backup Restore Manager.py"
```

## Project Background

This project was developed to make Rust project backups easier during development and debugging, reducing reliance on manual file copying and repetitive command-line operations.

The project may serve as a starting point for developers who want to adapt the backup workflow for other programming languages.

## License

See the [LICENSE](LICENSE) file for licensing terms.
