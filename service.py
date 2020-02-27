from resources.lib.monitor import Monitor
from resources.lib.utils import kodilog


def main():  # type: () -> None
    m = Monitor()
    m.waitForAbort()


if __name__ == "__main__":
    kodilog.setup_logging()
    main()
