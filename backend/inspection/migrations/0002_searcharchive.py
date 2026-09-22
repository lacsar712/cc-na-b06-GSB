# Added: archive of 附言+判词 combined searches

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inspection', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SearchArchive',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('keyword', models.CharField(blank=True, max_length=200, verbose_name='附言查询字')),
                ('verdict', models.CharField(blank=True, max_length=20, verbose_name='判词条件')),
                ('hits', models.JSONField(default=dict, verbose_name='命中主键集合')),
                ('created_by', models.CharField(max_length=64, verbose_name='存档人')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-id'],
            },
        ),
    ]
