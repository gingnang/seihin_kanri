from django.db import models
from decimal import Decimal


class Material(models.Model):
    """原料マスタモデル"""
    material_id = models.CharField(max_length=50, unique=True, verbose_name="原料ID")
    material_name = models.CharField(max_length=200, verbose_name="原料名")
    manufacturer = models.CharField(max_length=200, blank=True, verbose_name="メーカー")
    supplier = models.CharField(max_length=200, blank=True, verbose_name="発注先")
    application = models.CharField(max_length=200, blank=True, verbose_name="適用")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="単価")
    order_quantity = models.DecimalField(max_digits=10, decimal_places=3, default=0, verbose_name="発注量")
    remarks = models.TextField(blank=True, verbose_name="備考")

    # 既存フィールド（管理用）
    material_category = models.CharField(max_length=100, blank=True, verbose_name="原料区分")
    is_active = models.BooleanField(default=True, verbose_name="有効")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日時")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")

    class Meta:
        verbose_name = "原料"
        verbose_name_plural = "原料"
        ordering = ['material_id']

    def __str__(self):
        return f"{self.material_id} - {self.material_name}"


class Product(models.Model):
    """製品マスタモデル"""
    product_id = models.CharField(max_length=50, unique=True, verbose_name="製品ID")
    product_name = models.CharField(max_length=200, verbose_name="製品名")
    factory = models.CharField(max_length=100, verbose_name="工場")
    sales_destination = models.CharField(max_length=200, blank=True, verbose_name="販売先")
    filling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="充填価格")
    batch_amount = models.DecimalField(max_digits=10, decimal_places=3, default=0, verbose_name="仕込量")
    output_amount = models.DecimalField(max_digits=10, decimal_places=3, default=0, verbose_name="出来数")
    is_active = models.BooleanField(default=True, verbose_name="有効")

    class Meta:
        verbose_name = "製品"
        verbose_name_plural = "製品"
        ordering = ['product_id']

    def __str__(self):
        return f"{self.product_id} - {self.product_name}"


class Recipe(models.Model):
    """配合詳細モデル"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="製品")
    material = models.ForeignKey(Material, on_delete=models.CASCADE, verbose_name="原料")
    pattern = models.IntegerField(verbose_name="パターン")
    blend_amount_kg = models.DecimalField(max_digits=10, decimal_places=3, verbose_name="配合量(kg)")
    correction_category = models.CharField(max_length=50, blank=True, verbose_name="補正区分")
    remarks = models.TextField(blank=True, verbose_name="備考")

    class Meta:
        verbose_name = "配合詳細"
        verbose_name_plural = "配合詳細"
        unique_together = ('product', 'material', 'pattern')

    def __str__(self):
        return f"{self.product.product_id} - {self.material.material_name} (パターン{self.pattern})"