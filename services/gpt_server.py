import sys
import os

root_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(root_path, '..')
sys.path.append(project_root)
from apps import app
import uvicorn
from utils.logger_tools import get_general_logger
from configs import HOST, PORT, DEBUG
import multiprocessing

# Assuming your logging setup and config loading remain valid
logger = get_general_logger(name='gpt_server', path='logs')


def main():
    # Use uvicorn to run the app
    logger.info('parrot GPT Started.')
    logger.info(f'Host: {HOST} Port: {PORT} URL: http://{HOST}:{PORT}')
    cores = multiprocessing.cpu_count()
    if DEBUG:
        uvicorn.run("apps.app:create_app", host=HOST, port=int(PORT), log_level="debug", reload=True)
    else:
        uvicorn.run("apps.app:create_app", host=HOST, port=int(PORT), log_level="info", workers=cores*2+1)


if __name__ == '__main__':
    main()
