from django.contrib import admin
from .models import *
from .forms import ProductForm

class ProductAdmin(admin.ModelAdmin):
    form = ProductForm

class PerfilAdmin(admin.ModelAdmin):
    list_display =('user', 'direccion', 'localidad', 'telefono', 'user_group')
    search_fields =('localidad', 'user__username', 'user__groups__name')
    list_filter = ('user__groups', 'localidad')

    def user_group(self, obj):
        return " - ".join([t.name for t in obj.user.groups.all().order_by('name')])

    user_group.short_description = 'Grupo'

@admin.register(OrdenCatalogo)
class OrdenCatalogoAdmin(admin.ModelAdmin):
    list_display = ['campo_orden', 'activo', 'fecha_creacion']
    list_editable = ['activo']
    list_display_links = ['campo_orden']
    ordering = ['-activo', '-fecha_creacion']

    def has_delete_permission(self, request, obj=None):
        # Prevenir eliminar la única configuración
        if OrdenCatalogo.objects.count() <= 1:
            return False
        return super().has_delete_permission(request, obj)

admin.site.register(Perfil, PerfilAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(CarruselImages)
admin.site.register(CartItem)
admin.site.register(Cart)
admin.site.register(Oferta)
admin.site.register(MainCategory)
admin.site.register(Category)
admin.site.register(GrillaExcel)
admin.site.register(Contacto)
admin.site.register(VisitNumber)
admin.site.register(DayNumber)
admin.site.register(Pedido)
admin.site.register(DetallePedido)
admin.site.register(Ubicacion)
admin.site.register(CargaArchivo)
admin.site.register(MercadoPagoCuenta)
admin.site.register(ClienteVendedor)
