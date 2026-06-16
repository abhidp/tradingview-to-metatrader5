"""Broker-profile CRUD + activate routes. Activate restarts the engine if running."""
from fastapi import Body, FastAPI, HTTPException

from app.storage import profiles
from app.engine_controller import EngineController


def add_profile_routes(app: FastAPI, controller: EngineController) -> None:
    @app.get("/api/profiles")
    def get_profiles():
        return profiles.list_profiles()

    @app.post("/api/profiles")
    def create(payload: dict = Body(...)):
        try:
            return profiles.create_profile(payload)
        except profiles.DuplicateProfileError as e:
            raise HTTPException(status_code=409, detail=str(e))

    @app.put("/api/profiles/{pid}")
    def update(pid: str, payload: dict = Body(...)):
        try:
            return profiles.update_profile(pid, payload)
        except KeyError:
            raise HTTPException(status_code=404, detail="Profile not found")

    @app.delete("/api/profiles/{pid}")
    def delete(pid: str):
        profiles.delete_profile(pid)
        return {"ok": True}

    @app.post("/api/profiles/{pid}/activate")
    async def activate(pid: str):
        try:
            profiles.activate_profile(pid)
        except KeyError:
            raise HTTPException(status_code=404, detail="Profile not found")
        # Reconnect MT5 in place (no proxy restart, no port rebind). No-op if the
        # engine isn't running — the next start picks up the new config.
        await controller.apply_mt5_settings()
        return {"ok": True, "status": controller.status().to_dict()}
