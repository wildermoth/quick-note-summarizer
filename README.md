# Quick Note Summarizer

I use automate on my phone to capture notes from the web. This script automates the process of summarizing the notes and formatting them into Obsidian zettlekansten notes using local models.

[![Overview](https://img.youtube.com/vi/sz6w_2Gpdow/0.jpg)](https://www.youtube.com/watch?v=sz6w_2Gpdow)

## Features

- Web content summarization
- Social media transcription
- Automated note formatting

## Setup

1. Install Python 3.10+
2. Install transcribe-anything:  
   `pipx install transcribe-anything`
3. `pip install -r requirements.txt`
4. Copy `config.example.yaml` to `config.yaml`
5. Configure paths in `config.yaml`

## Configuration

Create a `config.yaml` file in the project root with this structure:

```yaml
paths:
    quick_capture: 'path/to/your/quick_capture.md'
    summarize_script: 'path/to/your/summarize.py'
    output_dir: 'path/to/your/output_dir'

api:
    ollama_endpoint: 'http://localhost:11434/api/generate'
    model: 'deepseek-r1:8b' # or your preferred model

settings:
    headless_browser: true
    request_delay: 2
```

Replace paths with your actual local file paths.
