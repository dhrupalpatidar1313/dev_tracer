from django.test import TestCase
from rest_framework import status
from .helpers import make_user, auth_client, make_reporter, make_issue
from ..models import Label, Comment

class CollaborationAPITests(TestCase):
    def setUp(self):
        self.admin = make_user(role='admin')
        self.dev1 = make_user(role='developer', username='dev1')
        self.dev2 = make_user(role='developer', username='dev2')
        self.viewer = make_user(role='viewer')

        self.admin_client = auth_client(self.admin)
        self.dev1_client = auth_client(self.dev1)
        self.dev2_client = auth_client(self.dev2)
        self.viewer_client = auth_client(self.viewer)

        self.reporter = make_reporter()
        self.issue = make_issue(reporter=self.reporter, created_by=self.dev1)

    def test_comments_workflow_and_permissions(self):
        # Viewer cannot create comment -> 403
        r_view = self.viewer_client.post(f'/api/v1/issues/{self.issue.id}/comments/', {"body": "viewer comment"}, format='json')
        self.assertEqual(r_view.status_code, status.HTTP_403_FORBIDDEN)

        # Dev1 creates comment -> 201
        r_dev1 = self.dev1_client.post(f'/api/v1/issues/{self.issue.id}/comments/', {"body": "dev1 comment"}, format='json')
        self.assertEqual(r_dev1.status_code, status.HTTP_201_CREATED)
        comment_id = r_dev1.json()['id']

        # Dev2 cannot edit Dev1's comment -> 403
        r_dev2_edit = self.dev2_client.patch(f'/api/v1/issues/{self.issue.id}/comments/{comment_id}/', {"body": "tampered"}, format='json')
        self.assertEqual(r_dev2_edit.status_code, status.HTTP_403_FORBIDDEN)

        # Dev1 can edit own comment -> 200
        r_dev1_edit = self.dev1_client.patch(f'/api/v1/issues/{self.issue.id}/comments/{comment_id}/', {"body": "updated comment"}, format='json')
        self.assertEqual(r_dev1_edit.status_code, status.HTTP_200_OK)
        self.assertEqual(r_dev1_edit.json()['body'], "updated comment")

        # Admin can delete Dev1's comment -> 204
        r_admin_del = self.admin_client.delete(f'/api/v1/issues/{self.issue.id}/comments/{comment_id}/')
        self.assertEqual(r_admin_del.status_code, status.HTTP_204_NO_CONTENT)

    def test_labels_attach_and_detach(self):
        label = Label.objects.create(name="backend", color="#123456")

        # Dev1 (creator) attaches label -> 200 (idempotent)
        r_attach = self.dev1_client.post(f'/api/v1/issues/{self.issue.id}/labels/', {"label": label.id}, format='json')
        self.assertEqual(r_attach.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r_attach.json()), 1)

        # Attach again (idempotent)
        r_attach2 = self.dev1_client.post(f'/api/v1/issues/{self.issue.id}/labels/', {"label": label.id}, format='json')
        self.assertEqual(r_attach2.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r_attach2.json()), 1)

        # Detach label -> 204
        r_detach = self.dev1_client.delete(f'/api/v1/issues/{self.issue.id}/labels/{label.id}/')
        self.assertEqual(r_detach.status_code, status.HTTP_204_NO_CONTENT)

    def test_history_endpoint(self):
        resp = self.viewer_client.get(f'/api/v1/issues/{self.issue.id}/history/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
