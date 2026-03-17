from typing import List, Optional, Tuple, Set
from enum import Enum
from tile import Tile, Suit, Wind,Dragon
from utils.helpers import is_valid_sequence, is_valid_triplet, is_valid_quad
from wall import Wall

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
        
        self.is_tenpai: bool = False
        self.tenpai_wait_tiles: Set[Tile] = set()
        
        self.points: int = 25000
        self.riichi_stick: int = 0
        self.honba: int = 0
        
    # ========== Drawinf & Discarding tiles ==========
    
    def draw_tile(self,tile: Tile):
        """Draw tile from the wall"""
        
        self.hand.append(tile)
        self._sort_hand()
        print(f"{self.name} draws a tile")
        
        self.update_tenpai()
        
    def discard_tile(self,index:int, is_riichi_discard:bool =False) -> False:
        """Discard a tile from hand"""
        if index < 0 or index >= len(self.hand):
            raise ValueError(f"Invalid tile index: {index}")
        
        tile = self.hand.pop(index)
        self.discards.append(tile)
        self.discard_indicators.append("R" if is_riichi_discard else " ")
        
        print(f"{self.name} discards {tile}{' (Riichi)' if is_riichi_discard else ''}")
        
        if is_riichi_discard:
            remaining = self.hand.copy()
            remaining.sort(key=lambda t: (t.suit.value, t.rank or 0))
            if not self._is_tenpai_13_tiles(remaining):
                print("Warning: riichi discard does not leave tenpai")
            self.riichi_declared = True
            self.riichi_discard_index  = len(self.discards) - 1
            self.points -= self.riichi_bet
            self.state = PlayerState.RIICHI
            self.points -= self.riichi_bet
        else:
            self.update_tenpai()
        
        return tile    
        
    # ========== Melding (Calls) ==========
    def _draw_kan_replacemnet(self,wall:Wall):
        """Draw replacement tile from dead wall after any kan"""
        if wall.get_dead_wall_size() == 0:
            print("Warning: dead wall empty — cannot draw replacement")
            return
        replacement = wall.draw_tile(from_dead_wall=True)
        self.draw_tile(replacement)  # this also sorts + updates tenpai
        print(f"{self.name} draws replacement after kan: {replacement}")
    
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
        
        self.update_tenpai( )
        
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
        
        self.update_tenpai()
        
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
        
        self.update_tenpai()
        
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
        can,reason, _ = self.can_declare_riichi()
        if can:
            print(f"{self.name} declares riichi")
            return True
        else:
            print(f"{self.name} cannot declare Riichi: {reason}")
            return False
    
    def can_declare_riichi(self) -> Tuple[bool,str,Optional[List[Tile]]]:
        """
        Returns:
            (can_declare, reason, list_of_safe_discard_tiles_if_yes)
        """
        if self.riichi_declared:
            return False,"Alredy in riichi", None

        if self.melds:  # open melds
            return False, "Cannot riichi with open melds", None

        if self.points < 1000:
            return False, f"Need 1000 points, have {self.points}", None
        
        total_meld_tiles = sum(len(m) for m in self.melds) + sum(len(m) for m in self.concealed_melds)
        expected_hand_size = 14 - total_meld_tiles
        
        if len(self.hand) != expected_hand_size:
            return False, f"Hand size is {len(self.hand)}, expected {expected_hand_size}", None
        
        safe_discards = []
        
        for i in range(len(self.hand)):
            tile_to_discard =self.hand[i]
            remaining = self.hand[:i] + self.hand[i+1:]
            if self._is_tenpai_13_tiles(remaining):
                safe_discards.append(tile_to_discard)
                
        if safe_discards:
            # remove duplicates
            unique_safe = []
            seen = set()
            for t in safe_discards:
                if str(t) not in seen:
                    unique_safe.append(t)
                    seen.add(str(t))
            return True, "Can declare Riichi", unique_safe
        else:
            return False, "No discard leads to tenpai", None
    
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
        
        self.update_tenpai()
        
        if not self._check_tenpai():
            return False, "Hand is not tenpai"
        
        return True, "Can declare riichi"
        
    def _check_tenpai(self)->bool:
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
    
    def update_tenpai(self):
        """Check if hand is tenpai and update state accordingly"""
        was_tenpai = self.is_tenpai
        self.is_tenpai = self._check_tenpai()
        
        if self.is_tenpai:
            self.tenpai_wait_tiles = self._calculate_wait_tiles()
            
            # Update state based on conditions
            if self.riichi_declared:
                self.state = PlayerState.RIICHI
            elif self.in_furiten:
                self.state = PlayerState.FURITEN
            else:
                self.state = PlayerState.TENPAI
        else:
            self.tenpai_wait_tiles = set()
            if not self.riichi_declared and not self.in_furiten:
                self.state = PlayerState.NORMAL
        
        # Log state change if it happened
        if was_tenpai != self.is_tenpai:
            if self.is_tenpai:
                print(f"{self.name} is now TENPAI! Waiting for: {[str(t) for t in self.tenpai_wait_tiles]}")
            else:
                print(f"{self.name} is no longer tenpai")
    
    def _is_tenpai_13_tiles(self, tiles_13: List[Tile]) -> bool:
        """
        Checks if a 13-tile hand is tenpai (i.e. can be completed by adding one tile)
        """
        total_meld_tiles = sum(len(m) for m in self.melds) + sum(len(m) for m in self.concealed_melds)
        hand_tiles_needed = 14 - total_meld_tiles

        if len(tiles_13) != hand_tiles_needed - 1:
            return False

        # Try adding each possible tile and check if it completes the hand
        for test_tile in self._get_all_possible_tiles():
            test_hand = tiles_13 + [test_tile]
            test_hand.sort(key=lambda t: (t.suit.value, t.rank or 0))
            if self._is_complete_hand(test_hand, total_meld_tiles):
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
    
    def _get_all_possible_tiles(self) -> List[Tile]:
        """Cached or static list of all 34 unique tile types"""
        tiles = []
        for suit in [Suit.BAMBOO, Suit.CHARACTERS, Suit.DOTS]:
            for rank in range(1,10):
                tiles.append(Tile(suit,rank=rank))
        for wind in Wind:
            tiles.append(Tile(Suit.WINDS, wind=wind))
        for dragon in Dragon:
            tiles.append(Tile(Suit.DRAGONS, dragon=dragon))
        return tiles
    
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
    
    def _is_complete_hand(self, tiles: List[Tile], existing_meld_tiles: int = 0) -> bool:
        """
        Checks if tiles + existing melds form a standard winning hand (4 melds + 1 pair)
        Assumes tiles is already sorted!
        """
        total_tiles = len(tiles) + existing_meld_tiles
        if total_tiles != 14:
            return False

        # Base case: nothing left → success only if we used exactly 14 tiles
        if len(tiles) == 0:
            return True

        # Try to find the janto (pair) — we need exactly one
        for i in range(len(tiles) - 1):
            if tiles[i] == tiles[i + 1]:
                # Remove pair, recurse on the rest (must be pure melds)
                remaining = tiles[:i] + tiles[i+2:]
                if self._check_melds_only(remaining, existing_meld_tiles + 2):
                    return True

        return False

    def _check_melds_only(self, tiles: List[Tile], counted_so_far: int) -> bool:
        """Recursive check that remaining tiles form melds only (no more pair needed)"""
        n = len(tiles)
        if n == 0:
            return counted_so_far == 14

        if n < 3:
            return False

        first = tiles[0]

        # --- Triplet (pon) ---
        if n >= 3 and tiles[1] == first and tiles[2] == first:
            if self._check_melds_only(tiles[3:], counted_so_far + 3):
                return True

        # --- Kan (open/concealed) — treat as 4-of-a-kind ---
        if n >= 4 and tiles[1] == first and tiles[2] == first and tiles[3] == first:
            if self._check_melds_only(tiles[4:], counted_so_far + 4):
                return True

        # --- Sequence (chow) — only for suited tiles ---
        if first.suit in (Suit.BAMBOO, Suit.CHARACTERS, Suit.DOTS) and first.rank is not None:
            r = first.rank
            found_indices = [0]  # first tile used

            pos = 1
            needed = [r + 1, r + 2]

            while pos < n and len(found_indices) < 3:
                t = tiles[pos]
                if t.suit == first.suit and t.rank == needed[len(found_indices) - 1]:
                    found_indices.append(pos)
                    pos += 1
                else:
                    pos += 1

            if len(found_indices) == 3:
                remaining = [tiles[j] for j in range(n) if j not in found_indices]
                if self._check_melds_only(remaining, counted_so_far + 3):
                    return True

        return False
    
    def get_wait_tile_display(self) -> str:
        """Get a string of the current wait tiles"""
        
        if not self.tenpai_wait_tiles:
            return "No waits"
        
        waits_by_suit = {}
        for tile in self.tenpai_wait_tiles:
            suit_str = tile.suit.value
            if suit_str not in waits_by_suit:
                waits_by_suit[suit_str] = []
            waits_by_suit[suit_str].append(str(tile))
        
        result = []
        for suit, tile in waits_by_suit.items():
            result.append(f"{suit}:{' '.join(tiles)}")
        return" | ".join(result)       
    
    def show_hand(self, hide_last: bool = False) -> str:
        """Display hand as string"""
        if not self.hand:
            return "Empty hand"
        
        if hide_last and self.state == PlayerState.RIICHI:
            # Hide one tile when in riichi (for display)
            return ' '.join(str(t) for t in self.hand[:-1]) + " ?"
        
        return ' '.join(str(tile) for tile in self.hand)

    def show_melds(self) -> str:
        """Display open melds as string"""
        if not self.melds:
            return "No open melds"
        return ' | '.join(' '.join(str(t) for t in meld) for meld in self.melds)

    def show_concealed_melds(self) -> str:
        """Display concealed melds (kan) as string"""
        if not self.concealed_melds:
            return ""
        return ' | '.join(' '.join(str(t) for t in meld) for meld in self.concealed_melds)

    def show_discards(self) -> str:
        """Display discards with riichi indicators"""
        if not self.discards:
            return "No discards"
        
        result = []
        for i, (tile, indicator) in enumerate(zip(self.discards, self.discard_indicators)):
            if indicator == "R":
                result.append(f"*{tile}*")  # Highlight riichi discards
            else:
                result.append(str(tile))
            
            # Add line breaks every 6 tiles for readability
            if (i + 1) % 6 == 0 and i + 1 < len(self.discards):
                result.append("\n         ")
        
        return ' '.join(result)

    def get_state_indicator(self) -> str:
        """Get visual indicator for player state"""
        if self.state == PlayerState.RIICHI:
            return "🎋"  # Riichi bamboo symbol
        elif self.state == PlayerState.FURITEN:
            return "⚠️"  # Furiten warning
        elif self.state == PlayerState.TENPAI:
            return "🎯" # Tenpai targe
        return ""

    def __str__(self):
        return f"{self.name} ({self.wind.value}) {self.get_state_indicator()}"
    
    def check_win(self, tile:Optional[Tile] = None, from_discard: bool = True) -> bool:
        """
        Check if current hand is a winning hand
        If tile is provided, check with that tile added
        """
        hand_copy = self.hand.copy()
        
        if tile:
            hand_copy.append(tile)
            
        total_meld_tiles = sum(len(meld) for meld in self.melds) + sum(len(meld) for meld in self.concealed_melds)
        total_tiles = len(hand_copy) + total_meld_tiles
        
        if total_tiles != 14:
            return False
        
        # Check furiten (can't win on discard if in furiten)
        if from_discard and tile and self.in_furiten:
            if tile in self.discards:
                print(f"{self.name} is in furiten, cannot win on discard")
                return False
        
        # Sort the hand for checking
        hand_copy.sort(key=lambda t: (t.suit.value, t.rank or 0))
        
        # Check if hand is complete (4 melds + 1 pair)
        return self._is_complete_hand(hand_copy, total_meld_tiles)            
        

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