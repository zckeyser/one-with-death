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
class OneWithDeathGame(SerializableDataclass):
    id: str
    members: list[MemberInfo]
    library: Deck
    text_channel: str
    voice_channel: str

    graveyard: Graveyard = field(default_factory=lambda: Graveyard())
    game_started: datetime = field(default_factory=lambda: datetime.now())
    waiting_for_response_from: Optional[MemberInfo]=None

    @classmethod
    def from_dict(cls, d: dict[str, any]) -> 'OneWithDeathGame':
        return cls(
            id=d['id'],
            members=[MemberInfo(**member_info) for member_info in d['members']],
            library=Deck(**d['library']),
            graveyard=Graveyard(**d['graveyard']),
            text_channel=d['text_channel'],
            voice_channel=d['voice_channel'],
            waiting_for_response_from=MemberInfo(**d['waiting_for_response_from']) if 'waiting_for_response_from' in d and d['waiting_for_response_from'] else None
        )

    def to_dict(self) -> dict[str, Union[str, MemberInfo, Deck]]:
        d = super().to_dict()
        d['game_started'] = d['game_started'].isoformat()
        return d
