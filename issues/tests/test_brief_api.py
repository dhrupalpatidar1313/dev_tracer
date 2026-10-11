from django.test import TestCase
from rest_framework.test import APIClient
from ..models import Reporter, Issue, StatusHistory

class BriefAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_brief_api_matrix(self):
        # 1. POST reporter
        r1 = self.client.post('/api/reporters/', {
            "id": 1, "name": "Asha Rao", "email": "asha@x.com", "team": "backend"
        }, format='json')
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r1.json(), {"id": 1, "name": "Asha Rao", "email": "asha@x.com", "team": "backend"})

        # 2. POST reporter, email: "bad"
        r2 = self.client.post('/api/reporters/', {
            "name": "Bob", "email": "bad", "team": "frontend"
        }, format='json')
        self.assertEqual(r2.status_code, 400)
        self.assertEqual(r2.json(), {"error": "Invalid email"})

        # 3. POST reporter, duplicate id
        r3 = self.client.post('/api/reporters/', {
            "id": 1, "name": "Dup", "email": "dup@x.com", "team": "ops"
        }, format='json')
        self.assertEqual(r3.status_code, 400)
        self.assertEqual(r3.json(), {"error": "Reporter with id 1 already exists"})

        # 4. POST reporter missing team
        r4 = self.client.post('/api/reporters/', {
            "name": "Miss", "email": "miss@x.com"
        }, format='json')
        self.assertEqual(r4.status_code, 400)
        self.assertEqual(r4.json(), {"error": "Missing required field: team"})

        # 5. POST reporter, name: ""
        r5 = self.client.post('/api/reporters/', {
            "name": "", "email": "empty@x.com", "team": "t"
        }, format='json')
        self.assertEqual(r5.status_code, 400)
        self.assertEqual(r5.json(), {"error": "Name cannot be empty"})

        # 6. GET /api/reporters/
        r6 = self.client.get('/api/reporters/')
        self.assertEqual(r6.status_code, 200)
        self.assertIsInstance(r6.json(), list)
        self.assertEqual(len(r6.json()), 1)

        # 7. GET /api/reporters/?id=1
        r7 = self.client.get('/api/reporters/?id=1')
        self.assertEqual(r7.status_code, 200)
        self.assertEqual(r7.json()['id'], 1)

        # 8. GET /api/reporters/?id=99
        r8 = self.client.get('/api/reporters/?id=99')
        self.assertEqual(r8.status_code, 404)
        self.assertEqual(r8.json(), {"error": "Reporter not found"})

        # 9. GET /api/reporters/?id=abc
        r9 = self.client.get('/api/reporters/?id=abc')
        self.assertEqual(r9.status_code, 400)
        self.assertEqual(r9.json(), {"error": "id must be an integer"})

        # 10. POST issue = brief's sample
        r10 = self.client.post('/api/issues/', {
            "title": "Login button not working on mobile",
            "description": "The login button is unclickable on screens smaller than 768px.",
            "status": "open",
            "priority": "critical",
            "reporter_id": 1
        }, format='json')
        self.assertEqual(r10.status_code, 201)
        data = r10.json()
        self.assertEqual(data['title'], "Login button not working on mobile")
        self.assertEqual(data['message'], "[URGENT] Login button not working on mobile — needs immediate attention")
        self.assertIn('created_at', data)
        self.assertEqual(data['reporter_id'], 1)

        # 11. POST issue, low
        r11 = self.client.post('/api/issues/', {
            "title": "Typo in footer", "priority": "low", "reporter_id": 1, "status": "open", "description": ""
        }, format='json')
        self.assertEqual(r11.status_code, 201)
        self.assertEqual(r11.json()['message'], "Typo in footer — low priority, handle when free")

        # 12. POST issue, medium
        r12 = self.client.post('/api/issues/', {
            "title": "Normal issue", "priority": "medium", "reporter_id": 1, "status": "open", "description": ""
        }, format='json')
        self.assertEqual(r12.status_code, 201)
        self.assertEqual(r12.json()['message'], "Normal issue [medium]")

        # 13. POST issue, high
        r13 = self.client.post('/api/issues/', {
            "title": "High issue", "priority": "high", "reporter_id": 1, "status": "open", "description": ""
        }, format='json')
        self.assertEqual(r13.status_code, 201)
        self.assertEqual(r13.json()['message'], "High issue [high]")

        # 14. POST issue, title: ""
        r14 = self.client.post('/api/issues/', {
            "title": "", "priority": "medium", "reporter_id": 1, "status": "open", "description": ""
        }, format='json')
        self.assertEqual(r14.status_code, 400)
        self.assertEqual(r14.json(), {"error": "Title cannot be empty"})

        # 15. POST issue, status: "banana"
        r15 = self.client.post('/api/issues/', {
            "title": "Bad status", "priority": "medium", "reporter_id": 1, "status": "banana", "description": ""
        }, format='json')
        self.assertEqual(r15.status_code, 400)
        self.assertEqual(r15.json(), {"error": "Invalid status. Must be one of: open, in_progress, resolved, closed"})

        # 16. POST issue, priority: "urgent"
        r16 = self.client.post('/api/issues/', {
            "title": "Bad priority", "priority": "urgent", "reporter_id": 1, "status": "open", "description": ""
        }, format='json')
        self.assertEqual(r16.status_code, 400)
        self.assertEqual(r16.json(), {"error": "Invalid priority. Must be one of: low, medium, high, critical"})

        # 17. POST issue, reporter_id: 99
        r17 = self.client.post('/api/issues/', {
            "title": "No reporter", "priority": "medium", "reporter_id": 99, "status": "open", "description": ""
        }, format='json')
        self.assertEqual(r17.status_code, 400)
        self.assertEqual(r17.json(), {"error": "Reporter with id 99 does not exist"})

        # 18. POST issue, empty title and reporter_id: 99
        r18 = self.client.post('/api/issues/', {
            "title": "", "priority": "medium", "reporter_id": 99, "status": "open", "description": ""
        }, format='json')
        self.assertEqual(r18.status_code, 400)
        self.assertEqual(r18.json(), {"error": "Title cannot be empty"})

        # 19. POST issue, duplicate id
        issue_id = data['id']
        r19 = self.client.post('/api/issues/', {
            "id": issue_id, "title": "Dup id", "priority": "medium", "reporter_id": 1, "status": "open", "description": ""
        }, format='json')
        self.assertEqual(r19.status_code, 400)
        self.assertEqual(r19.json(), {"error": f"Issue with id {issue_id} already exists"})

        # 20. POST issue, id: "1" (string)
        r20 = self.client.post('/api/issues/', {
            "id": "1a", "title": "Bad id type", "priority": "medium", "reporter_id": 1, "status": "open", "description": ""
        }, format='json')
        self.assertEqual(r20.status_code, 400)
        self.assertEqual(r20.json(), {"error": "id must be a positive integer"})

        # 21. POST issue without id (already tested in 10-13, but let's do one more)
        r21 = self.client.post('/api/issues/', {
            "title": "Auto id", "priority": "medium", "reporter_id": 1, "status": "open", "description": ""
        }, format='json')
        self.assertEqual(r21.status_code, 201)

        # 22. POST malformed JSON
        r22 = self.client.post('/api/issues/', "not a json", content_type='application/json')
        self.assertEqual(r22.status_code, 400)
        self.assertEqual(r22.json(), {"error": "Invalid JSON body"})

        # 23. GET /api/issues/
        r23 = self.client.get('/api/issues/')
        self.assertEqual(r23.status_code, 200)
        self.assertIsInstance(r23.json(), list)

        # 24. GET /api/issues/?id=...
        r24 = self.client.get(f'/api/issues/?id={issue_id}')
        self.assertEqual(r24.status_code, 200)
        self.assertNotIn('message', r24.json())

        # 25. GET /api/issues/?id=999
        r25 = self.client.get('/api/issues/?id=999')
        self.assertEqual(r25.status_code, 404)
        self.assertEqual(r25.json(), {"error": "Issue not found"})

        # 26. GET /api/issues/?status=open
        r26 = self.client.get('/api/issues/?status=open')
        self.assertEqual(r26.status_code, 200)

        # 27. GET /api/issues/?status=banana
        r27 = self.client.get('/api/issues/?status=banana')
        self.assertEqual(r27.status_code, 400)
        self.assertEqual(r27.json(), {"error": "Invalid status. Must be one of: open, in_progress, resolved, closed"})

        # 28. PUT/DELETE /api/issues/
        r28 = self.client.put('/api/issues/')
        self.assertEqual(r28.status_code, 405)
        self.assertEqual(r28.json(), {"error": "Method not allowed"})

        # 30. After a brief POST, a StatusHistory row exists
        history = StatusHistory.objects.filter(issue_id=issue_id)
        self.assertTrue(history.exists())
        self.assertIsNone(history.first().from_status)
        self.assertIsNone(history.first().changed_by)
