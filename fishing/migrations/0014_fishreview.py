from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('fishing', '0013_add_support_models'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='FishReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.PositiveSmallIntegerField(choices=[(1, '1 ★'), (2, '2 ★'), (3, '3 ★'), (4, '4 ★'), (5, '5 ★')])),
                ('category', models.CharField(choices=[('general', 'General'), ('quality', 'Quality'), ('freshness', 'Freshness'), ('delivery', 'Delivery'), ('packaging', 'Packaging'), ('value', 'Value for Money')], default='general', max_length=20)),
                ('comment', models.TextField(blank=True, max_length=1000)),
                ('is_approved', models.BooleanField(default=True)),
                ('helpful_count', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('fish', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='fishing.fish')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fish_reviews', to='users.user')),
            ],
            options={
                'ordering': ['-created_at'],
                'verbose_name': 'Fish Review',
                'verbose_name_plural': 'Fish Reviews',
                'unique_together': {('fish', 'user')},
            },
        ),
    ]
