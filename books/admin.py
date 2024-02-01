from django.contrib import admin
from .models import *

admin.site.register(CustomUser)
admin.site.register(Book)
admin.site.register(Group)
admin.site.register(UserBook)
admin.site.register(GroupMember)
admin.site.register(Transaction)
admin.site.register(Wishlist)

# class BookAdmin(admin.ModelAdmin):
#     list_display = ('google_book_id', 'pk')
#     search_fields = ('google_book_id', )