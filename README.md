# 🥇 Bot de Trading Or - Système Multi-Pivots

Bot de trading automatisé pour l'or avec système avancé de pivots multi-sessions et effet de levier x20.

## 🎯 Fonctionnalités

### 📊 Système Multi-Pivots
- **Pivots Classiques** (23h03 UTC) - Données de la veille
- **Pivots Asie** (4h03 UTC) - Session 0h-4h UTC  
- **Pivots Europe** (13h03 UTC) - Session 4h-13h UTC

### 🔍 Détection Intelligente
- Cassures validées avec amplitude + vitesse + stabilisation
- Zones de tension (3 touches en 30min)
- État neutre automatique si marché erratique
- Maximum 2 bascules de pivots par jour

### ⚡ Critères de Validation
- **Amplitude** : +2$ au-delà de R2/S2
- **Vitesse** : R1→R2 en <3min (bonus)
- **Stabilisation** : 15min dans fourchette ±2$
- **Priorité** : Europe > Asie > Classique

## 🛠️ Installation

```bash
# Cloner le repository
git clone <your-repo-url>
cd gold-trading-bot

# Installer les dépendances
pip install -r requirements.txt

# Configurer les variables d'environnement
cp .env.example .env
# Éditer .env avec tes clés API
```

## 🔑 Variables d'Environnement

```bash
NOTION_API_KEY=your_notion_api_key
NOTION_DATABASE_ID=your_signals_database_id
SEUILS_DATABASE_ID=your_thresholds_database_id
POLYGON_API_KEY=your_polygon_api_key
```

## 🧪 Tests

```bash
# Tests unitaires
pytest tests/ -v

# Tests avec couverture
pytest tests/ --cov=src --cov-report=html

# Tests spécifiques
pytest tests/test_advanced_system.py -v
```

## 🚀 Déploiement

### Render (Automatique)
1. Push sur `main` déclenche le déploiement automatique
2. Tests exécutés avant déploiement
3. Déploiement uniquement si tests passent

### Manuel
```bash
python main.py
```

## 📁 Structure du Projet

```
├── src/
│   ├── api_client.py              # Client Polygon.io
│   ├── notion_client.py           # Client Notion
│   ├── pivot_state_manager.py     # Gestion états pivots
│   ├── pivot_session_manager.py   # Calculs pivots par session
│   ├── breakout_validator.py      # Validation cassures
│   ├── enhanced_signal_detector.py # Détection signaux avancée
│   ├── threshold_manager.py       # Gestion seuils (legacy)
│   ├── state_manager.py          # État simple (legacy)
│   ├── config.py                 # Configuration
│   └── logger.py                 # Logging
├── tests/
│   ├── test_threshold_manager.py
│   ├── test_signal_detector.py
│   ├── test_state_manager.py
│   └── test_advanced_system.py
├── .github/workflows/tests.yml    # CI/CD GitHub Actions
├── main.py                        # Point d'entrée
├── requirements.txt
├── runtime.txt
├── render.yaml
└── pytest.ini
```

## 📈 Fonctionnement

1. **Initialisation** : Pivots classiques à 23h03
2. **Sessions** : Calcul auto des pivots Asie (4h03) et Europe (13h03)
3. **Détection** : Surveillance continue des cassures R2/S2
4. **Validation** : Critères stricts (amplitude + stabilisation)
5. **Bascule** : Changement intelligent de pivot si cassure validée
6. **Signaux** : Sauvegarde dans Notion avec niveaux de trading

## ⚠️ Avertissements

- **Effet de levier x20** : Risque de perte totale rapide
- **Marché 24h/24** : Surveillance continue requise
- **Tests recommandés** : Valider en mode démo d'abord

## 🔧 Configuration Avancée

Modifier `src/config.py` pour ajuster :
- Seuils de cassure
- Durées de validation  
- Limites de volatilité
- Nombre max de bascules

## 📊 Monitoring

- **Logs** : Détaillés avec horodatage UTC
- **État** : Sauvegardé dans `etat_pivot.json`
- **Historique** : Toutes les décisions tracées
- **Notion** : Signaux avec métadonnées complètes

## 🤝 Contribution

1. Fork le projet
2. Créer une branche feature
3. Commiter les changements
4. Pousser vers la branche
5. Ouvrir une Pull Request

## 📄 License

Projet privé - Tous droits réservés
