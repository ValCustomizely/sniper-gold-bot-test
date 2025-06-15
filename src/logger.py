"""
Module de logging centralisé
"""
import sys
from datetime import datetime
from typing import Any

class Logger:
    """Logger simple pour le bot"""
    
    def __init__(self):
        pass
    
    def _log(self, level: str, message: str, **kwargs):
        """Log interne avec timestamp"""
        timestamp = datetime.utcnow().isoformat()
        log_message = f"[{timestamp}] [{level}] {message}"
        
        if kwargs:
            log_message += f" | {kwargs}"
        
        print(log_message, flush=True)
    
    def info(self, message: str, **kwargs):
        """Log niveau INFO"""
        self._log("INFO", message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log niveau WARNING"""
        self._log("WARN", message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log niveau ERROR"""
        self._log("ERROR", message, **kwargs)
        
    def debug(self, message: str, **kwargs):
        """Log niveau DEBUG"""
        self._log("DEBUG", message, **kwargs)
