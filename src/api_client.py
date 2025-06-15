"""
Client pour l'API Polygon.io
"""
import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from .logger import Logger

logger = Logger()

class PolygonClient:
    """Client pour récupérer les données de l'or via Polygon.io"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.polygon.io/v2/aggs/ticker/C:XAUUSD/range"
        
    def get_previous_trading_day_for_thresholds(self) -> datetime:
        """Retourne le jour à utiliser pour calculer les seuils (données de la veille)"""
        now = datetime.now(timezone.utc)
        today = now.date()
        weekday = today.weekday()
        
        # Logique seuils : toujours données de la veille
        # Sauf dimanche et lundi → utiliser vendredi
        
        if weekday == 6:  # Dimanche
            return today - timedelta(days=2)  # Vendredi
        elif weekday == 0:  # Lundi
            return today - timedelta(days=3)  # Vendredi 
        elif weekday == 5:  # Samedi
            return today - timedelta(days=1)  # Vendredi
        else:  # Mardi, Mercredi, Jeudi, Vendredi
            return today - timedelta(days=1)  # Hier
    
    def get_current_date_for_minute_data(self) -> datetime:
        """Retourne la date à utiliser pour les données minute (temps réel)"""
        now = datetime.now(timezone.utc)
        today = now.date()
        weekday = today.weekday()
        hour = now.hour
        
        # Pour données minute : selon horaires d'ouverture du marché
        # L'or trade : Dimanche 22h00 UTC à Vendredi 22h00 UTC
        
        if weekday == 5:  # Samedi - marché fermé
            return today - timedelta(days=1)  # Dernières données de vendredi
        elif weekday == 6:  # Dimanche
            if hour < 22:  # Avant ouverture dimanche 22h UTC
                return today - timedelta(days=2)  # Dernières données de vendredi
            else:  # Après ouverture dimanche
                return today  # Données du dimanche
        elif weekday == 4 and hour >= 22:  # Vendredi après fermeture 22h UTC
            return today  # Vendredi mais marché fermé
        else:
            return today  # Jour courant
    
    async def get_last_trading_day_data(self) -> Optional[Dict[str, Any]]:
        """Récupère les données journalières pour calculer les seuils (données de la veille)"""
        try:
            target_date = self.get_previous_trading_day_for_thresholds()
            date_str = target_date.isoformat()
            
            url = f"https://api.polygon.io/v2/aggs/ticker/C:XAUUSD/range/1/day/{date_str}/{date_str}"
            
            logger.info(f"Calcul seuils - récupération données journalières: {date_str}")
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params={
                    "adjusted": "true",
                    "sort": "desc",
                    "limit": 1,
                    "apikey": self.api_key
                }, timeout=10)
                
                if response.status_code != 200:
                    logger.error(f"Erreur API Polygon journalier: {response.status_code} - {response.text}")
                    return None
                
                data = response.json()
                
                if data.get("status") != "OK":
                    logger.error(f"Statut API journalier non OK: {data.get('status')} - {data.get('message', 'Pas de message')}")
                    return None
                
                results = data.get("results", [])
                
                if not results:
                    logger.warning(f"Aucune donnée journalière disponible pour {date_str}")
                    return None
                
                candle = results[0]
                logger.info(f"Données journalières pour seuils récupérées: Open={candle['o']}, High={candle['h']}, Low={candle['l']}, Close={candle['c']}")
                
                return {
                    "high": candle["h"],
                    "low": candle["l"],
                    "close": candle["c"],
                    "open": candle["o"],
                    "volume": candle["v"],
                    "timestamp": candle["t"],
                    "date_used": date_str  # Pour debugging
                }
                
        except httpx.HTTPError as e:
            logger.error(f"Erreur HTTP lors de la récupération des données journalières: {e}")
            return None
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des données journalières: {e}")
            return None
    
    async def get_current_minute_data(self) -> Optional[Dict[str, Any]]:
        """Récupère les données minute pour le suivi temps réel"""
        try:
            target_date = self.get_current_date_for_minute_data()
            date_str = target_date.isoformat()
            
            # Si on cherche des données passées (marché fermé)
            if target_date < datetime.now(timezone.utc).date():
                logger.info(f"Marché fermé - récupération dernières données minute de {date_str}")
                return await self._get_end_of_day_minute_data(target_date)
            
            url = f"{self.base_url}/1/minute/{date_str}/{date_str}"
            
            logger.info(f"Récupération données minute temps réel: {date_str}")
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params={
                    "adjusted": "true",
                    "sort": "desc",
                    "limit": 10,
                    "apikey": self.api_key
                }, timeout=10)
                
                if response.status_code != 200:
                    logger.error(f"Erreur API Polygon minute: {response.status_code} - {response.text}")
                    return None
                
                data = response.json()
                
                if data.get("status") != "OK":
                    logger.error(f"Statut API minute non OK: {data.get('status')} - {data.get('message', 'Pas de message')}")
                    return None
                
                results = data.get("results", [])
                
                if not results:
                    logger.warning(f"Aucune donnée minute disponible pour {date_str}")
                    return None
                
                candle = results[0]
                timestamp_dt = datetime.fromtimestamp(candle['t']/1000, timezone.utc)
                logger.info(f"Données minute temps réel récupérées: Close={candle['c']} à {timestamp_dt}")
                
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
    
    async def _get_end_of_day_minute_data(self, date: datetime.date) -> Optional[Dict[str, Any]]:
        """Récupère les données de fin de journée pour une date passée"""
        try:
            date_str = date.isoformat()
            url = f"{self.base_url}/1/minute/{date_str}/{date_str}"
            
            logger.info(f"Récupération données de fin de journée: {date_str}")
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params={
                    "adjusted": "true",
                    "sort": "desc",  # Plus récent en premier
                    "limit": 50,  # Plus de données pour être sûr d'avoir la fin de journée
                    "apikey": self.api_key
                }, timeout=15)
                
                if response.status_code != 200:
                    logger.error(f"Erreur API pour données historiques: {response.status_code}")
                    # Fallback sur les données journalières
                    return await self._get_daily_close_as_minute_data(date)
                
                data = response.json()
                
                if data.get("status") != "OK":
                    logger.error(f"Statut API non OK pour données historiques: {data.get('status')}")
                    return await self._get_daily_close_as_minute_data(date)
                
                results = data.get("results", [])
                
                if not results:
                    logger.warning(f"Aucune donnée minute historique pour {date_str}")
                    return await self._get_daily_close_as_minute_data(date)
                
                # Prendre la dernière donnée de la journée (la plus récente)
                candle = results[0]
                timestamp_dt = datetime.fromtimestamp(candle['t']/1000, timezone.utc)
                
                logger.info(f"Données minute historiques récupérées: Close={candle['c']} à {timestamp_dt}")
                
                return {
                    "high": candle["h"],
                    "low": candle["l"],
                    "close": candle["c"],
                    "open": candle["o"],
                    "volume": candle["v"],
                    "timestamp": candle["t"]
                }
                
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des données historiques pour {date}: {e}")
            # Fallback sur les données journalières
            return await self._get_daily_close_as_minute_data(date)
    
    async def _get_daily_close_as_minute_data(self, date: datetime.date) -> Optional[Dict[str, Any]]:
        """Fallback: utilise les données journalières comme données minute"""
        try:
            date_str = date.isoformat()
            url = f"{self.base_url}/1/day/{date_str}/{date_str}"
            
            logger.info(f"Fallback: récupération données journalières pour {date_str}")
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params={
                    "adjusted": "true",
                    "apikey": self.api_key
                }, timeout=10)
                
                if response.status_code != 200:
                    logger.error(f"Erreur fallback données journalières: {response.status_code}")
                    return None
                
                data = response.json()
                
                if data.get("status") != "OK":
                    logger.error(f"Statut fallback non OK: {data.get('status')}")
                    return None
                
                results = data.get("results", [])
                
                if not results:
                    logger.error(f"Aucune donnée journalière disponible pour {date_str}")
                    return None
                
                candle = results[0]
                logger.info(f"Données journalières utilisées comme fallback: Close={candle['c']}")
                
                return {
                    "high": candle["h"],
                    "low": candle["l"],
                    "close": candle["c"],
                    "open": candle["o"],
                    "volume": candle["v"],
                    "timestamp": candle["t"]
                }
                
        except Exception as e:
            logger.error(f"Erreur lors du fallback journalier pour {date}: {e}")
            return None
    
    async def _try_minute_data_for_date(self, date: datetime.date) -> Optional[Dict[str, Any]]:
        """Essaie de récupérer les données minute pour une date spécifique"""
        try:
            date_str = date.isoformat()
            url = f"{self.base_url}/1/minute/{date_str}/{date_str}"
            
            logger.info(f"Tentative données minute pour: {date_str}")
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params={
                    "adjusted": "true",
                    "sort": "desc",
                    "limit": 10,
                    "apikey": self.api_key
                }, timeout=10)
                
                if response.status_code != 200:
                    return None
                
                data = response.json()
                if data.get("status") != "OK":
                    return None
                
                results = data.get("results", [])
                if not results:
                    return None
                
                candle = results[0]
                logger.info(f"Données minute trouvées pour {date_str}: Close={candle['c']}")
                
                return {
                    "high": candle["h"],
                    "low": candle["l"],
                    "close": candle["c"],
                    "open": candle["o"],
                    "volume": candle["v"],
                    "timestamp": candle["t"]
                }
                
        except Exception as e:
            logger.error(f"Erreur lors de la tentative pour {date}: {e}")
            return None
    
    async def get_asian_session_data(self) -> Optional[Dict[str, Any]]:
        """Récupère les données de la session asiatique (pour futures améliorations)"""
        # TODO: Implémenter la récupération des données de session asiatique
        # Cette méthode sera utilisée pour les améliorations futures
        pass
