import csv
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from test_ai_recommendations import item
from fastapi.testclient import TestClient
import httpx
from app.main import app
from app.core.database import get_db
from app.core.config import _DeepSeekSettings
from app.schema.recommendation import RecommendationRequest
from app.scripts.import_rentals import convert_row
from app.service.ai_recommendation_service import AIRecommendationService
from app.service.comparison_service import compare_rentals


class PropertyDataTests(unittest.TestCase):
    def test_import_preserves_optional_source_fields(self):
        with Path('data/rentals/28hse_rentals.csv').open() as f:
            row = next(csv.DictReader(f))
        row.update(latitude='22.3', longitude='114.2', bedrooms='2', usable_area_sqft='380')
        result = convert_row(row)
        self.assertEqual(result['bedrooms'], 2)
        self.assertEqual(str(result['saleable_area_sqft']), '380')
        self.assertEqual(result['property_details']['bathrooms'], '1')
        self.assertIsNone(result['property_details']['kitchen_type'])
        self.assertEqual(result['property_details']['description'], row['description'])
        self.assertNotIn('agency', result['property_details'])

    def test_ai_receives_space_and_property_facts(self):
        home = item()
        home.bedrooms = 0
        home.property_details = {'bathrooms':'1','description':'Source claim','unexpected':'secret'}
        candidate = AIRecommendationService._candidate(home)
        self.assertEqual(candidate['bedrooms'], 0)
        self.assertEqual(candidate['property_details']['bathrooms'], '1')
        self.assertNotIn('unexpected', candidate['property_details'])


class DetailEndpointTests(unittest.TestCase):
    def setUp(self):
        self.db = AsyncMock()
        async def fake_db():
            yield self.db
        app.dependency_overrides[get_db] = fake_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close()

    def test_detail_without_google_or_ai(self):
        self.db.get.return_value = SimpleNamespace(**item().model_dump(exclude={'commute'}), id=1)
        response=self.client.get('/api/recommendations/1')
        self.assertEqual(response.status_code,200)
        self.assertIsNone(response.json()['data']['bedrooms'])
        self.assertEqual(response.json()['data']['property_details'],{})

    def test_missing_listing(self):
        self.db.get.return_value=None
        self.assertEqual(self.client.get('/api/recommendations/999').status_code,404)


class SinglePropertyAnalysisTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_home_assessment(self):
        payload={'recommended_rental_id':1,'conclusion':'A good fit for your budget.', 'analyses':[{'rental_id':1,'strengths':'Lower rent','tradeoffs':'Area is unknown','suitable_for':'Someone prioritizing rent'}]}
        response=httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(payload)}}]},request=httpx.Request('POST','https://api.deepseek.com'))
        with patch('app.service.comparison_service.deepseek_settings',_DeepSeekSettings(_env_file=None,api_key='test-key')),patch.object(httpx.AsyncClient,'post',AsyncMock(return_value=response)):
            result=await compare_rentals(RecommendationRequest(work_address_id=1,max_monthly_rent_hkd=12000),[item()],allow_single=True)
        self.assertEqual(result.status,'success')
        self.assertEqual(len(result.narrative.analyses),1)
