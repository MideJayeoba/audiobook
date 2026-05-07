from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0005_chapternavigationevent"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="is_deleted",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="document",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
