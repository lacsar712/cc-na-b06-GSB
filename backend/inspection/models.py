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


class SearchArchive(models.Model):
    """一次附言+判词组合查询的存档：查询字、判词条件、当时命中的主键集合。"""

    keyword = models.CharField("附言查询字", max_length=200, blank=True)
    verdict = models.CharField("判词条件", max_length=20, blank=True)
    # {主键: {"note": 存档时附言, "verdict": 存档时判词}}，主键用字符串以满足 JSON 键类型
    hits = models.JSONField("命中主键集合", default=dict)
    created_by = models.CharField("存档人", max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]

    def hit_pks(self) -> set[int]:
        return {int(k) for k in self.hits.keys()}

    def snap_note(self, pk: int) -> str:
        item = self.hits.get(str(pk), {})
        return item.get("note", "") if isinstance(item, dict) else str(item)

    def snap_verdict(self, pk: int) -> str:
        item = self.hits.get(str(pk), {})
        return item.get("verdict", "—") if isinstance(item, dict) else "—"
