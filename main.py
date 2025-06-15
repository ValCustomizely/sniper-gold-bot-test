"""
Bot de trading or - Version refactorisée
Point d'entrée principal
"""
import asyncio
import os
from datetime import datetime
from src.config import Config
from src.api_client import PolygonClient
from src.notion_client import NotionManager
from src.signal_detector import SignalDetector
from src.threshold_manager import ThresholdManager
from src.state_manager import StateManager
from src.logger import Logger

logger = Logger()

class GoldTradingBot:
    def __init__(self):
        self.config = Config()
        self.polygon_client = PolygonClient(self.config.POLYGON_API_KEY)
        self.notion_manager = NotionManager(
            self.config.NOTION_API_KEY, 
            self.config.NOTION_DATABASE_ID_TEST, 
            self.config.SEUILS_DATABASE_ID_TEST
        )
        self.threshold_manager = ThresholdManager(self.notion_manager)
        self.state_manager = StateManager()
        self.signal_detector = SignalDetector(self.state_manager)
        self.last_updates = set()

    async def should_update_thresholds(self):
        """Vérifie s'il faut mettre à jour les seuils automatiquement"""
        now = datetime.utcnow()
        update_key = f"{now.date().isoformat()}_1"
        
        if now.hour == 1 and update_key not in self.last_updates:
            self.last_updates.add(update_key)
            return True
        return False

    async def update_automatic_thresholds(self):
        """Met à jour les seuils automatiquement basés sur les données de la veille"""
        try:
            logger.info("Mise à jour automatique des seuils")
            
            # Récupérer les données de la dernière session
            last_day_data = await self.polygon_client.get_last_trading_day_data()
            if not last_day_data:
                logger.warning("Aucune donnée trouvée pour la dernière session")
                return

            # Calculer les nouveaux seuils
            thresholds = self.threshold_manager.calculate_pivot_points(last_day_data)
            
            # Sauvegarder dans Notion
            await self.notion_manager.save_thresholds(thresholds)
            
            logger.info(f"Seuils mis à jour: {len(thresholds)} seuils sauvegardés")
            
        except Exception as e:
            logger.error(f"Erreur mise à jour seuils auto: {e}")

    async def process_current_data(self):
        """Traite les données actuelles et génère les signaux"""
        try:
            # Charger les seuils du jour
            await self.threshold_manager.load_daily_thresholds()
            
            # Récupérer le prix actuel
            current_data = await self.polygon_client.get_current_minute_data()
            if not current_data:
                logger.warning("Pas de données minute disponibles")
                return

            current_price = current_data["close"]
            volume = current_data["volume"]
            
            # Détecter les signaux
            signal = self.signal_detector.detect_signals(
                current_price, 
                self.threshold_manager.get_thresholds()
            )
            
            if signal:
                # Calculer les niveaux de trading
                trading_levels = self.signal_detector.calculate_trading_levels(
                    signal, current_price, self.threshold_manager.get_pivot()
                )
                
                # Sauvegarder le signal
                await self.notion_manager.save_signal(signal, current_price, volume, trading_levels)
                
                logger.info(f"Signal détecté: {signal['type']} à {current_price}$")
                
        except Exception as e:
            logger.error(f"Erreur traitement données: {e}")

    async def run_cycle(self):
        """Execute un cycle complet du bot"""
        # Mise à jour automatique des seuils si nécessaire
        if await self.should_update_thresholds():
            await self.update_automatic_thresholds()
        
        # Traitement des données courantes
        await self.process_current_data()

    async def start(self):
        """Démarre la boucle principale du bot"""
        logger.info("Démarrage du bot de trading or")
        
        while True:
            try:
                await self.run_cycle()
                await asyncio.sleep(60)  # Attendre 1 minute
                
            except KeyboardInterrupt:
                logger.info("Arrêt du bot demandé")
                break
            except Exception as e:
                logger.error(f"Erreur dans la boucle principale: {e}")
                await asyncio.sleep(60)  # Attendre avant de relancer

async def main():
    """Point d'entrée principal"""
    bot = GoldTradingBot()
    await bot.start()

if __name__ == "__main__":
    logger.info(f"[BOOT] {datetime.utcnow().isoformat()}")
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Erreur critique bot: {e}")
