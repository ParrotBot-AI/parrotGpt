import sys
import os
root_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(root_path, '..')
sys.path.append(project_root)
from apps import app
import uvicorn
from utils.logger_tools import get_general_logger
from configs import HOST, PORT, DEBUG

# Assuming your logging setup and config loading remain valid
logger = get_general_logger(name='gpt_server', path='logs')



def main():
    _app = app.create_app()
    logger.info('parrot GPT Started.')
    logger.info(f'Host: {HOST} Port: {PORT} URL: http://{HOST}:{PORT}')
    # Use uvicorn to run the app
    if DEBUG:
        uvicorn.run(_app, host=HOST, port=int(PORT), log_level="debug")
    else:
        uvicorn.run(_app, host=HOST, port=int(PORT), log_level="info")


if __name__ == '__main__':
    main()
