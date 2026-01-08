#!/bin/bash

# Start Ollama in the background
/bin/ollama serve &
# Ollama Process ID
pid=$!

# Pause for Ollama to start
sleep 5

# Default to llama3 model (if OLLAMA_MODEL is empty/doesn't exist)
MODEL="${OLLAMA_MODEL:-llama3:8b}"

# Pull Ollama model
echo "Pulling model: $MODEL"
ollama pull "$MODEL" > /var/log/ollama_pull.log 2>&1    # Removes clutter from docker build output
echo "Done!"

# Wait for Ollama process to finish
wait $pid