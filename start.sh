#!/bin/sh
# start.sh - Script de démarrage pour Railway

# Expand PORT variable correctly
PORT=${PORT:-8000}

echo "🚀 Starting KemTchop API on port $PORT"
exec uvicorn main:app --host 0.0.0.0 --port "$PORT"