"""
Client pour interagir avec Notion
"""
from notion_client import Client
from typing import List, Dict, Any, Optional
from datetime import datetime
from .logger import Logger

logger = Logger()

class NotionManager:
    """Gère les interactions avec Notion"""
    
    def __init__(self, api_key: str, signals_db_id: str, thresholds_db_id: str):
        self.client = Client(auth=api_key)
        self.signals_db_id = signals_db_id
        self.thresholds_db_id = thresholds_db_id
    
    async def save_thresholds(self, thresholds: List[Dict[str, Any]]):
        """Sauvegarde les seuils dans Notion"""
        try:
            today = datetime.utcnow().date().isoformat()
            
            for threshold in thresholds:
                properties = {
                    "Valeur": {"number": threshold["valeur"]},
                    "Type": {"select": {"name": threshold["type"]}},
                    "Date": {"date": {"start": today}}
                }
                
                self.client.pages.create(
                    parent={"database_id": self.thresholds_db_id},
                    properties=properties
                )
            
            logger.info(f"Seuils sauvegardés dans Notion: {len(thresholds)} seuils")
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde seuils Notion: {e}")
    
    async def get_daily_thresholds(self, date: str) -> List[Dict[str, Any]]:
        """Récupère les seuils du jour depuis Notion"""
        try:
            response = self.client.databases.query(
                database_id=self.thresholds_db_id,
                filter={
                    "property": "Date",
                    "date": {"equals": date}
                }
            )
            
            thresholds = []
            for page in response.get("results", []):
                props = page["properties"]
                
                valeur = props.get("Valeur", {}).get("number")
                type_obj = props.get("Type", {}).get("select")
                type_name = type_obj.get("name") if type_obj else None
                
                if valeur is not None and type_name:
                    thresholds.append({
                        "valeur": valeur,
                        "type": type_name
                    })
            
            logger.info(f"Seuils récupérés de Notion: {len(thresholds)} seuils")
            return thresholds
            
        except Exception as e:
            logger.error(f"Erreur récupération seuils Notion: {e}")
            return []
    
    async def save_signal(self, signal: Dict[str, Any], current_price: float, volume: int, trading_levels: Dict[str, Any], comment: str = "Signal via Polygon.io"):
        """Sauvegarde un signal dans Notion avec support avancé"""
        try:
            now = datetime.utcnow()
            
            properties = {
                "Signal": {
                    "title": [{"text": {"content": signal["type"]}}]
                },
                "Horodatage": {
                    "date": {"start": now.isoformat()}
                },
                "Prix": {
                    "number": float(current_price)
                },
                "Volume": {
                    "number": int(volume)
                },
                "Commentaire": {
                    "rich_text": [{"text": {"content": comment}}]
                }
            }
            
            # Ajouter les niveaux de trading s'ils existent
            if "sl" in trading_levels:
                properties["SL"] = {"number": trading_levels["sl"]}
            
            if "trailing_sl" in trading_levels:
                properties["SL suiveur"] = {"number": trading_levels["trailing_sl"]}
            
            if "tp" in trading_levels:
                properties["TP"] = {"number": trading_levels["tp"]}
            
            # Ajouter un deuxième objectif si disponible
            if "target_2" in trading_levels:
                properties["TP2"] = {"number": trading_levels["target_2"]}
            
            self.client.pages.create(
                parent={"database_id": self.signals_db_id},
                properties=properties
            )
            
            logger.info(f"Signal avancé sauvegardé dans Notion: {signal['type']}")
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde signal Notion: {e}")
