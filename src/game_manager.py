import json
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import requests

from src.game_engine import ConnectionsGameEngine, WordleGameEngine
from src.prompt_manager import PromptManager

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MAX_TOKENS = 256


class BaseGameManager(ABC):
    def __init__(
        self, model_id: str, prompt_manager_path: str | Path, max_attempts: int
    ):
        self.model_id = model_id
        self.prompt_manager = PromptManager(prompt_manager_path)
        self.max_attempts = max_attempts
        self.messages = []

    @abstractmethod
    def play(self) -> Any:
        pass

    def _get_assistant_response(self) -> str:
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                data=json.dumps(
                    {
                        "model": self.model_id,
                        "messages": self.messages,
                        "max_tokens": MAX_TOKENS,
                    }
                ),
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                timeout=30,
            )
            response.raise_for_status()
            assistant_response = response.json()["choices"][0]["message"]
            self.messages.append(assistant_response)
            return assistant_response
        except Exception as e:
            print(f"Error occurred: {str(e)}")
            raise e

    def _add_message(self, role: str, prompt_type: str, **kwargs):
        self.messages.append(
            {
                "role": role,
                "content": self.prompt_manager.get_prompt(prompt_type, **kwargs),
            }
        )

    def format_messages(self) -> str:
        return json.dumps(self.messages)

    def get_total_num_attempts(self) -> int:
        return self.engine.total_attempts


class WordleGameManager(BaseGameManager):
    def __init__(
        self,
        word: str,
        model_id: str,
        prompt_manager_path: str | Path,
        max_attempts: int = 6,
    ):
        super().__init__(model_id, prompt_manager_path, max_attempts)
        self.engine = WordleGameEngine(word, max_attempts)

    def play(self) -> int:
        self.engine.reset()
        self._add_message("system", "system", max_attempts=self.max_attempts)

        while not self.engine.is_game_over():
            self._add_message(
                "user",
                "user_prompt",
                remaining_attempts=self.max_attempts - self.engine.num_attempts,
            )
            self.engine.total_attempts += 1

            try:
                assistant_response = self._get_assistant_response()
                guess = self._parse_response(assistant_response)
                result = self.engine.guess(guess)
            except Exception as e:
                self._add_message("user", "user_error", error=str(e))
                print(f"-> Error occurred: {str(e)}")
                continue

            if self.engine.is_word_guessed(guess):
                self._add_message("user", "user_win", word=guess)
                return 1

            self._add_message(
                "user",
                "user_incorrect_guess",
                guess=guess,
                feedback="\n".join(json.dumps(item) for item in result.values()),
            )

        self._add_message("user", "user_lose", word=self.engine.word)
        return 0

    def _parse_response(self, response: dict) -> str:
        content = response["content"]
        try:
            guess = re.search(r"(?<=Guess:).*", content).group()
        except Exception as e:
            print(str(e))
            message = (
                "Couldn't parse your response.\n"
                "Please make sure to provide the response using the following format:\n"
                "Guess: YOUR_GUESS_HERE"
            )
            raise Exception(message)
        out = guess.strip().lower().replace(" ", "").replace('"', "")
        return out


class ConnectionsGameManager(BaseGameManager):
    def __init__(
        self,
        categories: dict[str, set[str]],
        model_id: str,
        prompt_manager_path: str | Path,
        max_attempts: int = 4,
    ):
        super().__init__(model_id, prompt_manager_path, max_attempts)
        self.engine = ConnectionsGameEngine(categories, max_attempts)

    def play(self) -> int:
        self.engine.reset()
        self._add_message("system", "system", max_attempts=self.max_attempts)

        while not self.engine.is_game_over():
            self._add_message(
                "user",
                "user_prompt",
                remaining_attempts=self.max_attempts - self.engine.num_attempts,
                words=", ".join(sorted(self.engine.remaining_words)),
            )
            self.engine.total_attempts += 1

            try:
                assistant_response = self._get_assistant_response()
                words = self._parse_response(assistant_response)
                result = self.engine.guess(words)
            except Exception as e:
                self._add_message("user", "user_error", error=str(e))
                print(f"-> Error occurred: {str(e)}")
                continue

            if result["category"]:
                self._add_message(
                    "user",
                    "user_correct_guess",
                    words=", ".join(words),
                    category=result["category"],
                )
            elif result["is_off_by_one"]:
                self._add_message("user", "user_offbyone_guess", words=", ".join(words))
            else:
                self._add_message(
                    "user", "user_incorrect_guess", words=", ".join(words)
                )

            if self.engine.all_categories_guessed():
                self._add_message(
                    "user", "user_win", categories=self._get_str_categories()
                )
                return 1

        if not self.engine.all_categories_guessed():
            self._add_message(
                "user", "user_lose", categories=self._get_str_categories()
            )

        return 0

    def _parse_response(self, response: dict) -> set[str]:
        content = response["content"]
        try:
            words = re.search(r"(?<=Guess:).*", content).group()
        except Exception as e:
            print(str(e))
            message = (
                "Couldn't parse your response.\n"
                "Please make sure to provide the response using the following format:\n"
                "Guess: YOUR_GUESS_HERE"
            )
            raise Exception(message)

        return {w.strip().lower() for w in words.split(",")}

    def _get_str_categories(self) -> str:
        return "\n".join(
            f"- {category}: {', '.join(words)}"
            for category, words in self.engine.categories.items()
        )
