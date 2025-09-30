# cv2pg-ai-schema-infer

AI-powered tool that automatically infers PostgreSQL schemas from CSV files and generates optimized pgloader configurations for fast, reliable imports.

## Features

- 🧠 **Intelligent Type Inference** - Uses Google Gemini to analyze CSV samples and suggest optimal PostgreSQL types
- 📊 **Large File Support** - Handles multi-GB CSVs efficiently with streaming processing
- 🔄 **Resume Capability** - Automatic state tracking with resume support for failed imports
- ⚡ **Fast Imports** - Leverages pgloader for high-performance bulk loading
- 🎯 **Zero Configuration** - Works out of the box with sensible defaults
- 🔧 **Fully Customizable** - Override any setting via config file or CLI flags

## Quick Start

### Installation
```bash
# Clone repository
git clone https://github.com/SEBK4C/csv2pg-ai-schema-infer.git
cd csv2pg-ai-schema-infer

# Install with UV
uv sync

# Set Gemini API key
export GEMINI_API_KEY="your-api-key-here"