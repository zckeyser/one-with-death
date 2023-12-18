from dataclasses import dataclass, asdict, is_dataclass
from typing import Optional

from deck import Deck


class SerializableDataclass():
    def to_dict(self):
        return {
            k: asdict(v) if is_dataclass(v) else v
            for k, v
            in asdict(self)
        }
    

@dataclass
class MemberInfo(SerializableDataclass):
    id: str
    name: str
    mention: str


@dataclass
class OneWithDeathGame(SerializableDataclass):
    members: list[MemberInfo]
    library: Deck
    graveyard: Deck
    text_channel: str
    voice_channel: str

    waiting_for_response_from: Optional[MemberInfo]=None

    @classmethod
    def from_dict(cls, d: dict[str, any]) -> 'OneWithDeathGame':
        return cls(
            members=[MemberInfo(**member_info) for member_info in d['members']],
            library=Deck(d['library']),
            graveyard=Deck(d['graveyard']),
            waiting_for_response_from=MemberInfo(**d['waiting_for_response_from']) if 'waiting_for_response_from' in d and d['waiting_for_response_from'] else None
        )
