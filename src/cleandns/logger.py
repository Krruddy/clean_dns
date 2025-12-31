import logging

class LoggerMeta(type):
    """
    The Singleton class can be implemented in different ways in Python. Some
    possible methods include: base class, decorator, metaclass. We will use the
    metaclass because it is best suited for this purpose.
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        """
        Possible changes to the value of the `__init__` argument do not affect
        the returned instance.
        """
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class Logger(metaclass=LoggerMeta):
    def __init__(self):
        # Create a logger
        self.logger = logging.getLogger("my_logger")

        # Create a StreamHandler and set the custom formatter
        handler = logging.StreamHandler()
        handler.setFormatter(CustomFormatter())

        # Add the handler to the logger
        self.logger.addHandler(handler)

        # Set the logging level
        self.logger.setLevel(logging.INFO)

    def info(self, string: str):
        self.logger.info(string)

    def error(self, string: str):
        self.logger.error(string)

    def warning(self, string: str):
        self.logger.warning(string)


class CustomFormatter(logging.Formatter):
    FORMATS = {
        logging.INFO: "[+] %(message)s",
        logging.WARNING: "[!] %(message)s",
        logging.ERROR: "[-] %(message)s",
    }

    def format(self, record):
        log_format = self.FORMATS.get(record.levelno, self._style._fmt)
        self._style._fmt = log_format
        return super().format(record)
