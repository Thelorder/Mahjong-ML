from enum import Enum 
from typing import List,Optional 

class Suit(Enum):
    BAMBOO = "bamboo"
    CHARACTERS = "characters"
    DOTS = "dots"
    WINDS = "winds"
    DRAGONS = "dragons"
    
class Wind(Enum):
    SOUTH = "south"
    EAST = "east"
    WEST = "west"
    NORTH = "north"
    
class Dragon(Enum):
    GREEN = "green"
    RED = "red"
    WHITE = "white"
    
class Tile:
    def __init__(self, suit:Suit,rank:Optional[int] = None, wind:Optional[Wind] = None,dragon:Optional[Dragon] = None):
        self.rank = rank
        self.suit = suit
        self.dragon = dragon
        self.wind = wind
    
    def __repr__(self):
        if self.suit in [Suit.BAMBOO, Suit.CHARACTERS, Suit.DOTS]:
            return f"{self.rank}{self.suit.value[0].upper()}"
        elif self.suit == Suit.WINDS:
            return self.wind.value[0].upper()
        else:
            return self.dragon.value[0].upper()
    
    def __eq__(self, other):
        if not isinstance(other, Tile):
            return False
        return (self.suit == other.suit and
                self.rank == other.rank and
                self.wind == other.wind and
                self.dragon == other.dragon)        
            