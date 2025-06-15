"""
Gestionnaire du contexte temporel pour l'adaptation des critères de validation
"""
from datetime import datetime, time
from typing import Dict, Any, Tuple
from enum import Enum
from .config import Config
from .logger import Logger

logger = Logger()

class SessionActivity(Enum):
    LOW = "low"      # Activité faible
    MEDIUM = "medium"  # Activité moyenne
    HIGH = "high"    # Activité élevée

class TemporalContextManager:
    """Gère l'adaptation des critères selon le contexte temporel"""
    
    def __init__(self):
        self.config = Config()
        
        # Profils de sessions avec critères adaptés
        self.session_profiles = {
            "asia": {
                "activity": SessionActivity.LOW,
                "stabilization_time": 20,  # +5min par rapport au standard
                "min_range_session": 6.0,  # Range minimum pour pivots valides
                "volatility_tolerance": 0.8,  # Plus tolérant (-0.2%)
                "speed_multiplier": 1.5,    # Mouvements plus lents
                "description": "Session calme - critères renforcés"
            },
            "europe": {
                "activity": SessionActivity.MEDIUM, 
                "stabilization_time": 15,  # Standard
                "min_range_session": 8.0,
                "volatility_tolerance": 1.0,  # Standard
                "speed_multiplier": 1.0,
                "description": "Session standard"
            },
            "us": {
                "activity": SessionActivity.HIGH,
                "stabilization_time": 10,  # -5min, mouvements rapides
                "min_range_session": 12.0,  # Range plus important requis
                "volatility_tolerance": 1.2,  # Plus permissif (+0.2%)
                "speed_multiplier": 0.7,    # Mouvements plus rapides
                "description": "Session active - validation accélérée"
            }
        }
    
    def get_current_session_profile(self) -> Dict[str, Any]:
        """Retourne le profil de la session actuelle"""
        current_session = self._get_current_session_name()
        return self.session_profiles.get(current_session, self.session_profiles["europe"])
    
    def _get_current_session_name(self) -> str:
        """Détermine la session actuelle"""
        hour = datetime.utcnow().hour
        
        if self.config.ASIA_SESSION_START <= hour < self.config.ASIA_SESSION_END:
            return "asia"
        elif self.config.EUROPE_SESSION_START <= hour < self.config.EUROPE_SESSION_END:
            return "europe"
        else:
            return "us"
    
    def get_adapted_stabilization_time(self) -> int:
        """Retourne le temps de stabilisation adapté à la session"""
        profile = self.get_current_session_profile()
        return profile["stabilization_time"]
    
    def get_adapted_volatility_threshold(self) -> float:
        """Retourne le seuil de volatilité adapté"""
        profile = self.get_current_session_profile()
        return profile["volatility_tolerance"]
    
    def get_adapted_speed_threshold(self) -> float:
        """Retourne le seuil de vitesse adapté (R1->R2)"""
        profile = self.get_current_session_profile()
        base_speed = self.config.SPEED_THRESHOLD
        return base_speed * profile["speed_multiplier"]
    
    def is_session_data_valid(self, ohlc_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Valide si les données de session sont suffisantes pour calculer des pivots fiables"""
        if not ohlc_data:
            return False, "Aucune donnée disponible"
        
        session_range = ohlc_data["high"] - ohlc_data["low"]
        profile = self.get_current_session_profile()
        min_range = profile["min_range_session"]
        
        if session_range < min_range:
            reason = f"Range insuffisant: {session_range:.2f}$ < {min_range}$ requis pour {profile['description']}"
            logger.warning(reason)
            return False, reason
        
        return True, f"Données valides - Range: {session_range:.2f}$"
    
    def should_use_enhanced_criteria(self) -> bool:
        """Vérifie si on doit utiliser des critères renforcés"""
        profile = self.get_current_session_profile()
        return profile["activity"] == SessionActivity.LOW
    
    def get_session_context_info(self) -> Dict[str, Any]:
        """Retourne des informations complètes sur le contexte de session"""
        profile = self.get_current_session_profile()
        session_name = self._get_current_session_name()
        
        return {
            "session": session_name,
            "activity_level": profile["activity"].value,
            "stabilization_time": profile["stabilization_time"],
            "volatility_threshold": profile["volatility_tolerance"],
            "speed_threshold": self.get_adapted_speed_threshold(),
            "min_range_required": profile["min_range_session"],
            "description": profile["description"],
            "enhanced_criteria": self.should_use_enhanced_criteria()
        }
    
    def is_pivot_switch_time_appropriate(self, target_session: str) -> bool:
        """Vérifie si c'est le bon moment pour basculer vers un pivot de session"""
        current_hour = datetime.utcnow().hour
        
        # Règles temporelles pour les bascules
        if target_session == "asia":
            # Bascule Asie possible entre 4h et 13h
            return self.config.ASIA_CALC_HOUR <= current_hour < self.config.EUROPE_CALC_HOUR
        elif target_session == "europe":
            # Bascule Europe possible après 13h
            return current_hour >= self.config.EUROPE_CALC_HOUR
        
        return False
    
    def get_breakout_confidence_modifier(self, threshold_name: str) -> float:
        """Retourne un modificateur de confiance selon le contexte"""
        profile = self.get_current_session_profile()
        current_time = datetime.utcnow().time()
        
        # Modificateurs horaires
        hour = current_time.hour
        
        # Heures de faible confiance (transitions, week-end approchant)
        low_confidence_hours = [23, 0, 1, 22]  # Autour de minuit et fin de semaine US
        high_confidence_hours = [8, 9, 10, 14, 15, 16]  # Heures de forte activité
        
        base_modifier = 1.0
        
        if hour in low_confidence_hours:
            base_modifier *= 0.8  # Réduction de confiance
        elif hour in high_confidence_hours:
            base_modifier *= 1.2  # Augmentation de confiance
        
        # Modificateur selon l'activité de session
        if profile["activity"] == SessionActivity.LOW:
            base_modifier *= 0.9
        elif profile["activity"] == SessionActivity.HIGH:
            base_modifier *= 1.1
        
        return round(base_modifier, 2)
    
    def log_session_context(self):
        """Log le contexte de session actuel"""
        context = self.get_session_context_info()
        logger.info(
            f"Contexte session: {context['session'].upper()} | "
            f"Activité: {context['activity_level']} | "
            f"Stabilisation: {context['stabilization_time']}min | "
            f"Volatilité: {context['volatility_threshold']}% | "
            f"Vitesse: {context['speed_threshold']:.1f}min"
        )
