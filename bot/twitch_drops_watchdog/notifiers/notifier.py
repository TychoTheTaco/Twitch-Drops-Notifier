import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import List, Optional, Iterator, Literal, Dict, Any, TypedDict, Union

from ..twitch import DropCampaign, Game


# Set up logging
logger = logging.getLogger(__name__)


class NewDropCampaignEventOptions(TypedDict):
    games: List[Union[int, str]]


EventName = Literal['new_drop_campaign', 'new_game']


class EventMapType(TypedDict, total=False):
    new_drop_campaign: NewDropCampaignEventOptions
    new_game: Dict[None, None]


class Subscriber(ABC):

    def __init__(self, events: EventMapType):
        self._events = events

    def events(self) -> EventMapType:
        return self._events


class SubscriberIterator(ABC):

    @abstractmethod
    def __iter__(self) -> Iterator[Subscriber]:
        raise NotImplementedError


class Notifier(ABC):

    def __init__(self):
        self._subscribers: [Subscriber] = []
        self._subscriber_iterators: [SubscriberIterator] = []

    def subscribe(self, subscriber: Subscriber | SubscriberIterator):
        if isinstance(subscriber, Subscriber):
            self._subscribers.append(subscriber)
        else:
            self._subscriber_iterators.append(subscriber)

    def _iterate_all_subscribers(self):
        for subscriber in self._subscribers:
            yield subscriber
        for subscriber_iterator in self._subscriber_iterators:
            for subscriber in subscriber_iterator:
                yield subscriber

    def on_new_drop_campaign(self, campaign: DropCampaign):
        for subscriber in self._iterate_all_subscribers():
            options = subscriber.events().get('new_drop_campaign')
            if options is None:
                continue
            games = options['games']

            def contains_game(game: Game) -> bool:
                for g in games:
                    if g == game['id']:
                        return True
                    if isinstance(g, str):
                        if g.lower() == game['displayName'].lower():
                            return True
                return False

            if len(games) > 0 and not contains_game(campaign['game']):
                continue
            try:
                self.notify_on_new_drop_campaign(subscriber, campaign)
            except Exception as exception:
                logger.error(f'Error notifying subscriber: {exception}')

    @abstractmethod
    def notify_on_new_drop_campaign(self, subscriber: Subscriber, campaign: DropCampaign):
        raise NotImplementedError

    def on_new_game(self, game: Game):
        for subscriber in self._iterate_all_subscribers():
            options = subscriber.events().get('new_game')
            if options is None:
                continue
            try:
                self.notify_on_new_game(subscriber, game)
            except Exception as exception:
                logger.error(f'Error notifying subscriber: {exception}')

    @abstractmethod
    def notify_on_new_game(self, subscriber: Subscriber, game: Game):
        raise NotImplementedError


class BufferedNotifier(Notifier):

    def __init__(self):
        super().__init__()
        self._event_buffers: Dict[EventName, Dict[Subscriber, list]] = defaultdict(lambda: defaultdict(list))

    def notify_on_new_drop_campaign(self, subscriber: Subscriber, campaign: DropCampaign):
        self._event_buffers['new_drop_campaign'][subscriber].append(campaign)

    @abstractmethod
    def notify_on_new_drop_campaigns(self, subscriber: Subscriber, campaigns: [DropCampaign]):
        raise NotImplementedError

    def notify_on_new_game(self, subscriber: Subscriber, game: Game):
        self._event_buffers['new_game'][subscriber].append(game)

    @abstractmethod
    def notify_on_new_games(self, subscriber: Subscriber, games: [Game]):
        raise NotImplementedError

    def send_all_events(self):
        subscribers = self._event_buffers['new_drop_campaign']
        for subscriber in subscribers:
            campaigns = subscribers[subscriber]
            if len(campaigns) > 0:
                self.notify_on_new_drop_campaigns(subscriber, campaigns)
        del self._event_buffers['new_drop_campaign']

        subscribers = self._event_buffers['new_game']
        for subscriber in subscribers:
            games = subscribers[subscriber]
            if len(games) > 0:
                self.notify_on_new_games(subscriber, games)
        del self._event_buffers['new_game']
