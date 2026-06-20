from django.contrib import admin

from .models import Song, Theme, Service, ServiceSong


class ServiceSongInline(admin.TabularInline):
    model = ServiceSong
    extra = 1


@admin.register(Song)
class SongAdmin(admin.ModelAdmin):
    list_display = ("book", "number", "title_preview", "key", "style", "song_type")
    list_display_links = ("number", "title_preview")
    list_filter = ("book", "style", "song_type")
    search_fields = ("number", "title", "lyrics")
    ordering = ("book", "number")
    fieldsets = (
        (None, {"fields": ("book", "number")}),
        ("Title", {"fields": ("title", "title_display")}),
        ("Lyrics", {"fields": ("lyrics",), "classes": ("collapse",)}),
        ("Music metadata", {
            "fields": ("key", "speed", "style", "song_type", "time_sig", "comments"),
            "classes": ("collapse",),
        }),
        ("Cross-book match", {
            "fields": ("match_book", "match_number", "match_score"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="Title")
    def title_preview(self, obj):
        return obj.display_title()[:70]


@admin.register(Theme)
class ThemeAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "song_count")
    list_display_links = ("number", "name")
    ordering = ("number",)
    search_fields = ("name",)
    filter_horizontal = ("songs",)

    @admin.display(description="Songs")
    def song_count(self, obj):
        return obj.songs.count()


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("filename", "date", "song_count")
    list_display_links = ("filename",)
    ordering = ("-date", "-filename")
    inlines = [ServiceSongInline]

    @admin.display(description="Songs")
    def song_count(self, obj):
        return obj.service_songs.count()


admin.site.site_header = "Armenian Hymns Admin"
admin.site.site_title = "Armenian Hymns"
admin.site.index_title = "Content management"
