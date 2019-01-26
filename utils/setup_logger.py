import logging, logging.handlers, sys

# setup logger

fmt = logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S')

stream = logging.StreamHandler(sys.stdout)
stream.setLevel(logging.INFO)
stream.setFormatter(fmt)

file = logging.handlers.TimedRotatingFileHandler('logs/log.log', when='midnight', encoding='utf-8-sig')
file.setLevel(logging.INFO)
file.setFormatter(fmt)


def config_logger(logger):
	logger.setLevel(logging.INFO)
	logger.addHandler(stream)
	logger.addHandler(file)

	return logger
