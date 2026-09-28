"""Read historical aggregates through GET; search is explicitly forbidden."""

import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.services.retrieval_runtime import RetrievalRuntime


def main():
    def forbidden(*args, **kwargs):
        raise AssertionError("Summary must not invoke runtime search")

    with patch.object(RetrievalRuntime, "search", forbidden):
        app = create_app(Settings(_env_file=None, environment="TEST", database_url="sqlite://"))
        with TestClient(app) as client:
            response = client.get("/api/v1/retrieval/summary")
            assert response.status_code == 200, response.text
            print(json.dumps(response.json(), ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
