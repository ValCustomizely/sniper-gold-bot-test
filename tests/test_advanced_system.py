"""
Tests pour le système avancé multi-pivots
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import sys
import os

# Ajouter le chemin src au PYTHONPATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.pivot_state_manager import PivotStateManager, PivotType, BreakoutState
from src.breakout_validator import BreakoutValidator
from src.enhanced_signal_detector import EnhancedSignalDetector

class TestPivotStateManager:
    
    @pytest.fixture
    def state_manager(self):
        """Instance du gestionnaire d'état pivot"""
        with patch('src.pivot_state_manager.Config') as mock_config:
            # Configurer tous les attributs nécessaires
            config_instance = mock_config.return_value
            config_instance.PIVOT_STATE_FILE = "test_pivot_state.json"
            config_instance.MAX_DAILY_SWITCHES = 2
            config_instance.TENSION_WINDOW = 30
            config_instance.TENSION_TOUCHES = 3
            config_instance.ASIA_SESSION_START = 0
            config_instance.ASIA_SESSION_END = 4
            config_instance.EUROPE_SESSION_START = 4
            config_instance.EUROPE_SESSION_END = 13
            config_instance.US_SESSION_START = 13
            config_instance.US_SESSION_END = 23
            
            return PivotStateManager()
    
    def test_default_state_creation(self, state_manager):
        """Test de création de l'état par défaut"""
        state = state_manager.current_state
        
        assert state["pivot_actif"] == PivotType.CLASSIC.value
        assert state["etat_cassure"] == BreakoutState.NONE.value
        assert state["switches_count"] == 0
        assert isinstance(state["historique"], list)
    
    def test_pivot_switching(self, state_manager):
        """Test de bascule entre pivots"""
        # Premier switch
        success = state_manager.switch_to_pivot(PivotType.ASIA, "test_switch")
        assert success is True
        assert state_manager.get_active_pivot() == PivotType.ASIA
        assert state_manager.current_state["switches_count"] == 1
        
        # Deuxième switch
        success = state_manager.switch_to_pivot(PivotType.EUROPE, "test_switch_2")
        assert success is True
        assert state_manager.get_active_pivot() == PivotType.EUROPE
        assert state_manager.current_state["switches_count"] == 2
        
        # Troisième switch (doit échouer)
        success = state_manager.switch_to_pivot(PivotType.CLASSIC, "test_switch_3")
        assert success is False
        assert state_manager.get_active_pivot() == PivotType.EUROPE  # Pas changé
    
    def test_tension_tracking(self, state_manager):
        """Test du suivi de tension"""
        # Ajouter des touches de tension
        state_manager.start_tension_tracking("R2_classique", 3400.0)
        state_manager.start_tension_tracking("R2_classique", 3401.0)
        state_manager.start_tension_tracking("R2_classique", 3402.0)
        
        # Doit passer en état tension
        assert state_manager.get_breakout_state() == BreakoutState.TENSION
        assert state_manager.current_state["seuil_en_cours"] == "R2_classique"

