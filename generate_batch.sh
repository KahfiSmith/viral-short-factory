#!/usr/bin/env bash
set -e

TOPICS=(
  "platypus"
  "axolotl"
  "pangolin"
  "hammerhead shark"
  "archerfish"
)

for topic in "${TOPICS[@]}"; do
  echo "========================================"
  echo "🚀 Memproses topik: $topic"
  echo "========================================"
  uv run vsf generate --profile facts --topic "$topic"
done

echo "========================================"
echo "✅ Selesai memproses semua topik!"
echo "========================================"
