"""
Configuration pytest globale avec support des nouvelles fonctionnalités
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
        
        # Calculs de pivots
        config_instance.CLASSIC_CALC_HOUR = 23
        config_instance.ASIA_CALC_HOUR = 4
        config_instance.EUROPE_CALC_HOUR = 13
        config_instance.CALC_MINUTE_OFFSET = 3
        
        yield config_instance

@pytest.fixture
def sample_ohlc_data():
    """Données OHLC d'exemple pour les tests"""
    return {
        "high": 3420.0,
        "low": 3380.0, 
        "close": 3400.0,
        "open": 3390.0,
        "volume": 1500,
        "timestamp": 1718467200000
    }

@pytest.fixture  
def sample_thresholds_with_reliability():
    """Seuils avec informations de fiabilité pour les tests"""
    return [
        {
            "nom": "R2_classique", 
            "valeur": 3415.0, 
            "type": "résistance",
            "pivot_type": "classique"
        },
        {
            "nom": "R1_classique", 
            "valeur": 3410.0, 
            "type": "résistance",
            "pivot_type": "classique"
        },
        {
            "nom": "Pivot_classique", 
            "valeur": 3400.0, 
            "type": "pivot",
            "pivot_type": "classique"
        },
        {
            "nom": "S1_classique", 
            "valeur": 3390.0, 
            "type": "support",
            "pivot_type": "classique"
        },
        {
            "nom": "S2_classique", 
            "valeur": 3385.0, 
            "type": "support",
            "pivot_type": "classique"
        }
    ]
