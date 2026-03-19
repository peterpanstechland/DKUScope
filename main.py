from pathlib import Path

from control_station.ui import ControlStationApp


def main() -> None:
    app = ControlStationApp(default_config_path=Path("config/project_config.json"))
    app.mainloop()


if __name__ == "__main__":
    main()

