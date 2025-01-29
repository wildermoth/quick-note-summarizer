# Quick Capture Processor

Automates processing of web content into Obsidian notes

## Features

- Web content summarization
- Social media transcription
- Automated note formatting

## Setup

1. Install Python 3.10+
2. `pip install -r requirements.txt`
3. Copy `config.example.yaml` to `config.yaml`
4. Configure paths in `config.yaml`

## Configuration

Create a `config.yaml` file in the project root with this structure:

```yaml
paths:
    quick_capture: 'path/to/your/quick_capture.md'
    transcribe_script: 'path/to/your/transcribe.py'
    output_dir: 'path/to/your/output_dir'

api:
    ollama_endpoint: 'http://localhost:11434/api/generate'
    model: 'deepseek-r1:8b' # or your preferred model

settings:
    headless_browser: true
    request_delay: 2
```

Replace paths with your actual local file paths.
