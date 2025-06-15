"""
Tests pour les nouvelles fonctionnalités strategiques
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import sys
import os

# Ajouter le chemin src au PYTHONPATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.pivot_state_manager import PivotStateManager
from src.temporal_context_manager import TemporalContextManager, SessionActivity
from src.pivot_session_manager import PivotSessionManager
from src.pivot_state_manager import PivotType

class TestReliabilityTracking:
    
    @pytest.fixture
    def state_manager(self):
        """Gestionnaire d'état pour tests de fiabilité"""
        manager = PivotStateManager()
        # Reset de l'état pour s'assurer qu'on part propre
        manager.current_state = manager._create_default_state()
        return manager
    
    def test_track_breakout_attempt(self, state_manager):
        """Test d'enregistrement des tentatives de cassure"""
        threshold_name = "R2_classique"
        
        # Première tentative
        state_manager.track_breakout_attempt(threshold_name)
        stats = state_manager.get_threshold_reliability(threshold_name)
        
        assert stats["tentatives"] == 1
        assert stats["validees"] == 0
        assert stats["score"] == 0.0
    
    def test_track_breakout_results(self, state_manager):
        """Test du suivi des résultats de cassures"""
        threshold_name = "R2_classique"
        
        # Créer un seuil avec exactement 3 tentatives de façon directe
        state_manager.current_state["seuil_stats"] = {
            threshold_name: {
                "tentatives": 3,
                "validees": 0,
                "invalidees": 0,
                "score": 0.0,
                "last_update": None
            }
        }
        
        # Enregistrer les résultats
        state_manager.track_breakout_result(threshold_name, True)   # Succès
        state_manager.track_breakout_result(threshold_name, True)   # Succès  
        state_manager.track_breakout_result(threshold_name, False)  # Échec
        
        stats = state_manager.get_threshold_reliability(threshold_name)
        
        # Vérifier les résultats
        assert stats["tentatives"] == 3  # Ne devrait pas avoir changé
        assert stats["validees"] == 2
        assert stats["invalidees"] == 1
        assert stats["score"] == 66.7  # 2/3 * 100
    
    def test_threshold_reliability_check(self, state_manager):
        """Test de vérification de fiabilité des seuils"""
        threshold_name = "R2_classique"
        
        # Seuil sans historique = fiable par défaut
        assert state_manager.is_threshold_reliable(threshold_name) == True
        
        # Créer un historique médiocre directement
        state_manager.current_state["seuil_stats"] = {
            threshold_name: {
                "tentatives": 5,
                "validees": 2,  # 2/5 = 40%
                "invalidees": 3,
                "score": 40.0,
                "last_update": None
            }
        }
        
        # Seuil peu fiable (40% < 50%)
        assert state_manager.is_threshold_reliable(threshold_name) == False
        assert state_manager.is_threshold_reliable(threshold_name, min_score=30.0) == True

class TestTemporalContext:
    
    @pytest.fixture
    def temporal_manager(self):
        """Gestionnaire de contexte temporel"""
        return TemporalContextManager()
    
    def test_session_profiles(self, temporal_manager):
        """Test des profils de sessions"""
        profiles = temporal_manager.session_profiles
        
        # Vérifier que tous les profils existent
        assert "asia" in profiles
        assert "europe" in profiles
        assert "us" in profiles
        
        # Vérifier les différences d'activité
        assert profiles["asia"]["activity"] == SessionActivity.LOW
        assert profiles["europe"]["activity"] == SessionActivity.MEDIUM
        assert profiles["us"]["activity"] == SessionActivity.HIGH
        
        # Vérifier l'adaptation des temps
        assert profiles["asia"]["stabilization_time"] > profiles["us"]["stabilization_time"]
    
    @patch('src.temporal_context_manager.datetime')
    def test_adapted_criteria_asia(self, mock_datetime, temporal_manager):
        """Test des critères adaptés pour session Asie"""
        # Simuler 2h UTC (session Asie)
        mock_datetime.utcnow.return_value = datetime(2025, 6, 15, 2, 0, 0)
        
        stabilization_time = temporal_manager.get_adapted_stabilization_time()
        volatility_threshold = temporal_manager.get_adapted_volatility_threshold()
        
        # Session Asie = critères renforcés
        assert stabilization_time == 20  # +5min par rapport au standard
        assert volatility_threshold == 0.8  # Plus tolérant
    
    @patch('src.temporal_context_manager.datetime')
    def test_adapted_criteria_us(self, mock_datetime, temporal_manager):
        """Test des critères adaptés pour session US"""
        # Simuler 15h UTC (session US)
        mock_datetime.utcnow.return_value = datetime(2025, 6, 15, 15, 0, 0)
        
        stabilization_time = temporal_manager.get_adapted_stabilization_time()
        volatility_threshold = temporal_manager.get_adapted_volatility_threshold()
        
        # Session US = critères accélérés
        assert stabilization_time == 10  # -5min par rapport au standard
        assert volatility_threshold == 1.2  # Plus permissif
    
    def test_session_data_validation(self, temporal_manager):
        """Test de validation des données de session"""
        # Données Asie avec range insuffisant
        asia_data = {"high": 3405.0, "low": 3401.0}  # Range de 4$ < 6$ requis
        is_valid, reason = temporal_manager.is_session_data_valid(asia_data)
        assert is_valid == False
        assert "Range insuffisant" in reason
        
        # Données Europe avec range suffisant
        europe_data = {"high": 3420.0, "low": 3405.0}  # Range de 15$ > 8$ requis
        with patch.object(temporal_manager, '_get_current_session_name', return_value="europe"):
            is_valid, reason = temporal_manager.is_session_data_valid(europe_data)
            assert is_valid == True

