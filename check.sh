#/bin/sh

for file in backend/core/*.py; do
    filename=$(basename "$file" .py)
    if grep -q "from \.$filename import\|from core\.$filename import" "$file" 2>/dev/null; then
        echo "Circular import found in $file"
        grep -n "from \.$filename import\|from core\.$filename import" "$file"
    fi
done
