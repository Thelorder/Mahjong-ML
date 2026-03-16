from typing import List, Optional, Tuple, Set
from enum import Enum
from tile import Tile, Suit, Wind,Dragon
from utils.helpers import is_valid_sequence, is_valid_triplet, is_valid_quad

class PlayerState(Enum):
    """Current State of player"""
    NORMAL = "normal"
    RIICHI = "riichi"
    FURITEN = "furiten"
    TENPAI = "tenpai"

class Player:
    """Represents a Mahjong player with Riichi rules"""
    
    WIND_ORDER = [Wind.EAST, Wind.SOUTH,Wind.WEST,Wind.NORTH]
    
    def __init__(self, name:str,wind: Wind= Wind.EAST):
        self.name = name
        self.wind = wind
        self.hand: List[Tile] = []
        self.melds: List[List[Tile]] = []
        self.concealed_melds: List[List[Tile]] = []  
        self.discards: List[Tile] = []  
        self.discard_indicators: List[str] = []
        
        self.state: PlayerState = PlayerState.NORMAL
        self.riichi_declared: bool = False
        self.riichi_bet: int = 1000  
        self.riichi_discard_index: Optional[int] = None  
        self.in_furiten: bool = False  
        self.temp_furiten: bool = False
        
        self.points: int = 25000
        self.riichi_stick: int = 0
        self.honba: int = 0
        
    # ========== Drawinf & Discarding tiles ==========
    
    def draw_tile(self,tile: Tile):
        """Draw tile from the wall"""
        
        self.hand.append(tile)
        self._sort_hand()
        print(f"{self.name} draws a tile")
        
    def discard_tile(self,index:int, is_riichi_discard:bool =False) -> False:
        """Discard a tile from hand"""
        if index < 0 or index >= len(self.hand):
            raise ValueError(f"Invalid tile index: {index}")
        
        tile = self.hand.pop(index)
        self.discards.append(tile)
        self.discard_indicators.append("R" if is_riichi_discard else " ")
        
        print(f"{self.name} discards {tile}{' (Riichi discard)' if is_riichi_discard else ''}")
        
        if is_riichi_discard:
            self.riichi_declared = True
            self.riichi_declared_index = len(self.discards) - 1
            self.state = PlayerState.RIICHI
            self.points -= self.riichi_bet
        
        return tile    
        
    # ========== Melding (Calls) ==========
    
    def call_chi(self,tile:Tile, hand_indices: List[int]) -> bool:
        """ 
        Call chow using a discarded tile
        Can only be called if not in riichi
        Returns True if successful
        """

        if self.riichi_declared:
            print(f"{self.name} cannot call Chi after declaring Riichi")
            return False
        
        if len(hand_indices) != 2:
            return False
        
        hand_tiles = [self.hand[i] for i in sorted(hand_indices)]
        
        potential_meld =hand_tiles + [tile]
        
        if is_valid_sequence(potential_meld):
            # Remove tiles from hand 
            for i in sorted(hand_indices, reverse=True):
                self.hand.pop(i)
            
            self.melds.append(sorted(potential_meld, key=lambda t: (t.suit.value, t.rank or 0)))
            print(f"{self.name} calls CHI with {potential_meld}")
            return True
        
        return False
        
    def call_pon(self,tile:Tile, hand_indices: List[int]) -> bool:
        """
        Call pung (triplet) using a discarded tile
        Can be called even in riichi (but will break riichi)
        Returns True if successful
        """
        if self.riichi_declared:
            print(f"{self.name} cannot call Pon after declaring Riichi")
            return False
        
        if len(hand_indices) != 2:
            return False 
        
        hand_tiles = [self.hand[i] for i in hand_indices]
        
        potential_meld = hand_tiles + [tile]
        
        if is_valid_triplet(potential_meld):
            for i in sorted(hand_indices, reverse=True):
                self.hand.pop(i)
                
            self.melds.append(potential_meld)
            print(f"{self.name} calls PON with {potential_meld}")
            return True  
        
        return False
    
    def call_kan(self,tile:Tile, hand_indices: List[int]) -> bool:
        """
        Call open kong (quad) using a discarded tile
        Returns True if successful
        """
        
        if self.riichi_declared:
            print(f"{self.name} cannot call Kan after declaring Riichi")
            return False
        
        if len(hand_indices) != 3:
            return False
        
        hand_tiles = [self.hand[i] for i in hand_indices]
        
        first_tile = hand_tiles[0]
        if not all(t == first_tile for t in hand_tiles):
            return False
        
        # Check if discarded tile matches
        if tile != first_tile:
            return False
        
        # Remove tiles from hand
        for i in sorted(hand_indices, reverse=True):
            self.hand.pop(i)
        
        # Add to open melds (kong is open)
        self.melds.append(hand_tiles + [tile])
        print(f"{self.name} calls KAN with {hand_tiles + [tile]}")
        return True
    
    def declare_concealed_kan(self, tile_index: int) -> bool:
        """
        Declare a concealed kong (from own hand)
        Can be done in riichi, but will break riichi if it changes your waits
        Returns True if successful
        """
        if tile_index + 3 > len(self.hand):
            return False
        
        # Check if we have 4 of the same tile
        tiles = [self.hand[tile_index + i] for i in range(4)]
        first_tile = tiles[0]
        
        if all(t == first_tile for t in tiles):
            # Remove tiles from hand
            for i in range(3, -1, -1):
                self.hand.pop(tile_index + i)
            
            # Add to concealed melds (kan is special)
            self.concealed_melds.append(tiles)
            print(f"{self.name} declares concealed KAN with {tiles}")
            return True
        
        return False
    
    def declare_added_kan(self, meld_index: int, tile_index: int) -> bool:
        """
        Add a tile to an existing pon to make it a kan
        Returns True if successful
        """
        if meld_index >= len(self.melds):
            return False
        
        meld = self.melds[meld_index]
        if len(meld) != 3:  # Must be a pon
            return False
        
        # Check if the tile matches the pon
        tile = self.hand[tile_index]
        if tile != meld[0]:
            return False
        
        # Remove tile from hand
        self.hand.pop(tile_index)
        
        # Add to meld
        meld.append(tile)
        print(f"{self.name} upgrades PON to KAN: {meld}")
        return True
        
    # ========== Riichi-specific methods ==========
    
    def declare_riichi(self) -> bool:
        """
        Declare riichi if conditions are met
        Returns True if successful
        """
        can_declare,reason = self.check_riichi_conditions()
        if can_declare:
            print(f"{self.name} declares riichi")
            return True
        else:
            print(f"{self.name} cannot declare Riichi: {reason}")
            return False
        
    def check_riichi_conditions(self) ->Tuple[bool,str]:
        """
        Check if player can declare riichi
        Returns (can_declare, reason_if_cannot)
        """

        if self.riichi_declared:
            return False,"Already in riichi"
        
        if len(self.melds) > 0:
            return False,"Cannot declare riichi with open melds"
        
        if self.points < 1000:
            return False, f"Need 1000 points, have {self.points}"
        
        if not self.is_tenpai():
            return False, "Hand is not tenpai"
        
        return True, "Can declare riichi"
        
    def is_tenpai(self)->bool:
        """
        Check if hand is tenpai (one tile away from winning)
        Checks if hand can be completed by adding any tile
        """
        
        total_meld_tiles = sum(len(meld) for meld in self.melds) + sum(len(meld) for meld in self.concealed_melds)
        hand_tiles_needed = 14 - total_meld_tiles
        
        if len(self.hand) != hand_tiles_needed -1:
            return False
        
        all_possible_tiles = []
        
        for suit in [Suit.BAMBOO,Suit.CHARACTERS,Suit.DOTS]:
            for rank in range(1,10):
                all_possible_tiles.append(Tile(suit,rank=rank))
                
        for wind in Wind:
            all_possible_tiles.append(Tile(Suit.WINDS, wind=wind))
        
        for dragon in Dragon:
            all_possible_tiles.append(Tile(Suit.DRAGONS,dragon=dragon))
            
        for test_tile in all_possible_tiles:
            
            test_hand = self.hand.copy()
            test_hand.append(test_tile)
            test_hand.sort(key=lambda t: (t.suit.value, t.rank or 0))
            
            if self._is_complete_hand(test_hand,total_meld_tiles):
                return True
        return False
    
    # ========== Fruiten specific methods ==========
    
    def update_fruiten(self,all_discards:List[List[Tile]]):
        """
        Update furiten status based on all players' discards
        Furiten is when yu are waiting to draw the winning tile
        """
        
        if self.state == PlayerState.RIICHI:
            my_discrads = set(self.discards)
            
            wait_tiles = self._calculate_wait_tiles()
            
            for tile in wait_tiles:
                if tile in my_discrads:
                    self.in_furiten = True
                    self.state = PlayerState.FURITEN
                    return
            
            self.in_furiten = False
    
    def _calculate_wait_tiles(self) -> Set[Tile]:
        """
        Calculate which tiles would complete the hand
        Returns set of tiles that would make the hand winning
        """
        
        wait_tiles = set()
        total_meld_tiles = sum(len(meld) for meld in self.melds) + sum(len(meld) for meld in self.concealed_melds)
        
        all_posisble_tiles = []
        
        for suit in [Suit.BAMBOO,Suit.CHARACTERS, Suit.DOTS]:
            for rank in range(1,10):
                all_posisble_tiles.append(Tile(suit, rank = rank))
        
        for wind in Wind:
            all_posisble_tiles.append(Tile(Suit.WINDS, wind = wind))

        for dragon in Dragon:
            all_posisble_tiles.append(Tile(Suit.DRAGONS, dragon= dragon))
            
        for test_tile in all_posisble_tiles:
            
            test_hand = self.hand.copy()
            test_hand.append(test_tile)
            test_hand.sort(key=lambda t: (t.suit.value, t.rank or 0))
            
            if self._is_complete_hand(test_hand,total_meld_tiles):
                wait_tiles.add(test_tile)
        
        return wait_tiles
            
            

    def is_in_furiten(self,tile:Tile) -> bool:
        """Check if player is in furiten for a specific tile"""
        if not self.is_in_furiten:
            return False
        
        return tile in self.discards   
        
        
    # ========== Hand Managment ==========
    
    def _sort_hand(self):
        """Sort hand by suit then rank"""
        def sort_key(tile):
            # Suit order: Bamboo, Characters, Dots, Winds, Dragons
            suit_order = {
                Suit.BAMBOO: 0,
                Suit.CHARACTERS: 1, 
                Suit.DOTS: 2,
                Suit.WINDS: 3,
                Suit.DRAGONS: 4
            }
            rank = tile.rank if tile.rank is not None else 0
            return (suit_order[tile.suit], rank)
        
        self.hand.sort(key=sort_key)
    
    def get_hand_size(self) -> int:
        """Get number of tiles in hand"""
        return len(self.hand)
    
    def get_total_tiles(self) -> int:
        """Get total tiles (hand + melds * tiles in melds)"""
        meld_tiles = sum(len(meld) for meld in self.melds)
        concealed_tiles = sum(len(meld) for meld in self.concealed_melds)
        return len(self.hand) + meld_tiles + concealed_tiles
    
    def find_tile_indices(self, target_tile: Tile) -> List[int]:
        """Find all indices of a specific tile in hand"""
        return [i for i, tile in enumerate(self.hand) if tile == target_tile]
    
    def has_tile(self, tile: Tile) -> bool:
        """Check if player has a specific tile in hand"""
        return any(t == tile for t in self.hand)
    
    def count_tile(self, tile: Tile) -> int:
        """Count occurrences of a specific tile in hand"""
        return sum(1 for t in self.hand if t == tile)
    
    def _is_complete_hand(self, tiles:List[Tile], existing_meld_tiles:int =0) -> bool:
        """
        Checks if a list of tiles forms a complete Mahjong hand
        """
        if len(tiles) + existing_meld_tiles != 14:
            return False
        
        if len (tiles) == 0:
            return existing_meld_tiles == 14
        
        if len(tiles) == 2:
            return tiles[0] == tiles[1]
        
        if len(tiles) >= 3 and tiles[0] == tiles[1] == tiles[2]:
            if self._is_complete_hand(tiles[3:],existing_meld_tiles +3):
                return True    

        if tiles[0].suit in [Suit.BAMBOO, Suit.CHARACTERS, Suit.DOTS]:
            rank = tiles[0].rank
            
            found = False
            sequience_indices = []
            
            for i,tile in enumerate(tiles[:5]):
                if(tile.suit == tiles[0].suit and tile.rank == rank + len(sequience_indices)):
                    sequience_indices.append(i)
                    if len(sequience_indices) == 3:
                        found = True
                        break   
                    
            if found:
                remaining = []
                for i,tile in enumerate(tiles):
                    if i not in sequience_indices:
                        remaining.append(tile)
                if self._is_complete_hand(remaining, existing_meld_tiles +3):
                    return True
        return False
            
    

