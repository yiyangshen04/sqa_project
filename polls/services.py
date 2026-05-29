import random

ALERT_CLASSES = (
    'primary', 'secondary', 'success', 'danger', 'dark', 'warning', 'info',
)


def compute_poll_results(poll):
    total = poll.get_vote_count
    results = []
    for choice in poll.choice_set.all():
        choice_votes = choice.get_vote_count
        percentage = (choice_votes / total) * 100 if total else 0
        results.append({
            'text': choice.choice_text,
            'num_votes': choice_votes,
            'percentage': percentage,
        })
    return results


def attach_alert_classes(results, rng=None, classes=ALERT_CLASSES):
    rng = rng or random.Random()
    for entry in results:
        entry['alert_class'] = rng.choice(classes)
    return results


def build_poll_result_dicts(poll, rng=None):
    return attach_alert_classes(compute_poll_results(poll), rng=rng)
