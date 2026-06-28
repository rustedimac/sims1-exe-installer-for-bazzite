# Sims Asset Tools — Usage Guide

Two scripts for installing Maxis/EA skin and asset packs on Linux.

---

## Workflow Overview

```
Downloaded EXE packs
       │
       ▼
  extract_exes.sh          ← unpacks each EXE into its own folder
       │
       ▼
sims_asset_installer.py    ← reads each folder's script.txt and copies
                              files to the correct game directories
```

---

## 1. `extract_exes.sh`

Extracts all `.exe` self-extracting archives in a folder, each into a
subfolder named `<filename>_extracted`.

**Requirements:** `7z` must be installed (`sudo dnf install p7zip p7zip-plugins` on Bazzite).

Make both scripts executable before first use:
```bash
chmod +x extract_exes.sh
```

The Python script doesn't need it since you invoke it via `python3` directly.

### Usage

```bash
./extract_exes.sh
```

You will be prompted:
```
Enter folder path: /home/USER/Downloads/Maxis EA Official - skins
```

Paths with or without surrounding quotes are both accepted. Each EXE
produces a folder like:

```
MTVSkins.exe  →  MTVSkins_extracted/
HavocSkin.exe →  HavocSkin_extracted/
...
```

---

## 2. `sims_asset_installer.py`

Reads the `script.txt` inside each extracted folder and copies its
assets to the correct locations in your game installation directory.

**Requirements:** Python 3.

### Modes

**Normal install**
```bash
python3 sims_asset_installer.py
```

**Dry run — shows what would be copied without touching anything**
```bash
python3 sims_asset_installer.py --test
```

**Revert the last install run**
```bash
python3 sims_asset_installer.py --revert
```

### Install

You will be prompted for two paths:

```
Enter the absolute path to your extracted folders directory:
> /home/johnkwon/Downloads/Maxis EA Official - skins

Enter the absolute path to your top-level game installation directory:
> /home/johnkwon/Desktop/Link to The Sims Legacy Collection
```

The script then processes every subfolder that contains a `script.txt`,
copying files to the appropriate game subdirectory (`GameData/Skins/`,
`TemplateNPCs/`, etc.). Folders without a `script.txt` are skipped with
a note in the summary.

Files that already exist at the destination are skipped and counted
separately — they are never overwritten.

### Revert

The script keeps a log file (`sims_install_log.json`) next to itself.
Each run is recorded with a timestamp and the full list of files it copied.

Running with `--revert` shows all logged runs and lets you pick one to undo:

```
Logged install runs (oldest → newest):
  [1]  2025-06-28T14:00:00  —  54 file(s)
  [2]  2025-06-28T15:30:00  —  12 file(s)  ← most recent

Enter run number to revert (press Enter for most recent):
```

It then lists every file that will be deleted and asks for confirmation
before proceeding:

```
Type YES to confirm permanent deletion:
```

After reverting, that run is removed from the log. Only files the
installer actually copied are ever deleted — pre-existing files are
never touched.

> **Note:** `--test` runs are never logged, so they cannot be reverted.

### Summary Report

After every install the script prints a summary:

```
==========================================
                SUMMARY REPORT
==========================================
Total directories found:   35
Successfully processed:    16
Duplicates skipped:        597
Total skipped/failed:      18
==========================================
```

Folders listed under skipped/failed will show one of these reasons:

| Reason | What it means |
|--------|---------------|
| `No script.txt found` | Folder has no install instructions — manual install needed |
| `All N file(s) already present` | Every file in this pack is already installed |
| `No valid [copy] statements found` | `script.txt` exists but contains no recognised copy directives |
| `Assets specified in script.txt were missing on disk` | The files listed in `script.txt` weren't found in the extracted folder |

---

## Typical Full Workflow

```bash
# 1. Extract all EXEs in a pack folder
./extract_exes.sh
# > Enter folder path: /home/johnkwon/Downloads/Maxis EA Official - skins

# 2. Dry run to verify paths before committing
python3 sims_asset_installer.py --test

# 3. Run the actual install
python3 sims_asset_installer.py

# 4. If something went wrong, revert
python3 sims_asset_installer.py --revert
```
