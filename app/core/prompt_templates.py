"""
Module Name: app/core/prompt_templates.py
Purpose   : Manages prompt templates for different model formats
Params    : None
History   :
    Date            Notes
    2025-06-15      Initial implementation
"""

from typing import Dict, Optional, List, Any, Union
import json
import os
from pathlib import Path

from app.core.model_manager import ModelFormat

class PromptTemplate:
    """A template for formatting prompts for different model types"""

    def __init__(
        self,
        name: str,
        format_model: ModelFormat,
        system_prefix: str = "",
        system_suffix: str = "",
        user_prefix: str = "",
        user_suffix: str = "",
        assistant_prefix: str = "",
        assistant_suffix: str = "",
        default_system_prompt: str = "",
        stop_tokens: List[str] = None,
    ):
        """Initialize a prompt template

        Args:
            name: Template name
            format_model: Model format this template is for
            system_prefix: Prefix for system messages
            system_suffix: Suffix for system messages
            user_prefix: Prefix for user messages
            user_suffix: Suffix for user messages
            assistant_prefix: Prefix for assistant messages
            assistant_suffix: Suffix for assistant messages
            default_system_prompt: Default system prompt to use
            stop_tokens: List of stop tokens for this template
        """
        self.name = name
        self.format_model = format_model
        self.system_prefix = system_prefix
        self.system_suffix = system_suffix
        self.user_prefix = user_prefix
        self.user_suffix = user_suffix
        self.assistant_prefix = assistant_prefix
        self.assistant_suffix = assistant_suffix
        self.default_system_prompt = default_system_prompt
        self.stop_tokens = stop_tokens or []

    def format_prompt(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """Format a prompt for the model

        Args:
            user_prompt: The user's prompt
            system_prompt: Optional system prompt (uses default if None)
            chat_history: Optional chat history for context

        Returns:
            Formatted prompt string
        """
        sys_prompt = system_prompt if system_prompt is not None else self.default_system_prompt

        # If we have chat history, format a full conversation
        if chat_history:
            formatted_history = ""

            for msg in chat_history:
                role = msg.get("role", "").lower()
                content = msg.get("content", "")

                if role == "system":
                    formatted_history += f"{self.system_prefix}{content}{self.system_suffix}"
                elif role == "user":
                    formatted_history += f"{self.user_prefix}{content}{self.user_suffix}"
                elif role == "assistant":
                    formatted_history += f"{self.assistant_prefix}{content}{self.assistant_suffix}"

            # Add the current user prompt
            formatted_history += f"{self.user_prefix}{user_prompt}{self.user_suffix}"

            # Add assistant prefix to indicate where the model should start generating
            formatted_history += self.assistant_prefix

            return formatted_history

        # Simple case: just system prompt + user prompt
        if sys_prompt:
            return f"{self.system_prefix}{sys_prompt}{self.system_suffix}{self.user_prefix}{user_prompt}{self.user_suffix}{self.assistant_prefix}"
        else:
            return f"{self.user_prefix}{user_prompt}{self.user_suffix}{self.assistant_prefix}"

    def extract_response(self, full_response: str) -> str:
        """Extract the model's response from the full output

        Args:
            full_response: Raw response from the model

        Returns:
            Cleaned response
        """
        # If the assistant suffix is in the response, remove it and everything after
        if self.assistant_suffix and self.assistant_suffix in full_response:
            return full_response.split(self.assistant_suffix)[0].strip()

        # Otherwise, return the whole response
        return full_response.strip()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PromptTemplate':
        """Create a PromptTemplate from a dictionary

        Args:
            data: Dictionary with template parameters

        Returns:
            PromptTemplate instance
        """
        return cls(
            name=data.get("name", "Unknown"),
            format_model=ModelFormat(data.get("format_model", "uncategorized")),
            system_prefix=data.get("system_prefix", ""),
            system_suffix=data.get("system_suffix", ""),
            user_prefix=data.get("user_prefix", ""),
            user_suffix=data.get("user_suffix", ""),
            assistant_prefix=data.get("assistant_prefix", ""),
            assistant_suffix=data.get("assistant_suffix", ""),
            default_system_prompt=data.get("default_system_prompt", ""),
            stop_tokens=data.get("stop_tokens", []),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert the template to a dictionary

        Returns:
            Dictionary representation of the template
        """
        return {
            "name": self.name,
            "format_model": self.format_model,
            "system_prefix": self.system_prefix,
            "system_suffix": self.system_suffix,
            "user_prefix": self.user_prefix,
            "user_suffix": self.user_suffix,
            "assistant_prefix": self.assistant_prefix,
            "assistant_suffix": self.assistant_suffix,
            "default_system_prompt": self.default_system_prompt,
            "stop_tokens": self.stop_tokens,
        }

class PromptLibrary:
    """Manages a collection of prompt templates"""

    def __init__(self, templates_dir: Optional[str] = None):
        """Initialize the prompt library

        Args:
            templates_dir: Optional directory to load templates from
        """
        self.templates: Dict[str, PromptTemplate] = {}
        self._load_default_templates()

        if templates_dir:
            self.load_templates_from_directory(templates_dir)

    def _load_default_templates(self):
        """Load the default built-in templates"""
        # Mistral Instruct Template
        mistral = PromptTemplate(
            name="mistral",
            format_model=ModelFormat.MISTRAL,
            system_prefix="[INST] <<SYS>>\n",
            system_suffix="\n<</SYS>>\n\n",
            user_prefix="",
            user_suffix="\n[/INST]\n",
            assistant_prefix="",
            assistant_suffix="</s>",
            default_system_prompt="You are an advanced research assistant, named Solo. Your task is to support, advise and teach the user in any task they come across. Always speak in a natural tone, act like an absolute professional in the task at hand and speak as such. Refrain from report-like breakdowns, in favor of natural conversational tone.",
            stop_tokens=["</s>"],
        )
        self.add_template(mistral)

        # Llama 3 Template
        llama3 = PromptTemplate(
            name="llama3",
            format_model=ModelFormat.LLAMA3,
            system_prefix="<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n",
            system_suffix="<|eot_id|>",
            user_prefix="<|start_header_id|>user<|end_header_id|>\n\n",
            user_suffix="<|eot_id|>",
            assistant_prefix="<|start_header_id|>assistant<|end_header_id|>\n\n",
            assistant_suffix="<|eot_id|>",
            default_system_prompt="You are Solo, a helpful AI assistant. You provide accurate, concise, and clear answers to user queries.",
            stop_tokens=["<|eot_id|>"],
        )
        self.add_template(llama3)

        # TinyLlama Template
        tinyllama = PromptTemplate(
            name="tinyllama",
            format_model=ModelFormat.TINYLLAMA,
            system_prefix="<|system|>\n",
            system_suffix="\n",
            user_prefix="<|user|>\n",
            user_suffix="",
            assistant_prefix="<|assistant|>\n",
            assistant_suffix="",
            default_system_prompt="You are Solo, a helpful, respectful and honest assistant.",
            stop_tokens=["<|assistant|>"],
        )
        self.add_template(tinyllama)

        # Phi-4 Template
        phi4 = PromptTemplate(
            name="phi4",
            format_model=ModelFormat.PHI4,
            system_prefix="<|im_start|>system<|im_sep|>\n",
            system_suffix="<|im_end|>\n",
            user_prefix="<|im_start|>user<|im_sep|>\n",
            user_suffix="<|im_end|>\n",
            assistant_prefix="<|im_start|>assistant<|im_sep|>\n",
            assistant_suffix="<|im_end|>",
            default_system_prompt="You are Solo, a helpful, respectful and honest assistant.",
            stop_tokens=["<|im_end|>"],
        )
        self.add_template(phi4)

    def add_template(self, template: PromptTemplate):
        """Add a template to the library

        Args:
            template: PromptTemplate instance
        """
        self.templates[template.name] = template

    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """Get a template by name

        Args:
            name: Template name

        Returns:
            PromptTemplate or None if not found
        """
        return self.templates.get(name)

    def get_template_for_model(self, model_format: ModelFormat) -> Optional[PromptTemplate]:
        """Get a template for a specific model format

        Args:
            model_format: ModelFormat enum value

        Returns:
            PromptTemplate or None if no matching template
        """
        # Try to find an exact match
        for template in self.templates.values():
            if template.format_model == model_format:
                return template

        # If not found, return None
        return None

    def load_templates_from_directory(self, directory: str):
        """Load templates from JSON files in a directory

        Args:
            directory: Directory path containing template JSON files
        """
        if not os.path.exists(directory):
            return

        for file in os.listdir(directory):
            if file.endswith(".json"):
                try:
                    with open(os.path.join(directory, file), 'r') as f:
                        template_data = json.load(f)
                        template = PromptTemplate.from_dict(template_data)
                        self.add_template(template)
                except Exception as e:
                    print(f"Error loading template from {file}: {str(e)}")

    def save_template_to_file(self, template: PromptTemplate, directory: str):
        """Save a template to a JSON file

        Args:
            template: PromptTemplate to save
            directory: Directory to save to
        """
        os.makedirs(directory, exist_ok=True)

        filename = f"{template.name}.json"
        filepath = os.path.join(directory, filename)

        with open(filepath, 'w') as f:
            json.dump(template.to_dict(), f, indent=2)

    def list_templates(self) -> List[str]:
        """List all available template names

        Returns:
            List of template names
        """
        return list(self.templates.keys())
