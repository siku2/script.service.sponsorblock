from resources.lib.monitor import Monitor
from resources.lib.utils import kodilog


def main():  # type: () -> None
    m = Monitor()
    m.wait_for_abort()


if __name__ == "__main__":
    kodilog.setup_logging()
    main()
