from app.auth.dependencies import CurrentUser, DEV_USER_ID, get_current_user
from app.core import Base, get_db
from app.main import app
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from tests.async_session_adapter import AsyncSessionAdapter

engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
Base.metadata.create_all(engine)
session_factory = sessionmaker(bind=engine)

def override_get_db():
    with session_factory() as session:
        yield AsyncSessionAdapter(session)

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=DEV_USER_ID)
app.state.test_session_factory = session_factory

with TestClient(app) as c:
    r = c.post('/workspaces', json={'name': 'Engineering'}, headers={'Authorization': 'Bearer dev-token'})
    print('workspace', r.status_code, r.text)
    wid = r.json()['id']
    ch = c.post(f'/workspaces/{wid}/channels', json={'name': 'Backend'})
    print('channel', ch.status_code, ch.text)
    cid = ch.json()['id']
    resp = c.post(f'/channels/{cid}/members', json={'email': 'missing@example.com', 'role': 'member'})
    print('member', resp.status_code)
    print(resp.text)
    print(resp.json())
