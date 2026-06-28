import os
import re
import json
import shutil
import sys
from datetime import datetime

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sims_install_log.json")


# ─────────────────────────────────────────────
#  Log helpers
# ─────────────────────────────────────────────

def load_log() -> list:
    """Return the full log array, or [] if the file doesn't exist / is corrupt."""
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except (json.JSONDecodeError, OSError):
        pass
    return []


def save_log(log: list) -> None:
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)


def append_run(run_id: str, entries: list) -> None:
    """Append a completed run to the on-disk log."""
    log = load_log()
    log.append({"run_id": run_id, "entries": entries})
    save_log(log)


# ─────────────────────────────────────────────
#  Revert logic
# ─────────────────────────────────────────────

def run_revert() -> None:
    log = load_log()
    if not log:
        print("No install log found. Nothing to revert.")
        print(f"(Expected log at: {LOG_FILE})")
        return

    # Show available runs so the user knows what's on record
    print("Logged install runs (oldest → newest):")
    for i, run in enumerate(log):
        entry_count = len(run.get("entries", []))
        marker = "  ← most recent" if i == len(log) - 1 else ""
        print(f"  [{i + 1}]  {run['run_id']}  —  {entry_count} file(s){marker}")

    # Default to most recent; allow targeting a specific run by index
    target_index = len(log) - 1
    if len(log) > 1:
        raw = input("\nEnter run number to revert (press Enter for most recent): ").strip()
        if raw:
            try:
                chosen = int(raw) - 1
                if not (0 <= chosen < len(log)):
                    print("Invalid selection. Aborting.")
                    return
                target_index = chosen
            except ValueError:
                print("Invalid input. Aborting.")
                return

    target_run = log[target_index]
    entries    = target_run.get("entries", [])

    if not entries:
        print(f"\nRun '{target_run['run_id']}' has no file entries. Nothing to revert.")
        return

    print(f"\nRun to revert: {target_run['run_id']}")
    print(f"Files that will be DELETED ({len(entries)}):")
    for e in entries:
        exists_marker = "" if os.path.exists(e["destination"]) else "  [already gone]"
        print(f"  {e['destination']}{exists_marker}")

    confirm = input("\nType YES to confirm permanent deletion: ").strip()
    if confirm != "YES":
        print("Revert cancelled.")
        return

    deleted      = 0
    already_gone = 0
    errors       = []
    dirs_to_check = set()

    for entry in entries:
        dest = entry["destination"]
        if not os.path.exists(dest):
            already_gone += 1
            continue
        try:
            os.remove(dest)
            dirs_to_check.add(os.path.dirname(dest))
            deleted += 1
        except OSError as exc:
            errors.append((dest, str(exc)))
            print(f"  [Error] Could not delete '{dest}': {exc}")

    # Remove directories that are now empty, walking upward but never
    # removing the game root itself (we stop once a dir is non-empty)
    for d in sorted(dirs_to_check, key=len, reverse=True):
        try:
            if os.path.isdir(d) and not os.listdir(d):
                os.rmdir(d)
        except OSError:
            pass

    # Remove the reverted run from the log
    log.pop(target_index)
    save_log(log)

    print("\n==========================================")
    print("           REVERT SUMMARY                 ")
    print("==========================================")
    print(f"Files deleted:      {deleted}")
    print(f"Already missing:    {already_gone}")
    print(f"Errors:             {len(errors)}")
    print(f"Run '{target_run['run_id']}' removed from log.")
    print("==========================================")


# ─────────────────────────────────────────────
#  Main install logic
# ─────────────────────────────────────────────

