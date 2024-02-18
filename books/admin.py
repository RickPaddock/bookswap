from django.contrib import admin
from .models import *


admin.site.register(CustomUser)
admin.site.register(Book)
admin.site.register(Group)
admin.site.register(UserBook)
admin.site.register(GroupMember)
admin.site.register(Transaction)
admin.site.register(Wishlist)
admin.site.register(RequestBook)
