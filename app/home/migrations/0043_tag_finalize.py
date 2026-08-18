import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0042_tag_data"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="filetag",
            name="home_fileta_tag_410473_idx",
        ),
        migrations.AlterUniqueTogether(
            name="filetag",
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name="filetag",
            name="tag",
        ),
        migrations.RenameField(
            model_name="filetag",
            old_name="tag_ref",
            new_name="tag",
        ),
        migrations.AlterField(
            model_name="filetag",
            name="tag",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="file_tags",
                to="home.tag",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="filetag",
            unique_together={("file", "tag")},
        ),
        migrations.CreateModel(
            name="AlbumTag",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "album",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="tags", to="home.albums"
                    ),
                ),
                (
                    "tag",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="album_tags", to="home.tag"
                    ),
                ),
            ],
            options={
                "verbose_name": "Album Tag",
                "verbose_name_plural": "Album Tags",
                "unique_together": {("album", "tag")},
            },
        ),
    ]
