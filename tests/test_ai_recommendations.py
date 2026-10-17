import asyncio
import json
import os
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

# Tests do not require real credentials or a running database.
os.environ.update(DB_HOST="localhost", DB_PORT="5432", DB_NAME="test", DB_USER="test",
                  DB_PASSWORD="test", GOOGLE_ROUTES_API_KEY="test", DEEPSEEK_API_KEY="")

import httpx
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import _DeepSeekSettings
from app.core.database import get_db
from app.main import app
from app.schema.commute import CommuteRoute
from app.schema.recommendation import RecommendationItem, RecommendationRequest
from app.service.ai_recommendation_service import AIRecommendationService
from app.service.recommendation_service import RecommendationService


def item(rental_id=1, rent="9000", duration=1200):
    return RecommendationItem(
        rental_id=rental_id, title="Home", address="Private address", district="九龙",
        monthly_rent_hkd=Decimal(rent), emission_factor_version="test",
        latitude=22.3, longitude=114.2, listing_url="https://example.com/home",
        fetched_at=datetime.now(timezone.utc),
        commute=CommuteRoute(duration_seconds=duration, distance_meters=5000,
                             transfer_count=1, steps=[]),
    )


def reply(ids):
    return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({
        "recommendations": [{"rental_id": i, "reason": "通勤方便", "tradeoff": "交通费未知"} for i in ids]
    })}}]}


class AIRecommendationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.request = RecommendationRequest(work_address_id=1, max_monthly_rent_hkd=10000)
        self.settings = _DeepSeekSettings(_env_file=None, api_key="test-secret")
        self.service = AIRecommendationService(self.settings)
        self.calls = []

    async def run_ai(self, body=None, status=200, items=None, error=None):
        def handler(request):
            self.calls.append(json.loads(request.content))
            if error:
                raise error
            return httpx.Response(status, json=body)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await self.service.recommend(
                self.request, items if items is not None else [item(), item(2)], client,
            )

    async def test_valid_picks_and_minimal_payload(self):
        result = await self.run_ai(reply([2, 1]))
        self.assertEqual(result.status, "success")
        self.assertEqual([p.rental_id for p in result.recommendations], [2, 1])
        sent = json.loads(self.calls[0]["messages"][1]["content"])
        self.assertEqual(sent["recommendation_count"], 2)
        self.assertNotIn("address", sent["candidates"][0])
        self.assertNotIn("latitude", sent["candidates"][0])
        self.assertIsNone(sent["candidates"][0]["estimated_monthly_total_hkd"])

    async def test_single_candidate_and_budget_enforced(self):
        result = await self.run_ai(reply([1]), items=[item(), item(2, "10001")])
        self.assertEqual(result.status, "success")
        self.assertEqual(result.considered_count, 1)

    async def test_request_one_pick(self):
        self.request.ai_recommendation_count = 1
        self.assertEqual((await self.run_ai(reply([2]))).status, "success")

    async def test_skip_conditions_never_call_provider(self):
        self.assertEqual((await self.run_ai(items=[])).status, "no_candidates")
        self.request.include_ai = False
        self.assertEqual((await self.run_ai()).status, "disabled")
        self.request.include_ai = True
        self.service = AIRecommendationService(_DeepSeekSettings(_env_file=None, api_key=""))
        self.assertEqual((await self.run_ai()).status, "not_configured")
        self.assertEqual(self.calls, [])

    async def test_reject_hallucinated_duplicate_missing_and_wrong_type_ids(self):
        for ids in ([999, 1], [1, 1], [], [1], [True, 2], ["1", 2]):
            with self.subTest(ids=ids):
                result = await self.run_ai(reply(ids))
                self.assertEqual(result.status, "unavailable")
                self.assertEqual(result.recommendations, [])

    async def test_malformed_and_incomplete_responses(self):
        bodies = [None, {}, {"choices": []}, {"choices": [None]},
                  {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]}]
        for content in ("", "not json", "{}", '{"recommendations":null}'):
            bodies.append({"choices": [{"finish_reason": "stop", "message": {"content": content}}]})
        for body in bodies:
            with self.subTest(body=body):
                self.assertEqual((await self.run_ai(body)).status, "unavailable")

    async def test_upstream_failures(self):
        for status in (401, 429, 500):
            self.assertEqual((await self.run_ai(status=status)).status, "unavailable")
        self.assertEqual((await self.run_ai(error=httpx.ReadTimeout("timeout"))).status, "unavailable")

    async def test_total_deadline(self):
        self.settings.timeout_seconds = 0.01
        async def slow_response(request):
            await asyncio.sleep(1)
            return httpx.Response(200, json=reply([1, 2]))
        async with httpx.AsyncClient(transport=httpx.MockTransport(slow_response)) as client:
            result = await self.service.recommend(self.request, [item(), item(2)], client)
        self.assertEqual(result.status, "unavailable")

    async def test_candidate_limit_keeps_cheapest_and_fastest(self):
        self.settings.max_candidates = 2
        result = await self.run_ai(reply([1, 3]), items=[item(1, "9900", 100), item(2, "9500", 200), item(3, "8000", 500)])
        self.assertEqual(result.status, "success")
        self.assertEqual(result.considered_count, 2)

    def test_request_limits(self):
        for override in ({"ai_recommendation_count": 3}, {"preferences": "a" * 1001}, {"max_monthly_rent_hkd": 0}):
            with self.assertRaises(ValidationError):
                RecommendationRequest.model_validate({**self.request.model_dump(), **override})


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        async def fake_db():
            yield AsyncMock()
        app.dependency_overrides[get_db] = fake_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close()

    def test_original_endpoint_returns_list_and_ai_status(self):
        rental = SimpleNamespace(**item().model_dump(exclude={"commute"}), id=1)
        with patch.object(RecommendationService, "get_work_address", AsyncMock(return_value=SimpleNamespace(id=1, latitude=22.3, longitude=114.2))), \
             patch.object(RecommendationService, "find_rental_candidates", AsyncMock(return_value=[rental])), \
             patch("app.service.recommendation_service.GoogleRoutesClient.compute_transit_routes", AsyncMock(return_value=[{}])), \
             patch("app.service.recommendation_service.parse_commute_route", return_value=item().commute):
            response = self.client.post("/api/recommendations", json={"work_address_id": 1, "max_monthly_rent_hkd": 10000})
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["items"][0]["rental_id"], 1)
        self.assertEqual(data["ai"]["status"], "not_configured")

    def test_ai_success_and_failure_preserve_original_list(self):
        rental = SimpleNamespace(**item().model_dump(exclude={"commute"}), id=1)
        settings = _DeepSeekSettings(_env_file=None, api_key="test-secret")
        for status, expected in ((200, "success"), (503, "unavailable")):
            upstream = httpx.Response(status, json=reply([1]), request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"))
            with self.subTest(status=status), \
                 patch.object(RecommendationService, "get_work_address", AsyncMock(return_value=SimpleNamespace(id=1, latitude=22.3, longitude=114.2))), \
                 patch.object(RecommendationService, "find_rental_candidates", AsyncMock(return_value=[rental])), \
                 patch("app.service.recommendation_service.GoogleRoutesClient.compute_transit_routes", AsyncMock(return_value=[{}])), \
                 patch("app.service.recommendation_service.parse_commute_route", return_value=item().commute), \
                 patch("app.service.ai_recommendation_service.deepseek_settings", settings), \
                 patch.object(httpx.AsyncClient, "post", AsyncMock(return_value=upstream)):
                response = self.client.post("/api/recommendations", json={"work_address_id": 1, "max_monthly_rent_hkd": 10000})
            self.assertEqual(response.status_code, 200)
            data = response.json()["data"]
            self.assertEqual(data["items"][0]["rental_id"], 1)
            self.assertEqual(data["ai"]["status"], expected)
            if status == 200:
                self.assertEqual(data["ai"]["recommendations"][0]["rental_id"], 1)

    def test_empty_list(self):
        with patch.object(RecommendationService, "get_work_address", AsyncMock(return_value=SimpleNamespace(id=1))), \
             patch.object(RecommendationService, "find_rental_candidates", AsyncMock(return_value=[])):
            response = self.client.post("/api/recommendations", json={"work_address_id": 1, "max_monthly_rent_hkd": 10000})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["ai"]["status"], "no_candidates")


if __name__ == "__main__":
    unittest.main()
