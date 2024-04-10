ENV_PATH = "/home/ubuntu/anaconda3/envs/parrotgpt/bin/python"
HOST = '0.0.0.0'
PORT = '8000'
DEBUG = True


OPENAI_COMPLETIONS_V1_URL = "https://api.openai.com/v1/completions"
OPEN_AI_API_KEY = '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'
SPEECHSUPER_APPKEY = "17127194180002ca"
SPEECHSUPER_SECRETKEY = "2500da8fb9ee54b5622c4d644839c852"


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

