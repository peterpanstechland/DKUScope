from control_station.paths import ensure_default_config, get_default_config_path
from control_station.ui import ControlStationApp


def main() -> None:
    ensure_default_config()
    app = ControlStationApp(default_config_path=get_default_config_path())
    app.mainloop()


if __name__ == "__main__":
    main()
