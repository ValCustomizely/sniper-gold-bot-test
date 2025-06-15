"""
Détecteur de signaux avancé avec système multi-pivots
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from .config import Config
from .logger import Logger
from .pivot_state_manager import PivotStateManager, PivotType, BreakoutState
from .pivot_session_manager import PivotSessionManager
from .breakout_validator import BreakoutValidator

logger = Logger()

class EnhancedSignalDetector:
    """Détecteur de signaux avec logique multi-pivots avancée"""
    
    def __init__(self, pivot_state_manager: PivotStateManager, session_manager: PivotSessionManager):
        self.config = Config()
        self.state_manager = pivot_state_manager
        self.session_manager = session_manager
        self.breakout_validator = BreakoutValidator(pivot_state_manager)
    
    async def detect_signals(self, current_price: float) -> Optional[Dict[str, Any]]:
        """Point d'entrée principal pour la détection de signaux"""
        
        # 1. Vérifier si on doit calculer de nouveaux pivots
        await self._check_pivot_calculations()
        
        # 2. Obtenir les seuils du pivot actif
        active_thresholds = self._get_active_thresholds()
        if not active_thresholds:
            logger.warning("Aucun seuil actif disponible")
            return None
        
        # 3. Vérifier la volatilité excessive
        if self.breakout_validator.check_volatility():
            if self.state_manager.get_breakout_state() != BreakoutState.NEUTRAL:
                self.state_manager.set_breakout_state(BreakoutState.NEUTRAL, {
                    "raison": "volatilite_excessive"
                })
                logger.warning("Passage en mode neutre - volatilité excessive")
        
        # 4. Si on est en mode neutre, pas de signaux
        if self.state_manager.get_breakout_state() == BreakoutState.NEUTRAL:
            return {
                "type": "🚫 Mode NEUTRE - Marché trop erratique",
                "direction": "neutral",
                "status": "blocked"
            }
        
        # 5. Détecter les signaux avec le validateur de cassures
        signal = self.breakout_validator.check_breakout(current_price, active_thresholds)
        
        # 6. Vérifier les bascules de pivots si cassure validée
        if signal and signal.get("status") == "validated":
            await self._check_pivot_switch(signal, current_price)
        
        # 7. Ajouter les informations de contexte
        if signal:
            signal = self._enrich_signal(signal, current_price, active_thresholds)
        
        return signal
    
    async def _check_pivot_calculations(self):
        """Vérifie et effectue les calculs de pivots si nécessaire"""
        pivot_to_calculate = self.session_manager.should_calculate_pivots()
        
        if pivot_to_calculate:
            logger.info(f"Calcul des pivots {pivot_to_calculate.value} requis")
            
            # Calculer les nouveaux pivots
            new_pivots = await self.session_manager.calculate_session_pivots(pivot_to_calculate)
            
            if new_pivots:
                # Si ce sont les pivots classiques à 23h03, on bascule automatiquement
                if pivot_to_calculate == PivotType.CLASSIC:
                    self.state_manager.switch_to_pivot(PivotType.CLASSIC, "calcul_quotidien")
                
                logger.info(f"Pivots {pivot_to_calculate.value} calculés et disponibles")
            else:
                logger.error(f"Échec du calcul des pivots {pivot_to_calculate.value}")
    
    def _get_active_thresholds(self) -> List[Dict[str, Any]]:
        """Retourne les seuils du pivot actif"""
        active_pivot = self.state_manager.get_active_pivot()
        thresholds = self.session_manager.get_cached_pivots(active_pivot)
        
        if not thresholds:
            logger.warning(f"Aucun seuil disponible pour pivot {active_pivot.value}")
            return []
        
        return thresholds
    
    async def _check_pivot_switch(self, signal: Dict[str, Any], current_price: float):
        """Vérifie si une bascule de pivot est nécessaire après une cassure validée"""
        
        if not self.state_manager.can_switch_pivot():
            return
        
        current_hour = datetime.utcnow().hour
        active_pivot = self.state_manager.get_active_pivot()
        threshold_name = signal.get("threshold_name", "")
        
        # Logique de bascule selon les spécifications
        
        # Entre 4h et 13h UTC: possibilité de basculer vers Asie
        if (self.config.ASIA_CALC_HOUR <= current_hour < self.config.EUROPE_CALC_HOUR and
            active_pivot == PivotType.CLASSIC and
            self._is_extreme_threshold(threshold_name)):
            
            # Vérifier si les pivots Asie sont disponibles
            asia_pivots = self.session_manager.get_cached_pivots(PivotType.ASIA)
            if asia_pivots:
                success = self.state_manager.switch_to_pivot(
                    PivotType.ASIA, 
                    f"cassure_validee_{threshold_name}"
                )
                if success:
                    logger.info("Bascule vers pivots Asie suite à cassure validée")
        
        # Après 13h UTC: possibilité de basculer vers Europe
        elif (current_hour >= self.config.EUROPE_CALC_HOUR and
              active_pivot in [PivotType.CLASSIC, PivotType.ASIA] and
              self._is_extreme_threshold(threshold_name)):
            
            # Vérifier si les pivots Europe sont disponibles
            europe_pivots = self.session_manager.get_cached_pivots(PivotType.EUROPE)
            if europe_pivots:
                success = self.state_manager.switch_to_pivot(
                    PivotType.EUROPE,
                    f"cassure_validee_{threshold_name}"
                )
                if success:
                    logger.info("Bascule vers pivots Europe suite à cassure validée")
    
    def _is_extreme_threshold(self, threshold_name: str) -> bool:
        """Vérifie si c'est un seuil extrême (R2 ou S2)"""
        return threshold_name.startswith("R2") or threshold_name.startswith("S2")
    
    def _enrich_signal(self, signal: Dict[str, Any], current_price: float, thresholds: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Enrichit le signal avec des informations de contexte"""
        
        # Ajouter le pivot actif
        signal["pivot_actif"] = self.state_manager.get_active_pivot().value
        
        # Ajouter l'état de cassure
        signal["etat_cassure"] = self.state_manager.get_breakout_state().value
        
        # Calculer les niveaux de trading si cassure validée
        if signal.get("status") == "validated":
            trading_levels = self._calculate_trading_levels(signal, current_price, thresholds)
            signal["trading_levels"] = trading_levels
        
        # Ajouter le contexte de session
        current_hour = datetime.utcnow().hour
        if self.config.ASIA_SESSION_START <= current_hour < self.config.ASIA_SESSION_END:
            signal["session"] = "asie"
        elif self.config.EUROPE_SESSION_START <= current_hour < self.config.EUROPE_SESSION_END:
            signal["session"] = "europe"
        else:
            signal["session"] = "us"
        
        return signal
    
    def _calculate_trading_levels(self, signal: Dict[str, Any], current_price: float, thresholds: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calcule les niveaux de trading pour une cassure validée"""
        if not signal.get("broken_threshold"):
            return {}
        
        broken_threshold = signal["broken_threshold"]
        direction = signal["direction"]
        
        levels = {}
        
        # Stop Loss
        if direction == "bullish":
            levels["sl"] = round(broken_threshold - self.config.SL_OFFSET, 2)
            levels["trailing_sl"] = round(current_price + self.config.TRAILING_SL_OFFSET, 2)
        else:  # bearish
            levels["sl"] = round(broken_threshold + self.config.SL_OFFSET, 2)
            levels["trailing_sl"] = round(current_price - self.config.TRAILING_SL_OFFSET, 2)
        
        # Take Profit basé sur le pivot
        pivot_value = self._get_pivot_value(thresholds)
        if pivot_value is not None:
            tp = broken_threshold + (broken_threshold - pivot_value) * self.config.TP_MULTIPLIER
            levels["tp"] = round(tp, 2)
        
        # Niveaux suivants pour scaling out
        if direction == "bullish":
            # Prochaine résistance
            next_resistance = self._get_next_resistance(broken_threshold, thresholds)
            if next_resistance:
                levels["target_2"] = next_resistance
        else:
            # Prochain support
            next_support = self._get_next_support(broken_threshold, thresholds)
            if next_support:
                levels["target_2"] = next_support
        
        return levels
    
    def _get_pivot_value(self, thresholds: List[Dict[str, Any]]) -> Optional[float]:
        """Récupère la valeur du pivot"""
        for threshold in thresholds:
            if threshold["type"] == "pivot":
                return threshold["valeur"]
        return None
    
    def _get_next_resistance(self, broken_level: float, thresholds: List[Dict[str, Any]]) -> Optional[float]:
        """Trouve la prochaine résistance au-dessus du niveau cassé"""
        resistances = [
            t["valeur"] for t in thresholds 
            if t["type"] == "résistance" and t["valeur"] > broken_level
        ]
        return min(resistances) if resistances else None
    
    def _get_next_support(self, broken_level: float, thresholds: List[Dict[str, Any]]) -> Optional[float]:
        """Trouve le prochain support en-dessous du niveau cassé"""
        supports = [
            t["valeur"] for t in thresholds 
            if t["type"] == "support" and t["valeur"] < broken_level
        ]
        return max(supports) if supports else None
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Retourne un résumé de l'état actuel du système"""
        return {
            "pivot_actif": self.state_manager.get_active_pivot().value,
            "etat_cassure": self.state_manager.get_breakout_state().value,
            "switches_count": self.state_manager.current_state["switches_count"],
            "can_switch": self.state_manager.can_switch_pivot(),
            "pivots_disponibles": {
                pivot_type.value: self.session_manager.get_cached_pivots(pivot_type) is not None
                for pivot_type in PivotType
            }
        }
