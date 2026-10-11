from django.test import TestCase
from rest_framework import status
from .helpers import make_user, auth_client, make_reporter, make_issue

class ReportersAPITests(TestCase):
    def setUp(self):
        self.admin = make_user(role='admin')
        self.dev = make_user(role='developer')
        self.viewer = make_user(role='viewer')

        self.admin_client = auth_client(self.admin)
        self.dev_client = auth_client(self.dev)
        self.viewer_client = auth_client(self.viewer)

    def test_list_reporters_paginated(self):
        for i in range(5):
            make_reporter(name=f"Rep {i}", team="backend" if i % 2 == 0 else "frontend")

        resp = self.viewer_client.get('/api/v1/reporters/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('count', resp.json())
        self.assertIn('results', resp.json())
        self.assertEqual(resp.json()['count'], 5)

    def test_filter_and_search_reporters(self):
        r1 = make_reporter(name="Alice Bob", email="alice@test.com", team="backend")
        r2 = make_reporter(name="Charlie", email="charlie@test.com", team="frontend")

        # filter team
        resp = self.viewer_client.get('/api/v1/reporters/?team=backend')
        self.assertEqual(resp.json()['count'], 1)
        self.assertEqual(resp.json()['results'][0]['name'], "Alice Bob")

        # search
        resp_search = self.viewer_client.get('/api/v1/reporters/?search=Alice')
        self.assertEqual(resp_search.json()['count'], 1)

    def test_create_reporter_permissions(self):
        payload = {"name": "New Rep", "email": "new@rep.com", "team": "ops"}

        # Viewer forbidden
        r_view = self.viewer_client.post('/api/v1/reporters/', payload, format='json')
        self.assertEqual(r_view.status_code, status.HTTP_403_FORBIDDEN)

        # Dev allowed
        r_dev = self.dev_client.post('/api/v1/reporters/', payload, format='json')
        self.assertEqual(r_dev.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r_dev.json()['name'], "New Rep")

    def test_delete_reporter_permissions_and_conflict(self):
        r = make_reporter()

        # Dev cannot delete
        r_dev = self.dev_client.delete(f'/api/v1/reporters/{r.id}/')
        self.assertEqual(r_dev.status_code, status.HTTP_403_FORBIDDEN)

        # Admin can delete empty reporter
        r_admin = self.admin_client.delete(f'/api/v1/reporters/{r.id}/')
        self.assertEqual(r_admin.status_code, status.HTTP_204_NO_CONTENT)

        # Reporter with issues -> 409
        r2 = make_reporter()
        make_issue(reporter=r2)
        r_conflict = self.admin_client.delete(f'/api/v1/reporters/{r2.id}/')
        self.assertEqual(r_conflict.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(r_conflict.json()['error'], "Cannot delete reporter with existing issues")

    def test_reporter_issues_endpoint(self):
        r = make_reporter()
        make_issue(reporter=r, title="Issue 1")
        make_issue(reporter=r, title="Issue 2")

        resp = self.viewer_client.get(f'/api/v1/reporters/{r.id}/issues/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()['count'], 2)