class TestRangeReturnDetection:
    
    @pytest.fixture
    def state_manager(self):
        """Gestionnaire d'état pour tests de retour en range"""
        return PivotStateManager()
    
    def test_range_return_detection(self, state_manager):
        """Test de détection du retour en range"""
        r1_value = 3410.0
        s1_value = 3390.0
        
        # Prix dans le range pour la première fois
        assert state_manager.check_range_return(3400.0, r1_value, s1_value) == False
        
        # Simuler le passage du temps (impossible de mocker facilement datetime dans la méthode)
        # On teste la logique de base
        range_validation = state_manager.current_state.get("range_validation", {})
        assert range_validation.get("in_range_since") is not None
    
    def test_range_exit_reset(self, state_manager):
        """Test du reset quand le prix sort du range"""
        r1_value = 3410.0
        s1_value = 3390.0
        
        # Prix dans le range
        state_manager.check_range_return(3400.0, r1_value, s1_value)
        assert state_manager.current_state["range_validation"]["in_range_since"] is not None
        
        # Prix sort du range
        state_manager.check_range_return(3415.0, r1_value, s1_value)  # Au-dessus R1
        assert state_manager.current_state["range_validation"]["in_range_since"] is None

class TestMeaningfulSwitchValidation:
    
    @pytest.fixture
    def session_manager(self):
        """Gestionnaire de sessions pour tests de bascule"""
        mock_api = Mock()
        return PivotSessionManager(mock_api)
    
    def test_meaningful_pivot_switch(self, session_manager):
        """Test de validation de bascule significative"""
        # Simuler des pivots avec différences importantes
        classic_pivots = [
            {"nom": "R2_classique", "valeur": 3420.0, "type": "résistance"},
            {"nom": "Pivot_classique", "valeur": 3400.0, "type": "pivot"},
            {"nom": "S2_classique", "valeur": 3380.0, "type": "support"}
        ]
        
        asia_pivots = [
            {"nom": "R2_asie", "valeur": 3430.0, "type": "résistance"},  # +10$ différence
            {"nom": "Pivot_asie", "valeur": 3410.0, "type": "pivot"},     # +10$ différence
            {"nom": "S2_asie", "valeur": 3390.0, "type": "support"}       # +10$ différence
        ]
        
        # Mettre les pivots en cache
        session_manager.cached_pivots[PivotType.CLASSIC] = classic_pivots
        session_manager.cached_pivots[PivotType.ASIA] = asia_pivots
        
        # Test de bascule significative
        is_meaningful, reason = session_manager.is_pivot_switch_meaningful(PivotType.ASIA, PivotType.CLASSIC)
        assert is_meaningful == True
        assert "10.0$" in reason
    
    def test_non_meaningful_pivot_switch(self, session_manager):
        """Test de bascule non significative"""
        # Pivots très similaires
        classic_pivots = [
            {"nom": "R2_classique", "valeur": 3420.0, "type": "résistance"},
            {"nom": "Pivot_classique", "valeur": 3400.0, "type": "pivot"},
            {"nom": "S2_classique", "valeur": 3380.0, "type": "support"}
        ]
        
        asia_pivots = [
            {"nom": "R2_asie", "valeur": 3422.0, "type": "résistance"},  # +2$ seulement
            {"nom": "Pivot_asie", "valeur": 3401.0, "type": "pivot"},     # +1$ seulement  
            {"nom": "S2_asie", "valeur": 3381.0, "type": "support"}       # +1$ seulement
        ]
        
        session_manager.cached_pivots[PivotType.CLASSIC] = classic_pivots
        session_manager.cached_pivots[PivotType.ASIA] = asia_pivots
        
        # Test de bascule non significative
        is_meaningful, reason = session_manager.is_pivot_switch_meaningful(PivotType.ASIA, PivotType.CLASSIC)
        assert is_meaningful == False
        assert "Différences insuffisantes" in reason

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
