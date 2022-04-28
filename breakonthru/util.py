import logging


def teelogger(logfile=None, loglevel="INFO"):
    """ Log to stdout and logfile """
    loglevel = loglevel.upper()
    logging.basicConfig(
        filename=logfile,
        level=getattr(logging, loglevel),
        format='%(asctime)s %(message)s',
        datefmt='%m/%d/%Y %I:%M:%S %p'
    )
    logger = logging.getLogger()
    if logfile is not None:
        # tee to stdout too
        ch = logging.StreamHandler()
        ch.setLevel(getattr(logging, loglevel))
        formatter = logging.Formatter(
            '%(asctime)s %(message)s',
            datefmt='%m/%d/%Y %I:%M:%S %p'
        )
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    return logger
