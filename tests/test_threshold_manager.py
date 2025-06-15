"""
Tests pour le gestionnaire de seuils
"""
import pytest
from unittest.mock import Mock, AsyncMock
import sys
import os

# Ajouter le chemin src au PYTHONPATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.threshold_manager import ThresholdManager

class TestThresholdManager:
    
    @pytest.fixture
    def mock_notion_manager(self):
        """Mock du gestionnaire Notion"""
        mock = Mock()
        mock.get_daily_thresholds = AsyncMock()
        mock.save_thresholds = AsyncMock()
        return mock
    
    @pytest.fixture
    def threshold_manager(self, mock_notion_manager):
        """Instance du gestionnaire de seuils"""
        return ThresholdManager(mock_notion_manager)
    
    def test_calculate_pivot_points(self, threshold_manager):
        """Test du calcul des points pivots"""
        daily_data = {
            "high": 2000.0,
            "low": 1980.0,
            "close": 1990.0
        }
        
        thresholds = threshold_manager.calculate_pivot_points(daily_data)
        
        # Vérifier qu'on a 7 seuils
        assert len(thresholds) == 7
        
        # Vérifier les types
        types = [t["type"] for t in thresholds]
        assert "pivot" in types
        assert types.count("résistance") == 3
        assert types.count("support") == 3
        
        # Vérifier le pivot
        pivot = next(t for t in thresholds if t["type"] == "pivot")
        expected_pivot = round((2000 + 1980 + 1990) / 3, 2)
        assert pivot["valeur"] == expected_pivot
    
    def test_calculate_take_profit(self, threshold_manager):
        """Test du calcul du take profit"""
        broken_threshold = 2000.0
        pivot = 1990.0
        
        tp = threshold_manager.calculate_take_profit(broken_threshold, pivot)
        expected_tp = round(2000 + (2000 - 1990) * 0.8, 2)
        assert tp == expected_tp
    
    def test_calculate_take_profit_no_pivot(self, threshold_manager):
        """Test du calcul TP sans pivot"""
        tp = threshold_manager.calculate_take_profit(2000.0, None)
        assert tp is None
    
    @pytest.mark.asyncio
    async def test_load_daily_thresholds(self, threshold_manager, mock_notion_manager):
        """Test du chargement des seuils"""
        # Mock des données Notion
        mock_data = [
            {"valeur": 2010.0, "type": "résistance"},
            {"valeur": 2005.0, "type": "résistance"},
            {"valeur": 1995.0, "type": "pivot"},
            {"valeur": 1985.0, "type": "support"},
            {"valeur": 1980.0, "type": "support"}
        ]
        mock_notion_manager.get_daily_thresholds.return_value = mock_data
        
        await threshold_manager.load_daily_thresholds()
        
        # Vérifier que les seuils sont chargés
        thresholds = threshold_manager.get_thresholds()
        assert len(thresholds) == 5
        
        # Vérifier le pivot
        assert threshold_manager.get_pivot() == 1995.0
        
        # Vérifier les noms
        names = [t["nom"] for t in thresholds]
        assert "Pivot" in names
        assert "R1" in names
        assert "S1" in names
    
    def test_get_threshold_by_name(self, threshold_manager):
        """Test de récupération par nom"""
        threshold_manager.current_thresholds = [
            {"nom": "R1", "valeur": 2000.0, "type": "résistance"}
        ]
        
        r1 = threshold_manager.get_threshold_by_name("R1")
        assert r1 is not None
        assert r1["valeur"] == 2000.0
        
        # Test avec nom inexistant
        inexistant = threshold_manager.get_threshold_by_name("R5")
        assert inexistant is None
