from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any

import requests
from fastapi import HTTPException, Request


FREE_SERVICES = ("video_to_audio", "audio_to_text", "video_to_text")
PLAN_LABELS = {
    "free": "Cuenta gratuita",
    "premium": "Premium",
    "lifetime": "Acceso permanente",
    "master": "Administrador",
}


class AuthService:
    def __init__(self) -> None:
        self.url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.anon_key = os.getenv("SUPABASE_ANON_KEY", "").strip()
        self.service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        self.master_email = os.getenv("MASTER_EMAIL", "").strip().lower()
        self.required = os.getenv("AUTH_REQUIRED", "false").lower() in {"1", "true", "yes", "on"}

    @property
    def configured(self) -> bool:
        return bool(self.url and self.anon_key and self.service_key)

    def require_configured(self) -> None:
        if not self.configured:
            raise HTTPException(status_code=503, detail="La autenticación todavía no está configurada.")

    async def current_user(self, request: Request) -> dict[str, Any]:
        if not self.configured and not self.required:
            return {"id": "local-user", "email": self.master_email or "local@gmail.com"}
        self.require_configured()
        authorization = request.headers.get("Authorization", "")
        if not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Iniciá sesión para utilizar FluxMedia Pro.")
        user = await asyncio.to_thread(self._get_supabase_user, authorization)
        email = str(user.get("email", "")).lower()
        if not self._is_gmail(email):
            raise HTTPException(status_code=403, detail="Solo se permiten cuentas Gmail verificadas.")
        return user

    async def account(self, user: dict[str, Any]) -> dict[str, Any]:
        if not self.configured and not self.required:
            return {
                "id": user["id"], "email": user["email"], "plan": "master",
                "plan_label": "Modo local", "premium_active": True,
                "premium_until": None, "free_uses": {service: False for service in FREE_SERVICES},
                "is_master": True,
            }
        profile = await asyncio.to_thread(self._get_profile, user["id"], str(user.get("email", "")))
        if not profile:
            raise HTTPException(status_code=500, detail="No se encontró ni se pudo crear el perfil de la cuenta. Verificá que la tabla user_profiles exista en Supabase ejecutando supabase_schema.sql.")
        return self._account_payload(user, profile)

    async def consume_or_reject(self, user: dict[str, Any], service: str) -> dict[str, Any]:
        if service not in FREE_SERVICES:
            raise HTTPException(status_code=400, detail="Servicio no válido.")
        if not self.configured and not self.required:
            return await self.account(user)
        profile = await asyncio.to_thread(self._consume_free_use, user["id"], service)
        if profile is None:
            raise HTTPException(
                status_code=402,
                detail="Ya utilizaste tu prueba gratuita de este servicio. Suscribite por WhatsApp para continuar.",
            )
        return self._account_payload(user, profile)

    async def admin_users(self, user: dict[str, Any]) -> list[dict[str, Any]]:
        self._require_master(user)
        return await asyncio.to_thread(self._list_profiles)

    async def admin_set_plan(self, user: dict[str, Any], target_user_id: str, plan: str) -> dict[str, Any]:
        self._require_master(user)
        if plan not in {"free", "premium", "lifetime"}:
            raise HTTPException(status_code=400, detail="Plan no válido.")
        profile = await asyncio.to_thread(self._set_plan, target_user_id, plan)
        if not profile:
            raise HTTPException(status_code=404, detail="Usuario no encontrado.")
        return profile

    def _headers(self, prefer: str | None = None, use_anon: bool = False) -> dict[str, str]:
        key = self.anon_key if use_anon or not self.service_key else self.service_key
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers

    def _get_supabase_user(self, authorization: str) -> dict[str, Any]:
        response = requests.get(
            f"{self.url}/auth/v1/user",
            headers={"apikey": self.anon_key, "Authorization": authorization},
            timeout=15,
        )
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="La sesión no es válida o expiró.")
        return response.json()

    def _get_profile(self, user_id: str, email: str = "") -> dict[str, Any] | None:
        response = requests.get(
            f"{self.url}/rest/v1/user_profiles",
            params={"id": f"eq.{user_id}", "select": "*"},
            headers=self._headers(),
            timeout=15,
        )
        if response.status_code == 401 and self.anon_key:
            response = requests.get(
                f"{self.url}/rest/v1/user_profiles",
                params={"id": f"eq.{user_id}", "select": "*"},
                headers=self._headers(use_anon=True),
                timeout=15,
            )
        self._raise_database_error(response)
        rows = response.json()
        if rows:
            return rows[0]
        if email:
            headers = self._headers("return=representation")
            insert_resp = requests.post(
                f"{self.url}/rest/v1/user_profiles",
                json={"id": user_id, "email": email.lower()},
                headers=headers,
                timeout=15,
            )
            if insert_resp.status_code == 401 and self.anon_key:
                insert_resp = requests.post(
                    f"{self.url}/rest/v1/user_profiles",
                    json={"id": user_id, "email": email.lower()},
                    headers=self._headers("return=representation", use_anon=True),
                    timeout=15,
                )
            if insert_resp.ok:
                inserted = insert_resp.json()
                return inserted[0] if inserted else None
        return None

    def _consume_free_use(self, user_id: str, service: str) -> dict[str, Any] | None:
        response = requests.post(
            f"{self.url}/rest/v1/rpc/consume_free_use",
            json={"p_user_id": user_id, "p_service": service},
            headers=self._headers(),
            timeout=15,
        )
        if response.status_code == 401 and self.anon_key:
            response = requests.post(
                f"{self.url}/rest/v1/rpc/consume_free_use",
                json={"p_user_id": user_id, "p_service": service},
                headers=self._headers(use_anon=True),
                timeout=15,
            )
        self._raise_database_error(response)
        rows = response.json()
        return rows[0] if rows else None

    def _list_profiles(self) -> list[dict[str, Any]]:
        response = requests.get(
            f"{self.url}/rest/v1/user_profiles",
            params={"select": "*", "order": "created_at.desc"},
            headers=self._headers(),
            timeout=15,
        )
        if response.status_code == 401 and self.anon_key:
            response = requests.get(
                f"{self.url}/rest/v1/user_profiles",
                params={"select": "*", "order": "created_at.desc"},
                headers=self._headers(use_anon=True),
                timeout=15,
            )
        self._raise_database_error(response)
        return response.json()

    def _set_plan(self, user_id: str, plan: str) -> dict[str, Any] | None:
        updates: dict[str, Any] = {"plan": plan}
        if plan == "premium":
            now = datetime.now(timezone.utc)
            updates["premium_until"] = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
            updates["premium_until"] = self._add_days(updates["premium_until"], 30)
        else:
            updates["premium_until"] = None
        response = requests.patch(
            f"{self.url}/rest/v1/user_profiles",
            params={"id": f"eq.{user_id}"},
            json=updates,
            headers=self._headers("return=representation"),
            timeout=15,
        )
        if response.status_code == 401 and self.anon_key:
            response = requests.patch(
                f"{self.url}/rest/v1/user_profiles",
                params={"id": f"eq.{user_id}"},
                json=updates,
                headers=self._headers("return=representation", use_anon=True),
                timeout=15,
            )
        self._raise_database_error(response)
        rows = response.json()
        return rows[0] if rows else None

    def _account_payload(self, user: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
        email = str(user.get("email", "")).lower()
        plan = "master" if self.master_email and email == self.master_email else profile["plan"]
        premium_until = profile.get("premium_until")
        premium_active = plan in {"master", "lifetime"} or (
            plan == "premium" and premium_until and self._future_date(premium_until)
        )
        return {
            "id": user["id"],
            "email": email,
            "plan": plan if premium_active or plan != "premium" else "free",
            "plan_label": PLAN_LABELS[plan if premium_active else "free"],
            "premium_active": premium_active,
            "premium_until": premium_until if plan == "premium" and premium_active else None,
            "free_uses": {
                "video_to_audio": profile["used_video_to_audio"],
                "audio_to_text": profile["used_audio_to_text"],
                "video_to_text": profile["used_video_to_text"],
            },
            "is_master": plan == "master",
        }

    def _require_master(self, user: dict[str, Any]) -> None:
        if not self.master_email or str(user.get("email", "")).lower() != self.master_email:
            raise HTTPException(status_code=403, detail="No tenés permisos de administrador.")

    @staticmethod
    def _is_gmail(email: str) -> bool:
        return email.endswith("@gmail.com") or email.endswith("@googlemail.com")

    @staticmethod
    def _future_date(value: str) -> bool:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")) > datetime.now(timezone.utc)
        except ValueError:
            return False

    @staticmethod
    def _add_days(value: str, days: int) -> str:
        from datetime import timedelta

        date = datetime.fromisoformat(value.replace("Z", "+00:00")) + timedelta(days=days)
        return date.isoformat().replace("+00:00", "Z")

    @staticmethod
    def _raise_database_error(response: requests.Response) -> None:
        if response.ok:
            return
        detail = response.text[:300] or "Error de base de datos."
        raise HTTPException(status_code=500, detail=f"No se pudo actualizar la cuenta: {detail}")


auth_service = AuthService()
get_current_user = auth_service.current_user