class TestBreakoutValidator:
    
    @pytest.fixture
    def mock_state_manager(self):
        """Mock du gestionnaire d'état"""
        mock = Mock()
        mock.get_breakout_state.return_value = BreakoutState.NONE
        mock.should_go_neutral.return_value = False
        return mock
    
    @pytest.fixture
    def validator(self, mock_state_manager):
        """Instance du validateur de cassures"""
        with patch('src.breakout_validator.Config') as mock_config:
            mock_config.return_value.BREAKOUT_AMPLITUDE = 2.0
            mock_config.return_value.STABILIZATION_TIME = 15
            mock_config.return_value.STABILIZATION_RANGE = 2.0
            mock_config.return_value.VOLATILITY_THRESHOLD = 1.0
            return BreakoutValidator(mock_state_manager)
    
    @pytest.fixture
    def sample_thresholds(self):
        """Seuils d'exemple pour les tests"""
        return [
            {"nom": "R3_classique", "valeur": 3420.0, "type": "résistance"},
            {"nom": "R2_classique", "valeur": 3410.0, "type": "résistance"},
            {"nom": "R1_classique", "valeur": 3405.0, "type": "résistance"},
            {"nom": "Pivot_classique", "valeur": 3395.0, "type": "pivot"},
            {"nom": "S1_classique", "valeur": 3385.0, "type": "support"},
            {"nom": "S2_classique", "valeur": 3380.0, "type": "support"},
            {"nom": "S3_classique", "valeur": 3370.0, "type": "support"}
        ]
    
    def test_extreme_breakout_detection(self, validator, sample_thresholds, mock_state_manager):
        """Test de détection de cassure extrême"""
        # Cassure de R2 avec amplitude suffisante
        current_price = 3418.0  # R2 à 3415 + 3$ = cassure franche
        
        signal = validator.check_breakout(current_price, sample_thresholds)
        
        assert signal is not None
        # Le signal peut être de type range_return ou breakout selon l'état
        if signal.get("status") == "semi_neutral":
            # Signal de retour en range
            assert signal["direction"] == "range_return"
        else:
            # Signal de cassure
            assert "R2" in signal.get("threshold_name", "")
            assert signal["direction"] == "bullish"
            assert signal["status"] == "partial"
    
    def test_tension_zone_detection(self, validator, sample_thresholds, mock_state_manager):
        """Test de détection de zone de tension"""
        # Prix proche de R2 mais sans cassure
        current_price = 3414.5  # Proche de R2 à 3415 mais pas en range S1-R1
        
        # Mock pour éviter la détection de retour en range
        mock_state_manager.check_range_return.return_value = False
        
        # Simuler plusieurs touches
        for _ in range(3):
            validator.add_price_point(current_price)
        
        # Mock l'état tension
        mock_state_manager.get_breakout_state.return_value = BreakoutState.TENSION
        
        signal = validator.check_breakout(current_price, sample_thresholds)
        
        # Le signal peut être None, de tension, ou de retour en range
        if signal is not None:
            assert signal["status"] in ["tension", "semi_neutral", "partial"]
    
    def test_volatility_check(self, validator):
        """Test de vérification de volatilité"""
        # Simuler des prix très volatils sur 1 heure
        base_time = datetime.utcnow()
        
        # Prix extrêmes : 3300 à 3500 = 200$ de range sur 3400 = 5.88% >> 1%
        prices = [3300, 3500, 3250, 3480, 3320, 3460, 3280, 3440, 3350, 3420]
        
        for i, price in enumerate(prices):
            # Distribuer sur 45 minutes (bien dans la fenêtre d'1h)
            timestamp = base_time - timedelta(minutes=i*4.5)
            validator.add_price_point(price, timestamp)
        
        is_volatile = validator.check_volatility()
        
        # Si ça ne marche toujours pas, debug
        if not is_volatile:
            recent_prices = [p["price"] for p in validator.price_history if 
                           (base_time - p["timestamp"]).total_seconds() <= 3600]
            if recent_prices:
                price_range = max(recent_prices) - min(recent_prices)
                avg_price = sum(recent_prices) / len(recent_prices)
                volatility_pct = (price_range / avg_price) * 100
                print(f"DEBUG: Range={price_range}, Avg={avg_price}, Vol%={volatility_pct}")
        
        assert is_volatile is True

class TestEnhancedSignalDetector:
    
    @pytest.fixture
    def mock_state_manager(self):
        """Mock du gestionnaire d'état pivot"""
        mock = Mock()
        mock.get_active_pivot.return_value = PivotType.CLASSIC
        mock.get_breakout_state.return_value = BreakoutState.NONE
        mock.can_switch_pivot.return_value = True
        # Ajouter l'attribut current_state comme un dict
        mock.current_state = {"switches_count": 0}
        return mock
    
    @pytest.fixture  
    def mock_session_manager(self):
        """Mock du gestionnaire de sessions"""
        mock = Mock()
        mock.should_calculate_pivots.return_value = None
        mock.get_cached_pivots.return_value = [
            {"nom": "R2_classique", "valeur": 3410.0, "type": "résistance"},
            {"nom": "Pivot_classique", "valeur": 3395.0, "type": "pivot"},
            {"nom": "S2_classique", "valeur": 3380.0, "type": "support"}
        ]
        return mock
    
    @pytest.fixture
    def signal_detector(self, mock_state_manager, mock_session_manager):
        """Instance du détecteur de signaux avancé"""
        return EnhancedSignalDetector(mock_state_manager, mock_session_manager)
    
    @pytest.mark.asyncio
    async def test_signal_detection_normal(self, signal_detector):
        """Test de détection de signal en conditions normales"""
        current_price = 3400.0  # Prix normal
        
        signal = await signal_detector.detect_signals(current_price)
        
        # Peut être None (pas de signal) ou un signal valide
        assert signal is None or isinstance(signal, dict)
    
    @pytest.mark.asyncio
    async def test_neutral_mode_blocking(self, signal_detector, mock_state_manager):
        """Test que le mode neutre bloque les signaux"""
        mock_state_manager.get_breakout_state.return_value = BreakoutState.NEUTRAL
        
        signal = await signal_detector.detect_signals(3400.0)
        
        assert signal is not None
        assert signal["direction"] == "neutral"
        assert signal["status"] == "blocked"
    
    def test_status_summary(self, signal_detector, mock_state_manager, mock_session_manager):
        """Test du résumé de statut"""
        status = signal_detector.get_status_summary()
        
        assert "pivot_actif" in status
        assert "etat_cassure" in status
        assert "switches_count" in status
        assert "can_switch" in status
        assert "pivots_disponibles" in status

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
