# rank_thresholds.py

role_thresholds = {
    1000: 1178750004869996574,
    2500: 1178751163462586368,
    5000: 1178751322506416138,
    10000: 1178751607509364828,
    25000: 1178751819434963044,
    50000: 1178751897855856790,
    100000: 1178751985760079995,
    250000: 1178752169894223983,
    500000: 1178752236717883534,
    1000000: 1178752300592922634
}

def get_next_threshold(points, thresholds):
    for threshold in sorted(role_thresholds.keys()):
        if points < threshold:
            return threshold
    return max(role_thresholds.keys())