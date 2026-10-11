from django.db import migrations

def create_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name='admin')
    Group.objects.get_or_create(name='developer')
    Group.objects.get_or_create(name='viewer')

def delete_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=['admin', 'developer', 'viewer']).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('issues', '0001_initial'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(create_groups, delete_groups),
    ]
