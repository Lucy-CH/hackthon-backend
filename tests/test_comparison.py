import json
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import httpx
from pydantic import ValidationError

from test_ai_recommendations import item
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import get_db
from app.core.config import _DeepSeekSettings
from app.schema.comparison import ComparisonRequest
from app.schema.recommendation import RecommendationRequest
from app.service.comparison_service import compare_rentals, differences
from app.service.recommendation_service import RecommendationService


def narrative(ids=(1, 2), recommended=1):
    return {"recommended_rental_id": recommended, "conclusion": "优先选择房源1，租金较低。若更重视速度可选择房源2。",
            "analyses": [{"rental_id": i, "strengths": "租金符合预算", "tradeoffs": "交通费未知", "suitable_for": "重视预算的用户"} for i in ids]}


class ComparisonTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.request = RecommendationRequest(work_address_id=1, max_monthly_rent_hkd=12000)
        self.settings = _DeepSeekSettings(_env_file=None, api_key="test-secret")

    def test_decimal_deltas_and_unknowns(self):
        first, second = item(), item(2, "11000.25", 900)
        first.estimated_monthly_co2e_kg = Decimal('10')
        second.estimated_monthly_co2e_kg = Decimal('12')
        second.emission_factor_version = 'different'
        diff = differences([first, second])[1]
        self.assertEqual(diff.rent_hkd, Decimal('2000.25'))
        self.assertEqual(diff.commute_seconds, -300)
        self.assertIsNone(diff.monthly_total_hkd)
        self.assertIsNone(diff.monthly_co2e_kg)
        self.assertIsNone(diff.walking_meters)

    def test_request_validation(self):
        for ids in ([1], [1,1], [1,2,3,4], [-1,2]):
            with self.assertRaises(ValidationError):
                ComparisonRequest(work_address_id=1, max_monthly_rent_hkd=12000, rental_ids=ids)

    async def test_provider_success_receives_computed_differences(self):
        response = httpx.Response(200, json={"choices":[{"finish_reason":"stop","message":{"content":json.dumps(narrative())}}]}, request=httpx.Request('POST','https://api.deepseek.com/chat/completions'))
        with patch('app.service.comparison_service.deepseek_settings', self.settings), patch.object(httpx.AsyncClient,'post',AsyncMock(return_value=response)) as post:
            result = await compare_rentals(self.request, [item(), item(2, '11000', 900)])
        self.assertEqual(result.status, 'success')
        payload=json.loads(post.call_args.kwargs['json']['messages'][1]['content'])
        self.assertEqual(payload['differences'][1]['rent_hkd'], '2000')
        self.assertNotIn('address', payload['candidates'][0])

    async def test_invalid_coverage_recommendation_and_truncation(self):
        for data in (narrative((1,1)), narrative((1,999)), narrative(recommended=999), narrative((1,))):
            response=httpx.Response(200,json={"choices":[{"finish_reason":"stop","message":{"content":json.dumps(data)}}]},request=httpx.Request('POST','https://api.deepseek.com'))
            with patch('app.service.comparison_service.deepseek_settings',self.settings),patch.object(httpx.AsyncClient,'post',AsyncMock(return_value=response)):
                result=await compare_rentals(self.request,[item(),item(2)])
            self.assertEqual(result.status,'unavailable')
            self.assertIsNone(result.narrative)
            self.assertEqual(len(result.items),2)
            self.assertEqual(len(result.differences),2)

    async def test_provider_failure_keeps_table(self):
        with patch('app.service.comparison_service.deepseek_settings',self.settings),patch.object(httpx.AsyncClient,'post',AsyncMock(side_effect=httpx.ReadTimeout('timeout'))):
            result=await compare_rentals(self.request,[item(),item(2)])
        self.assertEqual(result.status,'unavailable')
        self.assertEqual(len(result.items),2)

    async def test_disabled_and_single_candidate_skip_api(self):
        with patch.object(httpx.AsyncClient,'post',AsyncMock()) as post:
            self.assertEqual((await compare_rentals(self.request,[item()])).status,'insufficient_candidates')
            self.request.include_ai=False
            self.assertEqual((await compare_rentals(self.request,[item(),item(2)])).status,'disabled')
            post.assert_not_called()

    async def test_selected_ids_must_be_in_budget_candidates(self):
        service=RecommendationService(AsyncMock())
        with patch.object(service,'get_work_address',AsyncMock(return_value=object())),patch.object(service,'find_rental_candidates',AsyncMock(return_value=[])):
            with self.assertRaises(ValueError):
                await service.recommend(self.request,rental_ids=[1,2],build_comparison=False)


class ComparisonEndpointTests(unittest.TestCase):
    def setUp(self):
        async def fake_db():
            yield AsyncMock()
        app.dependency_overrides[get_db] = fake_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close()

    def test_endpoint_rejects_invalid_selection(self):
        response=self.client.post('/api/recommendations/compare',json={'work_address_id':1,'max_monthly_rent_hkd':12000,'rental_ids':[1,1]})
        self.assertEqual(response.status_code,422)

    def test_endpoint_rejects_out_of_budget_ids(self):
        with patch.object(RecommendationService,'recommend',AsyncMock(side_effect=ValueError('Selected rentals must exist and be within budget.'))):
            response=self.client.post('/api/recommendations/compare',json={'work_address_id':1,'max_monthly_rent_hkd':12000,'rental_ids':[1,2]})
        self.assertEqual(response.status_code,422)
