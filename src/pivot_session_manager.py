"""
Gestionnaire des sessions de trading et calcul des pivots
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from .config import Config
from .logger import Logger
from .pivot_state_manager import PivotType

logger = Logger()

class PivotSessionManager:
    """Gère les sessions de trading et le calcul des pivots par session"""
    
    def __init__(self, api_client):
        self.config = Config()
        self.api_client = api_client
        self.cached_pivots = {
            PivotType.CLASSIC: None,
            PivotType.ASIA: None,
            PivotType.EUROPE: None
        }
        self.last_calculation_times = {}
    
    def should_calculate_pivots(self) -> Optional[PivotType]:
        """Détermine s'il faut calculer de nouveaux pivots"""
        now = datetime.utcnow()
        current_hour = now.hour
        current_minute = now.minute
        today = now.date().isoformat()
        
        # Vérifier chaque moment de calcul
        calc_moments = [
            (self.config.CLASSIC_CALC_HOUR, PivotType.CLASSIC),
            (self.config.ASIA_CALC_HOUR, PivotType.ASIA),
            (self.config.EUROPE_CALC_HOUR, PivotType.EUROPE)
        ]
        
        for calc_hour, pivot_type in calc_moments:
            calc_key = f"{today}_{pivot_type.value}"
            
            # Vérifier si c'est le bon moment (heure + 3 minutes)
            if (current_hour == calc_hour and 
                current_minute >= self.config.CALC_MINUTE_OFFSET and
                calc_key not in self.last_calculation_times):
                
                self.last_calculation_times[calc_key] = now.isoformat()
                return pivot_type
        
        return None
    
    async def calculate_session_pivots(self, pivot_type: PivotType) -> Optional[List[Dict[str, Any]]]:
        """Calcule les pivots pour une session donnée"""
        try:
            logger.info(f"Calcul des pivots {pivot_type.value}")
            
            # Récupérer les données selon le type de pivot
            if pivot_type == PivotType.CLASSIC:
                data = await self._get_classic_data()
            elif pivot_type == PivotType.ASIA:
                data = await self._get_asia_session_data()
            elif pivot_type == PivotType.EUROPE:
                data = await self._get_europe_session_data()
            else:
                logger.error(f"Type de pivot non supporté: {pivot_type}")
                return None
            
            if not data:
                logger.warning(f"Pas de données pour calculer pivots {pivot_type.value}")
                return None
            
            # Calculer les pivots
            pivots = self._calculate_pivot_points(data, pivot_type)
            
            # Mettre en cache
            self.cached_pivots[pivot_type] = pivots
            
            logger.info(f"Pivots {pivot_type.value} calculés: {len(pivots)} niveaux")
            return pivots
            
        except Exception as e:
            logger.error(f"Erreur calcul pivots {pivot_type.value}: {e}")
            return None
    
    async def _get_classic_data(self) -> Optional[Dict[str, Any]]:
        """Récupère les données pour pivots classiques (jour précédent)"""
        return await self.api_client.get_last_trading_day_data()
    
    async def _get_asia_session_data(self) -> Optional[Dict[str, Any]]:
        """Récupère les données de la session asiatique (0h-4h UTC)"""
        try:
            today = datetime.utcnow().date()
            start_time = datetime.combine(today, datetime.min.time().replace(
                hour=self.config.ASIA_SESSION_START
            ))
            end_time = datetime.combine(today, datetime.min.time().replace(
                hour=self.config.ASIA_SESSION_END - 1, minute=59
            ))
            
            return await self._get_session_ohlc(start_time, end_time)
            
        except Exception as e:
            logger.error(f"Erreur récupération données session Asie: {e}")
            return None
    
    async def _get_europe_session_data(self) -> Optional[Dict[str, Any]]:
        """Récupère les données de la session européenne (4h-13h UTC)"""
        try:
            today = datetime.utcnow().date()
            start_time = datetime.combine(today, datetime.min.time().replace(
                hour=self.config.EUROPE_SESSION_START
            ))
            end_time = datetime.combine(today, datetime.min.time().replace(
                hour=self.config.EUROPE_SESSION_END - 1, minute=59
            ))
            
            return await self._get_session_ohlc(start_time, end_time)
            
        except Exception as e:
            logger.error(f"Erreur récupération données session Europe: {e}")
            return None
    
    async def _get_session_ohlc(self, start_time: datetime, end_time: datetime) -> Optional[Dict[str, Any]]:
        """Récupère les données OHLC pour une période donnée"""
        try:
            # Pour simplifier, on utilise les données minute par minute et on calcule l'OHLC
            # Note: Cette méthode pourrait être optimisée avec une API plus directe
            
            start_date = start_time.date().isoformat()
            end_date = end_time.date().isoformat()
            
            # Récupérer les données minute de la période
            url = f"{self.api_client.base_url}/1/minute/{start_date}/{end_date}"
            
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params={
                    "adjusted": "true",
                    "sort": "asc",
                    "limit": 50000,  # Assez pour une session
                    "apiKey": self.api_client.api_key
                }, timeout=30)
                
                response.raise_for_status()
                data = response.json()
                results = data.get("results", [])
                
                if not results:
                    return None
                
                # Calculer OHLC de la session
                prices = [candle["c"] for candle in results]
                highs = [candle["h"] for candle in results]
                lows = [candle["l"] for candle in results]
                volumes = [candle["v"] for candle in results]
                
                return {
                    "open": results[0]["o"],
                    "high": max(highs),
                    "low": min(lows),
                    "close": prices[-1],
                    "volume": sum(volumes),
                    "timestamp": results[-1]["t"]
                }
                
        except Exception as e:
            logger.error(f"Erreur récupération OHLC session: {e}")
            return None
    
    def _calculate_pivot_points(self, data: Dict[str, Any], pivot_type: PivotType) -> List[Dict[str, Any]]:
        """Calcule les points pivots à partir des données OHLC"""
        try:
            high = data["high"]
            low = data["low"]
            close = data["close"]
            
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
            
            # Créer la liste des seuils avec identification du type de pivot
            pivot_suffix = f"_{pivot_type.value}"
            
            thresholds = [
                {"valeur": r3, "type": "résistance", "nom": f"R3{pivot_suffix}", "pivot_type": pivot_type.value},
                {"valeur": r2, "type": "résistance", "nom": f"R2{pivot_suffix}", "pivot_type": pivot_type.value},
                {"valeur": r1, "type": "résistance", "nom": f"R1{pivot_suffix}", "pivot_type": pivot_type.value},
                {"valeur": pivot, "type": "pivot", "nom": f"Pivot{pivot_suffix}", "pivot_type": pivot_type.value},
                {"valeur": s1, "type": "support", "nom": f"S1{pivot_suffix}", "pivot_type": pivot_type.value},
                {"valeur": s2, "type": "support", "nom": f"S2{pivot_suffix}", "pivot_type": pivot_type.value},
                {"valeur": s3, "type": "support", "nom": f"S3{pivot_suffix}", "pivot_type": pivot_type.value},
            ]
            
            logger.info(f"Pivots {pivot_type.value} - Pivot: {pivot}, R2: {r2}, S2: {s2}")
            return thresholds
            
        except Exception as e:
            logger.error(f"Erreur calcul points pivots {pivot_type.value}: {e}")
            return []
    
    def get_cached_pivots(self, pivot_type: PivotType) -> Optional[List[Dict[str, Any]]]:
        """Retourne les pivots en cache pour un type donné"""
        return self.cached_pivots.get(pivot_type)
    
    def get_all_cached_pivots(self) -> Dict[PivotType, List[Dict[str, Any]]]:
        """Retourne tous les pivots en cache"""
        return {k: v for k, v in self.cached_pivots.items() if v is not None}
    
    def is_pivot_switch_meaningful(self, new_pivot_type: PivotType, current_pivot_type: PivotType) -> Tuple[bool, str]:
        """Vérifie si une bascule de pivot apporte une vraie valeur stratégique"""
        new_pivots = self.get_cached_pivots(new_pivot_type)
        current_pivots = self.get_cached_pivots(current_pivot_type)
        
        if not new_pivots or not current_pivots:
            return False, "Pivots manquants pour comparaison"
        
        # Extraire les niveaux clés pour comparaison
        new_levels = self._extract_key_levels(new_pivots)
        current_levels = self._extract_key_levels(current_pivots)
        
        # Vérifier les différences significatives
        r2_diff = abs(new_levels["R2"] - current_levels["R2"])
        s2_diff = abs(new_levels["S2"] - current_levels["S2"])
        pivot_diff = abs(new_levels["Pivot"] - current_levels["Pivot"])
        
        min_meaningful_diff = 5.0  # Différence minimum en dollars
        
        # Au moins un niveau clé doit avoir une différence significative
        if max(r2_diff, s2_diff, pivot_diff) < min_meaningful_diff:
            return False, f"Différences insuffisantes: R2={r2_diff:.1f}$, S2={s2_diff:.1f}$, Pivot={pivot_diff:.1f}$"
        
        # Vérifier que les nouveaux pivots ne sont pas "inclus" dans les anciens
        if self._is_range_included(new_levels, current_levels):
            return False, "Nouveaux pivots inclus dans l'ancien range"
        
        return True, f"Bascule justifiée - Différences: R2={r2_diff:.1f}$, S2={s2_diff:.1f}$"
    
    def _extract_key_levels(self, pivots: List[Dict[str, Any]]) -> Dict[str, float]:
        """Extrait les niveaux clés d'un jeu de pivots"""
        levels = {}
        for pivot in pivots:
            if pivot["nom"].startswith("R2"):
                levels["R2"] = pivot["valeur"]
            elif pivot["nom"].startswith("S2"):
                levels["S2"] = pivot["valeur"]
            elif pivot["nom"].startswith("Pivot"):
                levels["Pivot"] = pivot["valeur"]
        return levels
    
    def _is_range_included(self, new_levels: Dict[str, float], current_levels: Dict[str, float]) -> bool:
        """Vérifie si le nouveau range est inclus dans l'ancien"""
        # Range des nouveaux pivots
        new_range = new_levels["R2"] - new_levels["S2"]
        # Range des pivots actuels  
        current_range = current_levels["R2"] - current_levels["S2"]
        
        # Si le nouveau range est plus petit ET centré dans l'ancien
        if new_range < current_range * 0.8:  # 20% plus petit
            new_center = (new_levels["R2"] + new_levels["S2"]) / 2
            current_center = (current_levels["R2"] + current_levels["S2"]) / 2
            center_diff = abs(new_center - current_center)
            
            # Centre proche = range inclus
            return center_diff < current_range * 0.3
        
        return False
    
    def validate_session_data_quality(self, pivot_type: PivotType, ohlc_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Valide la qualité des données de session pour éviter des pivots dérivés"""
        if not ohlc_data:
            return False, "Aucune donnée disponible"
        
        session_range = ohlc_data["high"] - ohlc_data["low"]
        session_volume = ohlc_data.get("volume", 0)
        
        # Critères de qualité selon le type de session
        quality_criteria = {
            PivotType.CLASSIC: {"min_range": 8.0, "min_volume": 1000},
            PivotType.ASIA: {"min_range": 6.0, "min_volume": 500},
            PivotType.EUROPE: {"min_range": 10.0, "min_volume": 1500}
        }
        
        criteria = quality_criteria.get(pivot_type, quality_criteria[PivotType.CLASSIC])
        
        # Vérification du range
        if session_range < criteria["min_range"]:
            return False, f"Range insuffisant: {session_range:.2f}$ < {criteria['min_range']}$ requis"
        
        # Vérification du volume (si disponible)
        if session_volume > 0 and session_volume < criteria["min_volume"]:
            logger.warning(f"Volume faible détecté: {session_volume} < {criteria['min_volume']}")
        
        return True, f"Données de qualité - Range: {session_range:.2f}$, Volume: {session_volume}"
    
    def clear_cache(self):
        """Vide le cache des pivots"""
        self.cached_pivots = {pivot_type: None for pivot_type in PivotType}
        self.last_calculation_times.clear()
        logger.info("Cache des pivots vidé")
