"""
Configuration du bot de trading
"""
import os
from dataclasses import dataclass

@dataclass
class Config:
    """Configuration centralisée du bot"""
    
    # APIs
    NOTION_API_KEY: str = os.environ.get("NOTION_API_KEY", "")
    NOTION_DATABASE_ID: str = os.environ.get("NOTION_DATABASE_ID", "")
    SEUILS_DATABASE_ID: str = os.environ.get("SEUILS_DATABASE_ID", "")
    POLYGON_API_KEY: str = os.environ.get("POLYGON_API_KEY", "")
    
    # Trading
    BREAKOUT_THRESHOLD: float = 0.5  # Seuil de cassure en dollars
    RESET_THRESHOLD: float = 0.2     # Seuil de reset en dollars
    MIN_CONFIRMATIONS: int = 5       # Nombre de confirmations pour signal fort
    
    # Calculs
    TP_MULTIPLIER: float = 0.8       # Multiplicateur pour take profit
    SL_OFFSET: float = 1.0           # Offset pour stop loss
    TRAILING_SL_OFFSET: float = 5.0  # Offset pour stop loss suiveur
    
    # Fichiers
    STATE_FILE: str = "etat_cassure.json"
    
    def validate(self):
        """Valide que toutes les clés API sont présentes"""
        required_keys = [
            "NOTION_API_KEY", 
            "NOTION_DATABASE_ID", 
            "SEUILS_DATABASE_ID", 
            "POLYGON_API_KEY"
        ]
        
        missing = []
        for key in required_keys:
            if not getattr(self, key):
                missing.append(key)
        
        if missing:
            raise ValueError(f"Variables d'environnement manquantes: {', '.join(missing)}")
        
        return True
