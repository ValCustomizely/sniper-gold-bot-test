"""
Gestionnaire de l'état des pivots multi-sessions
"""
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from enum import Enum
from .config import Config
from .logger import Logger

logger = Logger()

class PivotType(Enum):
    CLASSIC = "classique"
    ASIA = "asie"
    EUROPE = "europe"

class BreakoutState(Enum):
    NONE = "aucune"
    TENSION = "tension"
    PARTIAL = "cassure_partielle"
    VALIDATED = "cassure_validee"
    INVALIDATED = "cassure_invalidee"
    NEUTRAL = "neutre"

class Session(Enum):
    ASIA = "asie"
    EUROPE = "europe"
    US = "us"

class PivotStateManager:
    """Gère l'état complexe du système multi-pivots"""
    
    def __init__(self):
        self.config = Config()
        self.state_file = self.config.PIVOT_STATE_FILE
        self.current_state = self.load_state()
    
    def load_state(self) -> Dict[str, Any]:
        """Charge l'état depuis le fichier"""
        try:
            if not os.path.exists(self.state_file):
                return self._create_default_state()
            
            with open(self.state_file, "r") as f:
                state = json.load(f)
                
                # Validation et migration si nécessaire
                if not self._validate_state(state):
                    logger.warning("État invalide, création d'un nouvel état")
                    return self._create_default_state()
                
                logger.info(f"État pivot chargé: pivot actif={state['pivot_actif']}")
                return state
                
        except Exception as e:
            logger.error(f"Erreur chargement état pivot: {e}")
            return self._create_default_state()
    
    def _create_default_state(self) -> Dict[str, Any]:
        """Crée un état par défaut"""
        today = datetime.utcnow().date().isoformat()
        return {
            "pivot_actif": PivotType.CLASSIC.value,
            "etat_cassure": BreakoutState.NONE.value,
            "session_en_cours": self._get_current_session().value,
            "date": today,
            "switches_count": 0,
            "timestamp_derniere_cassure": None,
            "timestamp_premier_touch_r1": None,
            "timestamp_premier_touch_s1": None,
            "seuil_en_cours": None,
            "prix_cassure": None,
            "touches_tension": [],
            "historique": [],
            # Nouveau : statistiques de fiabilité par seuil
            "seuil_stats": {},
            # Nouveau : tracking du range pour validation pivot
            "range_validation": {
                "in_range_since": None,
                "last_range_check": None
            }
        }
    
    def _validate_state(self, state: Dict[str, Any]) -> bool:
        """Valide la structure de l'état"""
        required_keys = [
            "pivot_actif", "etat_cassure", "session_en_cours", 
            "date", "switches_count", "historique"
        ]
        return all(key in state for key in required_keys)
    
    def save_state(self):
        """Sauvegarde l'état"""
        try:
            with open(self.state_file, "w") as f:
                json.dump(self.current_state, f, indent=2)
            logger.debug("État pivot sauvegardé")
        except Exception as e:
            logger.error(f"Erreur sauvegarde état pivot: {e}")
    
    def _get_current_session(self) -> Session:
        """Détermine la session en cours"""
        hour = datetime.utcnow().hour
        
        if self.config.ASIA_SESSION_START <= hour < self.config.ASIA_SESSION_END:
            return Session.ASIA
        elif self.config.EUROPE_SESSION_START <= hour < self.config.EUROPE_SESSION_END:
            return Session.EUROPE
        else:
            return Session.US
    
    def get_active_pivot(self) -> PivotType:
        """Retourne le pivot actif"""
        return PivotType(self.current_state["pivot_actif"])
    
    def get_breakout_state(self) -> BreakoutState:
        """Retourne l'état de cassure actuel"""
        return BreakoutState(self.current_state["etat_cassure"])
    
    def can_switch_pivot(self) -> bool:
        """Vérifie si on peut encore changer de pivot aujourd'hui"""
        today = datetime.utcnow().date().isoformat()
        
        # Reset quotidien
        if self.current_state["date"] != today:
            self._reset_daily_state()
        
        return self.current_state["switches_count"] < self.config.MAX_DAILY_SWITCHES
    
    def switch_to_pivot(self, new_pivot: PivotType, reason: str = ""):
        """Bascule vers un nouveau pivot"""
        if not self.can_switch_pivot():
            logger.warning(f"Limite de bascules atteinte ({self.config.MAX_DAILY_SWITCHES})")
            return False
        
        old_pivot = self.current_state["pivot_actif"]
        self.current_state["pivot_actif"] = new_pivot.value
        self.current_state["switches_count"] += 1
        self.current_state["etat_cassure"] = BreakoutState.NONE.value
        
        # Historique
        self._add_to_history("pivot_switch", {
            "from": old_pivot,
            "to": new_pivot.value,
            "reason": reason
        })
        
        self.save_state()
        logger.info(f"Bascule pivot: {old_pivot} → {new_pivot.value} ({reason})")
        return True
    
    def set_breakout_state(self, state: BreakoutState, details: Dict[str, Any] = None):
        """Met à jour l'état de cassure"""
        old_state = self.current_state["etat_cassure"]
        self.current_state["etat_cassure"] = state.value
        
        if details:
            self.current_state.update(details)
        
        # Historique
        self._add_to_history("breakout_state", {
            "from": old_state,
            "to": state.value,
            "details": details or {}
        })
        
        self.save_state()
        logger.debug(f"État cassure: {old_state} → {state.value}")
    
    def start_tension_tracking(self, threshold_name: str, price: float):
        """Démarre le suivi de tension sur un seuil"""
        now = datetime.utcnow().isoformat()
        
        # Nettoyer les anciennes touches (> 30min)
        cutoff = datetime.utcnow() - timedelta(minutes=self.config.TENSION_WINDOW)
        self.current_state["touches_tension"] = [
            touch for touch in self.current_state["touches_tension"]
            if datetime.fromisoformat(touch["timestamp"]) > cutoff
        ]
        
        # Ajouter la nouvelle touche
        self.current_state["touches_tension"].append({
            "timestamp": now,
            "threshold": threshold_name,
            "price": price
        })
        
        # Vérifier si on atteint le seuil de tension
        recent_touches = [
            t for t in self.current_state["touches_tension"]
            if t["threshold"] == threshold_name
        ]
        
        if len(recent_touches) >= self.config.TENSION_TOUCHES:
            self.set_breakout_state(BreakoutState.TENSION, {
                "seuil_en_cours": threshold_name,
                "touches_count": len(recent_touches)
            })
            
            self._add_to_history("tension_detected", {
                "threshold": threshold_name,
                "touches": len(recent_touches)
            })
    
    def start_speed_tracking(self, r1_price: float):
        """Démarre le tracking de vitesse R1->R2"""
        self.current_state["timestamp_premier_touch_r1"] = datetime.utcnow().isoformat()
        self.current_state["prix_r1"] = r1_price
        self.save_state()
    
    def check_speed_breakout(self, r2_price: float, current_price: float) -> bool:
        """Vérifie si la cassure R1->R2 est rapide"""
        if not self.current_state.get("timestamp_premier_touch_r1"):
            return False
        
        start_time = datetime.fromisoformat(self.current_state["timestamp_premier_touch_r1"])
        time_diff = (datetime.utcnow() - start_time).total_seconds() / 60
        
        if current_price > r2_price + self.config.BREAKOUT_AMPLITUDE:
            is_fast = time_diff <= self.config.SPEED_THRESHOLD
            
            self._add_to_history("speed_check", {
                "time_minutes": round(time_diff, 2),
                "threshold_minutes": self.config.SPEED_THRESHOLD,
                "is_fast": is_fast
            })
            
            return is_fast
        
        return False
    
    def _reset_daily_state(self):
        """Reset quotidien de l'état"""
        today = datetime.utcnow().date().isoformat()
        self.current_state.update({
            "date": today,
            "switches_count": 0,
            "pivot_actif": PivotType.CLASSIC.value,
            "etat_cassure": BreakoutState.NONE.value,
            "touches_tension": [],
            "historique": []
        })
        logger.info("Reset quotidien de l'état pivot")
        self.save_state()
    
    def _add_to_history(self, event_type: str, data: Dict[str, Any]):
        """Ajoute un événement à l'historique"""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": event_type,
            "data": data
        }
        
        self.current_state["historique"].append(event)
        
        # Limiter la taille de l'historique
        if len(self.current_state["historique"]) > 100:
            self.current_state["historique"] = self.current_state["historique"][-50:]
    
    def should_go_neutral(self) -> bool:
        """Vérifie si on doit passer en état neutre"""
        # Compter les cassures invalidées récentes
        recent_invalidations = [
            event for event in self.current_state["historique"]
            if event["type"] == "breakout_state" 
            and event["data"]["to"] == BreakoutState.INVALIDATED.value
            and self._is_recent_event(event["timestamp"], hours=2)
        ]
        
        return len(recent_invalidations) >= 2
    
    def _is_recent_event(self, timestamp_str: str, hours: int = 2) -> bool:
        """Vérifie si un événement est récent"""
        event_time = datetime.fromisoformat(timestamp_str)
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return event_time > cutoff
    
    def track_breakout_attempt(self, threshold_name: str):
        """Enregistre une tentative de cassure"""
        if "seuil_stats" not in self.current_state:
            self.current_state["seuil_stats"] = {}
        
        if threshold_name not in self.current_state["seuil_stats"]:
            self.current_state["seuil_stats"][threshold_name] = {
                "tentatives": 0,
                "validees": 0,
                "invalidees": 0,
                "score": 0.0,
                "last_update": None
            }
        
        self.current_state["seuil_stats"][threshold_name]["tentatives"] += 1
        self.current_state["seuil_stats"][threshold_name]["last_update"] = datetime.utcnow().isoformat()
        
        self._add_to_history("breakout_attempt", {
            "threshold": threshold_name,
            "total_attempts": self.current_state["seuil_stats"][threshold_name]["tentatives"]
        })
        
        self.save_state()
    
    def track_breakout_result(self, threshold_name: str, success: bool):
        """Enregistre le résultat d'une cassure"""
        if threshold_name not in self.current_state.get("seuil_stats", {}):
            logger.warning(f"Tentative de tracker résultat pour seuil non suivi: {threshold_name}")
            return
        
        stats = self.current_state["seuil_stats"][threshold_name]
        
        if success:
            stats["validees"] += 1
        else:
            stats["invalidees"] += 1
        
        # Calculer le score de fiabilité
        if stats["tentatives"] > 0:
            stats["score"] = round((stats["validees"] / stats["tentatives"]) * 100, 1)
        
        stats["last_update"] = datetime.utcnow().isoformat()
        
        self._add_to_history("breakout_result", {
            "threshold": threshold_name,
            "success": success,
            "new_score": stats["score"],
            "validees": stats["validees"],
            "tentatives": stats["tentatives"]
        })
        
        logger.info(f"Score fiabilité {threshold_name}: {stats['score']}% ({stats['validees']}/{stats['tentatives']})")
        self.save_state()
    
    def get_threshold_reliability(self, threshold_name: str) -> Dict[str, Any]:
        """Retourne les statistiques de fiabilité d'un seuil"""
        if threshold_name in self.current_state.get("seuil_stats", {}):
            return self.current_state["seuil_stats"][threshold_name].copy()
        
        return {
            "tentatives": 0,
            "validees": 0,
            "invalidees": 0,
            "score": 0.0,
            "last_update": None
        }
    
    def is_threshold_reliable(self, threshold_name: str, min_attempts: int = 3, min_score: float = 50.0) -> bool:
        """Vérifie si un seuil est suffisamment fiable pour trader"""
        stats = self.get_threshold_reliability(threshold_name)
        
        # Pas assez de données
        if stats["tentatives"] < min_attempts:
            return True  # On donne le bénéfice du doute
        
        # Seuil peu fiable
        return stats["score"] >= min_score
    
    def check_range_return(self, current_price: float, r1_value: Optional[float], s1_value: Optional[float]) -> bool:
        """Vérifie si le prix est retourné durablement dans le range S1-R1"""
        if not r1_value or not s1_value:
            return False
        
        # Prix dans le range
        if s1_value <= current_price <= r1_value:
            now = datetime.utcnow()
            
            # Première fois dans le range
            if not self.current_state.get("range_validation", {}).get("in_range_since"):
                self.current_state["range_validation"] = {
                    "in_range_since": now.isoformat(),
                    "last_range_check": now.isoformat()
                }
                self.save_state()
                return False
            
            # Vérifier la durée
            in_range_since = datetime.fromisoformat(self.current_state["range_validation"]["in_range_since"])
            duration_minutes = (now - in_range_since).total_seconds() / 60
            
            # Retour durable (30+ minutes)
            if duration_minutes >= 30:
                logger.info(f"Retour durable en range S1-R1 détecté: {duration_minutes:.1f}min")
                return True
        else:
            # Reset si prix sort du range
            self.current_state["range_validation"] = {
                "in_range_since": None,
                "last_range_check": datetime.utcnow().isoformat()
            }
            self.save_state()
        
        return False