def parse_script_and_move() -> None:
    is_test_mode = "-test" in sys.argv or "--test" in sys.argv

    if is_test_mode:
        print("=== TEST MODE / DRY-RUN ENABLED ===")
        print("Files will NOT be copied. Showing planned target paths.\n")

    run_id      = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    run_entries = []   # Accumulates {"source": ..., "destination": ...} per copied file

    # 1. Gather inputs
    base_dir  = input("Enter the absolute path to your extracted folders directory:\n> ").strip()
    game_path = input(
        "\nEnter the absolute path to your top-level game installation directory:\n"
    ).strip()

    base_dir  = base_dir.strip("'\"")
    game_path = game_path.strip("'\"")

    if not os.path.isdir(base_dir):
        print(f"Error: Base directory '{base_dir}' does not exist.")
        return
    if not os.path.isdir(game_path):
        print(f"Error: Target game installation directory '{game_path}' does not exist.")
        return

    print("\n--- Starting Dynamic Processing ---")

    total_folders_found = 0
    folders_processed   = 0
    total_duplicates    = 0
    unprocessed_folders = []

    # 2. Loop through top-level extracted asset folders
    for item in os.listdir(base_dir):
        item_path = os.path.join(base_dir, item)
        if not os.path.isdir(item_path):
            continue

        total_folders_found += 1
        script_file_path = os.path.join(item_path, "script.txt")

        if not os.path.exists(script_file_path):
            print(f"Skipping folder: '{item}' (Reason: No script.txt found)")
            unprocessed_folders.append((item, "No script.txt found"))
            continue

        print(f"\nProcessing folder: {item}")

        # 3. Read script.txt and extract pairs of (source_pattern, win_target_path)
        copy_commands = []
        try:
            with open(script_file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("[copy]"):
                        matches = re.findall(r'"([^"]*)"', line)
                        if len(matches) >= 2:
                            copy_commands.append((matches[0], matches[1]))
        except Exception as e:
            print(f"  Error reading script.txt: {e}")
            unprocessed_folders.append((item, f"Error reading script.txt: {e}"))
            continue

        if not copy_commands:
            print("  [Warning] No valid [copy] directives found in script.txt.")
            unprocessed_folders.append((item, "No valid [copy] statements found"))
            continue

        # 4. Process each copy instruction dynamically
        files_moved_for_folder  = 0
        duplicates_for_folder   = 0

        for src_raw, dest_raw in copy_commands:
            # Clean destination variables and convert Windows slashes
            clean_dest = re.sub(r'%%[A-Z0-9_]+%%', '', dest_raw)
            clean_dest = clean_dest.replace('\\', '/')
            if clean_dest.startswith('/'):
                clean_dest = clean_dest[1:]

            # Case correction for Linux filesystem
            replacements = {
                "gamedata/": "GameData/",
                "/skins":    "/Skins",
                "userdata/": "UserData/",
                "/walls":    "/Walls",
                "/floors":   "/Floors",
                "/import":   "/Import",
            }
            for low_case, cap_case in replacements.items():
                clean_dest = re.sub(re.escape(low_case), cap_case, clean_dest, flags=re.IGNORECASE)

            full_target_path = os.path.join(game_path, clean_dest)
            clean_src        = src_raw.replace(".\\", "").replace("\\", "/")

            # ── Case A: Wildcard copy ──────────────────────────────────────────
            if clean_src.endswith('*.*') or clean_src.endswith('*'):
                src_sub_folder = clean_src.replace('*.*', '').replace('*', '').rstrip('/')
                full_source_dir = os.path.join(item_path, src_sub_folder) if src_sub_folder else item_path

                target_dir = (
                    os.path.dirname(full_target_path)
                    if full_target_path.endswith('/') or '*.*' in dest_raw
                    else full_target_path
                )

                if os.path.isdir(full_source_dir):
                    if not is_test_mode:
                        os.makedirs(target_dir, exist_ok=True)

                    for file_name in os.listdir(full_source_dir):
                        source_file = os.path.join(full_source_dir, file_name)
                        dest_file   = os.path.join(target_dir, file_name)
                        if os.path.isfile(source_file):
                            if os.path.exists(dest_file):
                                print(f"  [Skip] Already exists: {file_name}")
                                duplicates_for_folder += 1
                                continue
                            if is_test_mode:
                                print(f"  [MOCK] Wildcard Copy: {file_name} -> {dest_file}")
                            else:
                                shutil.copy2(source_file, dest_file)
                                run_entries.append({
                                    "source":      source_file,
                                    "destination": dest_file,
                                })
                            files_moved_for_folder += 1
                else:
                    print(f"  [Warning] Indicated asset source folder missing: {src_sub_folder}")

            # ── Case B: Single file copy ──────────────────────────────────────
            else:
                full_source_file = os.path.join(item_path, clean_src)
                if os.path.isfile(full_source_file):
                    if (
                        os.path.basename(full_target_path).lower()
                        == os.path.basename(clean_src).lower()
                        or '.' in os.path.basename(full_target_path)
                    ):
                        target_dir = os.path.dirname(full_target_path)
                        dest_file  = os.path.join(target_dir, os.path.basename(full_target_path))
                    else:
                        target_dir = full_target_path
                        dest_file  = os.path.join(target_dir, os.path.basename(clean_src))

                    if is_test_mode:
                        print(f"  [MOCK] File Copy: {os.path.basename(clean_src)} -> {dest_file}")
                        files_moved_for_folder += 1
                    elif os.path.exists(dest_file):
                        print(f"  [Skip] Already exists: {os.path.basename(clean_src)}")
                        duplicates_for_folder += 1
                    else:
                        try:
                            os.makedirs(target_dir, exist_ok=True)
                            shutil.copy2(full_source_file, dest_file)
                            run_entries.append({
                                "source":      full_source_file,
                                "destination": dest_file,
                            })
                            files_moved_for_folder += 1
                        except Exception as e:
                            print(f"  [Error] Failed copying file {clean_src}: {e}")
                else:
                    print(f"  [Warning] Explicitly listed file missing: {clean_src}")

        if files_moved_for_folder > 0 or duplicates_for_folder > 0:
            total_duplicates += duplicates_for_folder
            if files_moved_for_folder > 0:
                action_status = "Mock-processed" if is_test_mode else "Successfully routed"
                dup_note = f", {duplicates_for_folder} skipped (already exist)" if duplicates_for_folder else ""
                print(f"  {action_status} {files_moved_for_folder} assets to respective game destinations{dup_note}.")
                folders_processed += 1
            else:
                # Every file in this folder was already present
                print(f"  All {duplicates_for_folder} file(s) already exist — nothing new to copy.")
                unprocessed_folders.append((item, f"All {duplicates_for_folder} file(s) already present at destination"))
        else:
            unprocessed_folders.append((item, "Assets specified in script.txt were missing on disk"))

    # 5. Persist the log (skip in test mode — nothing actually moved)
    if not is_test_mode and run_entries:
        append_run(run_id, run_entries)
        print(f"\nRun '{run_id}' logged ({len(run_entries)} file(s)).")
        print(f"Log file: {LOG_FILE}")

    # 6. Summary
    print("\n==========================================")
    print("                SUMMARY REPORT             ")
    print("==========================================")
    print(f"Total directories found:   {total_folders_found}")
    print(f"Successfully processed:    {folders_processed}")
    print(f"Duplicates skipped:        {total_duplicates}")
    print(f"Total skipped/failed:      {len(unprocessed_folders)}")

    if unprocessed_folders:
        print("\n--- List of Skipped Folders ---")
        for folder_name, reason in unprocessed_folders:
            print(f"- {folder_name}: {reason}")

    print("==========================================")


# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    if "--revert" in sys.argv:
        run_revert()
    else:
        parse_script_and_move()
