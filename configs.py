ENV_PATH = "/home/ubuntu/anaconda3/envs/parrotgpt/bin/python"
HOST = '0.0.0.0'
PORT = '8000'
DEBUG = True

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

