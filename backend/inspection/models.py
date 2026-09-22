from django.db import models


class Inspection(models.Model):
    aid_code = models.CharField("航标编号", max_length=40)
    measured_cd = models.FloatField("实测光强")
    required_cd = models.FloatField("要求光强")
    bearing_error_deg = models.FloatField("方位偏差")
    verdict = models.CharField("结论", max_length=20)
    note = models.CharField("说明", max_length=200)
    created_by = models.CharField("登记人", max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]


class QueryArchive(models.Model):
    """一次附言查询的存档：查询字、判词条件与当时命中的主键集合。"""

    note_keyword = models.CharField("查询字", max_length=200)
    verdict = models.CharField("判词条件", max_length=20)
    saved_by = models.CharField("存档人", max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]

    def stale_hit_ids(self) -> set[int]:
        """存档命中行中附言已被改过（与存档时不一致）的主键。"""
        return {
            hit.inspection_id
            for hit in self.hits.select_related("inspection")
            if hit.note_snapshot != hit.inspection.note
        }


class ArchiveHit(models.Model):
    archive = models.ForeignKey(
        QueryArchive, related_name="hits", on_delete=models.CASCADE
    )
    inspection = models.ForeignKey(
        Inspection, related_name="archive_hits", on_delete=models.CASCADE
    )
    note_snapshot = models.CharField("存档时附言", max_length=200)
