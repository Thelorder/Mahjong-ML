import random
from typing import List, Optional, Self, Tuple
from .tile import Tile, Suit, Dragon, Wind

class Wall:
    """Represents the wall of tiles in the players hand()"""
    
    def __init__(self):
        self.tiles: List[Tile] = []
        self.dead_wall: List[Tuple] = []
        self._build_wall()
        
    def _build_wall(self):
        """Create all 144 tiles and randomly shuffle then"""
        
        for suit in[Suit.BAMBOO,Suit.CHARACTERS,Suit.DOTS]:
            for rank in range(1,10):
                for _ in range(4):
                    self.tiles.append(Tile(suit, rank= rank))
        
        for wind in Wind:
            for _ in range(4):
                self.tiles.append(Tile(Suit.WINDS,wind=wind))
        
        for dragon in Dragon:
            for _ in range(4):
                self.tiles.append(Tile(Suit.DRAGONS, dragon=dragon))
        
        print(f"Build {len(self.tiles)} tiles")
        
        random.shuffle(self.tiles)
    
    def build_wall_for_dealing(self) ->List[List[Tile]]:
        """
        Prepare the wall for dealing by splitting into 4 walls
        Returns a list of 4 walls (each wall is a list of tiles)
        Each player's wall section has 18 stacks (36 tiles)
        """
        
        walls =[]
        tiles_per_wall = len(self.tiles) //4
        
        for i in range(4):
            start = i * tiles_per_wall
            end = start+ tiles_per_wall
            walls.append(self.tiles[start:end])
        
        return walls
    
    def draw_tile(self, from_dead_wall: bool = False) -> Tile:
        """
        Draw a tile from the wall
        If from_dead_wall is True, draw from dead wall 
        """
        if from_dead_wall:
            if not self.dead_wall:
                raise Exception("No tiles in dead wall")
            return self.dead_wall.pop(0)
        else:
            if not self.tiles:
                raise Exception("No tiles left in wall")
            return self.tiles.pop(0)
    
    def set_dead_wall(self, count: int = 14):
        """
        Set aside tiles for the dead wall 
        """    
        
        if len(self.tiles) < count:
            raise Exception("Not enought tiles from dead wall")
        
        self.dead_wall = self.tiles[-count:]
        self.tiles = self.tiles[:-count]
        
    def get_wall_size(self) -> int:
        """Get number of tiles remaining in main wall"""
        return len(self.tiles)
    
    def get_dead_wall_size(self) -> int:
        """Get number of tiles remaining in dead wall"""
        return len(self.dead_wall)
    
    def is_empty(self) -> bool:
        """Cehck if main wall is empty"""        
        return len(self.tiles) == 0
    
    def peek_next_tile(self) ->Optional[Tile]:
        """Look at the next tile without drawing"""
        if self.tiles:
            return self.tiles[0]
        return None
    
    def __str__(self):
        return f"Wall: {len(self.tiles)} tiles, Dead wall: {len(self.dead_wall)} tiles"
    
# if __name__ == "__main__":
#     # Simple test
#     wall = Wall()
#     print(f"Created wall with {wall.get_wall_size()} tiles")
    
#     # Test drawing
#     tile = wall.draw_tile()
#     print(f"Drew tile: {tile}")
#     print(f"Remaining: {wall.get_wall_size()} tiles")
    
#     # Test dead wall
#     wall.set_dead_wall(14)
#     print(f"\nAfter setting dead wall:")
#     print(f"Main wall: {wall.get_wall_size()} tiles")
#     print(f"Dead wall: {wall.get_dead_wall_size()} tiles")
        