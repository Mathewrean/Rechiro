from django.db import migrations, models
import django.db.models.deletion


def map_delivery_statuses(apps, schema_editor):
    Delivery = apps.get_model('fishing', 'Delivery')
    status_map = {
        'PENDING': 'ASSIGNED',
        'READY_FOR_PICKUP': 'ASSIGNED',
        'DELIVERY_IN_PROGRESS': 'IN_TRANSIT',
        'DELIVERED': 'DELIVERED',
        'FAILED': 'FAILED',
    }
    for delivery in Delivery.objects.all():
        new_status = status_map.get(delivery.status, 'ASSIGNED')
        if delivery.status != new_status:
            delivery.status = new_status
            delivery.save(update_fields=['status'])


class Migration(migrations.Migration):

    dependencies = [
        ('fishing', '0007_chairmanapprovalrequest'),
    ]

    operations = [
        migrations.AddField(
            model_name='delivery',
            name='assigned_agent',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_deliveries', to='users.user'),
        ),
        migrations.AddField(
            model_name='delivery',
            name='confirmation_code',
            field=models.CharField(blank=True, max_length=12),
        ),
        migrations.AddField(
            model_name='delivery',
            name='proof_image',
            field=models.ImageField(blank=True, null=True, upload_to='delivery_proofs/'),
        ),
        migrations.AlterField(
            model_name='delivery',
            name='status',
            field=models.CharField(choices=[('ASSIGNED', 'Assigned'), ('PICKED_UP', 'Picked Up'), ('IN_TRANSIT', 'In Transit'), ('DELIVERED', 'Delivered'), ('FAILED', 'Delivery Failed')], default='ASSIGNED', max_length=20),
        ),
        migrations.RunPython(map_delivery_statuses, migrations.RunPython.noop),
    ]
