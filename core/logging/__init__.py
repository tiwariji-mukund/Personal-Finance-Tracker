from .logger import ApplicationLogger

def get_logger(name: str) -> ApplicationLogger:
    return ApplicationLogger(name)