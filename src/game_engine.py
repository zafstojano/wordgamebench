from abc import ABC, abstractmethod
from collections import Counter

HARD_CAP_MAX_ATTEMPTS = 10


class BaseGameEngine(ABC):
    def __init__(self, max_attempts: int):
        self.max_attempts = max_attempts
        self.num_attempts = 0  # number of valid attempts in the game
        self.total_attempts = 0  # number of total attempts in the game

    @abstractmethod
    def reset(self):
        self.num_attempts = 0
        self.total_attempts = 0

    @abstractmethod
    def guess(self, guess):
        pass

    def is_game_over(self) -> bool:
        return (
            self.num_attempts >= self.max_attempts
            or self.total_attempts >= HARD_CAP_MAX_ATTEMPTS
        )


class WordleGameEngine(BaseGameEngine):
    def __init__(self, word: str, max_attempts: int = 6) -> None:
        super().__init__(max_attempts)
        self.valid_words = set()
        self._load_valid_words()
        self.word = self._process_word(word)
        self._validate_word(self.word)
        self.guesses = set()

    def _load_valid_words(self):
        with open("src/words.txt", "r") as file:
            for line in file:
                word = line.strip()
                if word:
                    self.valid_words.add(word)

    def reset(self) -> None:
        super().reset()
        self.guesses = set()

    def _process_word(self, word: str) -> str:
        return word.strip().lower().replace(" ", "")

    def _validate_word(self, word: str) -> None:
        if not word.isalpha():
            raise ValueError(
                f"The word must contain only letters. You provided: {word}"
            )
        if len(word) != 5:
            raise ValueError(
                f"The word must be 5 letters long. The word {word} is {len(word)} letters long"
            )
        if word not in self.valid_words:
            raise ValueError(f"The word {word} is not in the dictionary of valid words")

    def guess(self, guess: str) -> dict:
        guess = self._process_word(guess)
        self._validate_word(guess)

        if guess in self.guesses:
            raise ValueError("You already guessed that word")

        self.guesses.add(guess)
        true_letter_count = Counter(self.word)
        result = {idx: {} for idx in range(len(guess))}

        # First give priority to correct letters in correct positions
        for idx, letter in enumerate(guess):
            result[idx]["index"] = idx
            result[idx]["letter"] = letter
            if letter == self.word[idx]:
                result[idx]["is_in_correct_position"] = True
                true_letter_count[letter] -= 1
            else:
                result[idx]["is_in_correct_position"] = False

        # Then check for correct letters in wrong positions
        for idx, letter in enumerate(guess):
            if result[idx]["is_in_correct_position"]:
                result[idx]["is_in_word"] = True
                continue
            if true_letter_count[letter] > 0:
                result[idx]["is_in_word"] = True
                true_letter_count[letter] -= 1
            else:
                result[idx]["is_in_word"] = False

        self.num_attempts += 1
        return result

    def is_word_guessed(self, guess: str) -> bool:
        return self._process_word(guess) == self.word


class ConnectionsGameEngine(BaseGameEngine):
    def __init__(self, categories: dict[str, list[str]], max_attempts: int = 4) -> None:
        super().__init__(max_attempts)
        self._validate_categories(categories)
        self.categories = {
            category: set(words) for category, words in categories.items()
        }
        self.guessed_categories = 0
        self.remaining_words = set(
            word for words in self.categories.values() for word in words
        )

    def reset(self) -> None:
        super().reset()
        self.guessed_categories = 0
        self.remaining_words = set(
            word for words in self.categories.values() for word in words
        )

    def _validate_categories(self, categories: dict[str, set[str]]) -> None:
        if len(categories) != 4:
            raise ValueError("You must provide exactly 4 categories")
        if any(len(words) != 4 for words in categories.values()):
            raise ValueError("Each category must have exactly 4 words")

    def guess(self, words: set[str]) -> dict:
        if len(words) != 4:
            raise ValueError(
                f"You must guess exactly 4 words, you provided {len(words)}: {', '.join(words)}"
            )

        for category, words_in_category in self.categories.items():
            if words == words_in_category:
                self.guessed_categories += 1
                self.remaining_words -= words
                return {"category": category, "is_off_by_one": False}
            elif len(words_in_category - words) == 1:
                self.num_attempts += 1
                return {"category": None, "is_off_by_one": True}

        self.num_attempts += 1
        return {"category": None, "is_off_by_one": False}

    def is_game_over(self) -> bool:
        return super().is_game_over() or self.all_categories_guessed()

    def all_categories_guessed(self) -> bool:
        return self.guessed_categories == 4
