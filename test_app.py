import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_index(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b'/' in response.data

def test_about(client):
    response = client.get('/about')
    assert response.status_code == 200
    assert b'about' in response.data

def test_results(client):
    response = client.get('/results')
    assert response.status_code == 200
    assert b'results' in response.data

def test_error(client):
    response = client.get('/error')
    assert response.status_code == 200
    assert b'Error' in response.data