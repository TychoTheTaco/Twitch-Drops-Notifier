from abc import ABC, abstractmethod
from typing import List, Optional, Iterator


class Notifier(ABC):

    def on_new_drop_campaigns(self, campaigns):
        pass

    def on_new_games(self, games):
        pass


class Recipient:
    """
    Represents the recipient of a notification.
    """

    def __init__(self, game_ids: Optional[List[str]] = None, new_game_notifications: bool = True):
        """
        :param game_ids: The game IDs that this recipient is subscribed to. If none, the recipient should be notified
        for all games.
        :param new_game_notifications: True if this recipient should get new game notifications
        """
        self._game_ids = game_ids
        self._new_game_notifications = new_game_notifications

    @property
    def game_ids(self):
        return self._game_ids

    @property
    def new_game_notifications(self):
        return self._new_game_notifications


class RecipientLoader(ABC):
    """
    A `RecipientLoader` loads recipient data from a source.
    """

    @abstractmethod
    def __iter__(self) -> Iterator[Recipient]:
        raise NotImplementedError
