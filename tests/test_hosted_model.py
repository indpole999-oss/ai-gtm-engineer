import json
from types import SimpleNamespace

import httpx
import pytest

from backend import hosted_model, planning_service, research_service
from test_planning_execution import proposal
from test_workspace_security import signup


@pytest.fixture
def hosted(monkeypatch):
    monkeypatch.setenv('GTM_HOSTED_AI_ENABLED', 'true')
    monkeypatch.setenv('GROQ_API_KEY', 'synthetic-test-key')
    monkeypatch.delenv('GROQ-API-KEY', raising=False)
    monkeypatch.delenv('GROQ_BASE_URL', raising=False)
    monkeypatch.delenv('GROQ_MODEL', raising=False)


@pytest.mark.asyncio
@pytest.mark.parametrize('enabled', [None, 'false'])
async def test_paused_hosted_ai_never_opens_http_client(hosted, monkeypatch, enabled):
    if enabled is None:
        monkeypatch.delenv('GTM_HOSTED_AI_ENABLED')
    else:
        monkeypatch.setenv('GTM_HOSTED_AI_ENABLED', enabled)
    def forbidden(**kwargs):
        pytest.fail('Paused provider must not open an HTTP client')
    monkeypatch.setattr(hosted_model.httpx, 'AsyncClient', forbidden)
    with pytest.raises(ValueError, match='paused'):
        await planning_service.planner_provider().plan({})
    with pytest.raises(ValueError, match='paused'):
        await research_service.research_provider().analyze({}, [], {})


def plan_document():
    return planning_service.research_template(
        SimpleNamespace(objective='Research this synthetic target', target_inputs=[{}]),
        SimpleNamespace(profile={'icp': 'Synthetic ICP'}),
    )


def assert_strict(node):
    if isinstance(node, dict):
        assert 'default' not in node
        if node.get('type') == 'object':
            assert node['additionalProperties'] is False
            assert set(node['required']) == set(node['properties'])
        for child in node.values():
            assert_strict(child)
    elif isinstance(node, list):
        for child in node:
            assert_strict(child)


@pytest.mark.parametrize('output_type', [planning_service.PlanDocument, research_service.ResearchOutput])
def test_strict_schema_includes_nested_optional_fields(output_type):
    original = output_type.model_json_schema()
    assert_strict(hosted_model.strict_schema(output_type))
    assert output_type.model_json_schema() == original


def test_shared_provider_selection(hosted, monkeypatch):
    assert isinstance(planning_service.planner_provider(), planning_service.GroqPlanner)
    assert isinstance(research_service.research_provider(), research_service.GroqResearchProvider)
    monkeypatch.delenv('GROQ_API_KEY')
    assert isinstance(planning_service.planner_provider(), planning_service.LocalPlanner)
    assert isinstance(research_service.research_provider(), research_service.LocalResearchProvider)
    monkeypatch.setenv('GROQ-API-KEY', 'synthetic-legacy-key')
    assert isinstance(planning_service.planner_provider(), planning_service.GroqPlanner)


@pytest.mark.asyncio
async def test_hosted_planner_validates_request_and_response(hosted, monkeypatch):
    original_client = httpx.AsyncClient
    document = plan_document()
    def handle(request):
        assert str(request.url) == 'https://api.groq.com/openai/v1/chat/completions'
        assert request.headers['Authorization'] == 'Bearer synthetic-test-key'
        payload = json.loads(request.content)
        assert payload['response_format']['json_schema']['strict'] is True
        assert_strict(payload['response_format']['json_schema']['schema'])
        assert json.loads(payload['messages'][1]['content']) == {'objective': 'Synthetic objective'}
        return httpx.Response(200, json={'choices': [{'message': {'content': document.model_dump_json()}}]})
    monkeypatch.setattr(hosted_model.httpx, 'AsyncClient', lambda **kw: original_client(transport=httpx.MockTransport(handle), **kw))
    output, method = await planning_service.planner_provider().plan({'objective': 'Synthetic objective'})
    assert output == document and method == 'groq:openai/gpt-oss-120b'


@pytest.mark.asyncio
@pytest.mark.parametrize('payload', [{'choices': []}, {'choices': [{'message': {'content': '{}'}}]}, {'choices': [{'message': {'content': None}}]}])
async def test_hosted_planner_rejects_missing_refused_and_invalid_output(hosted, monkeypatch, payload):
    original_client = httpx.AsyncClient
    monkeypatch.setattr(hosted_model.httpx, 'AsyncClient', lambda **kw: original_client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)), **kw))
    with pytest.raises(ValueError):
        await planning_service.planner_provider().plan({})


def test_generated_plan_cannot_expand_read_only_policy(client, monkeypatch):
    headers = signup(client, 'hosted-policy@example.com')
    existing = proposal(client, headers)
    document = plan_document().model_dump(mode='json')
    document['steps'][0].update(action='outreach_send', side_effect='outbound', message_id='00000000-0000-0000-0000-000000000001')
    class UnsafePlanner:
        async def plan(self, context):
            return planning_service.PlanDocument.model_validate(document), 'synthetic'
    monkeypatch.setattr(planning_service, 'planner_provider', UnsafePlanner)
    path = f"/api/v1/gtm/goals/{existing['goal_id']}/plans"
    response = client.post(path, headers=headers, json={'mode': 'local_ai'})
    assert response.status_code == 503
    assert len(client.get(path, headers=headers).json()) == 1
    assert client.get('/api/v1/gtm/cycles', headers=headers).json() == []
