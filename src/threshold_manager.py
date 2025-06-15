"""
Gestionnaire des seuils de trading (supports, résistances, pivots)
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from .logger import Logger

logger = Logger()

class ThresholdManager:
    """Gère les calculs et le stockage des seuils de trading"""
    
    def __init__(self, notion_manager):
        self.notion_manager = notion_manager
        self.current_thresholds = []
        self.pivot_value = None
    
    def calculate_pivot_points(self, daily_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Calcule les points pivots basés sur les données journalières"""
        try:
            high = daily_data["high"]
            low = daily_data["low"]
            close = daily_data["close"]
            
            # Calcul du pivot principal
            pivot = round((high + low + close) / 3, 2)
            
            # Calcul des résistances
            r1 = round((2 * pivot) - low, 2)
            r2 = round(pivot + (high - low), 2)
            r3 = round(high + 2 * (pivot - low), 2)
            
            # Calcul des supports
            s1 = round((2 * pivot) - high, 2)
            s2 = round(pivot - (high - low), 2)
            s3 = round(low - 2 * (high - pivot), 2)
            
            thresholds = [
                {"valeur": r3, "type": "résistance", "nom": "R3"},
                {"valeur": r2, "type": "résistance", "nom": "R2"},
                {"valeur": r1, "type": "résistance", "nom": "R1"},
                {"valeur": pivot, "type": "pivot", "nom": "Pivot"},
                {"valeur": s1, "type": "support", "nom": "S1"},
                {"valeur": s2, "type": "support", "nom": "S2"},
                {"valeur": s3, "type": "support", "nom": "S3"},
            ]
            
            logger.info(f"Points pivots calculés - Pivot: {pivot}, R1: {r1}, S1: {s1}")
            return thresholds
            
        except Exception as e:
            logger.error(f"Erreur calcul points pivots: {e}")
            return []
    
    async def load_daily_thresholds(self):
        """Charge les seuils du jour depuis Notion"""
        try:
            today = datetime.utcnow().date().isoformat()
            thresholds_data = await self.notion_manager.get_daily_thresholds(today)
            
            # Organiser les seuils
            supports = []
            resistances = []
            pivots = []
            
            for threshold in thresholds_data:
                if threshold["type"] == "support":
                    supports.append(threshold)
                elif threshold["type"] == "résistance":
                    resistances.append(threshold)
                elif threshold["type"] == "pivot":
                    pivots.append(threshold)
            
            # Trier et nommer
            self.current_thresholds = []
            
            # Résistances (triées par valeur croissante)
            for i, resistance in enumerate(sorted(resistances, key=lambda x: x["valeur"])):
                resistance["nom"] = f"R{i+1}"
                self.current_thresholds.append(resistance)
            
            # Pivots
            for pivot in pivots:
                pivot["nom"] = "Pivot"
                self.current_thresholds.append(pivot)
                self.pivot_value = pivot["valeur"]
            
            # Supports (triés par valeur décroissante)
            for i, support in enumerate(sorted(supports, key=lambda x: x["valeur"], reverse=True)):
                support["nom"] = f"S{i+1}"
                self.current_thresholds.append(support)
            
            logger.info(f"Seuils chargés: {len(self.current_thresholds)} seuils")
            
        except Exception as e:
            logger.error(f"Erreur chargement seuils: {e}")
            self.current_thresholds = []
    
    def get_thresholds(self) -> List[Dict[str, Any]]:
        """Retourne les seuils actuels"""
        return self.current_thresholds
    
    def get_pivot(self) -> Optional[float]:
        """Retourne la valeur du pivot"""
        return self.pivot_value
    
    def get_threshold_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Récupère un seuil par son nom"""
        for threshold in self.current_thresholds:
            if threshold.get("nom") == name:
                return threshold
        return None
    
    def get_resistances(self) -> List[Dict[str, Any]]:
        """Retourne uniquement les résistances"""
        return [t for t in self.current_thresholds if t["type"] == "résistance"]
    
    def get_supports(self) -> List[Dict[str, Any]]:
        """Retourne uniquement les supports"""
        return [t for t in self.current_thresholds if t["type"] == "support"]
    
    def calculate_take_profit(self, broken_threshold: float, pivot: Optional[float]) -> Optional[float]:
        """Calcule le take profit basé sur le seuil cassé et le pivot"""
        if broken_threshold is None or pivot is None:
            return None
        
        # TP = seuil_cassé + (seuil_cassé - pivot) * 0.8
        return round(broken_threshold + (broken_threshold - pivot) * 0.8, 2)
