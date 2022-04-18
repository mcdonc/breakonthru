import logging

def teelogger(logfile=None):
    """ Log to stdout and logfile """
    logging.basicConfig(filename=logfile,
                        level=logging.INFO,
                        format='%(asctime)s %(message)s',
                        datefmt='%m/%d/%Y %I:%M:%S %p')
    logger = logging.getLogger()
    if logfile is not None:
        # tee to stdout too
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s %(message)s',
            datefmt='%m/%d/%Y %I:%M:%S %p'
        )
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    return logger
