from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from .services import build_poll_result_dicts


class Poll(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    pub_date = models.DateTimeField(default=timezone.now)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def user_can_vote(self, user):
        # False if this user already voted on this poll
        user_votes = user.vote_set.all()
        qs = user_votes.filter(poll=self)
        return not qs.exists()

    @property
    def get_vote_count(self):
        return self.vote_set.count()

    def get_result_dict(self, rng=None):
        # kept so existing templates calling poll.get_result_dict still work
        return build_poll_result_dicts(self, rng=rng)

    def __str__(self):
        return self.text


class Choice(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE)
    choice_text = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def get_vote_count(self):
        return self.vote_set.count()

    def __str__(self):
        return f"{self.poll.text[:25]} - {self.choice_text[:25]}"


class Vote(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE)
    choice = models.ForeignKey(Choice, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # one vote per user per poll, enforced in the DB so it can't be raced
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'poll'),
                name='one_vote_per_user_per_poll',
            ),
        ]

    def __str__(self):
        return (
            f'{self.poll.text[:15]} - '
            f'{self.choice.choice_text[:15]} - '
            f'{self.user.username}'
        )
