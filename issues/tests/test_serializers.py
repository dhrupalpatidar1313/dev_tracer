from django.test import TestCase
from ..serializers import BriefReporterSerializer, BriefIssueSerializer, StrictCharField, StrictIntegerField
from rest_framework import serializers

class SerializerTests(TestCase):
    def test_strict_char_field(self):
        class DummySerializer(serializers.Serializer):
            field = StrictCharField(allow_blank=True)
            
        s = DummySerializer(data={'field': 'test'})
        self.assertTrue(s.is_valid())
        
        s2 = DummySerializer(data={'field': 123})
        self.assertFalse(s2.is_valid())
        self.assertEqual(s2.errors['field'][0].code, 'invalid')

        s3 = DummySerializer(data={'field': True})
        self.assertFalse(s3.is_valid())
        
    def test_strict_int_field(self):
        class DummySerializer(serializers.Serializer):
            field = StrictIntegerField()
            
        s = DummySerializer(data={'field': 123})
        self.assertTrue(s.is_valid())
        
        s2 = DummySerializer(data={'field': '123'})
        self.assertFalse(s2.is_valid())
        
        s3 = DummySerializer(data={'field': True})
        self.assertFalse(s3.is_valid())

    def test_brief_reporter_serializer(self):
        s = BriefReporterSerializer(data={
            "name": "Asha", "email": "asha@x.com", "team": "backend"
        })
        self.assertTrue(s.is_valid())
        
        s2 = BriefReporterSerializer(data={
            "name": "Asha"
        })
        self.assertFalse(s2.is_valid())
        self.assertEqual(s2.errors['email'][0].code, 'required')

    def test_brief_issue_serializer(self):
        s = BriefIssueSerializer(data={
            "title": "Bug", "description": "", "status": "open", 
            "priority": "critical", "reporter_id": 1
        })
        self.assertTrue(s.is_valid())
