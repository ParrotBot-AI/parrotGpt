from utils import abspath
from utils.logger_tools import get_general_logger
from utils.manager_tools import ServiceManager
import fire

logger = get_general_logger(name='manager', path=abspath('logs'))


class ParrotGpt(ServiceManager):
    name = 'ParrotGpt'
    file = 'gpt_server.py'
    dir_path = abspath('services')


SERVICES_MAP = {
    'ParrotGpt': ParrotGpt,
}


def run_service(service_name, action):
    """
    action: start | stop | run | enable | disable | status
    """
    if service_name not in SERVICES_MAP:
        print(f'No such service: {service_name}')
        return

    service = SERVICES_MAP[service_name]
    service(action=action)


def main():
    fire.Fire(run_service)


if __name__ == '__main__':
    main()
