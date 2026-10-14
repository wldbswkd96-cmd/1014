"""Jaro-Winkler 유사도 (외부 라이브러리 없이 구현). 한글은 음절 단위로 비교한다."""


def jaro(s1: str, s2: str) -> float:
    if s1 == s2:
        return 1.0
    len1, len2 = len(s1), len(s2)
    if not len1 or not len2:
        return 0.0
    window = max(max(len1, len2) // 2 - 1, 0)
    m1 = [False] * len1
    m2 = [False] * len2
    matches = 0
    for i, ch in enumerate(s1):
        lo, hi = max(0, i - window), min(i + window + 1, len2)
        for j in range(lo, hi):
            if not m2[j] and s2[j] == ch:
                m1[i] = m2[j] = True
                matches += 1
                break
    if not matches:
        return 0.0
    t, k = 0, 0
    for i in range(len1):
        if m1[i]:
            while not m2[k]:
                k += 1
            if s1[i] != s2[k]:
                t += 1
            k += 1
    t //= 2
    return (matches / len1 + matches / len2 + (matches - t) / matches) / 3


def jaro_winkler(s1: str, s2: str, p: float = 0.1) -> float:
    j = jaro(s1, s2)
    prefix = 0
    for a, b in zip(s1[:4], s2[:4]):
        if a != b:
            break
        prefix += 1
    return j + prefix * p * (1 - j)
