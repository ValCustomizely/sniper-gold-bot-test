"""
Configuration pytest globale
"""
import pytest
from unittest.mock import patch
import sys
import os

# Ajouter le chemin src au PYTHONPATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

@pytest.fixture(autouse=True)
def mock_config():
    """Mock de config automatique pour tous les tests"""
    with patch('src.config.Config') as mock:
        # Configuration par défaut pour tous les tests
        config_instance = mock.return_value
        
        # Paramètres legacy
        config_instance.BREAKOUT_THRESHOLD = 0.5  # Pour les anciens tests
        config_instance.BREAKOUT_AMPLITUDE = 2.0  # Pour les nouveaux
        config_instance.RESET_THRESHOLD = 0.2
        config_instance.MIN_CONFIRMATIONS = 5
        config_instance.TP_MULTIPLIER = 0.8
        config_instance.SL_OFFSET = 1.0
        config_instance.TRAILING_SL_OFFSET = 5.0
        config_instance.STATE_FILE = "test_etat_cassure.json"
        config_instance.PIVOT_STATE_FILE = "test_etat_pivot.json"
        
        # Paramètres avancés
        config_instance.STABILIZATION_TIME = 15
        config_instance.STABILIZATION_RANGE = 2.0
        config_instance.SPEED_THRESHOLD = 3
        config_instance.TENSION_WINDOW = 30
        config_instance.TENSION_TOUCHES = 3
        config_instance.VOLATILITY_THRESHOLD = 1.0
        config_instance.MAX_DAILY_SWITCHES = 2
        
        # Sessions
        config_instance.ASIA_SESSION_START = 0
        config_instance.ASIA_SESSION_END = 4
        config_instance.EUROPE_SESSION_START = 4
        config_instance.EUROPE_SESSION_END = 13
        config_instance.US_SESSION_START = 13
        config_instance.US_SESSION_END = 23
        
        yield config_instance
