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
    
    # Trading - Système multi-pivots
    BREAKOUT_THRESHOLD: float = 0.5      # Legacy - pour compatibilité anciens tests
    BREAKOUT_AMPLITUDE: float = 2.0      # Amplitude de cassure en dollars (R2/S2 + 2$)
    RESET_THRESHOLD: float = 0.2         # Seuil de reset en dollars
    MIN_CONFIRMATIONS: int = 5           # Nombre de confirmations pour signal fort
    STABILIZATION_TIME: int = 15         # Minutes pour valider une cassure
    STABILIZATION_RANGE: float = 2.0     # Fourchette de stabilisation en dollars
    SPEED_THRESHOLD: int = 3             # Minutes max pour R1->R2 (vitesse)
    TENSION_WINDOW: int = 30             # Minutes pour détecter tension (3 touches)
    TENSION_TOUCHES: int = 3             # Nombre de touches pour tension
    VOLATILITY_THRESHOLD: float = 1.0    # % de volatilité max par heure
    MAX_DAILY_SWITCHES: int = 2          # Bascules max par jour
    
    # Calculs
    TP_MULTIPLIER: float = 0.8           # Multiplicateur pour take profit
    SL_OFFSET: float = 1.0               # Offset pour stop loss
    TRAILING_SL_OFFSET: float = 5.0      # Offset pour stop loss suiveur
    
    # Fichiers
    STATE_FILE: str = "etat_cassure.json"
    PIVOT_STATE_FILE: str = "etat_pivot.json"
    
    # Sessions UTC
    ASIA_SESSION_START: int = 0          # 0h UTC
    ASIA_SESSION_END: int = 4            # 4h UTC
    EUROPE_SESSION_START: int = 4        # 4h UTC  
    EUROPE_SESSION_END: int = 13         # 13h UTC
    US_SESSION_START: int = 13           # 13h UTC
    US_SESSION_END: int = 23             # 23h UTC
    
    # Calculs de pivots
    CLASSIC_CALC_HOUR: int = 23          # 23h UTC + 3min
    ASIA_CALC_HOUR: int = 4              # 4h UTC + 3min
    EUROPE_CALC_HOUR: int = 13           # 13h UTC + 3min
    CALC_MINUTE_OFFSET: int = 3          # +3 minutes après l'heure
    
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
