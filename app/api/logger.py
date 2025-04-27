import logging
import sys
from typing import Optional

# Set up logging formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    if level is None:
        level = logging.INFO
        
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid adding handlers if they already exist
    if not logger.handlers:
        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
    # Disable propagation to parent loggers
    logger.propagate = False
        
    return logger