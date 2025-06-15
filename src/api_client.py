"""
Client pour l'API Polygon.io
"""
import httpx
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from .logger import Logger

logger = Logger()

class PolygonClient:
    """Client pour récupérer les données de l'or via Polygon.io"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.polygon.io/v2/aggs/ticker/C:XAUUSD/range"
        
    def get_last_trading_day(self) -> datetime:
        """Retourne la dernière journée de trading"""
        today = datetime.utcnow().date()
        weekday = today.weekday()
        
        # Lundi = 0, Dimanche = 6
        if weekday == 0:  # Lundi
            return today - timedelta(days=3)  # Vendredi précédent
        elif weekday == 6:  # Dimanche
            return today - timedelta(days=2)  # Vendredi précédent
        elif weekday == 5:  # Samedi
            return today - timedelta(days=1)  # Vendredi
        else:
            return today - timedelta(days=1)  # Jour précédent
    
    async def get_last_trading_day_data(self) -> Optional[Dict[str, Any]]:
        """Récupère les données de la dernière journée de trading"""
        try:
            last_day = self.get_last_trading_day().isoformat()
            url = f"{self.base_url}/1/day/{last_day}/{last_day}"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params={
                    "adjusted": "true",
                    "sort": "desc",
                    "limit": 1,
                    "apiKey": self.api_key
                }, timeout=10)
                
                response.raise_for_status()
                data = response.json()
                results = data.get("results", [])
                
                if not results:
                    logger.warning("Aucune donnée journalière disponible")
                    return None
                
                candle = results[0]
                return {
                    "high": candle["h"],
                    "low": candle["l"],
                    "close": candle["c"],
                    "open": candle["o"],
                    "volume": candle["v"],
                    "timestamp": candle["t"]
                }
                
        except httpx.HTTPError as e:
            logger.error(f"Erreur HTTP lors de la récupération des données journalières: {e}")
            return None
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des données journalières: {e}")
            return None
    
    async def get_current_minute_data(self) -> Optional[Dict[str, Any]]:
        """Récupère les données de la dernière minute"""
        try:
            today = datetime.utcnow().date().isoformat()
            url = f"{self.base_url}/1/minute/{today}/{today}"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params={
                    "adjusted": "true",
                    "sort": "desc",
                    "limit": 1,
                    "apiKey": self.api_key
                }, timeout=10)
                
                response.raise_for_status()
                data = response.json()
                results = data.get("results", [])
                
                if not results:
                    logger.warning("Aucune donnée minute disponible")
                    return None
                
                candle = results[0]
                return {
                    "high": candle["h"],
                    "low": candle["l"],
                    "close": candle["c"],
                    "open": candle["o"],
                    "volume": candle["v"],
                    "timestamp": candle["t"]
                }
                
        except httpx.HTTPError as e:
            logger.error(f"Erreur HTTP lors de la récupération des données minute: {e}")
            return None
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des données minute: {e}")
            return None
    
    async def get_asian_session_data(self) -> Optional[Dict[str, Any]]:
        """Récupère les données de la session asiatique (pour futures améliorations)"""
        # TODO: Implémenter la récupération des données de session asiatique
        # Cette méthode sera utilisée pour les améliorations futures
        pass
