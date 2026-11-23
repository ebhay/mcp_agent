"""HTTP clients. Each client logs in with one account from .env and checks that account's role."""
import time

import httpx


class TrainMateError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


class TrainMateUnavailable(Exception):
    """TrainMate did not answer after retries (often Render free tier waking up)."""


def _retry(fn, attempts: int = 3):
    """Retries reads and login only. Never use for create, delete, or override: a timed-out write may have succeeded."""
    last = None
    for attempt in range(attempts):
        try:
            return fn()
        except (httpx.TimeoutException, httpx.ConnectError) as err:
            last = err
            time.sleep(5 * (attempt + 1))
    raise TrainMateUnavailable("TrainMate did not respond. It may be waking up on Render; try again in a minute.") from last


class AppMailClient:
    """Mail through this app's mail API, logged in as one account."""

    def __init__(self, base_url: str, login_id: str, password: str):
        self.http = httpx.Client(base_url=base_url, timeout=60)
        r = self.http.post("/api/auth/login", json={"username": login_id, "password": password})
        r.raise_for_status()
        data = r.json()
        self.user = data["user"]
        self.http.headers["Authorization"] = f"Bearer {data['token']}"

    def inbox(self, unread_only: bool = False) -> list[dict]:
        params = {"limit": 50, "unread": "true"} if unread_only else {"limit": 50}
        r = self.http.get("/api/mail/inbox", params=params)
        r.raise_for_status()
        return r.json()

    def unread_inbox(self) -> list[dict]:
        """Newest unread mail first (the API sorts by creation time, newest first)."""
        return self.inbox(unread_only=True)

    def mark_read(self, message_id: str) -> None:
        self.http.get(f"/api/mail/{message_id}").raise_for_status()

    def send(self, to_username: str, subject: str, body: str) -> dict:
        r = self.http.post("/api/mail", json={"to_username": to_username, "subject": subject[:150], "body": body})
        r.raise_for_status()
        return r.json()


class CoachMailClient(AppMailClient):
    def __init__(self, base_url: str, login_id: str, password: str):
        super().__init__(base_url, login_id, password)
        if self.user["role"] != "coach":
            raise RuntimeError("Coach mail account must have the coach role")

    def reply(self, to_username: str, subject: str, body: str) -> dict:
        return self.send(to_username, subject, body)


class AdminMailClient(AppMailClient):
    def __init__(self, base_url: str, login_id: str, password: str):
        super().__init__(base_url, login_id, password)
        if self.user["role"] != "admin":
            raise RuntimeError("Admin mail account must have the admin role")


class _TrainMateSession:
    expected_role = ""

    def __init__(self, base_url: str, login_id: str, password: str):
        self.http = httpx.Client(base_url=base_url, timeout=120)
        try:
            self.http.get("/api/health/live")  # wakes a sleeping Render instance
        except httpx.HTTPError:
            pass
        r = _retry(lambda: self.http.post("/api/auth/login", json={"loginId": login_id, "password": password}))
        r.raise_for_status()
        data = r.json()
        if data.get("role") != self.expected_role:
            raise RuntimeError(f"TrainMate account must have the {self.expected_role} role")
        self.user_id = data["userId"]
        self.coach_id = data.get("coachId")
        self.name = data.get("name", "")

    @staticmethod
    def _unwrap(r: httpx.Response):
        body = r.json() if r.content else {}
        if r.status_code >= 400 or not body.get("success", False):
            raise TrainMateError(r.status_code, body.get("message") or f"TrainMate request failed ({r.status_code})")
        return body.get("data")

    def notifications(self) -> list[dict]:
        """TrainMate's own mailbox, including allocation notices."""
        return self._unwrap(_retry(lambda: self.http.get(f"/api/notifications/{self.user_id}")))


class TrainMateClient(_TrainMateSession):
    """Coach operations: only this coach's cohorts are listed."""
    expected_role = "COACH"

    def list_cohorts(self) -> list[dict]:
        return self._unwrap(_retry(lambda: self.http.get(f"/api/coach/{self.coach_id}/cohorts")))

    def create_cohort(self, payload: dict) -> dict:
        return self._unwrap(self.http.post(f"/api/coach/{self.coach_id}/cohorts", json=payload))

    def reallocate(self, cohort_id: int) -> dict:
        return self._unwrap(self.http.post(f"/api/cohorts/{cohort_id}/reallocate"))


class TrainMateAdminClient(_TrainMateSession):
    """Admin operations across all cohorts and trainers."""
    expected_role = "ADMIN"

    def list_all_cohorts(self) -> list[dict]:
        return self._unwrap(_retry(lambda: self.http.get("/api/admin/cohorts")))

    def get_cohort(self, cohort_id: int) -> dict:
        return self._unwrap(_retry(lambda: self.http.get(f"/api/cohorts/{cohort_id}")))

    def list_trainers(self) -> list[dict]:
        return self._unwrap(_retry(lambda: self.http.get("/api/admin/trainers")))

    def reallocate(self, cohort_id: int) -> dict:
        return self._unwrap(self.http.post(f"/api/cohorts/{cohort_id}/reallocate"))

    def override_trainer(self, cohort_id: int, trainer_id: int, reason: str) -> dict:
        return self._unwrap(self.http.put(
            f"/api/admin/cohorts/{cohort_id}/trainer",
            params={"adminUserId": self.user_id},
            json={"trainerId": trainer_id, "reason": reason[:500]},
        ))

    def set_status(self, cohort_id: int, status: str) -> dict:
        return self._unwrap(self.http.patch(f"/api/cohorts/{cohort_id}/status", params={"status": status}))

    def delete_cohort(self, cohort_id: int) -> dict:
        return self._unwrap(self.http.delete(f"/api/cohorts/{cohort_id}"))