# ========== SIMPLE TEST ==========
if __name__ == "__main__":
    print("Testing Player class...")
    
    # Create a player
    player = Player("Test Player", Wind.EAST)
    print(f"Created: {player}")
    
    # Create some tiles for testing
    tiles = [
        Tile(Suit.BAMBOO, rank=1),
        Tile(Suit.BAMBOO, rank=1),
        Tile(Suit.BAMBOO, rank=1),
        Tile(Suit.BAMBOO, rank=2),
        Tile(Suit.BAMBOO, rank=3),
        Tile(Suit.BAMBOO, rank=4),
        Tile(Suit.BAMBOO, rank=5),
        Tile(Suit.BAMBOO, rank=6),
        Tile(Suit.BAMBOO, rank=7),
        Tile(Suit.BAMBOO, rank=8),
        Tile(Suit.BAMBOO, rank=9),
        Tile(Suit.CHARACTERS, rank=1),
        Tile(Suit.CHARACTERS, rank=1),
    ]
    
    # Draw tiles
    for tile in tiles:
        player.draw_tile(tile)
    
    print(f"\nHand after drawing: {player.show_hand()}")
    print(f"Hand size: {player.get_hand_size()}")
    
    # Test discard
    discarded = player.discard_tile(5)
    print(f"After discarding {discarded}: {player.show_hand()}")
    print(f"Discards: {player.show_discards()}")
    
    # Test riichi check
    can_riichi, reason = player.check_riichi_conditions()
    print(f"\nCan declare Riichi? {can_riichi} - {reason}")
    
    # Test finding tiles
    test_tile = Tile(Suit.BAMBOO, rank=1)
    indices = player.find_tile_indices(test_tile)
    print(f"Indices of {test_tile}: {indices}")
    print(f"Count of {test_tile}: {player.count_tile(test_tile)}")
    
    print("\nPlayer class test complete!")