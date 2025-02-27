from datetime import datetime, timezone
from unittest.mock import create_autospec

import pytest

from irrd.updates.handler import ChangeSubmissionHandler
from irrd.utils.rpsl_samples import SAMPLE_MNTNER
from irrd.webui import datetime_format

from .conftest import WebRequestTest, create_permission


def test_datetime_format():
    date = datetime(2022, 3, 14, 12, 34, 56, tzinfo=timezone.utc)
    assert datetime_format(date) == "2022-03-14 12:34"


class TestIndex(WebRequestTest):
    url = "/ui/"
    requires_login = False
    requires_mfa = False

    def test_index(self, test_client):
        response = test_client.get(self.url)
        assert response.status_code == 200
        assert response.context["auth_sources"] == ["TEST"]
        assert response.context["mirrored_sources"] == ["MIRROR"]


class TestUserDetail(WebRequestTest):
    url = "/ui/user/"

    def test_get(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)
        response = test_client.get(self.url)
        assert response.status_code == 200


class TestMaintainedObjects(WebRequestTest):
    url = "/ui/maintained-objects"

    def test_get_no_user_mntners(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self._login_if_needed(test_client, user)
        response = test_client.get(self.url)
        assert response.status_code == 200
        assert response.context["objects"] is None

    def test_get(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        create_permission(session_provider, user)
        self._login_if_needed(test_client, user)
        response = test_client.get(self.url)
        assert response.status_code == 200
        assert len(response.context["objects"]) == 3
        displayed_pks = {obj["rpsl_pk"] for obj in response.context["objects"]}
        assert displayed_pks == {"ROLE-TEST", "TEST-MNT", "PERSON-TEST"}


class TestRpslDetail(WebRequestTest):
    url = "/ui/rpsl/TEST/mntner/TEST-MNT"
    requires_login = False
    requires_mfa = False

    def test_valid_mntner_logged_in_mfa_complete_user_management(
        self, test_client, irrd_db_session_with_user
    ):
        session_provider, user = irrd_db_session_with_user
        self._login(test_client, user)
        self._verify_mfa(test_client)
        create_permission(session_provider, user)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" in response.text
        assert "DUMMYVALUE" not in response.text.upper()

    def test_valid_mntner_not_logged_in(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self._login(test_client, user)
        create_permission(session_provider, user)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" in response.text
        assert "DUMMYVALUE" in response.text.upper()

    def test_valid_mntner_logged_in_mfa_incomplete_user_management(
        self, test_client, irrd_db_session_with_user
    ):
        session_provider, user = irrd_db_session_with_user
        self._login(test_client, user)
        # No MFA
        create_permission(session_provider, user)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" in response.text
        assert "DUMMYVALUE" in response.text.upper()

    def test_valid_mntner_logged_in_mfa_complete_no_user_management(
        self, test_client, irrd_db_session_with_user
    ):
        session_provider, user = irrd_db_session_with_user
        self._login(test_client, user)
        self._verify_mfa(test_client)
        create_permission(session_provider, user, user_management=False)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" in response.text
        assert "DUMMYVALUE" in response.text.upper()

    def test_object_not_exists(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        self._login(test_client, user)
        create_permission(session_provider, user)

        response = test_client.get(self.url + "-none")
        assert response.status_code == 200
        assert "TEST-MNT" not in response.text


@pytest.fixture()
def mock_change_submission_handler(monkeypatch):
    mock_csh = create_autospec(ChangeSubmissionHandler)
    monkeypatch.setattr("irrd.webui.endpoints.ChangeSubmissionHandler", mock_csh)
    return mock_csh


class TestRpslUpdateNoInitial(WebRequestTest):
    url = "/ui/rpsl/update/"
    requires_login = False
    requires_mfa = False

    def test_valid_mntner_logged_in_mfa_complete_no_user_management(
        self, test_client, irrd_db_session_with_user, mock_change_submission_handler
    ):
        session_provider, user = irrd_db_session_with_user
        self._login(test_client, user)
        self._verify_mfa(test_client)
        create_permission(session_provider, user, user_management=False)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" in response.text
        assert "(you can not update this mntner itself)" in response.text

    def test_valid_mntner_logged_in_mfa_complete_user_management(
        self, test_client, irrd_db_session_with_user, mock_change_submission_handler
    ):
        session_provider, user = irrd_db_session_with_user
        self._login(test_client, user)
        self._verify_mfa(test_client)
        create_permission(session_provider, user)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" in response.text
        assert "(you can not update this mntner itself)" not in response.text

        response = test_client.post(self.url, data={"data": SAMPLE_MNTNER})
        assert response.status_code == 200
        assert mock_change_submission_handler.mock_calls[1][0] == "().load_text_blob"
        mock_handler_kwargs = mock_change_submission_handler.mock_calls[1][2]
        assert mock_handler_kwargs["object_texts_blob"] == SAMPLE_MNTNER
        assert mock_handler_kwargs["internal_authenticated_user"].pk == user.pk

    def test_valid_mntner_logged_in_mfa_incomplete_user_management(
        self, test_client, irrd_db_session_with_user, mock_change_submission_handler
    ):
        session_provider, user = irrd_db_session_with_user
        self._login(test_client, user)
        create_permission(session_provider, user)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" not in response.text

        response = test_client.post(self.url, data={"data": SAMPLE_MNTNER})
        assert response.status_code == 200
        assert mock_change_submission_handler.mock_calls[1][0] == "().load_text_blob"
        mock_handler_kwargs = mock_change_submission_handler.mock_calls[1][2]
        assert mock_handler_kwargs["object_texts_blob"] == SAMPLE_MNTNER
        assert mock_handler_kwargs["internal_authenticated_user"] is None

    def test_valid_mntner_not_logged_in(
        self, test_client, irrd_db_session_with_user, mock_change_submission_handler
    ):
        session_provider, user = irrd_db_session_with_user
        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" not in response.text

        response = test_client.post(self.url, data={"data": SAMPLE_MNTNER})
        assert response.status_code == 200
        assert mock_change_submission_handler.mock_calls[1][0] == "().load_text_blob"
        mock_handler_kwargs = mock_change_submission_handler.mock_calls[1][2]
        assert mock_handler_kwargs["object_texts_blob"] == SAMPLE_MNTNER
        assert mock_handler_kwargs["internal_authenticated_user"] is None


class TestRpslUpdateWithInitial(WebRequestTest):
    url = "/ui/rpsl/update/TEST/mntner/TEST-MNT/"
    requires_login = False
    requires_mfa = False

    def test_valid_mntner_logged_in_mfa_complete_no_user_management(
        self, test_client, irrd_db_session_with_user
    ):
        session_provider, user = irrd_db_session_with_user
        self._login(test_client, user)
        self._verify_mfa(test_client)
        create_permission(session_provider, user, user_management=False)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" in response.text
        assert "(you can not update this mntner itself)" in response.text
        assert "DUMMYVALUE" in response.text.upper()

    def test_valid_mntner_logged_in_mfa_complete_user_management(
        self, test_client, irrd_db_session_with_user
    ):
        session_provider, user = irrd_db_session_with_user
        self._login(test_client, user)
        self._verify_mfa(test_client)
        create_permission(session_provider, user)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" in response.text
        assert "(you can not update this mntner itself)" not in response.text
        assert "DUMMYVALUE" not in response.text.upper()

    def test_valid_mntner_logged_in_mfa_incomplete_user_management(
        self, test_client, irrd_db_session_with_user
    ):
        session_provider, user = irrd_db_session_with_user
        self._login(test_client, user)
        create_permission(session_provider, user)

        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" in response.text
        assert "DUMMYVALUE" in response.text.upper()

    def test_valid_mntner_not_logged_in(self, test_client, irrd_db_session_with_user):
        session_provider, user = irrd_db_session_with_user
        response = test_client.get(self.url)
        assert response.status_code == 200
        assert "TEST-MNT" in response.text
        assert "DUMMYVALUE" in response.text.upper()
