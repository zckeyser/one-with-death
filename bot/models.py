from dataclasses import dataclass, asdict, is_dataclass, field
from datetime import datetime
from typing import Optional, Union

from lib.deck import Deck
from lib.graveyard import Graveyard


class SerializableDataclass():
    def to_dict(self):
        return {
            k: asdict(v) if is_dataclass(v) else v
            for k, v
            in asdict(self).items()
        }
    

@dataclass
class MemberInfo(SerializableDataclass):
    id: str
    name: str
    mention: str


@dataclass
class RequiredResponse(SerializableDataclass):
    member: MemberInfo
    action: str
    waiting_for_response_number: int


@dataclass
class OneWithDeathGame(SerializableDataclass):
    id: str
    members: list[MemberInfo]
    deck: Deck
    text_channel: str
    voice_channel: str

    graveyard: Graveyard = field(default_factory=lambda: Graveyard())
    game_started: datetime = field(default_factory=lambda: datetime.now())
    # ID of the member we're waiting on a response from
    waiting_for_response_from: Optional[str]=None
    # action we're waiting for a response on
    waiting_for_response_action: Optional[str]=None
    # if there's a number associated with an action, e.g. scry 4 -> reorder 4
    waiting_for_response_number: Optional[int]=None

    @classmethod
    def from_dict(cls, d: dict[str, any]) -> 'OneWithDeathGame':
        return cls(
            id=d['id'],
            members=[MemberInfo(**member_info) for member_info in d['members']],
            library=Deck(**d['library']),
            graveyard=Graveyard(**d['graveyard']),
            text_channel=d['text_channel'],
            voice_channel=d['voice_channel'],
            waiting_for_response_from=MemberInfo(**d['waiting_for_response_from']) if 'waiting_for_response_from' in d and d['waiting_for_response_from'] else None,
            waiting_for_response_action=d.get('waiting_for_response_action'),
            waiting_for_response_number=d.get('waiting_for_response_number'),
            game_started=datetime.fromisoformat(d['game_started']) if d.get('game_started') else datetime.now()
        )

    def to_dict(self) -> dict[str, Union[str, MemberInfo, Deck]]:
        d = super().to_dict()
        d['game_started'] = d['game_started'].isoformat()
        return d
