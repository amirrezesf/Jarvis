from abc import ABC, abstractmethod
from core.events import Utterance

class AudioSource(ABC):
    @abstractmethod
    def listen(self) -> Utterance | None:
        """Block until one utterance is ready and return it."""