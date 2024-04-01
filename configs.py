ENV_PATH = "/home/ubuntu/anaconda3/envs/parrotgpt/bin/python"
HOST = '0.0.0.0'
PORT = '8000'
DEBUG = True


OPENAI_COMPLETIONS_V1_URL = "https://api.openai.com/v1/completions"
OPEN_AI_API_KEY = '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'
SPEECHSUPER_APPKEY = "1709716879000299"
SPEECHSUPER_SECRETKEY = "41cb3809a1e5ffbd7b4cdce0e104e1a3"


# CACHE SETUP:
REDIS_PORT = 6379
REDIS_PASSWORD = 'test'
REDIS_SETTINGS = {
    'gpt_cache': {
        'host': '127.0.0.1',
        'port': REDIS_PORT,
        'db': 0,
        'password': REDIS_PASSWORD
    },
    'memory':{
        'host': '127.0.0.1',
        'port': REDIS_PORT,
        'db': 1,
        'password': REDIS_PASSWORD
    }
}

