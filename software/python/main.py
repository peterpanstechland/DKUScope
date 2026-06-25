from control_station.config_manager import load_config
from control_station.log_service import configure_logging, get_logger, install_tk_exception_hook
from control_station.paths import ensure_default_config, get_default_config_path
from control_station.ui import ControlStationApp


def main() -> None:
    ensure_default_config()
    config_path = get_default_config_path()
    config = load_config(config_path)
    configure_logging(config.logging)
    get_logger("app").info("DKUScope control station starting")
    app = ControlStationApp(default_config_path=config_path)
    install_tk_exception_hook(app)
    app.mainloop()


if __name__ == "__main__":
    main()
