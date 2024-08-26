import os
from pathlib import Path


class PromptManager:
    def __init__(self, prompt_path: str | Path) -> None:
        if not isinstance(prompt_path, Path):
            prompt_path = Path(prompt_path)

        self.prompts = {}
        for filename in os.listdir(prompt_path):
            with open(prompt_path / filename) as f:
                self.prompts[filename] = f.read()

    def get_prompt(self, role_type: str, **kwargs) -> str:
        assert role_type in self.prompts, f"Role type {role_type} not found"
        return self.prompts[role_type].format(**kwargs).strip()
