"""Wizard API routes (Plan 4a). Registered onto the app by create_app()."""
from fastapi import Body, FastAPI

from app.api.config_api import SettingsValidationError, update_settings
from app.config_accessors import get_tv_target
from app.storage.settings_store import SettingsStore
from app.wizard import cert, detect, state


def add_wizard_routes(app: FastAPI) -> None:
    @app.get("/api/wizard/state")
    def wizard_state():
        return {
            "onboarding_complete": state.is_onboarding_complete(),
            "step": state.get_step(),
        }

    @app.post("/api/wizard/step")
    def wizard_set_step(payload: dict = Body(...)):
        state.set_step(int(payload.get("step", 1)))
        return {"ok": True}

    @app.post("/api/wizard/complete")
    def wizard_complete():
        state.set_onboarding_complete(True)
        return {"ok": True}

    @app.get("/api/wizard/cert/status")
    def wizard_cert_status():
        return {"trusted": cert.is_cert_trusted()}

    @app.post("/api/wizard/cert/install")
    def wizard_cert_install():
        return cert.install_cert_elevated()

    @app.get("/api/wizard/mt5/detect")
    def wizard_mt5_detect():
        return {
            "terminals": detect.detect_mt5_terminals(),
            "current": SettingsStore().get("mt5.terminal_path"),
        }

    @app.post("/api/wizard/mt5/test")
    def wizard_mt5_test(payload: dict = Body(...)):
        mt5 = payload.get("mt5", {}) or {}
        result = detect.check_mt5_connection(
            mt5.get("account"), mt5.get("password", ""),
            mt5.get("server", ""), mt5.get("terminal_path"),
        )
        if result.get("ok"):
            try:
                update_settings({"mt5": mt5})
            except SettingsValidationError as e:
                return {"ok": False, "error": str(e)}
        return result

    @app.get("/api/wizard/tv/detection")
    def wizard_tv_detection():
        broker_url, account_id = get_tv_target()
        return {
            "detected": bool(broker_url and account_id),
            "broker_url": broker_url,
            "account_id": account_id,
        }

    @app.get("/api/wizard/symbols/suggest")
    def wizard_symbols_suggest():
        return {"suffix": detect.suggest_symbol_suffix()}
