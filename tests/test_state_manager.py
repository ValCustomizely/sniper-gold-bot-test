"""
Tests pour le gestionnaire d'état
"""
import pytest
import json
import os
import tempfile
from unittest.mock import patch
import sys

# Ajouter le chemin src au PYTHONPATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.state_manager import StateManager

class TestStateManager:
    
    @pytest.fixture
    def temp_state_file(self):
        """Fichier temporaire pour les tests"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            yield f.name
        # Nettoyer après le test
        if os.path.exists(f.name):
            os.unlink(f.name)
    
    @pytest.fixture
    def state_manager(self, temp_state_file):
        """Gestionnaire d'état avec fichier temporaire"""
        with patch('src.state_manager.Config') as mock_config:
            mock_config.return_value.STATE_FILE = temp_state_file
            mock_config.return_value.RESET_THRESHOLD = 0.2
            return StateManager()
    
    def test_load_state_new_file(self, state_manager):
        """Test chargement état avec nouveau fichier"""
        state = state_manager.load_state()
        assert state["seuil"] is None
        assert state["compteur"] == 0
    
    def test_save_and_load_state(self, state_manager):
        """Test sauvegarde et chargement d'état"""
        state_manager.save_state("R1", 3)
        
        assert state_manager.get_current_threshold() == "R1"
        assert state_manager.get_counter() == 3
        
        # Recharger depuis le fichier
        new_state = state_manager.load_state()
        assert new_state["seuil"] == "R1"
        assert new_state["compteur"] == 3
    
    def test_increment_counter_same_threshold(self, state_manager):
        """Test incrémentation compteur même seuil"""
        state_manager.save_state("R1", 2)
        
        new_counter = state_manager.increment_counter("R1")
        assert new_counter == 3
        assert state_manager.get_counter() == 3
    
    def test_increment_counter_new_threshold(self, state_manager):
        """Test incrémentation compteur nouveau seuil"""
        state_manager.save_state("R1", 5)
        
        new_counter = state_manager.increment_counter("R2")
        assert new_counter == 1
        assert state_manager.get_current_threshold() == "R2"
    
    def test_reset_state(self, state_manager):
        """Test remise à zéro de l'état"""
        state_manager.save_state("R1", 5)
        state_manager.reset_state()
        
        assert state_manager.get_current_threshold() is None
        assert state_manager.get_counter() == 0
    
    def test_should_reset_resistance(self, state_manager):
        """Test reset pour cassure de résistance"""
        thresholds = [
            {"nom": "R1", "valeur": 2000.0, "type": "résistance"}
        ]
        
        state_manager.save_state("R1", 3)
        
        # Prix repasse sous la résistance - seuil
        should_reset = state_manager.should_reset_for_price(1999.5, thresholds)
        assert should_reset is True
        
        # Prix reste au-dessus
        should_reset = state_manager.should_reset_for_price(2000.5, thresholds)
        assert should_reset is False
    
    def test_should_reset_support(self, state_manager):
        """Test reset pour cassure de support"""
        thresholds = [
            {"nom": "S1", "valeur": 1980.0, "type": "support"}
        ]
        
        state_manager.save_state("S1", 2)
        
        # Prix repasse au-dessus du support + seuil
        should_reset = state_manager.should_reset_for_price(1980.5, thresholds)
        assert should_reset is True
        
        # Prix reste en-dessous
        should_reset = state_manager.should_reset_for_price(1979.0, thresholds)
        assert should_reset is False
    
    def test_should_reset_no_current_threshold(self, state_manager):
        """Test reset sans seuil actuel"""
        thresholds = [{"nom": "R1", "valeur": 2000.0, "type": "résistance"}]
        
        should_reset = state_manager.should_reset_for_price(1999.0, thresholds)
        assert should_reset is False
    
    def test_load_state_corrupted_file(self, temp_state_file):
        """Test chargement fichier corrompu"""
        # Écrire un JSON invalide
        with open(temp_state_file, 'w') as f:
            f.write("invalid json")
        
        with patch('src.state_manager.Config') as mock_config:
            mock_config.return_value.STATE_FILE = temp_state_file
            mock_config.return_value.RESET_THRESHOLD = 0.2
            
            state_manager = StateManager()
            state = state_manager.load_state()
            
            # Doit retourner l'état par défaut
            assert state["seuil"] is None
            assert state["compteur"] == 0
