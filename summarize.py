import re
import os
from bs4 import BeautifulSoup
import requests
from urllib.parse import urlparse
import logging
from datetime import datetime
import time
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import yaml
from typing import Optional, Any, Dict, Union, Generator

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ConfigLoader:
    """Load configuration from YAML file"""
    def __init__(self, config_path: str = "config.yaml") -> None:
        self.config_path = config_path
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        default_config = {
            'paths': {
                'quick_capture': 'quick_capture/quick_capture.md',
                'transcribe_script': 'transcribe-anything',
                'output_dir': 'transcription_output'
            },
            'api': {
                'ollama_endpoint': 'http://localhost:11434',
                'model': 'deepseek-r1:8b'
            }
        }
        
        try:
            with open(self.config_path, 'r') as f:
                loaded_config = yaml.safe_load(f) or {}
                return {**default_config, **loaded_config}  # Merge defaults with loaded config
        except FileNotFoundError:
            logging.warning("Config file not found, using defaults")
            return default_config

class QuickCaptureProcessor:
    def __init__(self) -> None:
        config: Dict[str, Any] = ConfigLoader().config
        paths: Dict[str, Any] = config.get('paths', {})
        api: Dict[str, Any] = config.get('api', {})
        
        self.file_path: Optional[str] = paths.get('quick_capture')
        self.transcribe_script_path: Optional[str] = paths.get('transcribe_script')
        self.output_dir: Optional[str] = paths.get('output_dir')
        self.ollama_endpoint: Optional[str] = api.get('ollama_endpoint')
        self.model: Optional[str] = api.get('model')
        self.driver: Optional[webdriver.Chrome] = None

    def setup_selenium(self) -> Optional[webdriver.Chrome]:
        """Initialize Selenium WebDriver"""
        if not self.driver:
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
        return self.driver

    def cleanup_selenium(self) -> None:
        """Clean up Selenium WebDriver"""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def is_social_media_url(self, url: str) -> bool:
        """Determine if URL is from Instagram or YouTube"""
        domain: str = urlparse(url).netloc.lower()
        return "instagram.com" in domain or "youtube.com" in domain

    def read_file_content(self) -> str:
        """Read the Quick Capture file content"""
        with open(self.file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def write_file_content(self, content: str) -> None:
        """Write content back to Quick Capture file"""
        with open(self.file_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def extract_unprocessed_section(self, content: str) -> Optional[Dict[str, Union[int, str]]]:
        """Find the first unprocessed section"""
        sections: list[str] = re.split(r'(######\s+.*?\n)(?=######|\Z)', content, flags=re.DOTALL)
        
        for i in range(0, len(sections)-1, 2):
            header: str = sections[i]
            body: str = sections[i+1] if i+1 < len(sections) else ""
            
            # Check if section is unprocessed (only contains a URL)
            if body.strip().count('\n') <= 2 and any(url in body for url in ['http://', 'https://']):
                url_match: Optional[re.Match] = re.search(r'\[(.*?)\]\((https?://[^\s\)]+)\)', body.strip())
                if url_match:
                    return {
                        'index': i,
                        'header': header,
                        'title': url_match.group(1),
                        'url': url_match.group(2),
                        'full_section': header + body
                    }
        return None

    def clean_response(self, text: str) -> str:
        """Remove thinking patterns from response"""
        cleaned: str = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        cleaned = re.sub(r'\[think\].*?\[/think\]', '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'^thinking:.*$', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'\n\s*\n', '\n\n', cleaned).strip()
        return cleaned

    def process_instagram(self, url: str) -> str:
        """Process Instagram URL using transcribe-anything"""
        try:
            output_dir: str = "transcription_output"
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            subprocess.run([
                "transcribe-anything", 
                url, 
                "--output_dir", output_dir, 
                "--language", "en", 
                "--device", "insane"
            ], check=True)

            output_path: str = os.path.join(output_dir, "out.txt")
            if not os.path.exists(output_path):
                raise Exception(f"Transcription output not found at {output_path}")

            with open(output_path, "r", encoding="utf-8") as f:
                transcript: str = f.read()

            prompt: str = f"""You are creating a zettelkasten note for my obsidian vault. Put any thinking process in <think></think> tags.
            Please provide a concise summary of the following webpage content along with relevant hashtags in snake_case format i.e. #easy_recipe #cooking_tips. 
            Focus on the main points and key takeaways, respond only with the summary and hashtags:

            {transcript}"""

            response: requests.Response = requests.post(
                'http://localhost:11434/api/generate',
                json={
                    'model': 'deepseek-r1:8b',
                    'prompt': prompt,
                    'stream': False
                }
            )
            
            if response.status_code == 200:
                summary: str = self.clean_response(response.json()['response'])
                return summary
            else:
                raise Exception(f"Error getting summary from Ollama: {response.status_code}")
            
        except Exception as e:
            logging.error(f"Error processing Instagram URL {url}: {str(e)}")
            return f"Error processing Instagram content: {str(e)}"

    def process_youtube(self, url: str) -> str:
        """Process YouTube URL using transcribe-anything"""
        return self.process_instagram(url)

    def summarize_webpage(self, url: str) -> str:
        """Get summary of regular webpage content"""
        try:
            response: requests.Response = requests.get(url)
            soup: BeautifulSoup = BeautifulSoup(response.text, 'html.parser')
            
            for script in soup(["script", "style"]):
                script.decompose()
            
            text: str = soup.get_text()
            lines: Generator[str, None, None] = (line.strip() for line in text.splitlines())
            chunks: Generator[str, None, None] = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            prompt: str = f"""You are creating a zettelkasten note for my obsidian vault. Put any thinking process in <think></think> tags.
            Please provide a concise summary of the following webpage content along with relevant hashtags in snake_case format i.e. #easy_recipe #cooking_tips. 
            Focus on the main points and key takeaways, respond only with the summay and hashtags:

            {text[:2000]}"""

            response: requests.Response = requests.post(
                'http://localhost:11434/api/generate',
                json={
                    'model': 'deepseek-r1:8b',
                    'prompt': prompt,
                    'stream': False
                }
            )
            
            if response.status_code == 200:
                return self.clean_response(response.json()['response'])
            else:
                raise Exception(f"Error getting summary from Ollama: {response.status_code}")
            
        except Exception as e:
            logging.error(f"Error summarizing webpage {url}: {str(e)}")
            return f"Error summarizing webpage: {str(e)}"

    def process_section(self, section_info: Dict[str, Union[int, str]]) -> str:
        """Process a single section and return the processed content"""
        url: str = section_info['url']
        
        if self.is_social_media_url(url):
            if "instagram.com" in url.lower():
                return self.process_instagram(url)
            elif "youtube.com" in url.lower():
                return self.process_youtube(url)
        return self.summarize_webpage(url)

    def update_file_with_processed_section(self, section_info: Dict[str, Union[int, str]], processed_content: str) -> None:
        """Update the file with processed content"""
        content: str = self.read_file_content()
        new_section: str = (
            section_info['header'] +
            f"[{section_info['title']}]({section_info['url']})\n\n" +
            processed_content +
            "\n\n---\n"
        )
        updated_content: str = content.replace(section_info['full_section'], new_section)
        self.write_file_content(updated_content)

    def process_quick_capture(self) -> None:
        """Main function to process Quick Capture entries"""
        try:
            while True:
                content: str = self.read_file_content()
                section_info: Optional[Dict[str, Union[int, str]]] = self.extract_unprocessed_section(content)
                
                if not section_info:
                    logging.info("No more unprocessed sections found.")
                    break
                
                logging.info(f"Processing: {section_info['title']} - {section_info['url']}")
                processed_content: str = self.process_section(section_info)
                self.update_file_with_processed_section(section_info, processed_content)
                logging.info(f"Processed and saved: {section_info['title']}")
                time.sleep(2)
                
        except Exception as e:
            logging.error(f"Error in process_quick_capture: {str(e)}")
        finally:
            self.cleanup_selenium()

    def _validate_config(self) -> None:
        """Ensure required configuration exists"""
        if not all([self.file_path, self.transcribe_script_path]):
            raise ValueError("Missing required configuration values")

if __name__ == "__main__":
    processor: QuickCaptureProcessor = QuickCaptureProcessor()
    processor.process_quick_capture()
