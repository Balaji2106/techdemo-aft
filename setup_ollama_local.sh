#!/bin/bash
# Setup Ollama locally for AI-powered RCA

echo "🚀 Setting up Ollama for GenAI RCA Assistant"
echo "=============================================="

# Check if Ollama is installed
if command -v ollama &> /dev/null; then
    echo "✅ Ollama is already installed"
else
    echo "📥 Installing Ollama..."
    curl -fsSL https://ollama.ai/install.sh | sh
fi

# Start Ollama service
echo "🔄 Starting Ollama service..."
ollama serve &
OLLAMA_PID=$!
sleep 5

# Pull the model
echo "📦 Pulling deepseek-r1:latest model (this may take a few minutes)..."
ollama pull deepseek-r1:latest

# Test Ollama
echo "🧪 Testing Ollama..."
curl -s http://localhost:11434/api/tags | grep -q "deepseek-r1" && echo "✅ Ollama is working!" || echo "❌ Ollama test failed"

echo ""
echo "=============================================="
echo "✅ Setup Complete!"
echo ""
echo "📝 Update your .env file with:"
echo "   OLLAMA_HOST=http://localhost:11434"
echo "   OLLAMA_MODEL=deepseek-r1:latest"
echo ""
echo "🔄 Restart your RCA system for changes to take effect"
echo "=============================================="
