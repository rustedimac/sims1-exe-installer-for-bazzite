read -rp "Enter folder path: " target_dir
target_dir="${target_dir//\'/}"   # strip any quotes if pasted with them
target_dir="${target_dir//\"/}"

cd "$target_dir" || { echo "Error: could not access '$target_dir'"; exit 1; }

for file in *.exe; do
    [ -e "$file" ] || continue
    folder_name="${file%.exe}_extracted"
    echo "Extracting $file into $folder_name..."
    7z x "$file" -o"$folder_name"
done