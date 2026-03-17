from enum import Enum
from typing import Optional


class Suit(Enum):
    BAMBOO = "bamboo"
    CHARACTERS = "characters"
    DOTS = "dots"
    WINDS = "winds"
    DRAGONS = "dragons"


class Wind(Enum):
    EAST = "east"
    SOUTH = "south"
    WEST = "west"
    NORTH = "north"


class Dragon(Enum):
    CHUN = "chun"      # 中 red/chun
    HATSU = "hatsu"    # 發 green/hatsu
    HAKU = "haku"      # 白 white/haku


class Tile:
    def __init__(
        self,
        suit: Suit,
        rank: Optional[int] = None,
        wind: Optional[Wind] = None,
        dragon: Optional[Dragon] = None,
    ):
        self.suit = suit
        self.rank = rank
        self.wind = wind
        self.dragon = dragon

    def __repr__(self) -> str:
        if self.suit.value in ("bamboo", "characters", "dots"):
            return f"{self.rank}{self.suit.value[0].upper()}"
        elif self.suit.value == "winds":
            return f"{self.wind.value[0].upper()}w"
        else:
            return f"{self.dragon.value[0].upper()}d"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Tile):
            return False
        return (
            self.suit.value == other.suit.value
            and self.rank == other.rank
            and (self.wind.value if self.wind else None) == (other.wind.value if other.wind else None)
            and (self.dragon.value if self.dragon else None) == (other.dragon.value if other.dragon else None)
        )

    def __hash__(self) -> int:
        return hash((
            self.suit.value,
            self.rank,
            self.wind.value if self.wind else None,
            self.dragon.value if self.dragon else None,
        ))