from dataclasses import dataclass, asdict, is_dataclass

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

@dataclass
class Card(SerializableDataclass):
    name: str
    
    buyback: bool = False


@dataclass
class OneWithDeathGame(SerializableDataclass):
    members: list[MemberInfo]
    library: list[Card]
    graveyard: list[Card]

    current_turn: MemberInfo
    waiting_for_response_from: MemberInfo

    