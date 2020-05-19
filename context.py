from resources.lib.utils import addon, kodilog


def main():  # type: () -> None
    addon.ADDON.openSettings()


if __name__ == "__main__":
    kodilog.setup_logging()
    main()
