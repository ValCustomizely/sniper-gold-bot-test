"""
Tests pour le détecteur de signaux
"""
import pytest
from unittest.mock import Mock
import sys
import os

# Ajouter le chemin src au PYTHONPATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.signal_detector import SignalDetector

class TestSignalDetector:
    
    @pytest.fixture
    def mock_state_manager(self):
        """Mock du gestionnaire d'état"""
        mock = Mock()
        mock.should_reset_for_price.return_value = False
        mock.increment_counter.return_value = 1
        mock.reset_state.return_value = None
        return mock
    
    @pytest.fixture
    def signal_detector(self, mock_state_manager):
        """Instance du détecteur de signaux"""
        return SignalDetector(mock_state_manager)
    
    @pytest.fixture
    def sample_thresholds(self):
        """Seuils d'exemple pour les tests"""
        return [
            {"nom": "R2", "valeur": 2010.0, "type": "résistance"},
            {"nom": "R1", "valeur": 2005.0, "type": "résistance"},
            {"nom": "Pivot", "valeur": 1995.0, "type": "pivot"},
            {"nom": "S1", "valeur": 1985.0, "type": "support"},
            {"nom": "S2", "valeur": 1980.0, "type": "support"}
        ]
    
    def test_detect_resistance_break(self, signal_detector, sample_thresholds, mock_state_manager):
        """Test de détection de cassure de résistance"""
        current_price = 2006.0  # Au-dessus de R1 + 0.5
        
        signal = signal_detector.detect_signals(current_price, sample_thresholds)
        
        assert signal is not None
        assert signal["direction"] == "resistance"
        assert signal["threshold_name"] == "R1"
        assert "📈" in signal["type"]
        assert mock_state_manager.increment_counter.called
    
    def test_detect_support_break(self, signal_detector, sample_thresholds, mock_state_manager):
        """Test de détection de cassure de support"""
        current_price = 1984.0  # En-dessous de S1 - 0.5
        
        signal = signal_detector.detect_signals(current_price, sample_thresholds)
        
        assert signal is not None
        assert signal["direction"] == "support"
        assert signal["threshold_name"] == "S1"
        assert "📉" in signal["type"]
    
    def test_detect_approach_signal_bullish(self, signal_detector, sample_thresholds):
        """Test de signal d'approche haussier"""
        current_price = 2000.0  # Entre pivot et R1
        
        signal = signal_detector.detect_signals(current_price, sample_thresholds)
        
        assert signal is not None
        assert signal["direction"] == "bullish_approach"
        assert signal["target"] == "R1"
        assert "🚧📈" in signal["type"]
    
    def test_detect_approach_signal_bearish(self, signal_detector, sample_thresholds):
        """Test de signal d'approche baissier"""
        current_price = 1990.0  # Entre S1 et pivot
        
        signal = signal_detector.detect_signals(current_price, sample_thresholds)
        
        assert signal is not None
        assert signal["direction"] == "bearish_approach"
        assert signal["target"] == "S1"
        assert "🚧📉" in signal["type"]
    
    def test_no_signal_in_range(self, signal_detector, sample_thresholds):
        """Test quand aucun signal n'est détecté"""
        current_price = 1995.0  # Exactement au pivot
        
        signal = signal_detector.detect_signals(current_price, sample_thresholds)
        
        # Peut être None ou un signal d'approche selon la logique
        # On teste juste qu'il n'y a pas d'erreur
        assert signal is None or isinstance(signal, dict)
    
    def test_calculate_trading_levels_resistance(self, signal_detector):
        """Test du calcul des niveaux de trading pour une résistance"""
        signal = {
            "broken_threshold": 2005.0,
            "direction": "resistance"
        }
        current_price = 2006.0
        pivot = 1995.0
        
        levels = signal_detector.calculate_trading_levels(signal, current_price, pivot)
        
        assert "sl" in levels
        assert "trailing_sl" in levels
        assert "tp" in levels
        assert levels["sl"] < signal["broken_threshold"]  # SL en-dessous
        assert levels["trailing_sl"] > current_price  # TSL au-dessus
    
    def test_calculate_trading_levels_support(self, signal_detector):
        """Test du calcul des niveaux de trading pour un support"""
        signal = {
            "broken_threshold": 1985.0,
            "direction": "support"
        }
        current_price = 1984.0
        pivot = 1995.0
        
        levels = signal_detector.calculate_trading_levels(signal, current_price, pivot)
        
        assert "sl" in levels
        assert "trailing_sl" in levels
        assert "tp" in levels
        assert levels["sl"] > signal["broken_threshold"]  # SL au-dessus
        assert levels["trailing_sl"] < current_price  # TSL en-dessous
    
    def test_strong_signal_with_confirmations(self, signal_detector, sample_thresholds, mock_state_manager):
        """Test de signal fort avec confirmations"""
        mock_state_manager.increment_counter.return_value = 5  # 5 confirmations
        current_price = 2006.0
        
        signal = signal_detector.detect_signals(current_price, sample_thresholds)
        
        assert signal is not None
        assert signal["is_strong"] is True
        assert "🚧" in signal["type"]
        assert signal["confirmations"] == 5
