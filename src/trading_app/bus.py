"""
bus.py

Central application publish/subscribe event bus.

Traffic channels:

    market
        Market data events

    commands
        Trading commands

    system
        Application lifecycle events


Unlike asyncio.Queue, published events are
broadcast to all subscribers.
"""

from __future__ import annotations


import asyncio

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, AsyncIterator



# ==========================================================
# Event Types
# ==========================================================


class EventType(Enum):

    QUOTES = auto()

    POSITION = auto()

    ORDER = auto()

    ACCOUNT = auto()

    WATCHLIST = auto()

    SYSTEM = auto()



class CommandType(Enum):

    BUY = auto()

    SELL = auto()

    LIMIT_BUY = auto()

    LIMIT_SELL = auto()

    STOP = auto()

    STOP_LIMIT = auto()

    CANCEL = auto()

    FLATTEN = auto()

    PANIC = auto()



# ==========================================================
# Events
# ==========================================================


@dataclass(slots=True)
class MarketEvent:

    event: EventType

    payload: Any



@dataclass(slots=True)
class CommandEvent:

    command: CommandType

    payload: Any



@dataclass(slots=True)
class SystemEvent:

    name: str

    payload: Any = None



# ==========================================================
# Event Bus
# ==========================================================


class EventBus:


    MARKET_QUEUE_SIZE = 1000

    COMMAND_QUEUE_SIZE = 200

    SYSTEM_QUEUE_SIZE = 100



    def __init__(self):

        #
        # Subscriber registries
        #

        self.market_subscribers = []

        self.command_subscribers = []

        self.system_subscribers = []



    # ======================================================
    # Internal subscriber creation
    # ======================================================

    def _create_subscription(
        self,
        subscribers,
        size,
    ):

        queue = asyncio.Queue(
            maxsize=size
        )

        subscribers.append(
            queue
        )

        return queue



    # ======================================================
    # Market subscriptions
    # ======================================================


    def subscribe_market(
        self,
    ) -> AsyncIterator[MarketEvent]:

        queue = (
            self._create_subscription(
                self.market_subscribers,
                self.MARKET_QUEUE_SIZE,
            )
        )


        async def iterator():

            try:

                while True:

                    yield await queue.get()


            finally:

                self.market_subscribers.remove(
                    queue
                )


        return iterator()



    async def publish_market(
        self,
        event: MarketEvent,
    ):

        print("STATE:", event.payload)
        for queue in list(
            self.market_subscribers
        ):

            if not queue.full():

                await queue.put(
                    event
                )



    # ======================================================
    # Command subscriptions
    # ======================================================


    def subscribe_commands(
        self,
    ) -> AsyncIterator[CommandEvent]:


        queue = (
            self._create_subscription(
                self.command_subscribers,
                self.COMMAND_QUEUE_SIZE,
            )
        )


        async def iterator():

            try:

                while True:

                    yield await queue.get()


            finally:

                self.command_subscribers.remove(
                    queue
                )


        return iterator()



    async def publish_command(
        self,
        event: CommandEvent,
    ):


        for queue in list(
            self.command_subscribers
        ):

            if not queue.full():

                await queue.put(
                    event
                )



    # ======================================================
    # System subscriptions
    # ======================================================


    def subscribe_system(
        self,
    ) -> AsyncIterator[SystemEvent]:


        queue = (
            self._create_subscription(
                self.system_subscribers,
                self.SYSTEM_QUEUE_SIZE,
            )
        )


        async def iterator():

            try:

                while True:

                    yield await queue.get()


            finally:

                self.system_subscribers.remove(
                    queue
                )


        return iterator()



    async def publish_system(
        self,
        event: SystemEvent,
    ):


        for queue in list(
            self.system_subscribers
        ):

            if not queue.full():

                await queue.put(
                    event
                )