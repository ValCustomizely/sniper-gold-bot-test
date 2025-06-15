"""
Gestionnaire de l'état du bot (persistance des cassures)
"""
import json
import os
from typing import Dict, Any, Optional
from .config import Config
from .logger import Logger

logger = Logger()

class StateManager:
    """Gère la persistance de l'état du bot"""
    
    def __init__(self):
        self.config = Config()
        self.state_file = self.config.STATE_FILE
        self.current_state = self.load_state()
    
    def load_state(self) -> Dict[str, Any]:
        """Charge l'état depuis le fichier"""
        try:
            if not os.path.exists(self.state_file):
                return {"seuil": None, "compteur": 0}
            
            with open(self.state_file, "r") as f:
                state = json.load(f)
                logger.info(f"État chargé: {state}")
                return state
                
        except Exception as e:
            logger.error(f"Erreur chargement état: {e}")
            return {"seuil": None, "compteur": 0}
    
    def save_state(self, threshold_name: Optional[str], counter: int):
        """Sauvegarde l'état"""
        try:
            state = {"seuil": threshold_name, "compteur": counter}
            
            with open(self.state_file, "w") as f:
                json.dump(state, f)
            
            self.current_state = state
            logger.info(f"État sauvegardé: {state}")
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde état: {e}")
    
    def get_current_threshold(self) -> Optional[str]:
        """Retourne le seuil actuellement cassé"""
        return self.current_state.get("seuil")
    
    def get_counter(self) -> int:
        """Retourne le compteur de confirmations"""
        return self.current_state.get("compteur", 0)
    
    def reset_state(self):
        """Remet l'état à zéro"""
        self.save_state(None, 0)
        logger.info("État remis à zéro")
    
    def increment_counter(self, threshold_name: str) -> int:
        """Incrémente le compteur pour un seuil donné"""
        current_threshold = self.get_current_threshold()
        
        if current_threshold == threshold_name:
            # Même seuil, on incrémente
            new_counter = self.get_counter() + 1
        else:
            # Nouveau seuil, on repart à 1
            new_counter = 1
        
        self.save_state(threshold_name, new_counter)
        return new_counter
    
    def should_reset_for_price(self, current_price: float, thresholds: list) -> bool:
        """Vérifie si l'état doit être remis à zéro basé sur le prix"""
        current_threshold_name = self.get_current_threshold()
        
        if not current_threshold_name:
            return False
        
        # Trouver le seuil actuel
        current_threshold = None
        for threshold in thresholds:
            if threshold.get("nom") == current_threshold_name:
                current_threshold = threshold
                break
        
        if not current_threshold:
            return False
        
        threshold_value = current_threshold["valeur"]
        reset_threshold = self.config.RESET_THRESHOLD
        
        # Logique de reset
        if current_threshold_name.startswith("R"):  # Résistance
            # Reset si le prix repasse sous la résistance - seuil
            if current_price <= threshold_value - reset_threshold:
                return True
        elif current_threshold_name.startswith("S"):  # Support
            # Reset si le prix repasse au-dessus du support + seuil
            if current_price >= threshold_value + reset_threshold:
                return True
        
        return False
