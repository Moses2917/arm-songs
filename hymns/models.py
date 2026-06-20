from django.db import models


class Song(models.Model):
    BOOK_NEW = "New"
    BOOK_OLD = "Old"
    BOOK_CHOICES = [
        (BOOK_NEW, "Կարմիր Երգարան (New)"),
        (BOOK_OLD, "Word Songs (Old)"),
    ]

    book = models.CharField(max_length=3, choices=BOOK_CHOICES, db_index=True)
    number = models.CharField(max_length=10, db_index=True)
    title = models.TextField()
    title_display = models.TextField(blank=True, default="")
    lyrics = models.TextField(blank=True, default="")

    key = models.CharField(max_length=16, blank=True, default="")
    speed = models.CharField(max_length=16, blank=True, default="")
    style = models.CharField(max_length=50, blank=True, default="")
    song_type = models.CharField(max_length=50, blank=True, default="")
    time_sig = models.CharField(max_length=16, blank=True, default="")
    comments = models.TextField(blank=True, default="")

    # Cross-book link (from the `match` field in the source data).
    match_book = models.CharField(max_length=3, blank=True, default="")
    match_number = models.CharField(max_length=10, blank=True, default="")
    match_score = models.FloatField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["book", "number"]]
        indexes = [
            models.Index(fields=["book", "number"]),
            models.Index(fields=["book", "title"]),
        ]
        ordering = ["book", "number"]

    def __str__(self):
        return f"{self.book} #{self.number}: {self.display_title()[:60]}"

    def display_title(self):
        if self.title_display:
            return self.title_display
        first = (self.title or "").split("\n")[0].strip(" ,.")
        return first or f"#{self.number}"

    def matched_song(self):
        if not self.match_book or not self.match_number:
            return None
        return (
            Song.objects.filter(book=self.match_book, number=self.match_number)
            .only("id", "book", "number", "title_display", "title")
            .first()
        )

    @property
    def book_label(self):
        return dict(self.BOOK_CHOICES).get(self.book, self.book)


class Theme(models.Model):
    number = models.IntegerField(unique=True)
    name = models.CharField(max_length=200)
    songs = models.ManyToManyField(Song, blank=True, related_name="themes")

    class Meta:
        ordering = ["number"]

    def __str__(self):
        return f"{self.number}. {self.name}"


class Service(models.Model):
    filename = models.CharField(max_length=120, unique=True)
    date = models.DateField(null=True, blank=True)
    base_path = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        ordering = ["-date", "-filename"]

    def __str__(self):
        return self.filename


class ServiceSong(models.Model):
    service = models.ForeignKey(
        Service, on_delete=models.CASCADE, related_name="service_songs"
    )
    song = models.ForeignKey(Song, on_delete=models.CASCADE)
    position = models.IntegerField(default=0)

    class Meta:
        ordering = ["position"]

    def __str__(self):
        return f"{self.service.filename} - {self.song}"
