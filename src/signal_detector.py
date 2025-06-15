"""
Détecteur de signaux de trading
"""
from typing import List, Dict, Any, Optional
from .config import Config
from .logger import Logger

logger = Logger()

class SignalDetector:
    """Détecte les signaux de trading basés sur les cassures de seuils"""
    
    def __init__(self, state_manager):
        self.state_manager = state_manager
        self.config = Config()
    
    def detect_signals(self, current_price: float, thresholds: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Détecte les signaux basés sur le prix actuel et les seuils"""
        
        # Vérifier si on doit reset l'état
        if self.state_manager.should_reset_for_price(current_price, thresholds):
            self.state_manager.reset_state()
        
        # Détecter les cassures de résistances
        resistance_breaks = self._detect_resistance_breaks(current_price, thresholds)
        if resistance_breaks:
            return self._create_breakout_signal(resistance_breaks, "resistance", current_price)
        
        # Détecter les cassures de supports
        support_breaks = self._detect_support_breaks(current_price, thresholds)
        if support_breaks:
            return self._create_breakout_signal(support_breaks, "support", current_price)
        
        # Détecter les signaux d'approche
        approach_signal = self._detect_approach_signals(current_price, thresholds)
        if approach_signal:
            return approach_signal
        
        return None
    
    def _detect_resistance_breaks(self, current_price: float, thresholds: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Détecte les cassures de résistances"""
        resistance_breaks = []
        
        for threshold in thresholds:
            if threshold["type"] == "résistance":
                if current_price > threshold["valeur"] + self.config.BREAKOUT_THRESHOLD:
                    resistance_breaks.append({
                        "valeur": threshold["valeur"],
                        "nom": threshold["nom"]
                    })
        
        if resistance_breaks:
            # Prendre la résistance la plus haute cassée
            return max(resistance_breaks, key=lambda x: x["valeur"])
        
        return None
    
    def _detect_support_breaks(self, current_price: float, thresholds: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Détecte les cassures de supports"""
        support_breaks = []
        
        for threshold in thresholds:
            if threshold["type"] == "support":
                if current_price < threshold["valeur"] - self.config.BREAKOUT_THRESHOLD:
                    support_breaks.append({
                        "valeur": threshold["valeur"],
                        "nom": threshold["nom"]
                    })
        
        if support_breaks:
            # Prendre le support le plus bas cassé
            return min(support_breaks, key=lambda x: x["valeur"])
        
        return None
    
    def _detect_approach_signals(self, current_price: float, thresholds: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Détecte les signaux d'approche des seuils"""
        pivot = None
        r1 = None
        s1 = None
        
        for threshold in thresholds:
            if threshold["nom"] == "Pivot":
                pivot = threshold["valeur"]
            elif threshold["nom"] == "R1":
                r1 = threshold["valeur"]
            elif threshold["nom"] == "S1":
                s1 = threshold["valeur"]
        
        if not all([pivot, r1, s1]):
            return None
        
        # Signal d'approche R1 (entre pivot et R1 + 0.5)
        if pivot < current_price <= r1 + 0.5:
            distance = round(r1 - current_price, 2)
            return {
                "type": f"🚧📈 -{distance}$ du R1",
                "direction": "bullish_approach",
                "target": "R1",
                "distance": distance
            }
        
        # Signal d'approche S1 (entre S1 - 0.5 et pivot)
        if s1 - 0.5 <= current_price < pivot:
            distance = round(current_price - s1, 2)
            return {
                "type": f"🚧📉 +{distance}$ du S1",
                "direction": "bearish_approach",
                "target": "S1",
                "distance": distance
            }
        
        return None
    
    def _create_breakout_signal(self, broken_threshold: Dict[str, Any], direction: str, current_price: float) -> Dict[str, Any]:
        """Crée un signal de cassure"""
        threshold_value = broken_threshold["valeur"]
        threshold_name = broken_threshold["nom"]
        
        # Calculer l'écart
        if direction == "resistance":
            gap = round(current_price - threshold_value, 2)
            emoji = "📈"
            signal_type = f"{emoji} Cassure {threshold_name} +{gap}$"
        else:  # support
            gap = round(threshold_value - current_price, 2)
            emoji = "📉"
            signal_type = f"{emoji} Cassure {threshold_name} -{gap}$"
        
        # Gérer le compteur de confirmations
        counter = self.state_manager.increment_counter(threshold_name)
        
        # Ajouter indicateur de signal fort
        if counter >= self.config.MIN_CONFIRMATIONS:
            signal_type += " 🚧"
        
        return {
            "type": signal_type,
            "direction": direction,
            "broken_threshold": threshold_value,
            "threshold_name": threshold_name,
            "gap": gap,
            "confirmations": counter,
            "is_strong": counter >= self.config.MIN_CONFIRMATIONS
        }
    
    def calculate_
