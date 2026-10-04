import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
@pytest.fixture
def owner(db):
    return get_user_model().objects.create_user(username='tester',password='OnlyTestPassword2026!')
@pytest.fixture
def api(owner):
    client=APIClient();client.force_authenticate(owner);return client
@pytest.fixture(autouse=True)
def isolated_media(settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path/'media'
    settings.STATIC_ROOT=tmp_path/'staticfiles'
    settings.STATIC_ROOT.mkdir()
