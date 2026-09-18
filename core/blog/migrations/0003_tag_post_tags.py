from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "blog",
            "0002_rename_blog_post_status_idx_blog_post_status_02ce19_idx_and_more",
        ),
    ]

    operations = [
        migrations.CreateModel(
            name="Tag",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100, unique=True)),
                (
                    "slug",
                    models.SlugField(blank=True, max_length=120, unique=True),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="post",
            name="tags",
            field=models.ManyToManyField(
                blank=True, related_name="posts", to="blog.tag"
            ),
        ),
    ]
