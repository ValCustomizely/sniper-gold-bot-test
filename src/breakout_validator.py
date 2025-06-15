def check_breakout(self, current_price: float, thresholds: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Vérifie et valide les cassures selon la logique avancée avec contexte temporel"""
        
        # Ajouter le prix actuel à l'historique
        self.add_price_point(current_price)
        
        # 1. Vérifier si le prix est retourné durablement dans le range (revalidation pivot)
        range_return_signal = self._check_range_return(current_price, thresholds)
        if range_return_signal:
            return range_return_signal
        
        # 2. Vérifier les cassures de R2/S2 avec critères de fiabilité
        extreme_breakout = self._check_extreme_breakouts_with_reliability(current_price, thresholds)
        if extreme_breakout:
            return self._process_extreme_breakout(extreme_breakout, current_price, thresholds)
        
        # 3. Vérifier les zones de tension
        tension_signal = self._check_tension_zones(current_price, thresholds)
        if tension_signal:
            return tension_signal
        
        # 4. Vérifier les invalidations de cassures en cours
        self._check_breakout_invalidation(current_price, thresholds)
        
        # 5. Valider les cassures en cours de stabilisation (avec contexte temporel)
        stabilization_result = self._check_stabilization_with_context(current_price)
        if stabilization_result:
            return stabilization_result
        
        return None
    
    def _check_stabilization_with_context(self, current_price: float) -> Optional[Dict[str, Any]]:
        """Vérifie la stabilisation avec critères adaptés au contexte temporel"""
        results = []
        
        # Récupérer le temps de stabilisation adapté à la session
        adapted_stabilization_time = self.temporal_context.get_adapted_stabilization_time()
        
        for threshold_name, tracker in self.stabilization_tracker.items():
            # Ajouter le prix actuel
            tracker["price_points"].append({
                "price": current_price,
                "timestamp": datetime.utcnow()
            })
            
            # Nettoyer les anciens points (garder seulement les points pertinents)
            cutoff = datetime.utcnow() - timedelta(minutes=adapted_stabilization_time + 10)
            tracker["price_points"] = [
                p for p in tracker["price_points"]
                if p["timestamp"] > cutoff
            ]
            
            # Vérifier les critères de stabilisation avec contexte temporel
            stabilization_result = self._evaluate_stabilization_with_context(
                threshold_name, tracker, current_price, adapted_stabilization_time
            )
            if stabilization_result:
                results.append(stabilization_result)
        
        # Nettoyer les trackers terminés
        self._cleanup_stabilization_trackers()
        
        return results[0] if results else None
    
    def _evaluate_stabilization_with_context(self, threshold_name: str, tracker: Dict[str, Any], 
                                           current_price: float, stabilization_time: int) -> Optional[Dict[str, Any]]:
        """Évalue la stabilisation avec critères adaptés au contexte temporel"""
        start_time = tracker["start_time"]
        time_elapsed = (datetime.utcnow() - start_time).total_seconds() / 60
        
        # Utiliser le temps adapté à la session
        if time_elapsed < stabilization_time:
            return None
        
        price_points = tracker["price_points"]
        breakout_info = tracker["breakout_info"]
        
        # Critères adaptés au contexte temporel
        recent_prices = [p["price"] for p in price_points if 
                        (datetime.utcnow() - p["timestamp"]).total_seconds() / 60 <= stabilization_time]
        
        if len(recent_prices) < 3:
            return None
        
        # Critère 1: Prix dans une fourchette adaptée
        context_info = self.temporal_context.get_session_context_info()
        stabilization_range = self.config.STABILIZATION_RANGE
        
        # Ajuster la fourchette selon l'activité de session
        if context_info["activity_level"] == "high":
            stabilization_range *= 1.5  # Plus permissif en session active
        elif context_info["activity_level"] == "low":
            stabilization_range *= 0.8  # Plus strict en session calme
        
        price_range = max(recent_prices) - min(recent_prices)
        if price_range > stabilization_range * 2:
            logger.debug(f"Stabilisation {threshold_name}: range trop large ({price_range:.2f}$ > {stabilization_range*2:.2f}$)")
            return None
        
        # Critère 2: Pas de retour > 50% vers le seuil cassé (inchangé)
        broken_threshold = breakout_info["threshold"]["valeur"]
        start_price = tracker["start_price"]
        max_allowed_return = start_price - (start_price - broken_threshold) * 0.5
        
        if breakout_info["direction"] == "bullish" and min(recent_prices) < max_allowed_return:
            return None
        elif breakout_info["direction"] == "bearish" and max(recent_prices) > max_allowed_return:
            return None
        
        # Critère 3: Modification du nombre de prix consécutifs selon le contexte
        min_consecutive = 3
        if context_info["activity_level"] == "high":
            min_consecutive = 2  # Moins strict en session active
        elif context_info["activity_level"] == "low":
            min_consecutive = 4  # Plus strict en session calme
        
        consecutive_count = self._count_consecutive_direction(recent_prices, breakout_info["direction"])
        if consecutive_count < min_consecutive:
            return None
        
        # Cassure validée avec contexte !
        self.state_manager.set_breakout_state(BreakoutState.VALIDATED, {
            "seuil_valide": threshold_name,
            "prix_stabilisation": current_price,
            "duree_stabilisation": time_elapsed,
            "session_context": context_info["session"],
            "adapted_criteria": True
        })
        
        # Enregistrer le succès pour les statistiques
        self.state_manager.track_breakout_result(threshold_name, True)
        
        # Nettoyer ce tracker
        del self.stabilization_tracker[threshold_name]
        
        # Calculer le modificateur de confiance
        confidence_modifier = self.temporal_context.get_breakout_confidence_modifier(threshold_name)
        
        signal_type = "📈" if breakout_info["direction"] == "bullish" else "📉"
        amplitude_str = f"+{breakout_info['amplitude']:.2f}$" if breakout_info["direction"] == "bullish" else f"-{breakout_info['amplitude']:.2f}$"
        speed_str = " ⚡" if breakout_info.get("is_fast") else ""
        context_str = f" [{context_info['session'].upper()}]"
        confidence_str = f" (Conf: {confidence_modifier})"
        
        return {
            "type": f"{signal_type} Cassure {threshold_name} {amplitude_str}{speed_str} ✅ VALIDÉE{context_str}{confidence_str}",
            "direction": breakout_info["direction"],
            "broken_threshold": broken_threshold,
            "threshold_name": threshold_name,
            "amplitude": breakout_info["amplitude"],
            "stabilization_time": time_elapsed,
            "session_context": context_info,
            "confidence_modifier": confidence_modifier,
            "adapted_criteria": True,
            "status": "validated",
            "is_strong": True
        }
    
    def check_volatility(self) -> bool:
        """Vérifie si la volatilité est trop élevée avec seuil adapté"""
        if len(self.price_history) < 10:
            return False
        
        # Utiliser le seuil de volatilité adapté au contexte
        volatility_threshold = self.temporal_context.get_adapted_volatility_threshold()
        
        # Calculer la volatilité sur la dernière heure
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_prices = [
            p["price"] for p in self.price_history 
            if p["timestamp"] > one_hour_ago
        ]
        
        if len(recent_prices) < 5:
            return False
        
        price_range = max(recent_prices) - min(recent_prices)
        avg_price = sum(recent_prices) / len(recent_prices)
        volatility_pct = (price_range / avg_price) * 100
        
        is_volatile = volatility_pct > volatility_threshold
        
        if is_volatile:
            logger.warning(f"Volatilité excessive détectée: {volatility_pct:.2f}% > {volatility_threshold}% (seuil adapté)")
        
        return is_volatile
    
    def _check_range_return(self, current_price: float, thresholds: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Vérifie le retour durable dans le range S1-R1 pour revalidation du pivot"""
        r1_value = None
        s1_value = None
        
        for threshold in thresholds:
            if threshold["nom"].startswith("R1"):
                r1_value = threshold["valeur"]
            elif threshold["nom"].startswith("S1"):
                s1_value = threshold["valeur"]
        
        # Vérifier le retour en range avec le gestionnaire d'état
        if self.state_manager.check_range_return(current_price, r1_value, s1_value):
            # Passage en mode semi-neutre
            self.state_manager.set_breakout_state(BreakoutState.NEUTRAL, {
                "raison": "retour_durable_range",
                "duree_minutes": 30,
                "suggestion": "revalidation_pivot_precedent"
            })
            
            return {
                "type": "🔄 Retour durable en range S1-R1 - Revalidation pivot recommandée",
                "direction": "range_return",
                "status": "semi_neutral",
                "action": "consider_previous_pivot"
            }
        
        return None
    
    def _check_extreme_breakouts_with_reliability(self, current_price: float, thresholds: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Vérifie les cassures de R2/S2 en tenant compte de la fiabilité des seuils"""
        for threshold in thresholds:
            threshold_name = threshold["nom"]
            
            # Vérifier la fiabilité du seuil avant de l'utiliser
            if not self.state_manager.is_threshold_reliable(threshold_name):
                logger.warning(f"Seuil {threshold_name} peu fiable, cassure ignorée")
                continue
            
            if threshold_name.startswith("R2"):
                # Cassure résistance R2
                if current_price > threshold["valeur"] + self.config.BREAKOUT_AMPLITUDE:
                    # Enregistrer la tentative
                    self.state_manager.track_breakout_attempt(threshold_name)
                    
                    return {
                        "type": "resistance",
                        "threshold": threshold,
                        "amplitude": current_price - threshold["valeur"],
                        "direction": "bullish",
                        "reliability": self.state_manager.get_threshold_reliability(threshold_name)
                    }
        
        return Noneget_threshold_reliability(threshold_name)
                    }
            
            elif threshold_name.startswith("S2"):
                # Cassure support S2
                if current_price < threshold["valeur"] - self.config.BREAKOUT_AMPLITUDE:
                    # Enregistrer la tentative
                    self.state_manager.track_breakout_attempt(threshold_name)
                    
                    return {
                        "type": "support", 
                        "threshold": threshold,
                        "amplitude": threshold["valeur"] - current_price,
                        "direction": "bearish",
                        "reliability": self.state_manager."""
Validateur intelligent de cassures avec logique multi-critères et contexte temporel
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from .config import Config
from .logger import Logger
from .pivot_state_manager import PivotStateManager, BreakoutState, PivotType
from .temporal_context_manager import TemporalContextManager

logger = Logger()

class BreakoutValidator:
    """Valide les cassures selon les critères de trading avancés avec adaptation temporelle"""
    
    def __init__(self, pivot_state_manager: PivotStateManager):
        self.config = Config()
        self.state_manager = pivot_state_manager
        self.temporal_context = TemporalContextManager()
        self.price_history = []  # Historique des prix pour validation
        self.stabilization_tracker = {}
    
    def add_price_point(self, price: float, timestamp: Optional[datetime] = None):
        """Ajoute un point de prix à l'historique"""
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        self.price_history.append({
            "price": price,
            "timestamp": timestamp
        })
        
        # Garder seulement les 30 dernières minutes
        cutoff = timestamp - timedelta(minutes=30)
        self.price_history = [
            p for p in self.price_history 
            if p["timestamp"] > cutoff
        ]
    
    def check_breakout(self, current_price: float, thresholds: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Vérifie et valide les cassures selon la logique avancée"""
        
        # Ajouter le prix actuel à l'historique
        self.add_price_point(current_price)
        
        # 1. Vérifier les cassures de R2/S2 (niveaux extrêmes)
        extreme_breakout = self._check_extreme_breakouts(current_price, thresholds)
        if extreme_breakout:
            return self._process_extreme_breakout(extreme_breakout, current_price, thresholds)
        
        # 2. Vérifier les zones de tension
        tension_signal = self._check_tension_zones(current_price, thresholds)
        if tension_signal:
            return tension_signal
        
        # 3. Vérifier les invalidations de cassures en cours
        self._check_breakout_invalidation(current_price, thresholds)
        
        # 4. Valider les cassures en cours de stabilisation
        stabilization_result = self._check_stabilization(current_price)
        if stabilization_result:
            return stabilization_result
        
        return None
    
    def _check_extreme_breakouts(self, current_price: float, thresholds: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Vérifie les cassures de R2 ou S2"""
        for threshold in thresholds:
            if threshold["nom"].startswith("R2"):
                # Cassure résistance R2
                if current_price > threshold["valeur"] + self.config.BREAKOUT_AMPLITUDE:
                    return {
                        "type": "resistance",
                        "threshold": threshold,
                        "amplitude": current_price - threshold["valeur"],
                        "direction": "bullish"
                    }
            
            elif threshold["nom"].startswith("S2"):
                # Cassure support S2
                if current_price < threshold["valeur"] - self.config.BREAKOUT_AMPLITUDE:
                    return {
                        "type": "support", 
                        "threshold": threshold,
                        "amplitude": threshold["valeur"] - current_price,
                        "direction": "bearish"
                    }
        
        return None
    
    def _process_extreme_breakout(self, breakout: Dict[str, Any], current_price: float, thresholds: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Traite une cassure extrême détectée"""
        threshold_name = breakout["threshold"]["nom"]
        
        # Vérifier la vitesse si on a un R1 tracking en cours
        is_fast_breakout = False
        if breakout["type"] == "resistance":
            r2_price = breakout["threshold"]["valeur"]
            is_fast_breakout = self.state_manager.check_speed_breakout(r2_price, current_price)
        
        # Commencer la phase de stabilisation
        self._start_stabilization_tracking(threshold_name, current_price, breakout)
        
        # Mettre à jour l'état
        self.state_manager.set_breakout_state(BreakoutState.PARTIAL, {
            "seuil_en_cours": threshold_name,
            "prix_cassure": current_price,
            "timestamp_cassure": datetime.utcnow().isoformat(),
            "amplitude": breakout["amplitude"],
            "is_fast": is_fast_breakout
        })
        
        # Créer le signal de cassure partielle
        signal_type = "📈" if breakout["direction"] == "bullish" else "📉"
        amplitude_str = f"+{breakout['amplitude']:.2f}$" if breakout["direction"] == "bullish" else f"-{breakout['amplitude']:.2f}$"
        speed_str = " ⚡" if is_fast_breakout else ""
        
        return {
            "type": f"{signal_type} Cassure {threshold_name} {amplitude_str}{speed_str} [En validation...]",
            "direction": breakout["direction"],
            "broken_threshold": breakout["threshold"]["valeur"],
            "threshold_name": threshold_name,
            "amplitude": breakout["amplitude"],
            "is_fast": is_fast_breakout,
            "status": "partial",
            "needs_stabilization": True
        }
    
    def _check_tension_zones(self, current_price: float, thresholds: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Vérifie les zones de tension (approche de R2/S2)"""
        for threshold in thresholds:
            threshold_value = threshold["valeur"]
            threshold_name = threshold["nom"]
            
            # Zone de tension pour R2
            if threshold_name.startswith("R2"):
                if abs(current_price - threshold_value) <= 1.0:  # À moins de 1$ de R2
                    self.state_manager.start_tension_tracking(threshold_name, current_price)
                    
                    # Vérifier si on a atteint le seuil de tension
                    if self.state_manager.get_breakout_state() == BreakoutState.TENSION:
                        distance = threshold_value - current_price
                        return {
                            "type": f"🚧📈 Tension sur {threshold_name} (-{distance:.2f}$)",
                            "direction": "bullish_tension",
                            "target": threshold_name,
                            "distance": distance,
                            "status": "tension"
                        }
            
            # Zone de tension pour S2
            elif threshold_name.startswith("S2"):
                if abs(current_price - threshold_value) <= 1.0:  # À moins de 1$ de S2
                    self.state_manager.start_tension_tracking(threshold_name, current_price)
                    
                    # Vérifier si on a atteint le seuil de tension
                    if self.state_manager.get_breakout_state() == BreakoutState.TENSION:
                        distance = current_price - threshold_value
                        return {
                            "type": f"🚧📉 Tension sur {threshold_name} (+{distance:.2f}$)",
                            "direction": "bearish_tension",
                            "target": threshold_name,
                            "distance": distance,
                            "status": "tension"
                        }
        
        return None
    
    def _check_breakout_invalidation(self, current_price: float, thresholds: List[Dict[str, Any]]):
        """Vérifie si une cassure en cours doit être invalidée"""
        current_state = self.state_manager.get_breakout_state()
        
        if current_state not in [BreakoutState.PARTIAL, BreakoutState.VALIDATED]:
            return
        
        # Récupérer les seuils S1 et R1 pour définir le range central
        r1_value = None
        s1_value = None
        
        for threshold in thresholds:
            if threshold["nom"].startswith("R1"):
                r1_value = threshold["valeur"]
            elif threshold["nom"].startswith("S1"):
                s1_value = threshold["valeur"]
        
        # Vérifier le retour dans le range S1-R1
        if r1_value and s1_value and s1_value <= current_price <= r1_value:
            logger.warning(f"Prix {current_price} retourné dans range S1-R1, invalidation cassure")
            
            self.state_manager.set_breakout_state(BreakoutState.INVALIDATED, {
                "raison": "retour_range_central",
                "prix_invalidation": current_price
            })
            
            # Vérifier si on doit passer en état neutre
            if self.state_manager.should_go_neutral():
                self.state_manager.set_breakout_state(BreakoutState.NEUTRAL, {
                    "raison": "trop_invalidations"
                })
    
    def _start_stabilization_tracking(self, threshold_name: str, price: float, breakout: Dict[str, Any]):
        """Démarre le suivi de stabilisation pour une cassure"""
        self.stabilization_tracker[threshold_name] = {
            "start_time": datetime.utcnow(),
            "start_price": price,
            "breakout_info": breakout,
            "price_points": [{"price": price, "timestamp": datetime.utcnow()}],
            "is_stabilizing": False
        }
    
    def _check_stabilization(self, current_price: float) -> Optional[Dict[str, Any]]:
        """Vérifie la stabilisation des cassures en cours"""
        results = []
        
        for threshold_name, tracker in self.stabilization_tracker.items():
            # Ajouter le prix actuel
            tracker["price_points"].append({
                "price": current_price,
                "timestamp": datetime.utcnow()
            })
            
            # Nettoyer les anciens points (garder seulement les 20 dernières minutes)
            cutoff = datetime.utcnow() - timedelta(minutes=20)
            tracker["price_points"] = [
                p for p in tracker["price_points"]
                if p["timestamp"] > cutoff
            ]
            
            # Vérifier les critères de stabilisation
            stabilization_result = self._evaluate_stabilization(threshold_name, tracker, current_price)
            if stabilization_result:
                results.append(stabilization_result)
        
        # Nettoyer les trackers terminés
        self._cleanup_stabilization_trackers()
        
        return results[0] if results else None
    
    def _evaluate_stabilization(self, threshold_name: str, tracker: Dict[str, Any], current_price: float) -> Optional[Dict[str, Any]]:
        """Évalue si une cassure est stabilisée"""
        start_time = tracker["start_time"]
        time_elapsed = (datetime.utcnow() - start_time).total_seconds() / 60
        
        # Pas encore assez de temps écoulé
        if time_elapsed < self.config.STABILIZATION_TIME:
            return None
        
        price_points = tracker["price_points"]
        breakout_info = tracker["breakout_info"]
        
        # Critère 1: Prix dans une fourchette de ±2$ pendant 15min
        recent_prices = [p["price"] for p in price_points if 
                        (datetime.utcnow() - p["timestamp"]).total_seconds() / 60 <= self.config.STABILIZATION_TIME]
        
        if len(recent_prices) < 3:
            return None
        
        price_range = max(recent_prices) - min(recent_prices)
        if price_range > self.config.STABILIZATION_RANGE * 2:  # ±2$ = 4$ de range
            logger.debug(f"Stabilisation {threshold_name}: range trop large ({price_range:.2f}$)")
            return None
        
        # Critère 2: Pas de retour > 50% vers le seuil cassé
        broken_threshold = breakout_info["threshold"]["valeur"]
        start_price = tracker["start_price"]
        max_allowed_return = start_price - (start_price - broken_threshold) * 0.5
        
        if breakout_info["direction"] == "bullish" and min(recent_prices) < max_allowed_return:
            logger.debug(f"Stabilisation {threshold_name}: retour trop important vers seuil")
            return None
        elif breakout_info["direction"] == "bearish" and max(recent_prices) > max_allowed_return:
            logger.debug(f"Stabilisation {threshold_name}: retour trop important vers seuil")
            return None
        
        # Critère 3: Au moins 3 prix consécutifs dans la même direction
        consecutive_count = self._count_consecutive_direction(recent_prices, breakout_info["direction"])
        if consecutive_count < 3:
            logger.debug(f"Stabilisation {threshold_name}: pas assez de prix consécutifs ({consecutive_count})")
            return None
        
        # Cassure validée !
        self.state_manager.set_breakout_state(BreakoutState.VALIDATED, {
            "seuil_valide": threshold_name,
            "prix_stabilisation": current_price,
            "duree_stabilisation": time_elapsed
        })
        
        # Nettoyer ce tracker
        del self.stabilization_tracker[threshold_name]
        
        signal_type = "📈" if breakout_info["direction"] == "bullish" else "📉"
        amplitude_str = f"+{breakout_info['amplitude']:.2f}$" if breakout_info["direction"] == "bullish" else f"-{breakout_info['amplitude']:.2f}$"
        speed_str = " ⚡" if breakout_info.get("is_fast") else ""
        
        return {
            "type": f"{signal_type} Cassure {threshold_name} {amplitude_str}{speed_str} ✅ VALIDÉE",
            "direction": breakout_info["direction"],
            "broken_threshold": broken_threshold,
            "threshold_name": threshold_name,
            "amplitude": breakout_info["amplitude"],
            "stabilization_time": time_elapsed,
            "status": "validated",
            "is_strong": True
        }
    
    def _count_consecutive_direction(self, prices: List[float], direction: str) -> int:
        """Compte les prix consécutifs dans la même direction"""
        if len(prices) < 2:
            return 0
        
        consecutive = 0
        max_consecutive = 0
        
        for i in range(1, len(prices)):
            if direction == "bullish" and prices[i] >= prices[i-1]:
                consecutive += 1
                max_consecutive = max(max_consecutive, consecutive)
            elif direction == "bearish" and prices[i] <= prices[i-1]:
                consecutive += 1
                max_consecutive = max(max_consecutive, consecutive)
            else:
                consecutive = 0
        
        return max_consecutive
    
    def _cleanup_stabilization_trackers(self):
        """Nettoie les trackers de stabilisation obsolètes"""
        cutoff = datetime.utcnow() - timedelta(minutes=30)
        
        to_remove = []
        for threshold_name, tracker in self.stabilization_tracker.items():
            if tracker["start_time"] < cutoff:
                to_remove.append(threshold_name)
        
        for threshold_name in to_remove:
            del self.stabilization_tracker[threshold_name]
            logger.debug(f"Tracker de stabilisation {threshold_name} supprimé (timeout)")
    
    def check_volatility(self) -> bool:
        """Vérifie si la volatilité est trop élevée"""
        if len(self.price_history) < 10:
            return False
        
        # Calculer la volatilité sur la dernière heure
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_prices = [
            p["price"] for p in self.price_history 
            if p["timestamp"] > one_hour_ago
        ]
        
        if len(recent_prices) < 5:
            return False
        
        price_range = max(recent_prices) - min(recent_prices)
        avg_price = sum(recent_prices) / len(recent_prices)
        volatility_pct = (price_range / avg_price) * 100
        
        return volatility_pct > self.config.VOLATILITY_THRESHOLD
    
    def reset_daily(self):
        """Reset quotidien du validateur"""
        self.price_history.clear()
        self.stabilization_tracker.clear()
        logger.info("Validateur de cassures réinitialisé")
